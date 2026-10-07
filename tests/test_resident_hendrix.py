"""Real arithmetic/hash integration tests, with no emulated device evidence."""

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import replace

import numpy as np
import pytest

from chronus.resident_hendrix import ResidentHendrix, seal
from chronus.mla1517.mining.pythia_search import precompute_pythia_search, pythia_hendrix_nonces
from chronus.mla1517.mining.resident_search import compile_hendrix_plan
from chronus.mla1517.mining.search_plan import SearchPlan
from chronus.one_igpu_mining import ChronusOneIGPUHasher

GENESIS = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49"
    + "ffff001d"
    + "1dac2b7c"
)


def issue(window=1200, base=1000, header=GENESIS, target=b"\x00" * 32, use_hilbert=True):
    state = precompute_pythia_search()
    plan = SearchPlan(
        job_fingerprint="real-header-test",
        pool_session_id="local-test-only",
        generation=1,
        base_step=base,
        window=window,
        extranonce2="00000000",
        lane_order=tuple(range(32)),
        preferred_face=7,
        dispatch_breadth=32,
        executor_route="chronus_batch",
        policy_id="hendrix",
        evidence_refs={
            "search_precompute_digest": state.digest,
            "search_architecture": state.architecture_id,
        },
        created_at=time.monotonic(),
        plan_id="test-bound-plan",
    )
    artifact = compile_hendrix_plan(plan, header, target, state, use_hilbert=use_hilbert)
    bound = replace(
        plan, evidence_refs={**plan.evidence_refs, "resident_hendrix": artifact.as_dict()}
    )
    artifact.require_context(bound, header, target)
    return bound, artifact


@pytest.mark.parametrize("window", [1, 2, 31, 599, 600, 601, 1199, 1200, 5000, 65536])
def test_resident_operator_matches_canonical_reference_and_complete_coverage(window):
    plan, artifact = issue(window)
    expected = pythia_hendrix_nonces(GENESIS, plan.base_step, window, preferred_face=7)
    actual, bindings = artifact.batch(0, window)
    assert actual.tolist() == expected
    assert sorted(actual.tolist()) == list(range(plan.base_step, plan.base_step + window))
    assert bindings.shape == (window, 2)
    assert all(0 <= int(f) < 32 for f in bindings[:, 1])


def test_whole_uint32_domain_stays_bounded():
    _, artifact = issue(2**32, 0)
    values, _ = artifact.batch(2**32 - 4096, 4096)
    assert len(set(values.tolist())) == 4096
    assert values.dtype == np.uint32
    assert len(artifact.as_dict()["shards"]) == 600


@pytest.mark.parametrize("position,count", [(-1, 1), (0, 65537), (1199, 2), (True, 1)])
def test_boundaries_fail_closed(position, count):
    _, a = issue()
    with pytest.raises(ValueError):
        a.batch(position, count)


@pytest.mark.parametrize(
    "field,value",
    [("plan_id", "changed"), ("generation", 2), ("preferred_face", 8), ("window", 1199)],
)
def test_plan_semantics_cannot_be_reinterpreted(field, value):
    p, a = issue()
    with pytest.raises(ValueError):
        a.require_context(replace(p, **{field: value}), GENESIS, b"\x00" * 32)


def test_header_target_and_tampering_refused():
    p, a = issue()
    detached = p.evidence_refs["resident_hendrix"]["shards"]
    detached[0][2] += 1
    assert p.evidence_refs["resident_hendrix"]["shards"] == a.as_dict()["shards"]
    with pytest.raises(TypeError):
        p.evidence_refs["resident_hendrix"]["window"] = 1
    with pytest.raises(ValueError):
        a.require_context(p, bytes(80), b"\x00" * 32)
    with pytest.raises(ValueError):
        a.require_context(p, GENESIS, b"\xff" * 32)
    raw = a.as_dict()
    raw["shards"][0][2] += 1
    with pytest.raises(ValueError):
        ResidentHendrix.from_dict(raw)
    raw.pop("digest")
    forged = ResidentHendrix.issue(raw)
    with pytest.raises(ValueError):
        forged.validate()


def test_geometry_transport_and_serialisation_restart():
    _, a = issue()
    restored = ResidentHendrix.from_dict(json.loads(json.dumps(a.as_dict())))
    assert restored.encoded == a.encoded
    assert restored.batch(111, 37)[0].tolist() == a.batch(111, 37)[0].tolist()
    assert restored.validate()
    g = a.as_dict()["geometry"]
    assert len(g["adjacency"]) == 600
    assert sum(len(x) for x in g["adjacency"]) // 2 == 1200


def test_hilbert_is_explicitly_selected_or_declined():
    _, with_walk = issue(use_hilbert=True)
    _, without_walk = issue(use_hilbert=False)
    assert with_walk.as_dict()["support"]["turing_hilbert"]
    assert not without_walk.as_dict()["support"]["turing_hilbert"]
    assert without_walk.as_dict()["support"]["hilbert_digest"] is None
    assert set(with_walk.batch(0, 1200)[0]) == set(without_walk.batch(0, 1200)[0])


def test_actual_one_igpu_hashing_negative_control_and_receipt():
    from chronos_one_igpu import OneIGPU

    p, a = issue()
    with OneIGPU() as g:
        h = ChronusOneIGPUHasher(g)
        h.self_check()
        nonce, digest, done = h.grind_target_hendrix_plan(
            GENESIS, b"\x00" * 32, a.as_dict(), 0, 1200
        )
        assert nonce is None and digest is None and done == 1200
        r = h.last_batch_evidence
        assert r["plan_id"] == p.plan_id and r["plan_digest"] == a.as_dict()["plan_digest"]
        assert r["geometry_digest"] == a.as_dict()["geometry"]["digest"]
        assert r["physical_device_executed"] is False
        assert r["kernel_launch_count"] == 0 and r["pool_state"] == "NOT_SUBMITTED"
        assert r["sha256d_evaluations"] == 1200
        assert r["geometry_operations_counted_as_hashes"] is False
        assert r["receipt_digest"] == seal({k: v for k, v in r.items() if k != "receipt_digest"})


def test_actual_genesis_pow_and_independent_host_verification():
    from chronos_one_igpu import OneIGPU

    target = int("00000000ffff" + "00" * 26, 16).to_bytes(32, "big")
    p, a = issue(1, 2083236893, target=target)
    with OneIGPU() as g:
        result = g.execute_hendrix(
            a.as_dict(), GENESIS, target, position=0, count=1, current_epoch=lambda: 1
        )
        assert result["nonce"] == 2083236893
        assert (
            bytes.fromhex(result["digest"])[::-1].hex()
            == "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
        )
        assert result["host_verified"] and result["verification_sha256d_evaluations"] == 1


def test_stale_job_runs_no_work():
    from chronos_one_igpu import OneIGPU
    from chronos_one_igpu.adapters.base import DispatchError

    _, a = issue()
    with OneIGPU() as g:
        with pytest.raises(DispatchError):
            g.execute_hendrix(a.as_dict(), GENESIS, b"\x00" * 32, count=12, current_epoch=lambda: 2)
        assert g.fabric.mining_adapter is None


def test_explicit_lane_binds_by_real_self_check():
    from chronus.mla1517.mining.backend_registry import BackendRegistry

    selected = BackendRegistry().select("one_igpu")
    try:
        assert selected.hasher.backend == "chronus_one_igpu"
        assert selected.hasher.physical_device_executed is False
        assert selected.lane == "one_igpu" and not selected.fallback
    finally:
        selected.hasher.igpu.close()


def test_canonical_dual_is_actual_face_centroid_construction_and_m32_equivalent():
    import itertools
    import turing_core
    from chronos_one_igpu.manifold import build_m32

    vertices = np.asarray(turing_core.generate_icosahedron_vertices())
    distances = np.linalg.norm(vertices[:, None, :] - vertices[None, :, :], axis=2)
    edge = distances[distances > 1e-8].min()
    faces = [
        t
        for t in itertools.combinations(range(12), 3)
        if all(abs(distances[i, j] - edge) < 1e-9 for i, j in itertools.combinations(t, 2))
    ]
    centroids = np.asarray(
        [
            vertices[list(t)].sum(axis=0) / np.linalg.norm(vertices[list(t)].sum(axis=0))
            for t in faces
        ]
    )
    dual = np.asarray(turing_core.generate_dodecahedron_vertices())
    assert len(faces) == 20 and len(dual) == 20
    assert all(np.linalg.norm(centroids - v, axis=1).min() < 1e-9 for v in dual)
    reference = np.vstack([vertices, dual])
    retained = build_m32()
    assert len(reference) == 32 and len(retained) == 32
    assert all(np.linalg.norm(reference - v, axis=1).min() < 1e-9 for v in retained)


def test_production_router_executes_resident_plan_and_preserves_receipt_identity():
    from chronos_one_igpu import OneIGPU
    from chronus.mla1517.mining.resident_router import ProductionExecutionRouter
    from chronus.mla1517.mining.search_plan import NonceLease, EvidenceClass

    plan, artifact = issue()
    g = OneIGPU()
    hasher = ChronusOneIGPUHasher(g)
    router = ProductionExecutionRouter(hasher, cpu_executor=reference_scan)
    lease = NonceLease("actual-test-lease", 1, plan.plan_id, plan.base_step, plan.window)
    record, candidate = router.execute_plan(plan, GENESIS, bytes(32), lease=lease)
    assert candidate is None
    assert record.hash_count == 1200
    assert record.resident_execution_digest == artifact.digest
    assert record.plan_digest == artifact.as_dict()["plan_digest"]
    assert record.geometry_digest == artifact.as_dict()["geometry"]["digest"]
    assert record.evidence_class is EvidenceClass.SOFTWARE_VERIFIED
    assert record.kernel_launch_count == 0
    assert record.executed_nonce_order == "hendrix_coprime_stride"
    assert (
        hasher.last_batch_evidence["order_digest"]
        == hashlib.sha256(artifact.batch(0, 1200)[0].astype("<u4").tobytes()).hexdigest()
    )


def test_production_router_stale_and_foreign_bounds_are_refused():
    from chronos_one_igpu import OneIGPU
    from chronus.mla1517.mining.resident_router import ProductionExecutionRouter
    from chronus.mla1517.mining.search_plan import NonceLease

    p, _ = issue()
    h = ChronusOneIGPUHasher(OneIGPU())
    router = ProductionExecutionRouter(h, cpu_executor=reference_scan)
    record, candidate = router.execute_plan(p, GENESIS, bytes(32), is_still_fresh=lambda: False)
    assert record.hash_count == 0 and candidate is None
    assert h.last_batch_evidence is None
    with pytest.raises(ValueError):
        router.execute_plan(
            p, GENESIS, bytes(32), lease=NonceLease("wrong", 1, p.plan_id, 999, 1200)
        )


def test_production_router_real_genesis_candidate_is_independently_verified():
    from chronos_one_igpu import OneIGPU
    from chronus.mla1517.mining.resident_router import ProductionExecutionRouter

    target = (0xFFFF << (8 * (0x1D - 3))).to_bytes(32, "big")
    p, a = issue(1, 2083236893, target=target)
    record, candidate = ProductionExecutionRouter(
        ChronusOneIGPUHasher(OneIGPU()), cpu_executor=reference_scan
    ).execute_plan(p, GENESIS, target[::-1])
    assert record.hash_count == 1
    assert record.candidate_host_verified
    assert candidate["nonce"] == 2083236893
    assert record.resident_execution_digest == a.digest


def reference_scan(header, target, start, count):
    from chronus.mla1517.mining.execution_router import sha256d_scan

    return sha256d_scan(header, target, range(start, start + count))


def test_executor_cannot_compile_its_own_plan_or_accept_outside_candidate():
    from chronos_one_igpu import OneIGPU
    from chronus.mla1517.mining.resident_router import ProductionExecutionRouter

    p, a = issue()
    h = ChronusOneIGPUHasher(OneIGPU())
    router = ProductionExecutionRouter(h, cpu_executor=reference_scan)
    without_seal = replace(
        p, evidence_refs={k: v for k, v in p.evidence_refs.items() if k != "resident_hendrix"}
    )
    record, candidate = router.execute_plan(without_seal, GENESIS, bytes(32))
    assert candidate is None and record.hash_count == 0
    assert "must seal" in record.device_error
    with pytest.raises(RuntimeError):
        router._validate_ordered_result(a, 0, 20, (0, b"\x00" * 32, 1))
    with pytest.raises(RuntimeError):
        router._validate_ordered_result(a, 0, 20, (None, None, 19))


def test_m32_face_adjacency_and_dual_incidence_are_not_arbitrary_labels():
    from chronus.mla1517.mining.resident_search import m32_manifest

    m = m32_manifest()
    assert len(m["directions_3d"]) == 32
    for i in range(32):
        assert len(m["adjacency"][i]) == (5 if i < 12 else 3)
        assert len(m["dual_incidence"][i]) == (5 if i < 12 else 3)
        assert all(i in m["adjacency"][j] for j in m["adjacency"][i])
        assert all(i in m["dual_incidence"][j] for j in m["dual_incidence"][i])
