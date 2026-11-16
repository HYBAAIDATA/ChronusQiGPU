#!/usr/bin/env python3
"""Report real vs simulated test declarations without rebranding test doubles.

Every tests/**/test_*.py file needs exactly one module-level pytestmark
(pytest.mark.real or pytest.mark.simulated). A real file with mocks is flagged;
inline '# mock-ok: <specific reason>' is explicit and counted, not invisible.
Exit 0 clean, 2 findings, 1 scanner error. --json emits machine-readable data.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOCKERS = re.compile(
    r"\b(?:unittest\.mock|from\s+mock\b|monkeypatch\b|MagicMock\b|AsyncMock\b|"
    r"Mock\s*\(|mocker\b|mock\.(?:patch|MagicMock|Mock)|patch(?:\.object)?\s*\()"
)
MOCK_OK = re.compile(r"#\s*mock-ok:\s*\S.{3,}")


def marker(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
        and node.value.attr == "mark"
        and node.attr in {"real", "simulated"}
    ):
        return node.attr
    return None


def labels(tree: ast.Module) -> list[str]:
    result = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets
        ):
            values = stmt.value.elts if isinstance(stmt.value, (ast.List, ast.Tuple)) else [stmt.value]
            result.extend(label for v in values if (label := marker(v)) is not None)
    return result


def scan(root: Path) -> dict:
    report = {"files": {"real": 0, "simulated": 0, "unclassified": 0},
              "tests": {"real": 0, "simulated": 0, "unclassified": 0},
              "mock_exceptions": 0, "findings": []}
    for path in sorted((root / "tests").rglob("test_*.py")):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            report["findings"].append(f"{relative}:{exc.lineno}: invalid Python syntax: {exc.msg}")
            continue
        declared = labels(tree)
        status = declared[0] if len(declared) == 1 else "unclassified"
        if status == "unclassified":
            report["findings"].append(f"{relative}: require exactly one pytestmark real|simulated")
        count = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_") for node in ast.walk(tree)
        )
        report["files"][status] += 1
        report["tests"][status] += count
        if status == "real":
            for number, line in enumerate(source.splitlines(), 1):
                code = line.split("#", 1)[0]
                if MOCKERS.search(code):
                    if MOCK_OK.search(line):
                        report["mock_exceptions"] += 1
                    else:
                        report["findings"].append(f"{relative}:{number}: mock in a real test")
    return report


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = sys.argv[1:] if argv is None else argv
    if any(a != "--json" for a in args):
        print("usage: test_reality.py [--json]", file=sys.stderr)
        return 1
    try:
        report = scan(root)
    except (OSError, ValueError) as exc:
        print(f"test reality scan failed: {exc}", file=sys.stderr)
        return 1
    if "--json" in args:
        print(json.dumps(report, indent=2))
    else:
        for finding in report["findings"]:
            print("FAIL", finding)
        print("files:", report["files"], "tests:", report["tests"])
        print(f"documented mock exceptions: {report['mock_exceptions']}")
    print(f"{len(report['findings'])} findings", file=sys.stderr)
    return 2 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
