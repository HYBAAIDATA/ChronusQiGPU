"""Deploy sentry: static checks for the wiring pitfalls that break a deployment.

Each check guards a failure class found in this repository, where the code,
its packaging and its deployment disagreed without any test noticing:

DS01 dead-config    a variable a deployment sets (Dockerfile ENV, compose,
                    workflow, Bicep, .env.example) that no code reads
DS02 python-deps    a runtime import that pyproject does not declare, a
                    runtime module the image excludes, a declared
                    distribution that nothing imports, or an import that
                    an in-tree distribution's tests or entry points need
                    but that distribution's own pyproject (with the extras
                    CI or an image installs) does not declare
DS03 native-build   ``make -C DIR`` with no DIR/Makefile, or a native library
                    the runtime loads that the deploy image never builds
DS04 ci-triggers    a workflow that runs twice per PR commit, or one filtered
                    on a branch that does not exist
DS05 frontend-deps  a package.json dependency nothing references, or a
                    script binary that is not declared
DS06 boot-config    a deploy manifest that never sets a variable the service
                    refuses to boot without
DS07 entry-points   a compose file, Dockerfile or workflow that runs
                    ``python -m MODULE`` or ``python FILE.py`` for a local
                    module or file that does not exist

Findings on the deploy path (``deploy/``, ``.env.example``, workflows,
pyproject, the runtime import closure, the frontend) are errors and fail
the run; the rest of the repository is reported as warnings.

    python -m scripts.deploy_sentry            # report, exit 1 on errors
    python -m scripts.deploy_sentry --json     # machine-readable
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from scripts.import_audit import source_roots

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = "chronus/mla1517_platform/python"
SKIP_DIRS = {
    ".git",
    "node_modules",
    "build",
    "dist",
    "legacy",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".hypothesis",
    "PYTHIA-main",
}
APP_PREFIXES = ("PYTHIA_", "MLA1517_", "EUCLID_", "AETHEL_", "KELLOGG_", "TOE_", "HYBA_", "LHRAS_")
DEPLOY_PATHS = ("deploy/", ".env.example", ".github/workflows/")
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".sh", ".c", ".h"}
ENTRY_SCRIPTS = (
    "main.py",
    f"{PLATFORM}/mining_runtime.py",
    f"{PLATFORM}/salamander_engine.py",
    f"{PLATFORM}/discovery_runtime.py",
)
# Distributions whose import name differs from the distribution name.
IMPORT_NAMES = {"pyyaml": "yaml", "scikit-learn": "sklearn", "pytest-asyncio": "pytest_asyncio"}
# Distributions used as tools or plugins rather than imported.
TOOL_DISTS = {"black", "flake8", "mypy", "pytest", "pytest-asyncio", "ruff", "setuptools", "wheel"}
SHELL_WORDS = {
    "cd",
    "echo",
    "exit",
    "npm",
    "npx",
    "node",
    "rm",
    "cp",
    "mkdir",
    "true",
    "env",
    "set",
}


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    path: str
    message: str
    fix: str

    def line(self) -> str:
        return f"{self.severity.upper():7s} {self.check} {self.path}: {self.message}\n        fix: {self.fix}"


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _severity(rel: str) -> str:
    return "error" if rel.startswith(DEPLOY_PATHS) else "warning"


def _walk(root: Path, suffixes: set[str] | None = None):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".venv")]
        for name in filenames:
            path = Path(dirpath) / name
            if suffixes is None or path.suffix in suffixes:
                yield path


def _is_test(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return (
        rel.startswith("tests/")
        or "/tests/" in rel
        or "/__tests__/" in rel
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.ts", ".test.tsx", "conftest.py"))
    )


def _app_var(name: str) -> bool:
    return name.startswith(APP_PREFIXES)


# ─────────────────────────────── DS01 dead config ─────────────────────────────── #


def _env_line_names(text: str) -> list[str]:
    names = []
    for match in re.finditer(r"(?<![A-Za-z0-9_$])([A-Z][A-Z0-9_]+)=", text):
        names.append(match.group(1))
    return names


def configured_variables(root: Path) -> dict[str, list[str]]:
    """Variable name -> the deployment files that set it."""
    found: dict[str, set[str]] = {}

    def add(name: str, rel: str) -> None:
        if _app_var(name):
            found.setdefault(name, set()).add(rel)

    for path in _walk(root):
        rel = _rel(path, root)
        name = path.name
        try:
            if name.startswith("Dockerfile"):
                logical = re.sub(r"\\\n", " ", path.read_text(encoding="utf-8", errors="replace"))
                for line in logical.splitlines():
                    stripped = line.strip()
                    if stripped.upper().startswith("ENV "):
                        body = stripped[4:]
                        names = _env_line_names(body)
                        if not names and body.split():
                            names = [body.split()[0]]
                        for n in names:
                            add(n, rel)
            elif name == ".env.example":
                for line in path.read_text(encoding="utf-8").splitlines():
                    match = re.match(r"^#?\s*([A-Z][A-Z0-9_]+)=", line)
                    if match:
                        add(match.group(1), rel)
            elif name.endswith(".bicep"):
                for match in re.finditer(
                    r"name:\s*'([A-Z][A-Z0-9_]+)'", path.read_text(encoding="utf-8")
                ):
                    add(match.group(1), rel)
            elif path.suffix in {".yml", ".yaml"} and (
                "compose" in name or rel.startswith(".github/workflows/")
            ):
                text = path.read_text(encoding="utf-8")
                for match in re.finditer(r"-e\s+([A-Z][A-Z0-9_]+)=", text):
                    add(match.group(1), rel)
                data = yaml.safe_load(text) or {}
                for env in _yaml_env_blocks(data):
                    for key in env:
                        add(str(key), rel)
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
    return {k: sorted(v) for k, v in found.items()}


def _yaml_env_blocks(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("env", "environment"):
                if isinstance(value, dict):
                    yield value
                elif isinstance(value, list):
                    yield {str(item).split("=", 1)[0]: None for item in value}
            else:
                yield from _yaml_env_blocks(value)
    elif isinstance(node, list):
        for item in node:
            yield from _yaml_env_blocks(item)


def _template_regex(node: ast.JoinedStr, suffixes: set[str]) -> str | None:
    """``f"MLA1517_{name}_USER"`` -> a pattern; ``f"{name}"`` names nothing.

    A template ending in a placeholder builds a prefix; it completes only
    with the upper-case suffix constants its own module uses.
    """
    parts, literal = [], ""
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(re.escape(value.value))
            literal += value.value
        else:
            parts.append("[A-Z0-9_]+")
    if len(literal) < 4 or "_" not in literal or not re.fullmatch(r"[A-Z0-9_]+", literal):
        return None
    pattern = "".join(parts)
    if not isinstance(node.values[-1], ast.Constant):
        if not suffixes:
            return None
        pattern += "(?:" + "|".join(sorted(map(re.escape, suffixes))) + ")"
    return pattern


def read_variables(root: Path) -> tuple[set[str], list[re.Pattern]]:
    """Literal variable names code reads, plus templated names as patterns."""
    literals: set[str] = set()
    patterns: list[re.Pattern] = []
    name_re = re.compile(r"^[A-Z][A-Z0-9_]+$")
    for path in _walk(root, CODE_SUFFIXES):
        rel = _rel(path, root)
        if _is_test(rel) or rel == "scripts/deploy_sentry.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            constants = {
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            }
            literals.update(c for c in constants if name_re.match(c) and _app_var(c))
            suffixes = {
                c for c in constants if len(c) >= 3 and name_re.match(c) and not _app_var(c)
            }
            for node in ast.walk(tree):
                if isinstance(node, ast.JoinedStr):
                    pattern = _template_regex(node, suffixes)
                    if pattern:
                        patterns.append(re.compile(pattern + "$"))
        else:
            for match in re.finditer(r"\b([A-Z][A-Z0-9_]{3,})\b", text):
                if _app_var(match.group(1)):
                    literals.add(match.group(1))
    return literals, patterns


def shell_reads(path: Path) -> set[str]:
    """Variables a deployment file's own container shell reads.

    Compose escapes a container-side ``$VAR`` as ``$$VAR`` / ``$${VAR}``;
    a Dockerfile's RUN/CMD/ENTRYPOINT shell reads ``$VAR`` / ``${VAR}``.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.name.startswith("Dockerfile"):
        lines = [
            line
            for line in re.sub(r"\\\n", " ", text).splitlines()
            if line.strip().upper().startswith(("RUN ", "CMD ", "ENTRYPOINT "))
        ]
        return set(re.findall(r"\$\{?([A-Z][A-Z0-9_]+)", "\n".join(lines)))
    return set(re.findall(r"\$\$\{?([A-Z][A-Z0-9_]+)", text))


def check_dead_config(root: Path) -> list[Finding]:
    configured = configured_variables(root)
    literals, patterns = read_variables(root)
    findings = []
    for name, sources in sorted(configured.items()):
        if name in literals or any(p.match(name) for p in patterns):
            continue
        sources = [rel for rel in sources if name not in shell_reads(root / rel)]
        for rel in sources:
            findings.append(
                Finding(
                    "DS01",
                    _severity(rel),
                    rel,
                    f"sets {name}, which no code reads",
                    f"remove {name} from {rel}, or wire the code that should read it",
                )
            )
    return findings


# ─────────────────────────────── DS02 python deps ─────────────────────────────── #


def _dist_name(requirement: str) -> str:
    return re.split(r"[<>=!~;\[ ]", requirement.strip(), maxsplit=1)[0].lower()


def declared_distributions(root: Path) -> tuple[set[str], dict[str, set[str]]]:
    """Core and extra distributions declared by ``root/pyproject.toml``."""
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = data.get("project", {})
    core = {_dist_name(r) for r in project.get("dependencies", [])}
    extras = {
        extra: {_dist_name(r) for r in reqs}
        for extra, reqs in project.get("optional-dependencies", {}).items()
    }
    return core, extras


def _import_name(dist: str) -> str:
    return IMPORT_NAMES.get(dist, dist.replace("-", "_"))


def _search_roots(root: Path) -> list[Path]:
    return [root, root / PLATFORM]


def _resolve_local(module: str, roots: list[Path]) -> Path | None:
    parts = module.split(".")
    for base in roots:
        candidate = base.joinpath(*parts)
        if candidate.with_suffix(".py").is_file():
            return candidate.with_suffix(".py")
        if (candidate / "__init__.py").is_file():
            return candidate / "__init__.py"
    return None


def _is_local_top(top: str, roots: list[Path]) -> bool:
    return any((base / f"{top}.py").is_file() or (base / top).is_dir() for base in roots)


def _guarded(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Inside a try block or a function body: absence is handled or lazy."""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.Try, ast.FunctionDef, ast.AsyncFunctionDef)):
            return True
        current = parents.get(current)
    return False


def runtime_closure(
    root: Path, entries: tuple[str, ...] | None = None
) -> tuple[dict[str, Path], dict[str, tuple[str, bool]]]:
    """Local modules reachable from the entry points, and third-party imports.

    Third-party imports map to ``(first importer, required)`` where required
    means an unguarded module-level import. Without ``entries`` the entry
    points are the service, its workers and the pyproject scripts.
    """
    roots = _search_roots(root)
    queue: list[Path] = [root / p for p in (entries or ENTRY_SCRIPTS) if (root / p).is_file()]
    if entries is None:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        for target in data.get("project", {}).get("scripts", {}).values():
            resolved = _resolve_local(target.split(":")[0], roots)
            if resolved:
                queue.append(resolved)
    return import_closure(root, queue, roots)


def import_closure(
    root: Path, queue: list[Path], roots: list[Path]
) -> tuple[dict[str, Path], dict[str, tuple[str, bool]]]:
    """Local modules reachable from ``queue`` through ``roots``, and third-party imports.

    A module reached only through guarded imports is optional, and so is
    everything it imports: a lazy ``from pkg import x`` inside a function or a
    ``try`` cannot break import of the entry point.
    """
    pending: list[tuple[Path, bool]] = [(p, True) for p in queue]
    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    local: dict[str, Path] = {}
    third: dict[str, tuple[str, bool]] = {}
    seen: dict[Path, bool] = {}
    while pending:
        path, reached = pending.pop()
        if path in seen and (seen[path] or not reached):
            continue
        seen[path] = reached
        local[_rel(path, root)] = path
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        # A script's own directory is on sys.path when it runs.
        module_roots = [path.parent, *roots]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            required = reached and not _guarded(node, parents)
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif node.level:
                package = path.parent
                for _ in range(node.level - 1):
                    package = package.parent
                target = (
                    package.joinpath(*(node.module or "").split(".")) if node.module else package
                )
                for candidate in (target.with_suffix(".py"), target / "__init__.py"):
                    if candidate.is_file():
                        pending.append((candidate, required))
                for alias in node.names:
                    sub = target / f"{alias.name}.py"
                    if sub.is_file():
                        pending.append((sub, required))
                continue
            elif node.module:
                modules = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for module in modules:
                top = module.split(".")[0]
                if top in stdlib:
                    continue
                if _is_local_top(top, module_roots):
                    parts = module.split(".")
                    # Importing a.b.c runs a/__init__.py and a/b/__init__.py first.
                    for depth in range(1, len(parts) + 1):
                        resolved = _resolve_local(".".join(parts[:depth]), module_roots)
                        if resolved:
                            pending.append((resolved, required))
                    continue
                previous = third.get(top)
                if previous is None or (required and not previous[1]):
                    third[top] = (_rel(path, root), required)
    return local, third


def _dockerignore(root: Path) -> list[str]:
    path = root / ".dockerignore"
    if not path.is_file():
        return []
    return [
        line.strip().rstrip("/")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _ignored(rel: str, patterns: list[str]) -> str | None:
    parts = rel.split("/")
    for pattern in patterns:
        if pattern.startswith("!"):
            continue
        if fnmatch.fnmatch(rel, pattern) or any(fnmatch.fnmatch(p, pattern) for p in parts[:-1]):
            return pattern
    return None


def check_python_deps(root: Path) -> list[Finding]:
    core, extras = declared_distributions(root)
    declared_any = core.union(*extras.values()) if extras else set(core)
    local, third = runtime_closure(root)
    findings = []
    core_imports = {_import_name(d) for d in core}
    any_imports = {_import_name(d) for d in declared_any}
    for top, (importer, required) in sorted(third.items()):
        if required and top not in core_imports:
            findings.append(
                Finding(
                    "DS02",
                    "error",
                    importer,
                    f"runtime imports {top!r} unguarded, but it is not a core dependency",
                    f"add the distribution providing {top!r} to [project].dependencies, or guard the import",
                )
            )
        elif not required and top not in any_imports:
            findings.append(
                Finding(
                    "DS02",
                    "warning",
                    importer,
                    f"runtime optionally imports {top!r}, which no extra declares",
                    "declare it in an optional-dependencies extra",
                )
            )
    ignored = _dockerignore(root)
    for rel in sorted(local):
        pattern = _ignored(rel, ignored)
        if pattern:
            findings.append(
                Finding(
                    "DS02",
                    "error",
                    rel,
                    f"runtime module is excluded from the image by .dockerignore ({pattern!r})",
                    "narrow the .dockerignore pattern or move the module",
                )
            )
    imported: set[str] = set()
    for path in _walk(root, {".py"}):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                imported.add(node.module.split(".")[0])
    for dist in sorted(declared_any - TOOL_DISTS):
        if _import_name(dist) not in imported:
            findings.append(
                Finding(
                    "DS02",
                    "error",
                    "pyproject.toml",
                    f"declares {dist!r}, which nothing imports",
                    f"remove {dist!r} from pyproject.toml",
                )
            )
    return findings + check_distribution_deps(root)


# In-tree distributions: a folder with its own pyproject.toml that CI or an
# image installs on its own (``cd DIR && pip install -e ".[test]"``) gets only
# what THAT pyproject declares, not the root one. The push gate failed at
# collection for five pushes because chronus/mla1517/learning.py imports yaml and only
# the root pyproject declared pyyaml.

_PIP_INSTALL = re.compile(r"\bpip3?\s+install\s+(.*)")
_PYTEST = re.compile(r"\bpytest\b(.*)")
_UVICORN = re.compile(r"\b(?:uvicorn|gunicorn)\s+(?:.*\s)?([\w.]+):\w+")


@dataclass(frozen=True)
class _Install:
    dist: Path
    extras: frozenset[str]
    source: str  # the file that installs it, or "" when nothing does
    commands: tuple[tuple[Path, str], ...]  # (working directory, command) run alongside
    # Distributions the same pip command installs beside it (a dependency
    # installed from the tree, e.g. the virtual quantum computer): what they
    # declare is installed too.
    beside: tuple[tuple[Path, frozenset[str]], ...] = ()


def _split_commands(command: str) -> list[str]:
    return [c.strip() for c in re.split(r"&&|\|\||;|\n", command) if c.strip()]


def _words(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _install_targets(command: str) -> list[tuple[str, frozenset[str]]]:
    """(path, extras) for every ``pip install`` argument in ``command``."""
    out = []
    for part in _split_commands(command):
        match = _PIP_INSTALL.search(part)
        if not match:
            continue
        for word in _words(match.group(1)):
            spec = re.fullmatch(r"([^\[\]\s]+)(?:\[([^\]]*)\])?", word)
            if word.startswith("-") or not spec:
                continue
            extras = frozenset(e.strip() for e in (spec.group(2) or "").split(",") if e.strip())
            out.append((spec.group(1), extras))
    return out


def _deploy_units(root: Path) -> list[tuple[str, list[tuple[Path, str]]]]:
    """(file, [(working directory, command)]) per workflow job, Dockerfile, compose file."""
    units: list[tuple[str, list[tuple[Path, str]]]] = []
    for path in _walk(root):
        rel = _rel(path, root)
        try:
            if path.name.startswith("Dockerfile"):
                # The build context: the Dockerfile's folder when it is a distribution.
                cwd = path.parent if (path.parent / "pyproject.toml").is_file() else root
                units.append((rel, [(cwd, c) for c in _commands(path)]))
            elif path.suffix in {".yml", ".yaml"} and rel.startswith(".github/workflows/"):
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                for job in (data.get("jobs") or {}).values():
                    if not isinstance(job, dict):
                        continue
                    default = ((job.get("defaults") or {}).get("run") or {}).get(
                        "working-directory", "."
                    )
                    steps = [s for s in job.get("steps") or [] if isinstance(s, dict)]
                    units.append(
                        (
                            rel,
                            [
                                (root / str(s.get("working-directory", default)), str(s["run"]))
                                for s in steps
                                if "run" in s
                            ],
                        )
                    )
            elif path.suffix in {".yml", ".yaml"} and "compose" in path.name:
                units.append((rel, [(path.parent, c) for c in _commands(path)]))
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
    return units


def _distributions(root: Path) -> list[Path]:
    """In-tree distributions other than the root one, as import_audit finds them."""
    return [d for d in source_roots(root) if d != root and (d / "pyproject.toml").is_file()]


def _dist_installs(root: Path) -> list[_Install]:
    dists = {d.resolve(): d for d in _distributions(root)}
    installs: list[_Install] = []
    installed: set[Path] = set()
    for rel, commands in _deploy_units(root):
        for cwd, command in commands:
            for part in _split_commands(command):
                targets = [((cwd / t).resolve(), extras) for t, extras in _install_targets(part)]
                # The command's own project ("." in its directory) is what runs;
                # other in-tree distributions it installs are its dependencies.
                primary = [t for t in targets if t[0] == cwd.resolve()] or targets
                for path, extras in targets:
                    if path in dists:
                        installed.add(dists[path])
                for path, extras in primary:
                    dist = dists.get(path)
                    if dist is None:
                        continue
                    beside = tuple((dists[p], e) for p, e in targets if p != path and p in dists)
                    installs.append(_Install(dist, extras, rel, tuple(commands), beside))
    for dist in dists.values():
        if dist not in installed:
            # Nothing installs it: hold it to the whole pyproject, as a warning.
            _, extras = declared_distributions(dist)
            installs.append(_Install(dist, frozenset(extras), "", ()))
    return installs


def _pyproject(dist: Path) -> dict:
    return tomllib.loads((dist / "pyproject.toml").read_text(encoding="utf-8"))


def _test_files(target: Path, stop: Path) -> list[Path]:
    """The test modules pytest collects under ``target``, with their conftests."""
    if target.is_file():
        files = [target]
    else:
        files = [
            p
            for p in _walk(target, {".py"})
            if p.name.startswith("test_") or p.name.endswith("_test.py") or p.name == "conftest.py"
        ]
    here = target if target.is_dir() else target.parent
    while True:
        if (here / "conftest.py").is_file():
            files.append(here / "conftest.py")
        if here == stop or stop not in here.parents:
            return files
        here = here.parent


def _install_entries(install: _Install, roots: list[Path]) -> list[Path]:
    """The files the installed distribution runs: its tests, scripts and commands."""
    dist = install.dist
    project = _pyproject(dist)
    entries: list[Path] = []
    for target in project.get("project", {}).get("scripts", {}).values():
        resolved = _resolve_local(target.split(":")[0], roots)
        if resolved:
            entries.append(resolved)
    testpaths = project.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("testpaths")
    default_tests = [dist / t for t in testpaths] if testpaths else [dist]
    commands = install.commands or ((dist, "pytest"),)
    for cwd, command in commands:
        for part in _split_commands(command):
            pytest = _PYTEST.search(part)
            if pytest and "pip" not in part:
                paths = [cwd / w for w in _words(pytest.group(1)) if (cwd / w).exists()]
                for target in paths or default_tests:
                    entries.extend(_test_files(target, dist))
            for match in _PY_RUN.finditer(part):
                module, script = match.group(2), match.group(3)
                if module:
                    resolved = _resolve_local(module, [cwd, *roots])
                    main = _resolve_local(f"{module}.__main__", [cwd, *roots])
                    entries.extend(p for p in (resolved, main) if p)
                elif script:
                    entries.extend(p for p in (cwd / script, dist / script) if p.is_file())
            for module in _UVICORN.findall(part):
                resolved = _resolve_local(module, [cwd, *roots])
                if resolved:
                    entries.append(resolved)
    return entries


def check_distribution_deps(root: Path) -> list[Finding]:
    findings: dict[tuple[str, str, str], Finding] = {}
    for install in _dist_installs(root):
        dist = install.dist
        rel = _rel(dist, root)
        package_dir = (
            _pyproject(dist).get("tool", {}).get("setuptools", {}).get("package-dir", {}).get("")
        )
        roots = list(
            dict.fromkeys(
                [*([dist / package_dir] if package_dir else []), dist, *source_roots(root)]
            )
        )
        core, extras = declared_distributions(dist)
        have = {
            _import_name(d) for d in core.union(*(extras.get(e, set()) for e in install.extras))
        }
        for other, other_extras in install.beside:
            other_core, other_all = declared_distributions(other)
            have |= {
                _import_name(d)
                for d in other_core.union(*(other_all.get(e, set()) for e in other_extras))
            }
        anywhere = {_import_name(d) for d in core.union(*extras.values())}
        how = f'.[{",".join(sorted(install.extras))}]' if install.extras else "."
        where = (
            f"{install.source} installs {rel} as {how!r}"
            if install.source
            else f"nothing installs {rel}; held to all its extras"
        )
        _, third = import_closure(root, _install_entries(install, roots), roots)
        for top, (importer, required) in sorted(third.items()):
            if required and top not in have:
                severity = "error" if install.source else "warning"
                message = (
                    f"imports {top!r} unguarded, which {rel}/pyproject.toml does not declare "
                    f"({where})"
                )
                fix = (
                    f"add the distribution providing {top!r} to {rel}/pyproject.toml "
                    "dependencies (or to the extra that install uses)"
                )
            elif not required and top not in anywhere and importer.startswith(f"{rel}/"):
                # Optional imports of code outside the distribution are its owner's to declare.
                severity = "warning"
                message = (
                    f"optionally imports {top!r}, which no extra of {rel}/pyproject.toml declares"
                )
                fix = f"declare it in an optional-dependencies extra of {rel}/pyproject.toml"
            else:
                continue
            findings.setdefault(
                (importer, top, severity), Finding("DS02", severity, importer, message, fix)
            )
    return list(findings.values())


# ─────────────────────────────── DS03 native build ────────────────────────────── #


def check_native_build(root: Path) -> list[Finding]:
    findings = []
    for path in _walk(root):
        if not (path.name.startswith("Dockerfile") or path.name == "Makefile"):
            continue
        rel = _rel(path, root)
        text = path.read_text(encoding="utf-8", errors="replace")
        # COPY <src> <dest> lets a make target inside the image map back to
        # the repository; the build context is the repo root or this dir.
        copies = [
            (dest.rstrip("/"), src.rstrip("/"))
            for src, dest in re.findall(r"^COPY\s+(?!--)(\S+)\s+(\S+)\s*$", text, re.MULTILINE)
        ]
        for match in re.finditer(r"make\)?\s+-C\s+([\w./-]+)", text):
            target = match.group(1).rstrip("/")
            sources = [target]
            for dest, src in copies:
                if target == dest or target.startswith(dest + "/"):
                    sources.append(src + target[len(dest) :])
            candidates = [base / t for t in sources for base in (path.parent, root)]
            if not any((c / "Makefile").is_file() for c in candidates):
                findings.append(
                    Finding(
                        "DS03",
                        (
                            "error"
                            if rel.startswith("deploy/") or path.name == "Makefile"
                            else "warning"
                        ),
                        rel,
                        f"runs make -C {match.group(1)}, but there is no Makefile there",
                        f"add a Makefile for {match.group(1)} or fix the path",
                    )
                )
    local, _ = runtime_closure(root)
    libraries: dict[str, str] = {}
    for rel, path in local.items():
        for match in re.finditer(
            r"\b(lib[\w]+\.so)\b", path.read_text(encoding="utf-8", errors="replace")
        ):
            libraries.setdefault(match.group(1), rel)
    for dockerfile in sorted((root / "deploy").glob("*/Dockerfile")):
        text = dockerfile.read_text(encoding="utf-8", errors="replace")
        for library, loader in sorted(libraries.items()):
            if library not in text:
                findings.append(
                    Finding(
                        "DS03",
                        "error",
                        _rel(dockerfile, root),
                        f"the runtime loads {library} ({loader}) but this image never builds or copies it",
                        f"build {library} in a build stage and copy it into the image",
                    )
                )
    return findings


# ───────────────────────────── DS06 boot requirements ─────────────────────────── #


def boot_requirements(root: Path) -> dict[str, str]:
    """Variables the service refuses to boot without: ``raise ...("X is required")``."""
    local, _ = runtime_closure(root, ("main.py",))
    required: dict[str, str] = {}
    for rel, path in local.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            for arg in node.exc.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    match = re.fullmatch(r"([A-Z][A-Z0-9_]+) is required", arg.value.strip())
                    if match and _app_var(match.group(1)):
                        required.setdefault(match.group(1), rel)
    return required


def check_boot_requirements(root: Path) -> list[Finding]:
    findings = []
    required = boot_requirements(root)
    for manifest in sorted((root / "deploy").glob("*/*.bicep")):
        text = manifest.read_text(encoding="utf-8")
        dockerfile = manifest.parent / "Dockerfile"
        image_env = dockerfile.read_text(encoding="utf-8") if dockerfile.is_file() else ""
        for name, source in sorted(required.items()):
            if f"'{name}'" in text or re.search(rf"\b{name}=", image_env):
                continue
            findings.append(
                Finding(
                    "DS06",
                    "error",
                    _rel(manifest, root),
                    f"never sets {name}, which the service requires at boot ({source})",
                    f"add {name} to the container env (as a parameter or secret)",
                )
            )
    return findings


# ─────────────────────────────── DS04 CI triggers ─────────────────────────────── #


def _remote_branches(root: Path) -> set[str] | None:
    try:
        out = subprocess.run(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return {line.split("refs/heads/", 1)[1] for line in out.splitlines() if "refs/heads/" in line}


def check_ci_triggers(root: Path, branches: set[str] | None = None) -> list[Finding]:
    findings = []
    remote = branches if branches is not None else _remote_branches(root)
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        rel = _rel(path, root)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        on = data.get("on", data.get(True, {}))
        if isinstance(on, str):
            on = {on: None}
        elif isinstance(on, list):
            on = {name: None for name in on}
        push = on.get("push") if isinstance(on, dict) else None
        push_filter = (push or {}).get("branches") if isinstance(push, dict) else None
        if isinstance(on, dict) and "push" in on and "pull_request" in on:
            if not push_filter or any(b in ("*", "**") for b in push_filter):
                findings.append(
                    Finding(
                        "DS04",
                        "error",
                        rel,
                        "runs on push to every branch and on pull_request: every PR commit runs it twice",
                        "restrict push to the default branch (branches: [main])",
                    )
                )
        if remote is None or not isinstance(on, dict):
            continue
        for event in ("push", "pull_request"):
            spec = on.get(event)
            names = spec.get("branches", []) if isinstance(spec, dict) else []
            for name in names or []:
                if any(ch in name for ch in "*?[!") or name in remote:
                    continue
                findings.append(
                    Finding(
                        "DS04",
                        "warning",
                        rel,
                        f"{event} filters on branch {name!r}, which does not exist on origin",
                        f"remove {name!r} from the {event} branches filter",
                    )
                )
    return findings


# ─────────────────────────────── DS05 frontend deps ───────────────────────────── #


# Binaries whose name differs from their package, for checkouts without
# node_modules (CI runs this check before any npm install).
KNOWN_BINS = {"typescript": {"tsc", "tsserver"}}


def _package_bins(package_dir: Path, dep: str) -> set[str]:
    manifest = package_dir / "node_modules" / dep / "package.json"
    bins = {dep.rsplit("/", 1)[-1]} | KNOWN_BINS.get(dep, set())
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        declared = data.get("bin")
        if isinstance(declared, dict):
            bins |= set(declared)
        elif isinstance(declared, str):
            bins.add(data.get("name", dep).rsplit("/", 1)[-1])
    return bins


def check_frontend_deps(root: Path) -> list[Finding]:
    findings = []
    for manifest in sorted(p for p in _walk(root) if p.name == "package.json"):
        package_dir = manifest.parent
        rel = _rel(manifest, root)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if not deps:
            continue
        scripts = " && ".join(str(v) for v in data.get("scripts", {}).values())
        sources = []
        for path in _walk(package_dir, {".ts", ".tsx", ".js", ".mjs", ".cjs", ".css", ".html"}):
            sources.append(path.read_text(encoding="utf-8", errors="replace"))
        corpus = "\n".join(sources)
        bins = {dep: _package_bins(package_dir, dep) for dep in deps}

        def used(dep: str) -> bool:
            if dep.startswith("@types/"):
                target = dep[len("@types/") :]
                return (
                    target == "node"
                    or (target in deps and used(target))
                    or bool(re.search(rf"['\"]{re.escape(target)}(/[^'\"]*)?['\"]", corpus))
                )
            if dep.startswith("@vitest/coverage-"):
                return "--coverage" in scripts
            if re.search(rf"['\"]{re.escape(dep)}(/[^'\"]*)?['\"]", corpus):
                return True
            return any(re.search(rf"(^|[\s&;|(]){re.escape(b)}(\s|$)", scripts) for b in bins[dep])

        for dep in sorted(deps):
            if not used(dep):
                findings.append(
                    Finding(
                        "DS05",
                        "error",
                        rel,
                        f"declares {dep!r}, which nothing references",
                        f"npm uninstall {dep}",
                    )
                )
        declared_bins = set().union(*bins.values()) if bins else set()
        for command in re.split(r"&&|\|\||;", scripts):
            words = [w for w in command.split() if "=" not in w]
            if not words:
                continue
            binary = words[0]
            if binary in SHELL_WORDS or binary in declared_bins:
                continue
            findings.append(
                Finding(
                    "DS05",
                    "error",
                    rel,
                    f"a script runs {binary!r}, which is not a declared dependency",
                    f"npm install --save-dev {binary}, or remove the script",
                )
            )
    return findings


# ─────────────────────────────── DS07 entry points ─────────────────────────────── #

_PY_RUN = re.compile(r"\bpython3?(?:\.\d+)?\s+(?:-u\s+)?(-m\s+([\w.]+)|([\w./-]+\.py)\b)")


def _commands(path: Path) -> list[str]:
    """The command strings a deployment file runs."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.name.startswith("Dockerfile"):
        out = []
        for line in re.sub(r"\\\n", " ", text).splitlines():
            head = line.strip().split(None, 1)
            if head and head[0].upper() in ("RUN", "CMD", "ENTRYPOINT") and len(head) > 1:
                body = head[1]
                try:
                    body = " ".join(json.loads(body)) if body.startswith("[") else body
                except json.JSONDecodeError:
                    pass
                out.append(body)
        return out
    data = yaml.safe_load(text) or {}
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("command", "entrypoint", "run", "test"):
                    out.append(" ".join(map(str, value)) if isinstance(value, list) else str(value))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return out


def _local_module(root: Path, dotted: str) -> tuple[bool, bool]:
    """(is_local, exists) for ``dotted`` against the repository's source roots."""
    top = dotted.split(".")[0]
    local = exists = False
    for base in (root, root / PLATFORM):
        if (base / top).is_dir() or (base / f"{top}.py").is_file():
            local = True
            target = base.joinpath(*dotted.split("."))
            if target.with_suffix(".py").is_file() or (target / "__init__.py").is_file():
                exists = True
            elif (target / "__main__.py").is_file():
                exists = True
    return local, exists


def check_entry_points(root: Path) -> list[Finding]:
    findings = []
    for path in _walk(root):
        rel = _rel(path, root)
        is_deploy = path.name.startswith("Dockerfile") or (
            path.suffix in {".yml", ".yaml"}
            and ("compose" in path.name or rel.startswith(".github/workflows/"))
        )
        if not is_deploy:
            continue
        try:
            commands = _commands(path)
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        for command in commands:
            for match in _PY_RUN.finditer(command):
                module, script = match.group(2), match.group(3)
                if module:
                    local, exists = _local_module(root, module)
                    if local and not exists:
                        findings.append(
                            Finding(
                                "DS07",
                                _severity(rel),
                                rel,
                                f"runs python -m {module}, which does not exist",
                                f"point it at the module that replaced {module}, or remove it",
                            )
                        )
                elif script and not script.startswith(("/", "$")):
                    candidates = [root / script, root / PLATFORM / script]
                    if "/" in script and not any(c.is_file() for c in candidates):
                        findings.append(
                            Finding(
                                "DS07",
                                _severity(rel),
                                rel,
                                f"runs {script}, which does not exist",
                                f"point it at the script that replaced {script}, or remove it",
                            )
                        )
    return findings


# ───────────────────────────────────── main ───────────────────────────────────── #

CHECKS = {
    "DS01": check_dead_config,
    "DS02": check_python_deps,
    "DS03": check_native_build,
    "DS04": check_ci_triggers,
    "DS05": check_frontend_deps,
    "DS06": check_boot_requirements,
    "DS07": check_entry_points,
}


def scan(root: Path = ROOT, checks: tuple[str, ...] = tuple(CHECKS)) -> list[Finding]:
    findings: list[Finding] = []
    for check in checks:
        findings.extend(CHECKS[check](root))
    return findings


def _markdown(findings: list[Finding]) -> str:
    errors = [f for f in findings if f.severity == "error"]
    lines = [
        "## Deploy sentry",
        "",
        f"**{len(errors)} error(s), {len(findings) - len(errors)} warning(s)**",
        "",
    ]
    if findings:
        lines += ["| | Check | Where | Finding | Fix |", "|---|---|---|---|---|"]
        for f in sorted(findings, key=lambda f: (f.severity != "error", f.check, f.path)):
            mark = "❌" if f.severity == "error" else "⚠️"
            lines.append(f"| {mark} | {f.check} | `{f.path}` | {f.message} | {f.fix} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deploy sentry: wiring pitfalls that break a deployment"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="append", choices=sorted(CHECKS))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--errors-only", action="store_true")
    args = parser.parse_args(argv)
    findings = scan(args.root.resolve(), tuple(args.check or CHECKS))
    if args.errors_only:
        findings = [f for f in findings if f.severity == "error"]
    errors = sum(f.severity == "error" for f in findings)
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        for finding in sorted(findings, key=lambda f: (f.severity != "error", f.check, f.path)):
            print(finding.line())
        print(f"\ndeploy sentry: {errors} error(s), {len(findings) - errors} warning(s)")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(_markdown(findings))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
