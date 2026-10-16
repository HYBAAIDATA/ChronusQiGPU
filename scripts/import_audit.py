"""Import audit: every local import resolves, and no import failure is hidden.

The broken wire this was built for: Salamander's ``__init__`` did
``from .skill_loader import load_skills`` inside ``try: ... except
Exception: pass``. ``load_skills`` did not exist, the ImportError was
swallowed, and Salamander ran for months with no skills. No test failed,
so nothing (self-healing included) ever saw it.

Checks, statically and with the standard library only:

IA01  a local module that does not exist (``import pkg.missing``)
IA02  a name that the local module does not define (``from pkg import nope``)
IA03  a relative import that climbs out of its package or names nothing
IA04  ``importlib.import_module("literal")`` of a local module that does not exist

Every finding also says whether the import sits in a ``try`` whose handler
swallows the failure, which is how such a bug survives: the finding is an
error either way.

A module is *local* when its top-level name is a package or module in one of
the source roots: the repository root, the platform tree, every in-tree
distribution, and, for a script or test file outside any package, its own
directory (``python file.py`` and pytest put it on ``sys.path``).
Third-party imports are the deploy sentry's concern (DS02).

Usage:  python scripts/import_audit.py [--json FILE]   (exit 1 on findings)
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source_roots(root: Path = ROOT) -> tuple[Path, ...]:
    """The repository root, the platform tree, and every in-tree distribution
    (a top-level folder with its own pyproject.toml, whose package is inside
    it and is put on ``sys.path`` by the code and tests that use it)."""
    dists = sorted(d for d in root.iterdir() if d.is_dir() and (d / "pyproject.toml").is_file())
    return (root, root / "chronus/mla1517_platform" / "python", *dists)


EXCLUDE = (
    "legacy/",
    "Intelligence/skills/",
    "build/",
    "node_modules/",
    "PYTHIA-main/",
    # Vendored third-party workshop tree (aws-samples/sample-saas-multi-agents-
    # workshop). Flat sibling imports (import ops_context, from log_agent import
    # ...) and a lab-generated constants.py do not resolve on the consolidated
    # import graph; excluded as a standalone vendored tree (same rule as
    # PYTHIA-main/). See external/README.md.
    "external/",
    # Preserved standalone package: carries its own src/chronos namespace and
    # is not part of the consolidated import graph (same rule as PYTHIA-main/).
    "chronus/packages/chronos-one-igpu/",
)
CATCH_ALL = {"Exception", "BaseException", "ImportError", "ModuleNotFoundError"}


@dataclass(frozen=True)
class Finding:
    code: str
    file: str
    line: int
    module: str
    name: str | None
    swallowed: bool

    @property
    def hidden(self) -> bool:
        return self.swallowed

    def render(self) -> str:
        what = f"{self.module}.{self.name}" if self.name else self.module
        hidden = " (failure swallowed by try/except)" if self.swallowed else ""
        messages = {
            "IA01": f"imports {self.module}, which does not exist",
            "IA02": f"imports {what}, which {self.module} does not define",
            "IA03": f"relative import {self.module!r} resolves to nothing",
            "IA04": f"import_module({self.module!r}) names a module that does not exist",
        }
        return f"{self.code} {self.file}:{self.line}: {messages[self.code]}{hidden}"


def live_files(root: Path = ROOT) -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "*.py"], capture_output=True, text=True, check=True
    ).stdout.split()
    return [root / f for f in out if not f.startswith(EXCLUDE)]


def _module_path(base: Path, dotted: str) -> Path | None:
    """The file or package directory for ``dotted`` under ``base``, if any."""
    target = base.joinpath(*dotted.split("."))
    if target.with_suffix(".py").is_file():
        return target.with_suffix(".py")
    if target.is_dir() and (
        (target / "__init__.py").is_file() or any(target.glob("*.py")) or any(target.iterdir())
    ):
        return target
    return None


def _str_tuple_literals(value: ast.AST) -> frozenset[str]:
    """The literal strings in a ``("a", "b")`` tuple/list/set constant."""
    if not isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        return frozenset()
    return frozenset(
        elt.value
        for elt in value.elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    )


def _assigns_sys_modules(node: ast.AST) -> bool:
    """Whether ``node`` is a ``sys.modules[...] = ...`` assignment."""
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return False
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for target in targets:
        if (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "modules"
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "sys"
        ):
            return True
    return False


def _runtime_module_aliases(pkg_init: Path) -> frozenset[str]:
    """Submodule names a package installs into ``sys.modules`` at import
    time — facade/alias packages (e.g. ``chronos`` → ``chronus.v33``) whose
    ``pkg.<name>`` has no file on disk but resolves at runtime.

    Detects ``for <name> in <literal tuple>:`` loops whose body assigns
    ``sys.modules[...]``; the iterable may be a literal tuple or a module
    top-level Name bound to one.
    """
    try:
        tree = ast.parse(pkg_init.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return frozenset()
    bound: dict[str, frozenset[str]] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            vals = _str_tuple_literals(node.value)
            if vals:
                bound[node.targets[0].id] = vals
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)) or not isinstance(
            node.target, ast.Name
        ):
            continue
        names: frozenset[str] = frozenset()
        if isinstance(node.iter, (ast.Tuple, ast.List, ast.Set)):
            names = _str_tuple_literals(node.iter)
        elif isinstance(node.iter, ast.Name):
            names = bound.get(node.iter.id, frozenset())
        if names and any(_assigns_sys_modules(inner) for inner in ast.walk(node)):
            out.update(names)
    return frozenset(out)


@lru_cache(maxsize=None)
def _bindings(path: Path) -> tuple[frozenset[str], bool]:
    """Names a module binds at top level, and whether it may bind anything else."""
    if path.is_dir():
        init = path / "__init__.py"
        if not init.is_file():
            return frozenset(), False
        path = init
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return frozenset(), True
    names: set[str] = set()
    open_ended = False

    def targets(node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                targets(elt)
        elif isinstance(node, ast.Starred):
            targets(node.value)

    def visit(body: list[ast.stmt]) -> None:
        nonlocal open_ended
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
                if node.name == "__getattr__":
                    open_ended = True
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    targets(t)
                    if isinstance(t, ast.Name) and t.id == "__getattr__":
                        open_ended = True
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets(node.target)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        open_ended = True
                    else:
                        names.add(alias.asname or alias.name)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                targets(node.target)
                visit(node.body)
                visit(node.orelse)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        targets(item.optional_vars)
                visit(node.body)
            elif isinstance(node, ast.If):
                visit(node.body)
                visit(node.orelse)
            elif isinstance(node, ast.Try) or type(node).__name__ == "TryStar":
                visit(node.body)
                for handler in node.handlers:
                    if handler.name:
                        names.add(handler.name)
                    visit(handler.body)
                visit(node.orelse)
                visit(node.finalbody)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                # globals().update(...) / globals()[...] = ... bind names dynamically.
                func = node.value.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Call)
                    and getattr(func.value.func, "id", None) == "globals"
                ):
                    open_ended = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Call):
                if getattr(node.value.func, "id", None) == "globals":
                    open_ended = True
            if isinstance(node, ast.NamedExpr):
                targets(node.target)

    visit(tree.body)
    return frozenset(names), open_ended


class Auditor:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.roots = source_roots(root)

    def _dist_base(self, top: str) -> Path | None:
        """The in-tree distribution that owns ``top``, if any.

        A top-level folder with its own ``pyproject.toml`` whose package lives
        inside it (``<dist>/<top>/__init__.py``) is itself a ``sys.path`` entry:
        ``import <top>`` binds the inner package, not the outer folder. Checking
        it before the repo root keeps namespace-package shadows (a dist dir that
        also holds stray modules) from swallowing the real package.
        """
        candidate = self.root / top
        if (candidate / "pyproject.toml").is_file() and _module_path(candidate, top) is not None:
            return candidate
        return None

    def _locate(self, dotted: str, extra: Path | None) -> tuple[Path | None, bool]:
        """(path, is_local): the module's path, and whether its top name is local."""
        top = dotted.split(".")[0]
        local = False
        dist = self._dist_base(top)
        bases = [b for b in (extra, dist, *self.roots) if b is not None]
        for base in bases:
            top_path = _module_path(base, top)
            if top_path is not None:
                local = True
                found = _module_path(base, dotted)
                if found is not None:
                    return found, True
                # sys.modules-installed alias: pkg.<name> has no file but the
                # package registers it at import time (facade packages).
                rest = dotted.split(".", 1)[1]
                if (
                    "." not in rest
                    and top_path.is_dir()
                    and rest in _runtime_module_aliases(top_path / "__init__.py")
                ):
                    return top_path, True
        return None, local

    def _name_ok(self, module: Path, name: str) -> bool:
        if module.is_dir() and _module_path(module.parent, f"{module.name}.{name}"):
            return True
        bound, open_ended = _bindings(module)
        return open_ended or name in bound

    def audit_file(self, path: Path) -> list[Finding]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            return []
        rel = path.relative_to(self.root).as_posix()
        findings: list[Finding] = []
        swallowed = _swallowed_imports(tree)
        package = _package_of(path)
        # Only a script or test outside any package has its own folder on sys.path.
        extra = None if package is not None else path.parent
        for node in ast.walk(tree):
            hidden = id(node) in swallowed
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found, local = self._locate(alias.name, extra)
                    if local and found is None:
                        findings.append(Finding("IA01", rel, node.lineno, alias.name, None, hidden))
            elif isinstance(node, ast.ImportFrom):
                findings.extend(self._audit_from(node, path, rel, package, extra, hidden))
            elif isinstance(node, ast.Call) and _is_import_module(node):
                literal = node.args[0].value
                if not literal.startswith("."):
                    found, local = self._locate(literal, extra)
                    if local and found is None:
                        findings.append(Finding("IA04", rel, node.lineno, literal, None, hidden))
        return findings

    def _audit_from(self, node, path, rel, package, extra, hidden) -> list[Finding]:
        if node.level:
            base = path.parent
            for _ in range(node.level - 1):
                base = base.parent
            if package is None or not _inside(base, package):
                return [
                    Finding(
                        "IA03",
                        rel,
                        node.lineno,
                        "." * node.level + (node.module or ""),
                        None,
                        hidden,
                    )
                ]
            if node.module:
                module = _module_path(base, node.module)
                if module is None:
                    return [
                        Finding(
                            "IA01", rel, node.lineno, "." * node.level + node.module, None, hidden
                        )
                    ]
            else:
                module = base
            shown = "." * node.level + (node.module or "")
        else:
            module, local = self._locate(node.module, extra)
            if not local:
                return []
            if module is None:
                return [Finding("IA01", rel, node.lineno, node.module, None, hidden)]
            shown = node.module
        out = []
        for alias in node.names:
            if alias.name != "*" and not self._name_ok(module, alias.name):
                out.append(Finding("IA02", rel, node.lineno, shown, alias.name, hidden))
        return out

    def audit(self, files: list[Path]) -> list[Finding]:
        findings: list[Finding] = []
        for path in files:
            findings.extend(self.audit_file(path))
        return sorted(findings, key=lambda f: (f.file, f.line, f.module, f.name or ""))


def _package_of(path: Path) -> Path | None:
    """The outermost package directory containing ``path`` (None for a script)."""
    top = None
    here = path.parent
    while (here / "__init__.py").is_file():
        top = here
        here = here.parent
    return top


def _inside(base: Path, package: Path) -> bool:
    try:
        base.relative_to(package)
        return True
    except ValueError:
        return False


def _is_import_module(node: ast.Call) -> bool:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    return (
        name in ("import_module", "__import__")
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    )


def _swallowed_imports(tree: ast.AST) -> set[int]:
    """ids of import nodes inside a try whose handler hides an import failure."""
    hidden: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        swallows = False
        for handler in node.handlers:
            caught = _caught(handler.type)
            reraises = any(isinstance(n, ast.Raise) for n in ast.walk(handler))
            if (caught is None or caught & CATCH_ALL) and not reraises:
                swallows = True
        if not swallows:
            continue
        for stmt in node.body:
            for inner in ast.walk(stmt):
                if isinstance(inner, (ast.Import, ast.ImportFrom)) or (
                    isinstance(inner, ast.Call) and _is_import_module(inner)
                ):
                    hidden.add(id(inner))
    return hidden


def _caught(expr: ast.expr | None) -> set[str] | None:
    if expr is None:
        return None  # a bare except catches everything
    if isinstance(expr, ast.Tuple):
        return {getattr(e, "id", getattr(e, "attr", "")) for e in expr.elts}
    return {getattr(expr, "id", getattr(expr, "attr", ""))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the findings here as JSON")
    args = parser.parse_args(argv)
    findings = Auditor().audit(live_files())
    for f in findings:
        print(f.render())
    hidden = sum(f.swallowed for f in findings)
    print(f"\nimport audit: {len(findings)} finding(s), {hidden} of them swallowed")
    if args.json:
        Path(args.json).write_text(
            json.dumps([f.__dict__ for f in findings], indent=2), encoding="utf-8"
        )
    return 1 if findings else 0


if __name__ == "__main__":
    from gate_impl import main as _gate_main

    raise SystemExit(_gate_main("import-audit"))
