from __future__ import annotations

from scripts.federation import FederationManifest, handshake
from scripts.lucas_scale_matrix import LucasScaleMatrixEngine


def test_exact_match_accepts():
    engine = LucasScaleMatrixEngine()
    fp = engine.compute_fingerprint()
    manifest = FederationManifest(("A",), 1, {"A": fp})
    decision = handshake(engine, {"B": fp}, manifest)
    assert decision.accepted
    assert decision.status == "ACCEPTED_EXACT_MATCH"


def test_authority_quorum_accepts_canonical_fingerprint():
    engine = LucasScaleMatrixEngine()
    fp = engine.compute_fingerprint()
    manifest = FederationManifest(("A", "B", "C"), 2, {"A": fp, "B": fp, "C": "0" * 64})
    decision = handshake(engine, {"B": "0" * 64}, manifest)
    assert decision.accepted
    assert decision.status == "ACCEPTED_AUTHORITY_QUORUM"


def test_mismatch_fails_closed_without_coercion():
    engine = LucasScaleMatrixEngine()
    manifest = FederationManifest(("A",), 1, {"A": "f" * 64})
    decision = handshake(engine, {"B": "f" * 64}, manifest)
    assert not decision.accepted
    assert decision.status == "INCOMPATIBLE_MATRIX_FEDERATION"
