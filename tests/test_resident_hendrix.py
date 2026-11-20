"""Real arithmetic/hash integration tests, with no emulated device evidence."""

import json
import time
from dataclasses import replace

import numpy as np
import pytest

pytestmark = pytest.mark.real

from chronus.execution.resident_hendrix import ResidentHendrix, seal
from chronus.pythia.exact_search import (
    precompute_exact_search as precompute_pythia_search,
    exact_reference_nonces as pythia_hendrix_nonces,
    exact_face_order,
)
from chronus.pythia.resident_search import compile_hendrix_plan
from chronus.pythia.search_plan import SearchPlan

GENESIS = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49"
    + "ffff001d"
    + "1dac2b7c"
)


def issue(
    window=1200, base=1000, header=GENESIS, target=b"\x00" * 32, use_hilbert=True
):
    state = precompute_pythia_search()
    plan = SearchPlan(
        job_fingerprint="real-header-test",
        pool_session_id="local-test-only",
        generation=1,
        base_step=base,
        window=window,
        extranonce2="00000000",
        lane_order=exact_face_order(header, state),
        preferred_face=exact_face_order(header, state)[0],
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
    artifact = compile_hendrix_plan(
        plan, header, target, state, use_hilbert=use_hilbert
    )
    bound = replace(
        plan,
        evidence_refs={**plan.evidence_refs, "resident_hendrix": artifact.as_dict()},
    )
    artifact.require_context(bound, header, target)
    return bound, artifact


@pytest.mark.parametrize("window", [1, 2, 31, 599, 600, 601, 1199, 1200, 5000, 65536])
def test_resident_operator_matches_canonical_reference_and_complete_coverage(window):
    plan, artifact = issue(window)
    expected = pythia_hendrix_nonces(
        GENESIS, plan.base_step, window, preferred_face=plan.preferred_face
    )
    actual, bindings = artifact.batch(0, window)
    assert actual.tolist() == expected
    assert sorted(actual.tolist()) == list(
        range(plan.base_step, plan.base_step + window)
    )
    assert bindings.shape == (window, 2)
    assert all(0 <= int(f) < 32 for f in bindings[:, 1])


def test_whole_uint32_domain_stays_bounded():
    _, artifact = issue(2**32, 0)
    values, _ = artifact.batch(2**32 - 4096, 4096)
    assert len(set(values.tolist())) == 4096
    assert values.dtype == np.uint32
    assert len(artifact.as_dict()["shards"]) == 600


def test_advisory_lane_order_cannot_enter_exact_compiler():
    plan, _ = issue()
    state = precompute_pythia_search()
    altered = replace(plan, lane_order=plan.lane_order[1:] + plan.lane_order[:1])
    with pytest.raises(ValueError, match="advisory lane"):
        compile_hendrix_plan(altered, GENESIS, bytes(32), state)
    with pytest.raises(ValueError, match="advisory nonce"):
        compile_hendrix_plan(
            replace(plan, schedule=(plan.base_step,)), GENESIS, bytes(32), state
        )


def test_legacy_binary64_transport_refused_even_with_new_seals():
    _, artifact = issue()
    value = artifact.as_dict()
    value["geometry"]["transport"]["encoding"] = "lucas.M15.binary64"
    value["geometry"]["digest"] = seal(
        {k: v for k, v in value["geometry"].items() if k != "digest"}
    )
    with pytest.raises(ValueError, match="binary64"):
        ResidentHendrix.issue(
            {k: v for k, v in value.items() if k != "digest"}
        ).validate()


def test_resealed_quantum_metadata_cannot_claim_different_execution():
    _, artifact = issue()
    value = artifact.as_dict()
    value["support"]["hilbert_digest"] = "0" * 64
    with pytest.raises(ValueError, match="Turing support"):
        ResidentHendrix.issue(
            {k: v for k, v in value.items() if k != "digest"}
        ).validate()


@pytest.mark.parametrize("position,count", [(-1, 1), (0, 65537), (1199, 2), (True, 1)])
def test_boundaries_fail_closed(position, count):
    _, a = issue()
    with pytest.raises(ValueError):
        a.batch(position, count)


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_id", "changed"),
        ("generation", 2),
        ("preferred_face", 8),
        ("window", 1199),
    ],
)
def test_plan_semantics_cannot_be_reinterpreted(field, value):
    p, a = issue()
    with pytest.raises(ValueError):
        a.require_context(replace(p, **{field: value}), GENESIS, b"\x00" * 32)


def test_expired_plan_is_refused_by_resident_context():
    plan, artifact = issue()
    expired = replace(plan, created_at=plan.created_at - 1, expires_at=plan.created_at)
    with pytest.raises(ValueError, match="expired SearchPlan"):
        artifact.require_context(expired, GENESIS, bytes(32))


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



def test_installed_resident_executes_real_genesis_and_refuses_foreign_work():
    from chronus.execution.resident_hendrix import execute_resident
    from chronus.pythia.search_plan import WorkIdentity
    nonce = int.from_bytes(GENESIS[76:], "little")
    target = (0xffff << 208).to_bytes(32, "big")
    p, a = issue(window=1200, base=nonce-599, target=target)
    wi = WorkIdentity(p.pool_session_id, p.generation, "genesis", p.job_fingerprint, 0, True, time.monotonic())
    result = execute_resident(p, a, GENESIS, target, wi, 0, p.window)
    assert result["nonce"] == nonce and result["digest"] == (
        bytes.fromhex("000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")[::-1].hex()
    )
    assert result["oracle_evaluations"] == result["completed"]
    assert result["executed_algorithm"] == "hendrix_coprime_stride"
    with pytest.raises(ValueError, match="stale"):
        execute_resident(p, a, GENESIS, target, replace(wi, generation=2), 0, p.window)


@pytest.mark.parametrize("stride", [-1, 2**80 + 1])
def test_unbounded_local_stride_uses_exact_modulo(stride):
    _, artifact = issue(window=1200)
    value = artifact.as_dict()
    for row in value["shards"]:
        row[4] = stride
    value.pop("digest")
    altered = ResidentHendrix.issue(value)
    assert altered.batch(0, 1200)[0].tolist() == artifact.batch(0, 1200)[0].tolist()


def test_resealed_artifact_cannot_change_plan_lease():
    plan, _ = issue()
    _, foreign = issue(window=601, base=2000)
    from chronus.execution.resident_hendrix import plan_identity
    value = foreign.as_dict()
    value["plan_digest"] = seal(plan_identity(plan))
    value.pop("digest")
    artifact = ResidentHendrix.issue(value)
    with pytest.raises(ValueError, match="lease differs"):
        artifact.require_context(plan, GENESIS, bytes(32))


@pytest.mark.parametrize("route", ["cpu_reference", "opencl_m32", "opencl_gold", "opencl_range"])
def test_unsupported_resident_routes_rejected(route):
    plan, _ = issue()
    with pytest.raises(ValueError, match="executor route"):
        compile_hendrix_plan(replace(plan, executor_route=route), GENESIS, bytes(32), precompute_pythia_search())


def test_resident_rejects_rank_outside_certified_geometry():
    plan, _ = issue()
    state = precompute_pythia_search()
    altered = replace(state, hilbert_walk_rank=tuple(reversed(state.hilbert_walk_rank)))
    with pytest.raises(ValueError, match="certified geometry"):
        compile_hendrix_plan(plan, GENESIS, bytes(32), altered)


def test_all_evidence_is_detached_and_keeps_plan_digest():
    from chronus.execution.resident_hendrix import plan_identity
    plan, artifact = issue()
    nested = {"items": [{"values": [1, 2]}], "tuple": ([3],)}
    plan = replace(plan, evidence_refs={**plan.evidence_refs, "extra": nested})
    artifact = compile_hendrix_plan(plan, GENESIS, bytes(32), precompute_pythia_search())
    digest = seal(plan_identity(plan))
    nested["items"][0]["values"].append(9)
    nested["tuple"][0].append(9)
    plan.evidence_refs["extra"]["items"][0]["values"].append(8)
    plan.evidence_refs["extra"]["tuple"][0].append(8)
    assert seal(plan_identity(plan)) == digest
    artifact.require_context(plan, GENESIS, bytes(32))


def test_execution_snapshots_inputs_before_validation(monkeypatch):  # mock-ok: inject caller mutation while exercising real validation and hashing
    from chronus.execution.resident_hendrix import execute_resident
    from chronus.pythia.search_plan import WorkIdentity
    header, target = bytearray(GENESIS), bytearray(b"\xff" * 32)
    plan, artifact = issue(window=1, target=target)
    identity = WorkIdentity(plan.pool_session_id, plan.generation, "local", plan.job_fingerprint, 0, True, time.monotonic())
    original = ResidentHendrix.require_context

    def validate_then_mutate(self, plan, checked_header, checked_target):
        assert type(checked_header) is type(checked_target) is bytes
        original(self, plan, checked_header, checked_target)
        header[:] = bytes(80)
        target[:] = bytes(32)

    monkeypatch.setattr(ResidentHendrix, "require_context", validate_then_mutate)  # mock-ok: wrapper calls real validation before mutating caller inputs
    result = execute_resident(plan, artifact, header, target, identity, 0, 1)
    assert result["nonce"] == plan.base_step
    from chronus.execution.asic_sha256 import sha256d_unrolled
    assert result["digest"] == sha256d_unrolled(GENESIS[:76] + plan.base_step.to_bytes(4, "little")).hex()
