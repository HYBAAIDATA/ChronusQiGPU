"""Mutation check: do the tests fail when the logic is wrong?

A passing suite says the code does what the tests expect; it does not say
the tests would notice a mistake. This tool plants one small mistake at a
time in a module (``<`` for ``<=``, ``+`` for ``-``, ``min`` for ``max``,
``and`` for ``or``, a constant off by one, a dropped ``not``) and runs the
tests against it. A killed mutant is a mistake the tests catch; a survivor
is logic no test pins down, either a missing test or an equivalent change
worth a look.

Each worker mutates its own throwaway copy of the package, so the working
tree is never touched, and the check aborts unless the copy is what the
tests import.

    python scripts/mutation_check.py \\
        chronus/mla1517/mining/hashrate_governor.py \\
        --tests test_hashrate_governor.py --workers 4
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COPY_ROOT = ROOT / "chronus/mla1517_platform" / "python"

_COMPARE = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}
_BINARY = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Div,
    ast.Mod: ast.FloorDiv,
    ast.Pow: ast.Mult,
}
_SYMBOL = {
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.In: "in",
    ast.NotIn: "not in",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.And: "and",
    ast.Or: "or",
}
_LOGGERS = {"LOG", "log", "logger", "logging", "print", "warnings"}


@dataclass(frozen=True)
class Mutant:
    index: int
    walk_position: int
    slot: int
    line: int
    description: str


@dataclass
class Result:
    mutant: Mutant
    status: str  # killed | survived | timeout | error
    seconds: float


def _skipped_subtrees(tree: ast.AST) -> set[int]:
    """Annotations, docstrings, logging calls and __main__ blocks."""
    skip: set[int] = set()

    def mark(node: ast.AST | None) -> None:
        if node is not None:
            skip.update(id(n) for n in ast.walk(node))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mark(node.returns)
            for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                mark(arg.annotation)
        elif isinstance(node, ast.AnnAssign):
            mark(node.annotation)
        elif isinstance(node, ast.Call):
            func = node.func
            base = func
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name) and base.id in _LOGGERS:
                mark(node)
        elif isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
            mark(node)
        elif isinstance(node, ast.JoinedStr):
            mark(node)
    return skip


def _mutations(node: ast.AST) -> list[tuple[int, str]]:
    """(slot, description) pairs for the mutations this node supports."""
    out: list[tuple[int, str]] = []
    if isinstance(node, ast.Compare):
        for slot, op in enumerate(node.ops):
            if type(op) in _COMPARE:
                new = _COMPARE[type(op)]
                out.append((slot, f"{_SYMBOL[type(op)]} -> {_SYMBOL[new]}"))
    elif isinstance(node, (ast.BinOp, ast.AugAssign)) and type(node.op) in _BINARY:
        out.append((0, f"{_SYMBOL[type(node.op)]} -> {_SYMBOL[_BINARY[type(node.op)]]}"))
    elif isinstance(node, ast.BoolOp):
        new = "or" if isinstance(node.op, ast.And) else "and"
        out.append((0, f"{_SYMBOL[type(node.op)]} -> {new}"))
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub)):
        out.append((0, "drop " + ("not" if isinstance(node.op, ast.Not) else "unary -")))
    elif isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            out.append((0, f"{value} -> {not value}"))
        elif isinstance(value, int):
            out.append((0, f"{value} -> {value + 1}"))
        elif isinstance(value, float):
            out.append((0, f"{value} -> {value * 2 if value else 1.0}"))
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in ("min", "max"):
            out.append((0, f"{node.func.id} -> {'max' if node.func.id == 'min' else 'min'}"))
    return out


def _apply(node: ast.AST, slot: int) -> None:
    if isinstance(node, ast.Compare):
        node.ops[slot] = _COMPARE[type(node.ops[slot])]()
    elif isinstance(node, (ast.BinOp, ast.AugAssign)):
        node.op = _BINARY[type(node.op)]()
    elif isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            node.value = not value
        elif isinstance(value, int):
            node.value = value + 1
        else:
            node.value = value * 2 if value else 1.0
    elif isinstance(node, ast.Call):
        node.func.id = "max" if node.func.id == "min" else "min"


class _DropUnary(ast.NodeTransformer):
    def __init__(self, target: ast.AST) -> None:
        self.target = target

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        return node.operand if node is self.target else node


def enumerate_mutants(source: str, lines: set[int] | None = None) -> list[Mutant]:
    tree = ast.parse(source)
    skip = _skipped_subtrees(tree)
    docstrings = {
        id(body[0].value)
        for body in (
            getattr(n, "body", None)
            for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        )
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
    }
    mutants: list[Mutant] = []
    for position, node in enumerate(ast.walk(tree)):
        if id(node) in skip or id(node) in docstrings:
            continue
        line = getattr(node, "lineno", 0)
        if lines is not None and line not in lines:
            continue
        for slot, description in _mutations(node):
            mutants.append(Mutant(len(mutants), position, slot, line, description))
    return mutants


def mutate(source: str, mutant: Mutant) -> str:
    tree = ast.parse(source)
    for position, node in enumerate(ast.walk(tree)):
        if position == mutant.walk_position:
            if isinstance(node, ast.UnaryOp):
                tree = _DropUnary(node).visit(tree)
            else:
                _apply(node, mutant.slot)
            return ast.unparse(tree)
    raise LookupError(f"mutation point {mutant.walk_position} not found")


class Sandbox:
    """A private copy of the package; the working tree is never written."""

    def __init__(self, copy_root: Path, module: Path, extra_path: Path = ROOT) -> None:
        self.extra_path = extra_path
        self.dir = Path(tempfile.mkdtemp(prefix="mutation-"))
        self.root = self.dir / copy_root.name
        shutil.copytree(
            copy_root,
            self.root,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
        self.module = self.root / module.relative_to(copy_root)
        self.original = self.module.read_text(encoding="utf-8")

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(self.root), str(self.extra_path)])
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def run(self, tests: list[str], timeout: float) -> tuple[str, float]:
        started = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests],
                cwd=self.root,
                env=self.env(),
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return "timeout", time.monotonic() - started
        seconds = time.monotonic() - started
        if proc.returncode == 0:
            return "survived", seconds
        # 1: a test failed. 2: collection failed, so the mutant broke the
        # module's import and no test could pass against it. Both catch it.
        if proc.returncode in (1, 2):
            return "killed", seconds
        return "error", seconds

    def imports_copy(self, module_name: str) -> bool:
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module_name} as m; print(m.__file__)"],
            cwd=self.root,
            env=self.env(),
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0 and Path(proc.stdout.strip()).resolve() == self.module.resolve()

    def close(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def run(args, root: Path = ROOT) -> dict:
    module = Path(args.module).resolve()
    copy_root = Path(args.copy_root).resolve()
    module_name = ".".join(module.relative_to(copy_root).with_suffix("").parts)
    source = module.read_text(encoding="utf-8")
    lines = None
    if args.lines:
        lo, _, hi = args.lines.partition("-")
        lines = set(range(int(lo), int(hi or lo) + 1))
    mutants = enumerate_mutants(source, lines)
    if args.limit:
        mutants = mutants[: args.limit]
    sandboxes = [Sandbox(copy_root, module, root) for _ in range(max(1, args.workers))]
    try:
        if not sandboxes[0].imports_copy(module_name):
            raise SystemExit(f"{module_name} does not import from the sandbox; refusing to run")
        status, baseline = sandboxes[0].run(args.tests, timeout=args.timeout or 900)
        if status != "survived":
            raise SystemExit(f"tests do not pass on the unmutated module ({status})")
        timeout = args.timeout or max(30.0, baseline * 4)
        print(f"{module_name}: {len(mutants)} mutants, baseline {baseline:.1f}s", flush=True)
        free = list(sandboxes)
        lock = threading.Lock()

        def check(mutant: Mutant) -> Result:
            with lock:
                box = free.pop()
            try:
                box.module.write_text(mutate(box.original, mutant), encoding="utf-8")
                status, seconds = box.run(args.tests, timeout)
            finally:
                box.module.write_text(box.original, encoding="utf-8")
                with lock:
                    free.append(box)
            print(f"  {status:8s} L{mutant.line:<4d} {mutant.description}", flush=True)
            return Result(mutant, status, seconds)

        with ThreadPoolExecutor(max_workers=len(sandboxes)) as pool:
            results = list(pool.map(check, mutants))
    finally:
        for box in sandboxes:
            box.close()
    source_lines = source.splitlines()
    killed = sum(r.status in ("killed", "timeout") for r in results)
    report = {
        "module": str(module.relative_to(root)) if module.is_relative_to(root) else str(module),
        "tests": args.tests,
        "mutants": len(results),
        "killed": killed,
        "score": killed / len(results) if results else None,
        "survivors": [
            {
                **asdict(r.mutant),
                "source": source_lines[r.mutant.line - 1].strip() if r.mutant.line else "",
            }
            for r in results
            if r.status in ("survived", "error")
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("module", help="module to mutate, a path under --copy-root")
    parser.add_argument(
        "--tests", nargs="+", required=True, help="pytest targets, relative to --copy-root"
    )
    parser.add_argument("--copy-root", default=str(DEFAULT_COPY_ROOT))
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--timeout", type=float, default=0.0)
    parser.add_argument("--lines", help="only mutate these lines, e.g. 40-120")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", help="write the report here")
    parser.add_argument("--min-score", type=float, default=0.0, help="fail below this score")
    args = parser.parse_args()
    report = run(args)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
    score = report["score"]
    print(
        f"\n{report['module']}: {report['killed']}/{report['mutants']} killed"
        + (f" ({score:.0%})" if score is not None else "")
    )
    for survivor in report["survivors"]:
        print(
            f"  survived L{survivor['line']}: {survivor['description']:14s} | {survivor['source']}"
        )
    failed = score is not None and score < args.min_score
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        lines = [
            f"### Mutation check: `{report['module']}`",
            "",
            f"**{report['killed']}/{report['mutants']} killed"
            + (f" ({score:.0%})" if score is not None else "")
            + f"**, floor {args.min_score:.0%} — {'FAIL' if failed else 'PASS'}",
            "",
        ]
        if report["survivors"]:
            lines += ["| Line | Mutation | Source |", "|---|---|---|"]
            lines += [
                f"| {s['line']} | `{s['description']}` | `{s['source'].replace('|', '/')}` |"
                for s in report["survivors"]
            ]
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
