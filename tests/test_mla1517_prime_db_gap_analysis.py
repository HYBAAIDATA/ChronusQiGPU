from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_transfer_gap_ledger_preserves_authority_and_scope():
    ledger = json.loads((ROOT / "manifests/mla1517_prime_db_gap_analysis.json").read_text())
    assert ledger["ownership"]["OVID"].startswith("authoritative durable")
    assert ledger["ownership"]["THESEUS"].startswith("rebuildable")
    assert "local execution" in ledger["ownership"]["PRIME-DB"]
    assert ledger["repository_scope"].startswith("PYTHIA mining")
    assert ledger["production_ready"] is False
    assert all(gate["status"] != "PASS" for gate in ledger["open_evidence_gates"])


def test_refuted_claims_remain_non_promotable():
    ledger = json.loads((ROOT / "manifests/mla1517_prime_db_gap_analysis.json").read_text())
    prohibited = set(ledger["refuted_or_prohibited_claims"])
    assert {
        "zeckendorf_reduces_generic_address_bits",
        "float64_binet_alone_is_lossless_storage",
        "lucas_pisot_phase_is_a_quantum_speedup",
        "global_phase_changes_measurement_probabilities",
    } <= prohibited
    reference = (ROOT / "chronus/mla1517_platform/python/reference_test.py").read_text()
    assert '"status": "REFUTED"' in reference
    assert '"not_promoted"' in reference


def test_contracts_do_not_promote_prime_db_over_ovid():
    contracts = (ROOT / "CONTRACTS.md").read_text()
    delivery = (ROOT / "al_haras/delivery_plan.py").read_text()
    assert "PRIME-DB AUTHORITATIVE OBJECT" not in contracts
    assert "OVID AUTHORITATIVE RECORD / PRIME-DB EXECUTION VIEW" in contracts
    assert "OVID remains the durable authority" in contracts
    assert "PRIME-DB authoritative transaction core" not in delivery
    assert "OVID authoritative transaction core" in delivery


def test_physical_and_live_pool_gates_remain_open():
    manifest = json.loads((ROOT / "chronus/mla1517_platform/build_manifest.json").read_text())
    assert manifest["production_ready"] is False
    assert manifest["strict_hardware_gate"].startswith("FAIL_CLOSED")
    assert "OpenCL device execution" in manifest["what_was_not_measured"]
    assert "live pool acceptance" in manifest["what_was_not_measured"]
