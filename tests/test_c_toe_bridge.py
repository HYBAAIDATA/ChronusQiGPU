"""Owner C — deterministic-seam contract tests for toe.bridge.TOEBridge.

tests/test_toe_elevation.py and test_toe_independent_verification.py cover
the causal-ladder functions and the reason() envelope; this file targets the
bridge-level seams they leave open: the unitary propagator math (not just
cache identity), state encoding normalization, Hermitian Hamiltonian, the
matrix payload codec, np_var/np_std, canonical JSON, the bridge wrappers'
``available``/receipt envelopes, receipt-ledger tamper classes, and
``evaluator_agreement``/``algebraic_signature`` behavior through the bridge.
"""

from __future__ import annotations

import json
import random

import pytest

from toe.bridge import (
    CAPABILITY_EVIDENCE,
    TOEBridge,
    _canonical_json_bytes,
    _FORECAST_TIMES,
    _matrix_from_payload,
    _matrix_to_payload,
    np_std,
    np_var,
)

# Tiny linear SCM: Z -> X (1.0), X -> Y (2.0), Z -> Y (3.0).
FORK_EDGES = [("Z", "X", 1.0), ("X", "Y", 2.0), ("Z", "Y", 3.0)]


# --- honesty surfaces -------------------------------------------------------------


def test_status_and_execution_evidence_are_honest():
    bridge = TOEBridge()
    status = bridge.status()
    assert status["available"] is True
    assert status["no_external_ml"] is True
    assert status["hilbert_dim"] == 32
    assert bridge.available() is True
    evidence = bridge.execution_evidence()
    # Exact-arithmetic core reports cpu-exact — never a fabricated GPU claim.
    assert evidence["backend"] == "cpu-exact"
    assert evidence["by_design"] is True
    # Capability labels stay honest: causal discovery is NOT ESTABLISHED.
    assert "NOT ESTABLISHED" in CAPABILITY_EVIDENCE["causal_discovery"]
    assert "not causal" in CAPABILITY_EVIDENCE["explain_causality_ranking"]


# --- quantum substrate seams -------------------------------------------------------


def test_encode_state_normalized_and_deterministic():
    bridge = TOEBridge()
    s1 = bridge._encode_state({"a": [1, 2, 3], "b": 0.5})
    s2 = bridge._encode_state({"a": [1, 2, 3], "b": 0.5})
    assert s1.dim == 32
    assert s1.norm() == pytest.approx(1.0)
    assert s1.as_dict() == s2.as_dict()  # identical data -> identical state


def test_hamiltonian_hermitian_and_cached():
    bridge = TOEBridge()
    H = bridge._hamiltonian()
    ok, _residual = H.is_hermitian()
    assert ok is True
    assert bridge._hamiltonian() is H  # scale-fold store serves the same object


def test_propagator_is_unitary_on_table_and_lazy_paths():
    bridge = TOEBridge()
    for t in _FORECAST_TIMES:
        ok, _residual = bridge._propagator(t).is_unitary()
        assert ok is True, f"U({t}) not unitary"
        assert bridge._propagator(t) is bridge._propagator(t)  # cached identity
    # Off-grid time falls to the lazy scale-fold path and stays unitary
    # (small dim keeps the matrix exponential cheap).
    small = TOEBridge(config={"hilbert_dim": 4})
    ok, _residual = small._propagator(1.234).is_unitary()
    assert ok is True


def test_propagator_integrity_check_passes_on_small_dim():
    small = TOEBridge(config={"hilbert_dim": 4})
    small._verify_propagator_integrity()  # raises on store corruption


def test_matrix_payload_codec_roundtrips():
    bridge = TOEBridge()
    H = bridge._hamiltonian()
    rebuilt = _matrix_from_payload(_matrix_to_payload(H))
    assert rebuilt.rows == H.rows and rebuilt.cols == H.cols
    for r in range(H.rows):
        for c in range(H.cols):
            assert rebuilt.data[r][c].equals(H.data[r][c], tol=0.0)


def test_np_var_and_np_std_exact():
    values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    assert np_var(values) == pytest.approx(4.0)  # population variance
    assert np_std(values) == pytest.approx(2.0)
    assert np_var([]) == 0.0 and np_var([3.0]) == 0.0
    assert np_std([3.0]) == 0.0


def test_canonical_json_bytes_sorted_and_compact():
    blob = _canonical_json_bytes({"b": 1, "a": [3, 2]})
    assert blob == b'{"a":[3,2],"b":1}'
    assert _canonical_json_bytes({"x": {}}) == _canonical_json_bytes({"x": {}})


# --- causal-ladder wrappers ----------------------------------------------------------


def test_identify_adjustment_finds_backdoor_set():
    bridge = TOEBridge()
    out = bridge.identify_adjustment(FORK_EDGES, "X", "Y")
    assert out["available"] is True
    assert out["adjustment_set"] == ["Z"]  # the fork confounder
    assert out["is_dag"] is True
    # Unconfounded chain needs no adjustment.
    chain = bridge.identify_adjustment([("X", "Y", 1.0)], "X", "Y")
    assert chain["available"] is True and chain["adjustment_set"] == []
    # Unobserved confounder fails closed.
    unobs = bridge.identify_adjustment(FORK_EDGES, "X", "Y", observed=["X", "Y"])
    assert unobs["available"] is False
    assert unobs["adjustment_set"] is None


def test_intervene_cuts_incoming_edges_and_propagates():
    bridge = TOEBridge()
    out = bridge.intervene(FORK_EDGES, {"X": 2.0})
    assert out["available"] is True
    # do(X=2): Y = 2*X + 3*Z with Z at its mean 0 -> 4.0; X pinned at 2.0.
    assert out["values"]["X"] == 2.0
    assert out["values"]["Z"] == 0.0
    assert out["values"]["Y"] == pytest.approx(4.0)
    surgery = out["surgery"]
    assert surgery["edges_cut"] == [["Z", "X"]]
    assert surgery["incoming_edges_after"]["X"] == []
    assert surgery["factual_graph_sha256"] != surgery["mutilated_graph_sha256"]


def test_counterfactual_abduction_is_exact():
    bridge = TOEBridge()
    # Factual: X=1, Z=1, Y=5 -> abduced exogenous noise for Y is 5-2-3 = 0.
    out = bridge.counterfactual(FORK_EDGES, {"X": 1.0, "Z": 1.0, "Y": 5.0}, {"X": 2.0}, ["Y"])
    assert out["available"] is True
    assert out["abduced_exogenous"]["Y"] == pytest.approx(0.0)
    # do(X=2) on the mutilated model: Y = 2*2 + 3*1 + 0 = 7.
    assert out["outcome_values"]["Y"] == pytest.approx(7.0)
    assert out["factual_model_unchanged"] is True
    assert out["receipt_sha256"]
    assert bridge.verify_receipts()["ok"] is True


def test_estimate_effect_adjusts_away_confounder_bias():
    rng = random.Random(0)
    n = 400
    z = [rng.gauss(0.0, 1.0) for _ in range(n)]
    x = [2.0 * zi + rng.gauss(0.0, 0.01) for zi in z]
    y = [3.0 * xi + 1.0 * zi + rng.gauss(0.0, 0.01) for xi, zi in zip(x, z)]
    out = TOEBridge().estimate_effect(
        {"Z": z, "X": x, "Y": y}, FORK_EDGES, "X", "Y", do_values=(0.0, 1.0)
    )
    assert out["available"] is True
    assert out["adjustment_set"] == ["Z"]
    # True structural coefficient on X->Y is 3.0; the naive regression is
    # biased upward toward 3.5 by the confounded Z->X->Y path.
    assert out["adjusted_effect"] == pytest.approx(3.0, abs=0.2)
    assert out["adjusted_effect"] < out["naive_effect"]
    means = out["interventional_means"]
    assert means["1.0"] - means["0.0"] == pytest.approx(3.0, abs=0.2)
    assert out["receipt_sha256"]


# --- receipt ledger -------------------------------------------------------------------


def _issued_bridge() -> TOEBridge:
    bridge = TOEBridge()
    # counterfactual is a receipt-issuing wrapper; intervene() is not, so two
    # distinct counterfactual calls give the ledger two linked records.
    bridge.counterfactual(FORK_EDGES, {"X": 1.0, "Z": 1.0, "Y": 5.0}, {"X": 2.0}, ["Y"])
    bridge.counterfactual(FORK_EDGES, {"X": 2.0, "Z": 1.0, "Y": 7.0}, {"X": 3.0}, ["Y"])
    assert len(bridge.receipts.records) == 2
    return bridge


def test_verify_receipts_detects_output_mutation():
    bridge = _issued_bridge()
    assert bridge.verify_receipts()["ok"] is True
    bridge.receipts.records[0].output["tampered"] = True
    result = bridge.verify_receipts()
    assert result["ok"] is False
    assert any("output altered" in f["problem"] for f in result["failures"])


def test_verify_receipts_detects_reorder_and_removal():
    # receipts.records returns a copy; tampering goes through _records.
    bridge = _issued_bridge()
    bridge.receipts._records.reverse()
    result = bridge.verify_receipts()
    assert result["ok"] is False
    assert result["failures"]

    bridge2 = _issued_bridge()
    del bridge2.receipts._records[0]  # survivor's sequence no longer matches
    assert bridge2.verify_receipts()["ok"] is False


def test_replay_recomputes_against_recorded_output():
    bridge = _issued_bridge()
    receipt = bridge.receipts.records[0]
    # The recorded output is the dict as issued (receipt_sha256 excluded).
    recorded = dict(receipt.output)
    assert bridge.replay(receipt, lambda: recorded)["ok"] is True
    assert bridge.replay(receipt, lambda: {**recorded, "outcome_values": {"Y": 9.0}})["ok"] is False


# --- evaluator agreement + family signature -------------------------------------------


def test_evaluator_agreement_needs_two_distinct():
    bridge = TOEBridge()
    assert bridge.evaluator_agreement({"a": 1.0})["agreement"] is None
    # Identical predictions from distinct evaluators agree perfectly.
    same = bridge.evaluator_agreement({"a": 1.0, "b": 1.0})
    assert same["n_distinct"] == 2 and same["agreement"] == pytest.approx(1.0)
    # Evaluators sharing a configuration id count once, not twice.
    dup = bridge.evaluator_agreement(
        {"a": 1.0, "b": 1.0, "c": 2.0}, evaluator_ids={"a": "cfg", "b": "cfg", "c": "other"}
    )
    assert dup["n_distinct"] == 2
    assert dup["duplicates_merged"]
    mixed = bridge.evaluator_agreement({"a": 1.0, "b": 2.0})
    assert mixed["available"] is True
    assert 0.0 <= mixed["agreement"] <= 1.0
    assert mixed["n_distinct"] == 2


def test_algebraic_signature_detects_golden_family():
    bridge = TOEBridge()
    sig = bridge.algebraic_signature([1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144])
    assert sig["available"] is True
    assert sig["family"] == "golden"
    # The golden lag template fits the Fibonacci series with zero residual.
    assert float(sig["residuals"]["golden"]) == 0.0
    assert "golden" in sig["families"]


def test_state_tomography_reports_unit_norm():
    tomo = TOEBridge().state_tomography({"a": [1.0, 2.0, 3.0], "b": 0.5})
    d = tomo.as_dict()
    assert d["available"] is True
    assert d["diagnostics"]["norm"] == pytest.approx(1.0)


def test_json_serializable_report_keys():
    # status() feeds an operator panel — it must be JSON-serializable.
    json.dumps(TOEBridge().status())
