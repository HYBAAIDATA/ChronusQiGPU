"""Private mining thesis: exact production planning, not a live-pool claim.

Real exact geometry, PYTHIA directive code and structured nonce iterator run.
The coordinator seam uses an explicitly labelled Stratum fixture; this is not
full runtime startup, native execution, authorization or pool qualification.
"""

from dataclasses import replace
import hashlib
import time
from types import SimpleNamespace

import pytest

from chronus.mla1517.mining.exact_search import (
    exact_face_order,
    exact_mining_directive,
    exact_reference_nonces,
    exact_vertex_itinerary,
    precompute_exact_search,
)
from chronus.mla1517.mining.geodesic_support import PythiaProductionMiningCoordinator
from chronus.mla1517.mining.pythia_agentic_cycle import PythiaAgenticMiningAuthority
from chronus.mla1517.mining.search_plan import PlanSource, SearchPlan

HEADER = bytes(range(80))


@pytest.fixture(scope="module")
def geometry():
    return precompute_exact_search()


def test_actual_geometry_and_quantum_walk_keep_all_positions(geometry):
    assert len(geometry.coarse_frames_11d) == 32
    assert len(geometry.frames_11d) == 600
    assert set(geometry.coarse_anchor) == set(range(32))
    assert sorted(geometry.hilbert_walk_rank) == list(range(600))
    assert sorted(exact_vertex_itinerary(HEADER, geometry)) == list(range(600))
    assert geometry.math_domain == "exact_q_phi_positive_radicals"


@pytest.mark.parametrize(
    "base,window",
    [(0, 1), (17, 31), (93, 599), (17, 600), (17, 601), (2**32 - 1201, 1201)],
)
def test_complete_exact_itinerary_never_prunes_or_repeats_lease(geometry, base, window):
    actual = exact_reference_nonces(HEADER, base, window)
    assert len(actual) == len(set(actual)) == window
    assert sorted(actual) == list(range(base, base + window))


@pytest.mark.parametrize(
    "base,window", [(-1, 1), (0, 0), (0, -1), (2**32 - 1, 2), (True, 1), (0, True)]
)
def test_exact_authority_rejects_invalid_uint32_lease(geometry, base, window):
    with pytest.raises(ValueError, match="bounded uint32"):
        exact_mining_directive(
            header=HEADER,
            target_be=bytes(32),
            base_step=base,
            window=window,
            state=geometry,
        )


def test_directive_binds_header_target_lease_and_actual_quantum_state(geometry):
    directive = exact_mining_directive(
        header=HEADER, target_be=b"\x01" * 32, base_step=17, window=601, state=geometry
    )
    evidence = directive.as_evidence()
    assert evidence["header_digest"] == hashlib.sha256(HEADER[:76]).hexdigest()
    assert evidence["target_hex"] == "01" * 32
    assert (evidence["base_step"], evidence["window"]) == (17, 601)
    assert evidence["geometry_digest"] == geometry.digest
    assert evidence["quantum_digest"] == geometry.hilbert_walk_digest
    assert evidence["physical_qpu_executed"] is False
    assert evidence["heuristics_used"] is False
    assert evidence["approximations_used"] is False
    assert "pool_accepted" not in evidence


def test_only_nonce_bytes_are_irrelevant_to_header_prefix_order(geometry):
    nonce_changed = HEADER[:76] + bytes(4)
    assert exact_face_order(HEADER, geometry) == exact_face_order(
        nonce_changed, geometry
    )
    changed = bytes([HEADER[0] ^ 1]) + HEADER[1:]
    a = exact_mining_directive(
        header=HEADER, target_be=bytes(32), base_step=0, window=1, state=geometry
    )
    b = exact_mining_directive(
        header=changed, target_be=bytes(32), base_step=0, window=1, state=geometry
    )
    assert a.header_digest != b.header_digest


def test_advisory_face_cannot_override_exact_production_profile(geometry):
    wrong = (exact_face_order(HEADER, geometry)[0] + 1) % 32
    with pytest.raises(ValueError, match="advisory face"):
        exact_vertex_itinerary(HEADER, geometry, preferred_face=wrong)


@pytest.mark.parametrize("source", list(PlanSource))
def test_actual_production_authority_seam_rewrites_both_plan_sources(geometry, source):
    # Boundary fixture only: no fake endpoint is connected and no submission runs.
    root = PythiaProductionMiningCoordinator.__new__(PythiaProductionMiningCoordinator)
    root.execution_hasher = SimpleNamespace(backend="cpu")
    root.pythia_search_precompute = geometry
    root.pythia_authority = PythiaAgenticMiningAuthority()
    adapter = SimpleNamespace(
        current_job=SimpleNamespace(job_id="fixture-job", target=7, ntime="00000000"),
        build_header=lambda *args: HEADER,
    )
    root.client = SimpleNamespace(proof_adapter=adapter)
    plan = SearchPlan(
        job_fingerprint="fixture-fp",
        pool_session_id="fixture-session",
        generation=1,
        base_step=17,
        window=601,
        extranonce2="00000000",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=32,
        executor_route="cpu_reference",
        policy_id="fixture-policy",
        source=source,
        evidence_refs={},
        created_at=time.monotonic(),
        plan_fallback_reason=(
            "fixture_queue_empty" if source is PlanSource.BASELINE_FALLBACK else None
        ),
    )
    bound = root._apply_pythia_authority(plan, SimpleNamespace(job_id="fixture-job"))
    assert bound.source is source
    assert bound.lane_order == exact_face_order(HEADER, geometry)
    assert bound.preferred_face == bound.lane_order[0]
    assert bound.schedule == ()
    assert (bound.base_step, bound.window, bound.extranonce2) == (17, 601, "00000000")
    assert bound.evidence_refs["pythia_planning_authority"] is True
    assert (
        bound.evidence_refs["pythia_authority"]["quantum_digest"]
        == geometry.hilbert_walk_digest
    )
    assert bound.evidence_refs["advisory_ordering_executed"] is False
    assert (
        root.pythia_authority.last_agentic_cycle is None
    )  # exact, not learned profile
    with pytest.raises(RuntimeError, match="current authoritative Stratum job"):
        root._apply_pythia_authority(replace(plan), SimpleNamespace(job_id="other-job"))
    root.pythia_authority.close()
