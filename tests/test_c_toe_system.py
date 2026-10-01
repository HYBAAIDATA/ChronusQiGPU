"""Owner C — contract tests for toe.system.TOESystem.

Covers the provenance-ledger seams left open by test_elevation_correctness:
hash-chain link structure, parameter deep-copy honesty, mutation/reorder
detection, ``TOEProvenanceRecord`` field honesty, the 12-theorem matrix
recomputed per-theorem, and the deterministic coordination-pattern bounds.
"""

from __future__ import annotations

import pytest

from toe.manifold_bridge import ManifoldBridge
from toe.system import TOEProvenanceRecord, TOESystem


def _params():
    return {"w": 0.5, "tags": ["a", "b"], "nested": {"k": [1, 2]}}


# --- provenance ledger ---------------------------------------------------------


def test_record_decision_builds_hash_chain():
    toe = TOESystem()
    r0 = toe.record_decision("p0", "geometric", "compute", _params(), 1, True)
    r1 = toe.record_decision("p1", "causal", "route", _params(), 2, False)
    r2 = toe.record_decision("p2", "quantum", "verify", _params(), 3, True)

    assert len(toe.provenance_ledger) == 3
    assert r0.prev_hash == ""
    assert r1.prev_hash == r0.provenance_hash
    assert r2.prev_hash == r1.provenance_hash
    for rec in toe.provenance_ledger:
        assert rec.provenance_hash == rec.compute_hash()
    assert toe.verify_provenance() is True


def test_verify_provenance_detects_parameter_mutation():
    toe = TOESystem()
    toe.record_decision("p0", "geometric", "compute", _params(), 1, True)
    record = toe.provenance_ledger[0]
    record.parameters["w"] = 999.0  # tamper after issue
    assert toe.verify_provenance() is False


def test_verify_provenance_detects_reorder_and_truncation():
    toe = TOESystem()
    for i in range(4):
        toe.record_decision(f"p{i}", "causal", "route", {"i": i}, 1, True)
    assert toe.verify_provenance() is True

    toe.provenance_ledger[1], toe.provenance_ledger[2] = (
        toe.provenance_ledger[2],
        toe.provenance_ledger[1],
    )
    assert toe.verify_provenance() is False

    toe2 = TOESystem()
    for i in range(4):
        toe2.record_decision(f"p{i}", "causal", "route", {"i": i}, 1, True)
    toe2.provenance_ledger.pop()  # deletion breaks no hash but is still a change
    assert toe2.verify_provenance() is True  # truncated chain is internally valid
    # ...but re-inserting a foreign record breaks the link.
    foreign = TOEProvenanceRecord("x", "y", "z", {}, 0, True, prev_hash="bogus")
    toe2.provenance_ledger.append(foreign)
    assert toe2.verify_provenance() is False


def test_verify_provenance_detects_overwritten_hash():
    toe = TOESystem()
    toe.record_decision("p0", "geometric", "compute", _params(), 1, True)
    toe.provenance_ledger[0].provenance_hash = "0" * 64
    assert toe.verify_provenance() is False


def test_record_decision_deep_copies_parameters():
    """The recorded snapshot must be immune to caller-side mutation."""
    toe = TOESystem()
    params = _params()
    record = toe.record_decision("p0", "plastic", "mutate", params, 4, True)
    params["w"] = -1.0
    params["nested"]["k"].append(999)
    assert record.parameters == _params()
    assert toe.verify_provenance() is True


def test_provenance_record_field_honesty():
    rec = TOEProvenanceRecord(
        phase_name="phase",
        initiating_intelligence="intel",
        action_type="act",
        parameters={"a": 1},
        contract_number=7,
        verified=False,
        timestamp=1234.5,
        prev_hash="prev",
    )
    d = rec.to_dict()
    assert d["phase_name"] == "phase"
    assert d["initiating_intelligence"] == "intel"
    assert d["action_type"] == "act"
    assert d["parameters"] == {"a": 1}
    assert d["contract_number"] == 7
    assert d["verified"] is False
    assert d["timestamp"] == 1234.5
    assert d["provenance_hash"] == rec.compute_hash()
    assert rec.to_scalar() == 0
    assert TOEProvenanceRecord("p", "i", "a", {}, 1, True).to_scalar() == 1


def test_provenance_hash_is_deterministic_for_identical_fields():
    a = TOEProvenanceRecord("p", "i", "a", {"x": 1}, 2, True, timestamp=9.0, prev_hash="h")
    b = TOEProvenanceRecord("p", "i", "a", {"x": 1}, 2, True, timestamp=9.0, prev_hash="h")
    assert a.provenance_hash == b.provenance_hash
    # Any single field difference must change the hash.
    c = TOEProvenanceRecord("p", "i", "a", {"x": 2}, 2, True, timestamp=9.0, prev_hash="h")
    assert c.provenance_hash != a.provenance_hash


def test_empty_ledger_verifies():
    assert TOESystem().verify_provenance() is True


# --- 12-theorem candidate matrix -------------------------------------------------


def test_verify_12_theorems_candidate_recomputable():
    bridge = ManifoldBridge()
    candidate = bridge.store_candidate(nonce=2805728801, header_template=bytes(range(80)))
    toe = TOESystem(bridge=bridge)
    all_ok, results = toe.verify_12_theorems_candidate(candidate, n_anchor=7)

    assert len(results) == 12
    assert all(isinstance(v, bool) for v in results.values())
    assert all_ok is all(results.values())
    # Recompute the candidate-derived theorems independently.
    mask = candidate.zeckendorf_mask
    assert results["T5_zeckendorf_spacing"] == ((mask & (mask << 1)) == 0)
    assert results["T8_structure_existence"] == (candidate.nonce > 0 or mask == 0)
    assert results["T11_born_rule_threshold"] == (candidate.born_probability >= 0.5)
    from toe.hardened_unified_substrate import MODULUS_Q

    assert results["T12_galois_bound"] == (candidate.galois_composite < MODULUS_Q)
    # This candidate passed end-to-end inside verify_full_chain — all 12 here.
    assert all_ok is True


# --- deterministic coordination bookkeeping ------------------------------------


def test_learn_coordination_pattern_direction_and_bounds():
    toe = TOESystem()
    toe.learn_coordination_pattern("new_pattern", 2.0)
    assert toe.active_coordination_patterns["new_pattern"] == pytest.approx(0.55)
    toe.learn_coordination_pattern("new_pattern", 0.5)
    assert toe.active_coordination_patterns["new_pattern"] == pytest.approx(0.50)

    # Cap and floor are enforced.
    for _ in range(100):
        toe.learn_coordination_pattern("new_pattern", 5.0)
    assert toe.active_coordination_patterns["new_pattern"] == 2.0
    for _ in range(100):
        toe.learn_coordination_pattern("new_pattern", 0.0)
    assert toe.active_coordination_patterns["new_pattern"] == 0.1


def test_escalate_anomaly_records_typed_entry():
    toe = TOESystem()
    toe.escalate_anomaly("divergence", {"detail": "test"})
    assert len(toe.escalations_logged) == 1
    entry = toe.escalations_logged[0]
    assert entry["anomaly_type"] == "divergence"
    assert entry["details"] == {"detail": "test"}
    assert entry["timestamp"] > 0
