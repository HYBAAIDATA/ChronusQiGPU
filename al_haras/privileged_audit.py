"""AST-backed privileged-route audit with explicit exemption policy."""

from __future__ import annotations
from dataclasses import asdict, dataclass
import ast
import hashlib
import hmac
import json
import time
from pathlib import Path

PRIVILEGED_PREFIXES = (
    "/api/v1/mining/",
    "/api/v1/policy/",
    "/api/v1/worker/",
    "/api/v1/recovery/",
    "/api/v1/admin/",
    "/api/v1/toe/",
    "/api/v1/quantum/",
    "/api/v1/scale/",
    "/api/v1/assembly/",
    "/api/v1/security/",
)
EXCLUDED_PARTS = {"tests", "test", "artifacts", "legacy", ".git", "node_modules", "venv", ".venv"}


@dataclass(frozen=True)
class Route:
    file: str
    path: str
    function: str
    line: int
    decorators: tuple[str, ...]
    kind: str


@dataclass(frozen=True)
class Violation:
    file: str
    path: str
    function: str
    line: int
    reason: str


def privileged(path):
    return any(path.startswith(p) for p in PRIVILEGED_PREFIXES)


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ""


def discover_file(path: Path, root: Path) -> list[Route]:
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except (SyntaxError, UnicodeError):
        return []
    prefixes = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, ast.Call) and _name(value.func).endswith("APIRouter"):
                prefix = ""
                for kw in value.keywords:
                    if (
                        kw.arg == "prefix"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                    ):
                        prefix = kw.value.value
                for target in targets:
                    if isinstance(target, ast.Name):
                        prefixes[target.id] = prefix
    routes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = tuple(_name(d) for d in node.decorator_list)
            for d in node.decorator_list:
                if (
                    not isinstance(d, ast.Call)
                    or not isinstance(d.func, ast.Attribute)
                    or d.func.attr not in {"get", "post", "put", "patch", "delete"}
                    or not d.args
                    or not isinstance(d.args[0], ast.Constant)
                ):
                    continue
                owner = _name(d.func.value)
                route = prefixes.get(owner, "") + str(d.args[0].value)
                routes.append(
                    Route(
                        str(path.relative_to(root)),
                        route,
                        node.name,
                        node.lineno,
                        decorators,
                        "decorator",
                    )
                )
    # Table-driven HTTP server: only inspect literals inside concrete
    # BaseHTTPRequestHandler subclasses. Constants in policy/audit code are not
    # routes and must never become false positives.
    handler_classes = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef)
        and any(_name(base).endswith("BaseHTTPRequestHandler") for base in n.bases)
    ]
    strings = []
    for handler in handler_classes:
        for node in ast.walk(handler):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and privileged(node.value)
            ):
                strings.append((node.value, getattr(node, "lineno", 0)))
    source = path.read_text()
    installed = (
        "PRIVILEGED_MEDIATION_INSTALLED = True" in source
        and "_guardian_preflight" in source
        and "_guardian_commit_evidence" in source
    )
    for route, line in strings:
        if not any(r.path == route for r in routes):
            routes.append(
                Route(
                    str(path.relative_to(root)),
                    route,
                    "<table-driven>",
                    line,
                    ("guardian_middleware", "evidence_attach") if installed else (),
                    "table",
                )
            )
    return routes


def discover(root: Path) -> list[Route]:
    return [
        route
        for path in root.rglob("*.py")
        if not (set(path.relative_to(root).parts) & EXCLUDED_PARTS)
        for route in discover_file(path, root)
    ]


def audit(root: Path) -> tuple[list[Route], list[Violation]]:
    routes = discover(root)
    violations = []
    for route in routes:
        if not privileged(route.path):
            continue
        dec = set(route.decorators)
        exemption = [d for d in dec if d.endswith("privileged_exempt")]
        if exemption:
            if not any(x in route.path for x in ("/health", "/ready")):
                violations.append(
                    Violation(
                        route.file,
                        route.path,
                        route.function,
                        route.line,
                        "invalid_privileged_exemption",
                    )
                )
            continue
        if not any(d.endswith("guardian_middleware") for d in dec):
            violations.append(
                Violation(
                    route.file,
                    route.path,
                    route.function,
                    route.line,
                    "privileged_route_without_guardian",
                )
            )
        if not any(d.endswith("evidence_attach") for d in dec):
            violations.append(
                Violation(
                    route.file,
                    route.path,
                    route.function,
                    route.line,
                    "privileged_route_without_evidence",
                )
            )
    return routes, violations


def manifest(routes, violations, key: bytes | None = None):
    body = {
        "version": 1,
        "generated_at": int(time.time()),
        "mediated": [asdict(r) for r in routes if privileged(r.path)],
        "violations": [asdict(v) for v in violations],
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body["content_hash"] = hashlib.sha256(raw).hexdigest()
    body["signature_algorithm"] = "HMAC-SHA256" if key else "UNSIGNED"
    body["signature"] = hmac.new(key, raw, hashlib.sha256).hexdigest() if key else None
    return body


def verify_manifest(value, key: bytes) -> bool:
    signature = value.get("signature")
    body = {
        k: v
        for k, v in value.items()
        if k not in {"content_hash", "signature_algorithm", "signature"}
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return bool(signature) and hmac.compare_digest(
        signature, hmac.new(key, raw, hashlib.sha256).hexdigest()
    )
