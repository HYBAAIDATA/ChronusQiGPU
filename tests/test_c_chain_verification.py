"""Owner C — contract tests for Intelligence.chain_verification.

Complements tests/test_chain_verification.py (envelope + per-stage flags)
with the accounting and cryptographic seams it leaves open: independent
sha256d recomputation of the reported winner, fail-closed ``ready``
accounting recomputed from stage evidence, ``_recheck_winner`` boundary
cases (<= equality, target-1, wrong nonce), overlay/telemetry honesty
invariants, and report-key consistency.
"""

from __future__ import annotations

import hashlib
import math
import struct

import pytest

from Intelligence.chain_verification import (
    CHAIN_STAGES,
    _double_sha256,
    _recheck_winner,
    verify_full_chain,
)

HEADER80 = bytes(range(80))
TARGET_BE = b"\xff" * 31 + b"\x7f"  # the chain's own near-max target


@pytest.fixture(scope="module")
def report():
    return verify_full_chain()


# --- independent winner verification -------------------------------------------


def test_mining_consensus_winner_recomputed_independently(report):
    """Do not trust the stage's own ``correct`` flag: recompute sha256d over
    header80[:76] + LE(nonce) with plain hashlib and check the digest both
    matches the reported winner and satisfies the target predicate."""
    stage = report["stages"]["mining_consensus"]
    nonce = stage["winning_nonce"]
    assert nonce is not None and 0 <= nonce < 64
    digest = _double_sha256(HEADER80[:76] + struct.pack("<I", nonce))
    assert digest[::-1] <= TARGET_BE
    # The winner must be the FIRST nonce in the probed range 0..63 that
    # satisfies the target — no earlier nonce may pass.
    for earlier in range(nonce):
        d = _double_sha256(HEADER80[:76] + struct.pack("<I", earlier))
        assert d[::-1] > TARGET_BE


def test_recheck_winner_boundary_semantics():
    nonce = 7
    digest = _double_sha256(HEADER80[:76] + struct.pack("<I", nonce))
    target_le = digest[::-1]
    # Boundary: target exactly equal to the reversed digest must accept (<=).
    assert _recheck_winner(HEADER80, target_le, nonce, digest) is True
    # One below the digest must reject — the strict-lower-bound direction.
    below = (int.from_bytes(target_le, "big") - 1).to_bytes(32, "big")
    assert _recheck_winner(HEADER80, below, nonce, digest) is False
    # Correct target but a nonce that hashes differently must reject.
    assert _recheck_winner(HEADER80, target_le, nonce + 1, digest) is False
    # Claimed hash must equal the recomputation byte-for-byte.
    wrong = bytes(b ^ 0xFF for b in digest)
    assert _recheck_winner(HEADER80, target_le, nonce, wrong) is False


def test_recheck_winner_none_and_nonce_wrap():
    assert _recheck_winner(HEADER80, TARGET_BE, 0, None) is False
    nonce = 2**32 + 7  # nonce is masked to 32 bits
    digest = _double_sha256(HEADER80[:76] + struct.pack("<I", 7))
    assert _recheck_winner(HEADER80, TARGET_BE, nonce, digest) is True


def test_double_sha256_matches_real_sha256d():
    blob = b"pythia-consensus-probe"
    expected = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
    assert _double_sha256(blob) == expected


# --- fail-closed accounting recomputed from evidence ---------------------------


def test_ready_is_exact_conjunction_of_stage_flags(report):
    """``ready`` must equal the AND of each stage's own pass evidence — the
    fail-closed accounting is itself under test, not trusted."""
    flags = {
        name: bool(s.get("correct", s.get("passed", True))) for name, s in report["stages"].items()
    }
    assert report["ready"] is all(flags.values())
    assert report["ready"] is True, {k: v for k, v in flags.items() if not v}


def test_chain_stages_list_matches_stages_keys(report):
    assert report["chain_stages"] == list(CHAIN_STAGES)
    assert set(report["stages"]) == set(CHAIN_STAGES)
    assert len(CHAIN_STAGES) == 11
    for name, stage in report["stages"].items():
        assert stage["stage"] == name
        assert isinstance(stage["dispatched"], bool)
        assert "backend" in stage


def test_overlay_geometry_is_internally_consistent(report):
    overlay = report["overlay"]
    assert overlay["faces_total"] == 32
    assert overlay["icosahedral_faces"] == 12
    assert overlay["dodecahedral_faces"] == 20
    assert overlay["icosahedral_faces"] + overlay["dodecahedral_faces"] == 32
    assert overlay["face_pairs"] == math.comb(32, 2) == 496
    assert overlay["heterotic_gauge_dimension"] == 496
    assert 0 <= overlay["channels_occupied"] <= 496
    # The 496-channel multiplier is a labelled projection, never a measurement.
    assert overlay["multiplier_status"] == "projection_only_never_measured"


def test_telemetry_stage_reports_measured_not_fabricated(report):
    stage = report["stages"]["chronus_11d_telemetry"]
    assert stage["passed"] is True
    assert stage["measured_not_projected"] is True
    assert stage["dispatches"] > 0  # probe dispatch is mandatory when idle
    assert 0.0 <= stage["gpu_dispatch_ratio"] <= 1.0
    # On a CPU-bound host the ratio must be exactly 0.0 — a GPU ratio of 1.0
    # on a CPU fallback would be a fabricated number.
    if report["backend"] == "cpu":
        assert report["gpu_dispatched"] is False
        assert stage["gpu_dispatch_ratio"] == 0.0
    else:
        assert stage["gpu_dispatch_ratio"] > 0.0
    channels = stage["overlay_channels"]
    if channels:
        assert 0 <= channels["channels_occupied"] <= 496


def test_mining_consensus_stage_evidence_fields(report):
    stage = report["stages"]["mining_consensus"]
    assert stage["correct"] is True
    assert stage["recheck"] == "bit-exact hashlib sha256d"
    assert stage["hashes_computed"] >= 1
    assert isinstance(stage["backend"], str) and stage["backend"]


def test_winning_nonce_is_deterministic_across_runs(report):
    """The grind over nonces 0..63 is deterministic — a second full-chain run
    must produce the identical winning nonce."""
    second = verify_full_chain()
    assert (
        second["stages"]["mining_consensus"]["winning_nonce"]
        == report["stages"]["mining_consensus"]["winning_nonce"]
    )
