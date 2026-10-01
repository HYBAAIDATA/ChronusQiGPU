"""Production contract for hyba_core_v1 on the live import path."""

from __future__ import annotations

import math

from chronus.mla1517.mining.hyba_bridge import (
    AVAILABLE,
    describe_share,
    face_of,
    measure_window,
    resonance_of,
)
from chronus.mla1517.mining.pow import check_pow, compact_target, sha256d
from python_backend.mathematical_foundation.hilbert_manifold_solver import (
    ManifoldPrecomputationEngine,
    build_m32_normals,
)
from python_backend.phi_grover_v4 import bits_to_target, build_header, phi_resonance
from python_backend.pythia_mining.intelligence_chooser import MiningIntelligenceChooser


def test_package_loads():
    assert AVAILABLE is True
    normals = build_m32_normals()
    assert len(normals) == 32
    assert all(abs(math.sqrt(sum(c * c for c in n)) - 1.0) < 1e-9 for n in normals)


def test_manifold_engine_bounds():
    engine = ManifoldPrecomputationEngine.get_instance()
    face = engine.assign_voronoi_face(2166572038)
    score = engine.compute_phi_resonance(2166572038)
    assert 0 <= face < 32
    assert 0.0 <= score <= 1.0
    assert engine.compute_phi_resonance(0) == 0.0


def test_chooser_fail_closed_without_job():
    choice = MiningIntelligenceChooser().choose(has_job=False, error_count=0)
    assert choice["lead"] == "salamander"
    assert choice["proof"] == "sha256d"
    assert choice["throttle"] is True


def test_chooser_live_job_keeps_sha256d_proof():
    choice = MiningIntelligenceChooser().choose(
        has_job=True,
        error_count=0,
        candidate_window=[1, 2, 3, 5, 8, 13, 21],
    )
    assert choice["proof"] == "sha256d"
    assert choice["job_kind"] == "sha256d_share"
    assert "structure_prior" in choice


def test_bridge_measure_does_not_claim_proof():
    measured = measure_window([1, 2, 3, 5, 8, 13, 21, 34])
    assert measured["gates_proof"] is False
    assert measured["proof"] == "sha256d"
    assert measured["available"] is True
    assert measured["window_size"] == 8
    assert face_of(1) is not None
    assert resonance_of(1) is not None


def test_describe_share():
    payload = describe_share({"job_id": "abc", "nonce": 1, "accepted": False})
    assert payload["proof"] == "sha256d"
    assert payload["hyba_available"] is True


def test_resonance_does_not_equal_pow():
    header = build_header(
        1,
        "00" * 32,
        "11" * 32,
        1,
        "1d00ffff",
        1,
    )
    target = bits_to_target("1d00ffff")
    digest = int.from_bytes(sha256d(header), "little")
    hit = digest <= target
    # Resonance is independent telemetry: both a hit and a miss still have a score.
    assert 0.0 <= phi_resonance(1) <= 1.0
    assert isinstance(hit, bool)
    assert check_pow(header, compact_target("1d00ffff")) == hit
