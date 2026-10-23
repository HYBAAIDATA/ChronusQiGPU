"""Bounded executable successors to the deprecated .github/agents roles.

These are local diagnostics and draft producers, NOT autonomous authorities.
No supplied code is executed, no files are written, no action is authorized,
and absence of a static finding is not a security proof.
"""
from __future__ import annotations

import ast
import hashlib
import json
import threading
from fractions import Fraction
from pathlib import PurePosixPath
from typing import Any, Mapping

from .control_plane import EvidenceLedger

SCHEMA = "salamander.agent-capabilities.v1"
ROLE_LAYERS = {
    "auditor": "TRUTH", "remediator": "CHANGE", "test_engineer": "CHANGE",
    "governance": "CONTROL", "provenance": "CONTROL", "math_verifier": "TRUTH",
    "security_verifier": "TRUTH", "quantum_checker": "TRUTH",
    "precision_sentinel": "TRUTH", "pin_verifier": "TRUTH",
}
MAX_BYTES = 131072
MAX_NODES = 10000


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def safe_path(path: str) -> bool:
    p = PurePosixPath(path)
    return bool(path and path.strip()) and str(p) != "." and len(path) <= 1024 and not p.is_absolute() and not any(
        part in ("..", ".git") for part in p.parts
    ) and "\\" not in path and ":" not in path and "\x00" not in path


def exact_expression(text: str) -> Fraction:
    """Deliberately small exact-rational evaluator; no eval/import/call/power."""
    if not isinstance(text, str) or len(text) > 2048:
        raise ValueError("bounded rational expression required")
    tree = ast.parse(text, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ValueError("expression node budget exceeded")

    def visit(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            result = visit(node.body)
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            result = Fraction(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            result = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): result = left + right
            elif isinstance(node.op, ast.Sub): result = left - right
            elif isinstance(node.op, ast.Mult): result = left * right
            else: result = left / right
        else:
            raise ValueError("outside exact-rational grammar")
        if max(result.numerator.bit_length(), result.denominator.bit_length()) > 4096:
            raise ValueError("exact arithmetic bit budget exceeded")
        return result
    return visit(tree)


def finding(status: str, reason: str, **details: Any) -> dict[str, Any]:
    return {"status": status, "reason": reason, **details}


def _math(data: Mapping[str, Any]) -> dict[str, Any]:
    cases = data.get("identities", [])
    if not cases:
        return finding("NOT_PROVABLE", "no exact rational identities supplied")
    if not isinstance(cases, list) or len(cases) > 32:
        raise ValueError("at most 32 identities")
    outcomes = [exact_expression(c["left"]) == exact_expression(c["right"]) for c in cases]
    return finding("PASS" if all(outcomes) else "FAIL", "exact rational identities only", outcomes=outcomes)


def _quantum(data: Mapping[str, Any]) -> dict[str, Any]:
    raw = data.get("quantum")
    if not raw:
        return finding("NOT_PROVABLE", "no exact real-rational gate/channel supplied")
    kind, matrices = raw.get("kind"), raw.get("matrices")
    if kind not in ("unitary", "kraus") or not isinstance(matrices, list) or not 1 <= len(matrices) <= 8:
        raise ValueError("bounded unitary/Kraus matrix list required")
    if kind == "unitary" and len(matrices) != 1:
        raise ValueError("unitary check requires one matrix")
    n = len(matrices[0])
    if not 1 <= n <= 8:
        raise ValueError("matrix dimension must be 1..8")
    parsed = []
    for matrix in matrices:
        if len(matrix) != n or any(len(row) != n for row in matrix):
            raise ValueError("square, equally sized matrices required")
        parsed.append([[exact_expression(str(x)) for x in row] for row in matrix])
    # Real matrices: transpose equals adjoint. Kraus completeness sum K†K=I.
    holds = all(sum((m[k][i] * m[k][j] for m in parsed for k in range(n)), Fraction(0))
                == int(i == j) for i in range(n) for j in range(n))
    return finding("PASS" if holds else "FAIL", "exact real-rational adjoint completeness only",
                   scope="unitarity" if kind == "unitary" else "Kraus trace preservation; CP by supplied Kraus form")


def _security(tree: ast.AST) -> dict[str, Any]:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name in {"eval", "exec", "system", "popen"}:
                hits.append({"line": node.lineno, "rule": "dynamic-execution"})
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            word in node.name.lower() for word in ("verify", "authenticate", "authorize")
        ):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                body = body[1:]
            if len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Constant) and body[0].value.value is True:
                hits.append({"line": node.lineno, "rule": "constant-true-verifier"})
        if isinstance(node, ast.ExceptHandler) and any(isinstance(x, ast.Pass) for x in node.body):
            hits.append({"line": node.lineno, "rule": "swallowed-exception-review"})
    return finding("FAIL" if hits else "NOT_PROVABLE", "bounded AST findings; not comprehensive security or key-lifecycle verification", findings=hits)


def _precision(tree: ast.AST, data: Mapping[str, Any]) -> dict[str, Any]:
    if data.get("declared_exact") is not True:
        return finding("NOT_PROVABLE", "no exact surface declared")
    lines = sorted({n.lineno for n in ast.walk(tree) if
                    isinstance(n, ast.Constant) and type(n.value) in (float, complex) or
                    isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"float", "complex"}})
    return finding("FAIL" if lines else "NOT_PROVABLE", "float/complex syntax scan only; runtime nondeterminism and numerical bounds unmeasured", lines=lines)


def _pin(tree: ast.AST, data: Mapping[str, Any]) -> dict[str, Any]:
    # The legacy hard-coded theorem_proven=False policy is NOT silently revived.
    pins = data.get("pins", {})
    if not pins:
        return finding("NOT_PROVABLE", "no current owner-selected literal pins supplied")
    if not isinstance(pins, dict) or len(pins) > 32 or any(type(v) is not bool for v in pins.values()):
        raise ValueError("at most 32 boolean literal pins")
    observed: dict[str, list[bool | None]] = {key: [] for key in pins}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in pins:
                    literal = node.value.value if isinstance(node.value, ast.Constant) and type(node.value.value) is bool else None
                    observed[target.id].append(literal)
    if any(any(v is not pins[k] for v in values) for k, values in observed.items()):
        return finding("FAIL", "literal assignment violates requested pin", observed=observed)
    return finding("PASS" if all(observed.values()) else "NOT_PROVABLE", "literal assignments only; not a whole-program proof", observed=observed)


def _audit(source: str, data: Mapping[str, Any]) -> dict[str, Any]:
    claims = data.get("claims", [])
    if not claims:
        return finding("NOT_PROVABLE", "no source-digest claims supplied")
    if not isinstance(claims, list) or len(claims) > 32:
        raise ValueError("at most 32 source-digest claims")
    holds = all(c.get("source_sha256") == sha(source) for c in claims)
    return finding("PASS" if holds else "FAIL", "claim/source digest binding only; does not prove claim semantics")


def _drafts(data: Mapping[str, Any]) -> dict[str, Any]:
    patches = data.get("draft_files", {})
    if not patches:
        return finding("NOT_PROVABLE", "no candidate remediation supplied")
    if not isinstance(patches, dict) or len(patches) > 4:
        raise ValueError("remediation file cap is four")
    if any(not safe_path(p) or not isinstance(v, str) for p, v in patches.items()):
        raise ValueError("unsafe draft path or non-text candidate")
    if sum(len(v.encode()) for v in patches.values()) > MAX_BYTES:
        raise ValueError("remediation byte cap exceeded")
    return finding("DRAFT", "candidate bundle only; complexity, fanout and correctness remain unverified",
                   files=dict(patches), auto_apply=False)


def _tests(data: Mapping[str, Any]) -> dict[str, Any]:
    cases = data.get("identities", [])
    if not cases:
        return finding("NOT_PROVABLE", "no exact identities for known-answer test generation")
    _math(data)  # Validate grammar/budgets before emitting any source.
    def render(node: ast.AST) -> str:
        if isinstance(node, ast.Constant): return f"Fraction({node.value!r})"
        if isinstance(node, ast.UnaryOp): return f"({'-' if isinstance(node.op, ast.USub) else '+'}{render(node.operand)})"
        op = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/'}[type(node.op)]
        return f"({render(node.left)} {op} {render(node.right)})"
    lines = ["from fractions import Fraction", "import unittest", "", "class ExactKnownAnswers(unittest.TestCase):"]
    for i, case in enumerate(cases):
        left, right = [render(ast.parse(case[k], mode="eval").body) for k in ("left", "right")]
        lines.extend([f"    def test_identity_{i}(self):", f"        self.assertEqual({left}, {right})"])
    return finding("DRAFT", "known-answer tests only; not executed and no property/falsification coverage claimed",
                   files={"tests/test_agent_exact_known_answers.py": '\n'.join(lines) + '\n'}, auto_apply=False)


class AgentCapabilitySuite:
    """Tenant-bound local diagnostics; caller retains authentication/authorization."""
    def __init__(self, ledger: EvidenceLedger | None = None):
        self.ledger = ledger if ledger is not None else EvidenceLedger()
        self._append_lock = threading.RLock()

    def inspect(self, *, tenant_id: str, target: str, source: str,
                evidence: Mapping[str, Any] | None = None, at_ns: int = 0) -> dict[str, Any]:
        if type(at_ns) is not int or at_ns < 0:
            raise ValueError("nonnegative integer evidence timestamp required")
        if not isinstance(tenant_id, str) or not tenant_id.strip() or len(tenant_id) > 256:
            raise ValueError("explicit bounded tenant identity required")
        if not isinstance(target, str) or not safe_path(target):
            raise ValueError("safe repository-relative target required")
        if not isinstance(source, str) or len(source.encode()) > MAX_BYTES:
            raise ValueError("source byte budget exceeded")
        # Strict JSON copying prevents callbacks/custom objects and detaches mutable input.
        data = json.loads(canonical(dict(evidence or {})))
        if len(canonical(data).encode()) > MAX_BYTES:
            raise ValueError("evidence byte budget exceeded")
        try:
            tree = ast.parse(source)
            if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
                raise ValueError("source AST node budget exceeded")
        except (SyntaxError, RecursionError) as exc:
            tree = None
            syntax_error = type(exc).__name__
        results: dict[str, Any] = {}
        checks = {
            "auditor": lambda: _audit(source, data), "remediator": lambda: _drafts(data),
            "test_engineer": lambda: _tests(data), "math_verifier": lambda: _math(data),
            "quantum_checker": lambda: _quantum(data),
            "security_verifier": lambda: _security(tree),
            "precision_sentinel": lambda: _precision(tree, data),
            "pin_verifier": lambda: _pin(tree, data),
        }
        for role, check in checks.items():
            try:
                if tree is None and role in {"security_verifier", "precision_sentinel", "pin_verifier"}:
                    results[role] = finding("NOT_PROVABLE", f"source parse failed: {syntax_error}")
                else:
                    results[role] = check()
            except (ValueError, TypeError, KeyError, ZeroDivisionError, SyntaxError, RecursionError, AttributeError, OverflowError):
                results[role] = finding("NOT_PROVABLE", "unsupported, invalid or over-budget input")
        results["provenance"] = finding("PASS", "input digest binding only; not canonical THESEUS custody",
                                           source_sha256=sha(source), input_sha256=sha(canonical(data)))
        truth = [v["status"] for k, v in results.items() if ROLE_LAYERS[k] == "TRUTH"]
        results["governance"] = finding("FAIL" if "FAIL" in truth else "PASS" if all(x == "PASS" for x in truth) else "NOT_PROVABLE",
                                           "aggregate diagnostic verdict only; no approval, merge or actuation authority")
        report = {"schema": SCHEMA, "tenant_id": tenant_id, "target": target,
                  "source_sha256": sha(source), "capabilities": results,
                  "self_healing_ready": False, "actuation": "NOT_PERFORMED"}
        # Do not put draft source or supplied evidence/secrets into the shared ledger.
        summary = {role: {"status": value["status"], "reason": value["reason"]} for role, value in results.items()}
        with self._append_lock:
            ref = self.ledger.append("agent-capability-review", {
                "tenant_id": tenant_id, "target": target, "source_sha256": sha(source),
                "input_sha256": sha(canonical(data)), "report_sha256": sha(canonical(report)),
                "capabilities": summary,
            }, at_ns=at_ns)
        return {**report, "evidence_ref": ref}
