"""Tests for the end-to-end chain verification (search → storage → TOE → consensus).

Gate 5 of the JV acceptance plan, wired against the LIVE main-tree modules:
backend binding, Zeckendorf storage encode/decode, 11D indexing, geodesic
search projection, ManifoldBridge candidate hold, the TOE 12-theorem arbiter,
the Yang-Mills mass gap, the hyperbolic Ricci/Einstein relation, and the
real sha256d mining consensus (bit-exact recheck).
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHIA_DIR = os.path.dirname(_THIS_DIR)

for p in (_PYTHIA_DIR, os.path.abspath(".")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from Intelligence.chain_verification import (
    CHAIN_STAGES,
    THEOREM_PROVEN,
    _double_sha256,
    _recheck_winner,
    verify_full_chain,
)

# ---------------------------------------------------------------------------
# Chain envelope
# ---------------------------------------------------------------------------


def test_chain_stages_declared():
    assert CHAIN_STAGES == (
        "backend_binding",
        "storage_encoding",
        "storage_reconstruction",
        "storage_indexing",
        "search_projection",
        "storage_hold",
        "toe_arbiter",
        "yang_mills_gap",
        "ricci_einstein",
        "mining_consensus",
        "chronus_11d_telemetry",
    )


def test_theorem_proven_stays_false():
    assert THEOREM_PROVEN is False


@pytest.fixture(scope="module")
def report():
    return verify_full_chain()


def test_chain_ready(report):
    assert report["ready"] is True, report["stages"]


def test_all_stages_present(report):
    assert list(report["stages"]) == list(CHAIN_STAGES)


def test_theorem_proven_false_in_report(report):
    assert report["theorem_proven"] is False


def test_consensus_rule_recorded(report):
    assert "sha256" in report["consensus_rule"] and "target_be" in report["consensus_rule"]


# ---------------------------------------------------------------------------
# Storage stages
# ---------------------------------------------------------------------------


def test_storage_reconstruction_lossless(report):
    assert report["stages"]["storage_reconstruction"]["correct"] is True


def test_storage_encoding_real_work(report):
    stage = report["stages"]["storage_encoding"]
    assert stage["work_items"] > 0


def test_storage_hold_o1_lookup(report):
    stage = report["stages"]["storage_hold"]
    assert stage["correct"] is True
    assert stage["lookup_ms"] < 1.0
    assert stage["md_memory_entries"] == 1
    assert stage["chronus_vram_cached"] == 1


def test_search_projection_batch(report):
    stage = report["stages"]["search_projection"]
    assert stage["work_items"] == 8
    assert stage["correct"] is True


# ---------------------------------------------------------------------------
# TOE arbiter / Yang-Mills / Ricci
# ---------------------------------------------------------------------------


def test_toe_12_theorems_all_pass(report):
    stage = report["stages"]["toe_arbiter"]
    assert stage["passed"] is True
    assert len(stage["theorems"]) == 12
    assert all(stage["theorems"].values())


def test_yang_mills_mass_gap_positive(report):
    stage = report["stages"]["yang_mills_gap"]
    phi = (1.0 + 5**0.5) / 2.0
    assert stage["passed"] is True
    assert stage["mass_gap"] > 0.0
    # Computed eigenvalue of the finite 2I Laplacian, not the old √5 predicate.
    assert abs(stage["mass_gap"] - (1.0 - phi / 2.0)) < 1e-6
    assert stage["continuum_claim"] is False


def test_ricci_einstein_relation_exact(report):
    stage = report["stages"]["ricci_einstein"]
    assert stage["passed"] is True
    assert stage["fold_roundtrip_lossless"] is True
    assert stage["in_poincare_ball"] is True
    assert stage["sectional_curvature"] == -1.0
    assert stage["ric_over_g"] == -10


def test_exact_stages_never_claim_gpu_dispatch(report):
    for name in ("toe_arbiter", "yang_mills_gap", "ricci_einstein"):
        assert report["stages"][name]["backend"] == "cpu-exact"
        assert report["stages"][name]["dispatched"] is False


# ---------------------------------------------------------------------------
# Mining consensus — the only accept authority
# ---------------------------------------------------------------------------


def test_mining_consensus_winner_bit_exact(report):
    stage = report["stages"]["mining_consensus"]
    assert stage["correct"] is True
    assert stage["winning_nonce"] is not None
    assert stage["hashes_computed"] >= 1


def test_recheck_rejects_wrong_nonce():
    header80 = bytes(range(80))
    target_be = b"\xff" * 31 + b"\x7f"
    nonce = 7
    blob = header80[:76] + nonce.to_bytes(4, "little")
    digest = _double_sha256(blob)
    # digest is near-max, so reversed digest < target holds; the recheck must
    # still fail when the *claimed* hash does not match the recomputation.
    wrong = bytes(32)
    assert _recheck_winner(header80, target_be, nonce, wrong) is False
    assert _recheck_winner(header80, target_be, nonce, digest) is True


def test_recheck_rejects_none_claim():
    header80 = bytes(range(80))
    target_be = b"\xff" * 31 + b"\x7f"
    assert _recheck_winner(header80, target_be, 0, None) is False


# ---------------------------------------------------------------------------
# Fail-explicit behaviour
# ---------------------------------------------------------------------------


def test_every_stage_has_backend_and_dispatch_flag(report):
    for stage in report["stages"].values():
        assert "backend" in stage
        assert isinstance(stage["dispatched"], bool)


def test_report_elapsed_recorded(report):
    assert report["elapsed_seconds"] >= 0.0
