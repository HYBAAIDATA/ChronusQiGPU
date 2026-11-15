#!/usr/bin/env python3
"""Fail on unclassified additions to the historical quantum namespace.

The module inventory is classification, not quantum-performance certification.
Legacy QuantumStateEngine must remain an explicitly classical PredictiveEngine
alias until a separately reviewed implementation and migration exist.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = Path("scripts/ci/quantum_naming_policy.json")
VALID = frozenset({"historical_namespace", "algebraic_model", "finite_field_model"})


def scan(root: Path, policy: dict) -> list[str]:
    if policy.get("schema") != "chronus.quantum-naming/1":
        raise ValueError("unsupported quantum naming schema")
    relroot = policy["legacy_root"]
    modules = policy["legacy_modules"]
    if not isinstance(modules, dict) or not modules:
        raise ValueError("legacy module inventory is empty")
    actual = {p.name for p in (root / relroot).glob("*.py") if p.is_file()}
    recorded = set(modules)
    problems = [
        f"{relroot}/{name}: new legacy quantum-labelled module needs explicit classification"
        for name in sorted(actual - recorded)
    ] + [
        f"{relroot}/{name}: recorded module missing from source"
        for name in sorted(recorded - actual)
    ]
    problems += [
        f"{relroot}/{name}: invalid classification {kind}"
        for name, kind in modules.items() if kind not in VALID
    ]
    alias = policy["classical_alias"]
    source = (root / alias["path"]).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=alias["path"])
    correct = any(
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == alias["exported_name"] for t in node.targets)
        and isinstance(node.value, ast.Name)
        and node.value.id == alias["target_name"]
        for node in tree.body
    )
    if not correct:
        problems.append(f"{alias['path']}: legacy quantum-labelled alias changed; review actual implementation")
    boundaries = {
        f"{relroot}/README.md": ("finite-field", "not TURING", "not"),
        "docs/system-update/quantum-package-taxonomy.md": ("finite-field", "TURING", "hardware"),
    }
    for path, required in boundaries.items():
        content = (root / path).read_text(encoding="utf-8").casefold()
        for term in required:
            if term.casefold() not in content:
                problems.append(f"{path}: missing source taxonomy boundary {term!r}")
    return problems


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        print("usage: quantum_naming.py", file=sys.stderr)
        return 1
    try:
        problems = scan(root, json.loads((root / POLICY).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, SyntaxError) as exc:
        print(f"quantum naming check failed: {exc}", file=sys.stderr)
        return 1
    for problem in problems:
        print("FAIL", problem)
    print(f"{len(problems)} quantum-naming findings")
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
