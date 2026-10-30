#!/usr/bin/env python3
"""Fail when TURING production Python directly imports Chronus."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "turing_universal_quantum_computer"
    / "turing_universal_quantum_computer"
)


def chronus_imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module] if node.module else []
        else:
            continue

        for module in modules:
            if module == "chronus" or module.startswith("chronus."):
                violations.append((node.lineno, module))

    return violations


def main() -> int:
    failures: list[str] = []

    for path in sorted(PACKAGE.rglob("*.py")):
        try:
            violations = chronus_imports(path)
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            failures.append(
                f"{path.relative_to(ROOT)}: could not audit: {exc}"
            )
            continue

        for line, module in violations:
            failures.append(
                f"{path.relative_to(ROOT)}:{line}: "
                f"forbidden TURING -> Chronus dependency: {module}"
            )

    if failures:
        print("\n".join(failures))
        return 1

    print(
        "PASS: TURING production Python has no direct "
        "Chronus mathematical imports."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())