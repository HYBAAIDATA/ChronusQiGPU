#!/usr/bin/env python3
"""Rule 7 gate: no floating point in the exact math core.

An AST scan of the declared exact modules. Rejects float literals and
``float()``/``complex()`` usage in executable code.

COMMENTS AND DOCSTRINGS ARE STRIPPED BEFORE THE SCAN. A docstring that
DISCUSSES floats -- and this one does -- must not fail the gate, or the
gate would train people to hide the mathematics rather than write it down.
Only executable nodes are examined.

Exit code 0 = pass, 1 = fail. Suitable for CI as a hard dependency.
"""

from __future__ import annotations

import argparse
import ast

from pathlib import Path
from typing import Dict, List, Tuple

#: The exact core. Every module here must stay float-free.
EXACT_MODULES: Tuple[str, ...] = (
    "constants.py",
    "fibonacci_store.py",
    "zeckendorf_codec.py",
    "binet_view.py",
    "pisot_fold.py",
    "lucas_scale.py",
    "cassini.py",
    "m32_geometry.py",
    "prime_address.py",
    "state.py",
    "prime_db.py",
    "query.py",
    "rings.py",
    "quantum.py",
)

#: Names that are floating point when called.
FLOAT_NAMES = frozenset(
    {"float", "complex", "sqrt", "pow", "log", "log2", "exp", "sin", "cos", "tan", "cmath"}
)


def _strip_docs_and_comments(tree: ast.AST) -> ast.AST:
    """Blank out docstrings so prose about floats is not treated as code."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                first.value.value = ""
    return tree


def scan_file(path: Path) -> List[Tuple[int, str]]:
    """Return a list of (line, reason) violations in one file."""
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - unreadable file
        return [(0, f"unreadable: {exc}")]
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [(exc.lineno or 0, f"syntax error: {exc.msg}")]
    tree = _strip_docs_and_comments(tree)
    out: List[Tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            out.append((node.lineno, f"float literal {node.value!r}"))
        elif isinstance(node, ast.Attribute) and node.attr in FLOAT_NAMES:
            out.append((node.lineno, f"floating attribute .{node.attr}"))
        elif isinstance(node, ast.Name) and node.id in ("float", "complex"):
            out.append((node.lineno, f"callable {node.id}()"))
    return out


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(
            Path(__file__).resolve().parent.parent / "mla1517_platform_v3.4" / "python" / "mla1517"
        ),
        help="path to the mla1517 package",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    root = Path(args.root)
    results: Dict[str, List[Tuple[int, str]]] = {}
    scanned = 0
    for name in EXACT_MODULES:
        path = root / name
        if not path.is_file():
            results[name] = [(0, "MODULE MISSING")]
            continue
        scanned += 1
        violations = scan_file(path)
        if violations:
            results[name] = violations

    total = sum(len(v) for v in results.values())
    if args.json:
        import json

        print(
            json.dumps(
                {
                    "scanned": scanned,
                    "declared": len(EXACT_MODULES),
                    "violations": total,
                    "files": {k: [f"L{n}: {r}" for n, r in v] for k, v in results.items()},
                    "passed": total == 0,
                },
                indent=2,
            )
        )
        return 0 if total == 0 else 1

    print("=== Rule 7: no-float exact-core gate ===")
    print(f"  modules declared : {len(EXACT_MODULES)}")
    print(f"  modules scanned  : {scanned}")
    for name, violations in sorted(results.items()):
        for line, reason in violations:
            print(f"  VIOLATION {name}:{line}  {reason}")
    if total == 0:
        print("  RESULT: PASS -- the exact core contains no floating point")
        return 0
    print(f"  RESULT: FAIL -- {total} floating-point use(s) in the exact core")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
