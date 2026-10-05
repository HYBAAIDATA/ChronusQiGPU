"""Fail-closed release gates for the canonical Turing VQC.

A production release may not hide a mathematical failure behind pytest xfail,
may not resolve the canonical stabilizer from a committed test-fixture copy,
and must prove the canonical measurement invariant on the production package.
Hardware/QPU unavailability is a separate evidence state and is not converted
into a software pass here.
"""

from __future__ import annotations

import ast
from pathlib import Path

from turing_universal_quantum_computer.stabilizer import StabilizerState


DIST_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Attribute):
        prefix = _decorator_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def test_no_turing_mathematics_is_hidden_behind_xfail() -> None:
    offenders: list[str] = []
    for path in sorted(TEST_ROOT.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                name = _decorator_name(decorator)
                if name.endswith("xfail"):
                    offenders.append(f"{path.name}:{node.lineno}:{node.name}")
    assert not offenders, "Turing production tests contain xfail gates: " + ", ".join(offenders)


def test_no_duplicate_test_fixture_stabilizer_shadows_the_package() -> None:
    assert not (DIST_ROOT / "stabilizer.py").exists(), (
        "distribution root contains a duplicate stabilizer.py; the canonical "
        "implementation must live only inside the package"
    )


def test_canonical_stabilizer_measurement_preserves_symplectic_invariants() -> None:
    state = StabilizerState(6)
    state.h(0).h(2).h(4)
    state.cnot(0, 1).cnot(2, 3).cnot(4, 5)
    state.s(1).sdg(3).x(5)
    state.validate_invariants()

    for qubit, outcome in ((0, 1), (2, 0), (4, 1)):
        record = state.measure(qubit, outcome=outcome)
        assert record["outcome"] == outcome
        state.validate_invariants()
