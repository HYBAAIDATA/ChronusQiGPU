"""Real exact-lane conformance and explicitly labelled fault-injection checks."""
from fractions import Fraction

import pytest

from scripts import exact_conformance


def test_real_exact_implementations_agree_in_all_declared_joint_bases():
    report = exact_conformance.evaluate_conformance()
    assert report["passed"]
    assert report["vectors"] == 8
    assert report["checks"] == 138
    assert report["mismatches"] == []
    assert len(set(report["implementations"].values())) == 2


def test_conformance_detects_phase_operator_fault(monkeypatch):
    # Negative test only: this mutated operator is never used to issue PASS evidence.
    from turing_universal_quantum_computer.hilbert import QuantumRegister

    monkeypatch.setattr(QuantumRegister, "apply_s", lambda self, q: None)
    report = exact_conformance.evaluate_conformance()
    assert not report["passed"]
    assert report["mismatches"]


def test_conformance_refuses_non_normalized_tableau_probabilities(monkeypatch):
    from turing_universal_quantum_computer.stabilizer import StabilizerState

    monkeypatch.setattr(
        StabilizerState, "measurement_probabilities", lambda self, q: (Fraction(1), Fraction(1))
    )
    with pytest.raises(ArithmeticError, match="normalized"):
        exact_conformance.evaluate_conformance()


def test_empty_vector_inventory_cannot_issue_pass(monkeypatch):
    monkeypatch.setattr(exact_conformance, "VECTORS", ())
    report = exact_conformance.evaluate_conformance()
    assert not report["passed"]
    assert report["checks"] == 0


def test_gate_adapter_writes_actual_execution_artifact(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    # Match the CLI's script-directory import path; do not replace an operator.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from scripts.gate_impl import conformance

    outcome = conformance(tmp_path)
    assert outcome.status.value == "PASS"
    artifact = tmp_path / "results/conformance-execution.json"
    assert outcome.artifacts == (str(artifact),)
    report = json.loads(artifact.read_text())
    assert report["passed"] and report["checks"] == 138


def test_partial_vector_inventory_cannot_issue_pass(monkeypatch):
    monkeypatch.setattr(exact_conformance, "VECTORS", exact_conformance.VECTORS[:1])
    assert not exact_conformance.evaluate_conformance()["passed"]
