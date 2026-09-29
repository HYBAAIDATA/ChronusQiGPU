"""Import graph: cycles, orphans, blast radius and layer rules, statically.

Built on the import audit's resolver (``scripts/import_audit.py``), so a
module means the same thing in both. Every tracked Python file outside
``legacy/``, ``build/`` and the grafted skills is parsed (never executed)
and each local import becomes an edge, marked *eager* (runs at import time)
or *lazy* (inside a function, or ``importlib.import_module``). A string
literal naming a local ``.py`` file (``subprocess.Popen([python,
"salamander_engine.py"])``) is a *spawn* edge: the control API starts its
workers that way.

Questions it answers:

cycles    import-time loops among eager imports (``if TYPE_CHECKING`` and
          in-function imports cannot loop at import time and are excluded)
orphans   every file classed by what reaches it: ``runtime`` (main.py, the
          pyproject scripts, what the images and compose files run),
          ``ci`` (what a workflow runs, tests aside), ``tests_only``,
          ``standalone`` (a ``__main__`` script nothing else reaches), or
          ``unreached``
blast     everything that imports a module, directly or transitively
layers    rules the architecture depends on: live code never imports
          ``legacy/`` or a test module

Usage:
  python scripts/import_graph.py cycles|layers   (exit 1 on anything new
                                                  against the baseline)
  python scripts/import_graph.py orphans [--json FILE]
  python scripts/import_graph.py blast PATH_OR_MODULE
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.import_audit import (  # noqa: E402
    ROOT,
    Auditor,
    _is_import_module,
    _module_path,
    _package_of,
    live_files,
)

BASELINE = Path(__file__).with_name("import_graph_baseline.json")
_PY_RUN = re.compile(r"\bpython3?(?:\.\d+)?\s+(?:-u\s+)?(-m\s+([\w.]+)|([\w./-]+\.py)\b)")
_UVICORN = re.compile(r"\b(?:uvicorn|gunicorn)\s+(?:.*\s)?([\w.]+):\w+")


def _is_test(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return (
        rel.startswith("tests/")
        or "/tests/" in rel
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
    )


@dataclass
class Graph:
    root: Path
    files: list[Path]
    eager: dict[Path, set[Path]] = field(default_factory=lambda: defaultdict(set))
    lazy: dict[Path, set[Path]] = field(default_factory=lambda: defaultdict(set))
    lines: dict[tuple[Path, Path], int] = field(default_factory=dict)

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def edges(self, path: Path) -> set[Path]:
        return self.eager.get(path, set()) | self.lazy.get(path, set())


def _file_of(module: Path | None) -> Path | None:
    if module is None:
        return None
    if module.is_dir():
        init = module / "__init__.py"
        return init if init.is_file() else None
    return module


def _chain(auditor: Auditor, dotted: str, extra: Path | None) -> list[Path]:
    """``a.b.c`` runs a/__init__, a/b/__init__ and a/b/c: every file it loads."""
    parts = dotted.split(".")
    out = []
    for i in range(1, len(parts) + 1):
        found, _ = auditor._locate(".".join(parts[:i]), extra)
        f = _file_of(found)
        if f is not None:
            out.append(f)
    return out


def _nodes_with_context(tree: ast.AST):
    """(node, lazy, type_only) for every import-like node."""

    def walk(node: ast.AST, lazy: bool, type_only: bool):
        for child in ast.iter_child_nodes(node):
            child_lazy = lazy or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            child_type = type_only
            if isinstance(child, ast.If):
                test = child.test
                name = getattr(test, "id", None) or getattr(test, "attr", None)
                if name == "TYPE_CHECKING":
                    for stmt in child.body:
                        yield from _one(stmt, lazy, True)
                        yield from walk(stmt, lazy, True)
                    for stmt in child.orelse:
                        yield from _one(stmt, lazy, type_only)
                        yield from walk(stmt, lazy, type_only)
                    continue
            yield from _one(child, lazy, child_type)
            yield from walk(child, child_lazy, child_type)

    def _one(node, lazy, type_only):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node, lazy, type_only
        elif isinstance(node, ast.Call) and _is_import_module(node):
            yield node, True, type_only
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.endswith(".py")
        ):
            yield node, True, type_only

    yield from walk(tree, False, False)


def build(root: Path = ROOT, files: list[Path] | None = None) -> Graph:
    auditor = Auditor(root)
    files = files if files is not None else live_files(root)
    graph = Graph(root, files)
    known = set(files)
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        package = _package_of(path)
        extra = None if package is not None else path.parent
        for node, lazy, type_only in _nodes_with_context(tree):
            if type_only:
                continue
            targets: list[Path] = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    targets += _chain(auditor, alias.name, extra)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = path.parent
                    for _ in range(node.level - 1):
                        base = base.parent
                    module = _module_path(base, node.module) if node.module else base
                    targets += [f for f in [_file_of(module)] if f]
                    if module is not None and module.is_dir():
                        for alias in node.names:
                            targets += [
                                f for f in [_file_of(_module_path(module, alias.name))] if f
                            ]
                else:
                    targets += _chain(auditor, node.module, extra)
                    found, _ = auditor._locate(node.module, extra)
                    if found is not None and found.is_dir():
                        for alias in node.names:
                            targets += [f for f in [_file_of(_module_path(found, alias.name))] if f]
            elif isinstance(node, ast.Call):
                targets += _chain(auditor, node.args[0].value, extra)
            else:  # a spawned script named by a string literal
                for base in (path.parent, root):
                    candidate = (base / node.value).resolve()
                    if candidate in known:
                        targets.append(candidate)
                        break
            for target in targets:
                target = target.resolve()
                if target == path or target not in known:
                    continue
                (graph.lazy if lazy else graph.eager)[path].add(target)
                graph.lines.setdefault((path, target), getattr(node, "lineno", 0))
    return graph


# ───────────────────────────────── cycles ───────────────────────────────── #


def cycles(graph: Graph) -> list[list[str]]:
    """Strongly connected components of the eager graph with more than one file."""
    index: dict[Path, int] = {}
    low: dict[Path, int] = {}
    stack: list[Path] = []
    on_stack: set[Path] = set()
    out: list[list[str]] = []
    counter = [0]

    def strong(v: Path) -> None:
        # Iterative Tarjan: deep import chains overflow the recursion limit.
        work = [(v, iter(sorted(graph.eager.get(v, ()))))]
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        while work:
            node, children = work[-1]
            advanced = False
            for w in children:
                if w not in index:
                    index[w] = low[w] = counter[0]
                    counter[0] += 1
                    stack.append(w)
                    on_stack.add(w)
                    work.append((w, iter(sorted(graph.eager.get(w, ())))))
                    advanced = True
                    break
                if w in on_stack:
                    low[node] = min(low[node], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    component.append(w)
                    if w == node:
                        break
                if len(component) > 1:
                    out.append(sorted(graph.rel(p) for p in component))

    for v in sorted(graph.files):
        if v not in index:
            strong(v)
    return sorted(out)


# ───────────────────────────────── orphans ──────────────────────────────── #


def _deploy_commands(root: Path) -> tuple[list[str], list[str]]:
    """(runtime commands from images and compose files, commands CI workflows run)."""
    from scripts.deploy_sentry import _deploy_units

    runtime, ci = [], []
    for rel, commands in _deploy_units(root):
        target = ci if rel.startswith(".github/") else runtime
        target.extend(command for _, command in commands)
    return runtime, ci


def _entry_files(root: Path, commands: list[str], graph: Graph) -> set[Path]:
    auditor = Auditor(root)
    known = set(graph.files)
    out: set[Path] = set()
    for command in commands:
        if "pytest" in command:
            continue
        for match in _PY_RUN.finditer(command):
            module, script = match.group(2), match.group(3)
            if module:
                out.update(p.resolve() for p in _chain(auditor, module, None))
                found, _ = auditor._locate(module, None)
                if found is not None and found.is_dir():
                    main = found / "__main__.py"
                    if main.is_file():
                        out.add(main.resolve())
            elif script:
                for base in (root, root / "mla1517_platform_v3.4"):
                    candidate = (base / script).resolve()
                    if candidate in known:
                        out.add(candidate)
        for module in _UVICORN.findall(command):
            out.update(p.resolve() for p in _chain(auditor, module, None))
    return out & known


def _pyproject_scripts(root: Path, graph: Graph) -> set[Path]:
    import tomllib

    from scripts.import_audit import source_roots

    auditor = Auditor(root)
    out: set[Path] = set()
    for base in source_roots(root):
        project = base / "pyproject.toml"
        if base == root / "mla1517_platform_v3.4" / "python":
            project = base.parent / "pyproject.toml"
        if not project.is_file():
            continue
        scripts = tomllib.loads(project.read_text(encoding="utf-8")).get("project", {})
        for target in (scripts.get("scripts") or {}).values():
            out.update(p.resolve() for p in _chain(auditor, target.split(":")[0], None))
    return out & set(graph.files)


def _reach(graph: Graph, starts: set[Path]) -> set[Path]:
    seen = set(starts)
    todo = list(starts)
    while todo:
        for nxt in graph.edges(todo.pop()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def _has_main_guard(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return "__name__" in text and "__main__" in text


def orphans(graph: Graph) -> dict[str, list[str]]:
    root = graph.root
    runtime_cmds, ci_cmds = _deploy_commands(root)
    main = {p for p in graph.files if graph.rel(p) == "main.py"}
    runtime = _reach(
        graph, main | _pyproject_scripts(root, graph) | _entry_files(root, runtime_cmds, graph)
    )
    ci = _reach(graph, _entry_files(root, ci_cmds, graph)) - runtime
    tests = {p for p in graph.files if _is_test(graph.rel(p))}
    tested = _reach(graph, tests) - runtime - ci - tests
    classes: dict[str, list[str]] = defaultdict(list)
    for path in sorted(graph.files):
        rel = graph.rel(path)
        if path in tests:
            continue
        if path in runtime:
            kind = "runtime"
        elif path in ci:
            kind = "ci"
        elif path in tested:
            kind = "tests_only"
        elif _has_main_guard(path):
            kind = "standalone"
        else:
            kind = "unreached"
        classes[kind].append(rel)
    return dict(classes)


# ───────────────────────────────── blast ────────────────────────────────── #


def blast(graph: Graph, target: str) -> list[str]:
    """Every file that imports ``target`` (a path or dotted module), transitively."""
    auditor = Auditor(graph.root)
    candidate = (graph.root / target).resolve()
    starts = {candidate} if candidate in set(graph.files) else set()
    if not starts:
        chain = _chain(auditor, target, None)
        starts = {chain[-1].resolve()} if chain else set()
    if not starts:
        raise SystemExit(f"{target}: no such module or file")
    reverse: dict[Path, set[Path]] = defaultdict(set)
    for src in graph.files:
        for dst in graph.edges(src):
            reverse[dst].add(src)
    seen: set[Path] = set()
    todo = list(starts)
    while todo:
        for importer in reverse.get(todo.pop(), ()):
            if importer not in seen:
                seen.add(importer)
                todo.append(importer)
    return sorted(graph.rel(p) for p in seen - starts)


# ───────────────────────────────── layers ───────────────────────────────── #


def layer_violations(graph: Graph) -> list[str]:
    """Live code imports neither ``legacy/`` nor a test module."""
    out = []
    for src in graph.files:
        rel = graph.rel(src)
        if _is_test(rel):
            continue
        for dst in sorted(graph.edges(src)):
            to = graph.rel(dst)
            line = graph.lines.get((src, dst), 0)
            if to.startswith("legacy/"):
                out.append(f"{rel}:{line}: imports legacy module {to}")
            elif _is_test(to):
                out.append(f"{rel}:{line}: imports test module {to}")
    return sorted(out)


# ───────────────────────────────── main ─────────────────────────────────── #


def _baseline() -> dict[str, list]:
    if BASELINE.is_file():
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    return {"cycles": [], "layers": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["cycles", "orphans", "blast", "layers"])
    parser.add_argument("target", nargs="?")
    parser.add_argument("--json", help="write the result here as JSON")
    parser.add_argument(
        "--update-baseline", action="store_true", help="accept the current cycles/layers"
    )
    args = parser.parse_args(argv)
    graph = build()
    if args.command == "blast":
        if not args.target:
            parser.error("blast needs a path or module")
        result: object = blast(graph, args.target)
        for rel in result:
            print(rel)
        print(f"\n{len(result)} file(s) depend on {args.target}")
        status = 0
    elif args.command == "orphans":
        result = orphans(graph)
        for kind in ("runtime", "ci", "tests_only", "standalone", "unreached"):
            print(f"{kind}: {len(result.get(kind, []))}")
        for rel in result.get("unreached", []):
            print(f"  unreached {rel}")
        status = 0
    else:
        result = cycles(graph) if args.command == "cycles" else layer_violations(graph)
        baseline = _baseline()
        known = baseline.get(args.command, [])
        new = [item for item in result if item not in known]
        for item in result:
            shown = " <- ".join(item) if isinstance(item, list) else item
            print(("NEW " if item in new else "known ") + shown)
        print(f"\n{args.command}: {len(result)} ({len(new)} new against the baseline)")
        if args.update_baseline:
            baseline[args.command] = result
            BASELINE.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
            new = []
        status = 1 if new else 0
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
