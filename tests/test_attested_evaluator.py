"""Attested evidence evaluation must fail closed without conflating assessment and admission."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from chronus.core import qualification
from scripts.ci import evaluate_attested


def _evidence(path, *, status="PASS", skipped=0):
    path.write_text(
        json.dumps(
            {
                "schema": "chronus-ci-test-evidence-v1",
                "commit": "candidate-sha",
                "run_id": "4242",
                "status": status,
                "tests": {
                    "total": 4,
                    "passed": 4 - skipped,
                    "failed": 0,
                    "skipped": skipped,
                },
            }
        ),
        encoding="utf-8",
    )


def _gate_doc():
    return {
        "schema": "chronus-product-gates-v1",
        "commit": "candidate-sha",
        "run_id": "4242",
        "deployment_profile": "software-base",
        "status": "PASS",
        "facts": {
            "profile": {"name": "software-base", "verified": True},
            "post_quantum_signer": {
                "algorithm": "ML-DSA-65",
                "verified": True,
            },
            "custody": {
                "authority": "THESEUS",
                "mechanism": "sqlite-wal",
                "profile": "software-base",
                "verified": True,
            },
        },
        "gates": {gate: "PASS" for gate in qualification.MANDATORY},
    }


def _argv(evidence, output, *extra):
    return [
        "evaluate_attested.py",
        "--evidence",
        str(evidence),
        "--expected-commit",
        "candidate-sha",
        "--expected-run-id",
        "4242",
        "--repository",
        "HYBAAIDATA/ChronusQiGPU",
        "--output",
        str(output),
        *extra,
    ]


def test_verified_evidence_can_be_successfully_evaluated_while_unqualified(
    tmp_path, monkeypatch
):
    evidence = tmp_path / "evidence.json"
    output = tmp_path / "verdict.json"
    _evidence(evidence)
    monkeypatch.setattr(
        evaluate_attested.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(sys, "argv", _argv(evidence, output))

    assert evaluate_attested.main() == 0
    verdict = json.loads(output.read_text(encoding="utf-8"))
    assert verdict["status"] == "UNQUALIFIED"
    assert verdict["attestation_verified"] is True
    assert verdict["test_evidence_attestation_verified"] is True
    assert verdict["gate_attestation_verified"] is False
    assert verdict["production_evidence_verified"] is False
    assert verdict["deployment_profile"] is None
    assert set(verdict["gates"].values()) == {"UNQUALIFIED"}


def test_invalid_test_evidence_attestation_fails_evaluator(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence.json"
    output = tmp_path / "verdict.json"
    _evidence(evidence)
    monkeypatch.setattr(
        evaluate_attested.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )
    monkeypatch.setattr(sys, "argv", _argv(evidence, output))

    assert evaluate_attested.main() == 1
    verdict = json.loads(output.read_text(encoding="utf-8"))
    assert verdict["status"] == "UNQUALIFIED"


def test_supplied_product_gates_must_have_valid_attestation(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence.json"
    gates = tmp_path / "gates.json"
    output = tmp_path / "verdict.json"
    _evidence(evidence)
    gates.write_text(json.dumps(_gate_doc()), encoding="utf-8")

    calls = {"count": 0}

    def verification(*args, **kwargs):
        calls["count"] += 1
        # Test-evidence attestation succeeds, product-gate attestation fails.
        return SimpleNamespace(returncode=0 if calls["count"] == 1 else 1)

    monkeypatch.setattr(evaluate_attested.subprocess, "run", verification)
    monkeypatch.setattr(
        sys,
        "argv",
        _argv(evidence, output, "--product-gates", str(gates)),
    )

    assert evaluate_attested.main() == 1
    verdict = json.loads(output.read_text(encoding="utf-8"))
    assert verdict["status"] == "UNQUALIFIED"
    assert verdict["gate_attestation_verified"] is False
    assert verdict["production_evidence_verified"] is False


def test_all_attested_product_gates_can_admit_when_required_capability_is_available(
    tmp_path, monkeypatch
):
    evidence = tmp_path / "evidence.json"
    gates = tmp_path / "gates.json"
    output = tmp_path / "verdict.json"
    _evidence(evidence)
    gates.write_text(json.dumps(_gate_doc()), encoding="utf-8")

    monkeypatch.setattr(
        evaluate_attested.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        qualification.signers,
        "ml_dsa_available",
        lambda: True,
    )
    monkeypatch.setattr(
        evaluate_attested,
        "qualify",
        qualification.qualify,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _argv(evidence, output, "--product-gates", str(gates)),
    )

    assert evaluate_attested.main() == 0
    verdict = json.loads(output.read_text(encoding="utf-8"))
    assert verdict["status"] == "PASS"
    assert verdict["attestation_verified"] is True
    assert verdict["test_evidence_attestation_verified"] is True
    assert verdict["gate_attestation_verified"] is True
    assert verdict["production_evidence_verified"] is True
    assert verdict["deployment_profile"] == "software-base"
    assert verdict["product_gate_status"] == "PASS"
    assert verdict["product_facts"]["custody"]["authority"] == "THESEUS"
    assert set(verdict["gates"].values()) == {"PASS"}
