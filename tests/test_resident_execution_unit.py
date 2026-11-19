"""Controlled CPU boundary tests; these do not establish device execution."""
import hashlib
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from chronus.execution.resident_hendrix import execute_resident, issue_software_contract, plan_identity, seal
from chronus.pythia.search_plan import SearchPlan, WorkIdentity

pytestmark = pytest.mark.simulated


@pytest.fixture
def plan():
    return SearchPlan(
        job_fingerprint="synthetic-work", pool_session_id="synthetic-session",
        generation=1, base_step=10, window=3, extranonce2="00000000",
        lane_order=tuple(range(32)), preferred_face=0, dispatch_breadth=32,
        executor_route="chronus_batch", policy_id="hendrix", evidence_refs={},
        created_at=1, plan_id="unit-plan",
    )


@pytest.fixture
def identity(plan):
    return WorkIdentity(plan.pool_session_id, plan.generation, "job", plan.job_fingerprint, 0, True, 1)


@pytest.fixture
def execution(monkeypatch):
    import chronus.execution.hashrate_cap as module

    class Cap:
        grant = 3

        def __init__(self):
            self.requests, self.refunds = [], []

        def allow(self, count):
            self.requests.append(count)
            return min(count, self.grant)

        def refund(self, count):
            self.refunds.append(count)

    cap = Cap()
    monkeypatch.setattr(module, "process_cap", lambda: cap)
    contexts = []
    artifact = SimpleNamespace(
        digest="unit-artifact",
        require_context=lambda *args: contexts.append(args),
        batch=lambda position, count: (
            np.arange(10 + position, 10 + position + count, dtype=np.uint32),
            np.array([[42, 7]] * count, dtype=np.uint32).reshape(count, 2),
        ),
    )
    return cap, artifact, contexts


@pytest.mark.parametrize("target,winner,completed", [(bytes(32), None, 3), (b"\xff" * 32, 10, 1)])
def test_hashes_winner_and_sealed_receipt(plan, identity, execution, target, winner, completed):
    cap, artifact, contexts = execution
    header = bytes(80)
    result = execute_resident(plan, artifact, header, target, identity, 0, 3)
    assert contexts == [(plan, header, target)]
    assert result["completed"] == result["oracle_evaluations"] == completed
    assert result["nonce"] == winner
    expected = hashlib.sha256(hashlib.sha256(header[:76] + (10).to_bytes(4, "little")).digest()).digest()
    assert result["digest"] == (expected.hex() if winner is not None else None)
    assert result["vertex"] == (42 if winner is not None else None)
    assert result["face"] == (7 if winner is not None else None)
    assert result["verification_compressions"] == (3 if winner is not None else 0)
    assert result["fallback_used"] is False
    assert result["executed_algorithm"] == plan.nonce_order
    assert cap.requests == [3] and cap.refunds == [3 - completed]
    receipt = result.pop("receipt_sha256")
    assert receipt == seal(result)


@pytest.mark.parametrize("cancel,grant", [(True, 3), (False, 0), (False, 1)])
def test_cancellation_and_partial_grants(plan, identity, execution, cancel, grant):
    cap, artifact, _ = execution
    cap.grant = grant
    token = SimpleNamespace(is_set=lambda: cancel)
    result = execute_resident(plan, artifact, bytes(80), bytes(32), identity, 0, 3, cancel_token=token)
    done = 0 if cancel else grant
    assert result["completed"] == result["oracle_evaluations"] == done
    assert result["requested"] == 3
    assert result["executed_algorithm"] == (plan.nonce_order if done else None)
    assert cap.refunds == [grant - done]


@pytest.mark.parametrize("field,value", [("generation", 2), ("pool_session_id", "foreign"), ("job_fingerprint", "foreign")])
def test_foreign_work_refused_before_cap_use(plan, identity, execution, field, value):
    cap, artifact, contexts = execution
    with pytest.raises(ValueError, match="stale"):
        execute_resident(plan, artifact, bytes(80), bytes(32), replace(identity, **{field: value}), 0, 3)
    assert cap.requests == contexts == []


def test_verification_failure_refunds_unused_budget(plan, identity, execution, monkeypatch):
    import chronus.execution.asic_sha256 as verifier

    cap, artifact, _ = execution
    monkeypatch.setattr(verifier, "sha256d_unrolled", lambda header: b"wrong digest")
    with pytest.raises(ArithmeticError, match="verification mismatch"):
        execute_resident(plan, artifact, bytes(80), b"\xff" * 32, identity, 0, 3)
    assert cap.refunds == [2]


@pytest.mark.parametrize("mode,device", [("opencl", None), ("resident_software", "gpu"), ("resident_software", {})])
def test_contract_refuses_unavailable_implementations(mode, device):
    with pytest.raises(ValueError, match="unavailable"):
        issue_software_contract(execution_mode=mode, device=device)


def test_plan_identity_and_nested_immutability(plan):
    bound = replace(plan, evidence_refs={"resident_hendrix": {"nested": [1]}})
    assert plan_identity(bound) == plan_identity(plan)
    assert seal(plan_identity(replace(plan, policy_id="other"))) != seal(plan_identity(plan))
    assert seal(plan_identity(replace(plan, evidence_refs={"other": 1}))) != seal(plan_identity(plan))
    detached = bound.evidence_refs["resident_hendrix"]["nested"]
    detached.append(2)
    assert bound.evidence_refs["resident_hendrix"]["nested"] == [1]


def test_expiry_boundary_and_missing_identity(plan, identity, monkeypatch):
    import chronus.pythia.search_plan as module

    expiring = replace(plan, expires_at=5)
    monkeypatch.setattr(module.time, "monotonic", lambda: 4)
    assert expiring.is_valid_for(identity)
    monkeypatch.setattr(module.time, "monotonic", lambda: 5)
    assert not expiring.is_valid_for(identity)
    assert not plan.is_valid_for(None)


@pytest.mark.parametrize("changes,refs,message", [
    ({"nonce_order": "sequential"}, {}, "canonical Hendrix"),
    ({}, {"search_precompute_digest": "foreign"}, "different mathematical substrate"),
])
def test_compiler_rejects_wrong_algorithm_or_substrate(plan, changes, refs, message):
    from chronus.pythia.resident_search import compile_hendrix_plan

    candidate = replace(plan, evidence_refs=refs, **changes)
    with pytest.raises(ValueError, match=message):
        compile_hendrix_plan(candidate, bytes(80), bytes(32), SimpleNamespace(digest="expected"))


@pytest.mark.parametrize("header,target", [(bytes(79), bytes(32)), (bytes(81), bytes(32)), (bytes(80), bytes(31)), (bytes(80), bytes(33))])
def test_compiler_rejects_malformed_header_or_target(plan, header, target):
    from chronus.pythia.resident_search import compile_hendrix_plan

    with pytest.raises(ValueError, match="header80 and target256"):
        compile_hendrix_plan(plan, header, target, None)


@pytest.mark.parametrize("header", [bytes(79), bytes(81), bytearray(80), "0" * 80])
def test_exact_search_rejects_malformed_headers_without_precomputation(header):
    from chronus.pythia.exact_search import exact_face_order, exact_vertex_itinerary

    for order in (exact_face_order, exact_vertex_itinerary):
        with pytest.raises(ValueError, match="header80"):
            order(header)


@pytest.mark.parametrize("base,window", [(-1, 1), (0, 0), (0, -1), (True, 1), (0, True), (2**32 - 1, 2)])
def test_directive_rejects_invalid_lease_before_geometry(base, window):
    from chronus.pythia.exact_search import exact_mining_directive

    with pytest.raises(ValueError, match="uint32 lease"):
        exact_mining_directive(header=bytes(80), target_be=bytes(32), base_step=base, window=window)


def test_cancellation_between_hashes_stops_and_refunds(plan, identity, execution):
    cap, artifact, _ = execution
    checks = iter((False, True))
    token = SimpleNamespace(is_set=lambda: next(checks))
    result = execute_resident(plan, artifact, bytes(80), bytes(32), identity, 0, 3, cancel_token=token)
    assert result["completed"] == result["oracle_evaluations"] == 1
    assert result["nonce"] is None
    assert cap.refunds == [2]


def test_empty_execution_emits_zero_work_receipt(plan, identity, execution):
    cap, artifact, _ = execution
    result = execute_resident(plan, artifact, bytes(80), bytes(32), identity, 3, 0)
    assert result["position"] == 3
    assert result["requested"] == result["completed"] == result["oracle_evaluations"] == 0
    assert result["executed_algorithm"] is None
    assert result["nonce"] is result["digest"] is None
    assert cap.requests == cap.refunds == [0]


def test_context_rejection_happens_before_budget_reservation(plan, identity, execution):
    cap, artifact, _ = execution

    def reject(*args):
        raise ValueError("foreign context")

    artifact.require_context = reject
    with pytest.raises(ValueError, match="foreign context"):
        execute_resident(plan, artifact, bytes(80), bytes(32), identity, 0, 3)
    assert cap.requests == cap.refunds == []


@pytest.mark.parametrize("changes,message", [
    ({"base": True}, "integer lease"),
    ({"base": -1}, "outside uint32"),
    ({"base": 2**32 - 1, "window": 2}, "outside uint32"),
    ({"window": 0}, "outside uint32"),
    ({"hendrix_stride": 2}, "not a permutation"),
    ({"hendrix_stride": 0}, "not a permutation"),
    ({"shards": []}, "600 unique"),
])
def test_resealed_invalid_lease_or_shards_are_rejected(changes, message):
    from chronus.execution.resident_hendrix import ResidentHendrix, SCHEMA

    # Invalid outer fields must be refused before accessing geometry or execution metadata.
    body = {"schema": SCHEMA, "base": 0, "window": 6, "hendrix_stride": 1, "shards": []}
    with pytest.raises(ValueError, match=message):
        ResidentHendrix.issue({**body, **changes}).validate()


def test_artifact_snapshot_and_seal_detect_nested_mutation():
    from chronus.execution.resident_hendrix import ResidentHendrix, SCHEMA

    original = {"schema": SCHEMA, "nested": [1]}
    artifact = ResidentHendrix.issue(original)
    original["nested"].append(2)
    assert artifact.as_dict()["nested"] == [1]
    detached = artifact.as_dict()
    detached["nested"].append(3)
    with pytest.raises(ValueError, match="identity mismatch"):
        ResidentHendrix.from_dict(detached)
    assert seal({"b": [2], "a": 1}) == seal({"a": 1, "b": (2,)})
    with pytest.raises(ValueError):
        seal({"nonfinite": float("nan")})


def test_nested_evidence_cannot_change_plan_identity(plan):
    evidence = {"nested": {"list": [{"numbers": [1, 2]}], "tuple": ([3],)}}
    issued = replace(plan, evidence_refs=evidence)
    before = seal(plan_identity(issued))
    evidence["nested"]["list"][0]["numbers"].append(4)
    evidence["nested"]["tuple"][0].append(5)
    issued.evidence_refs["nested"]["list"][0]["numbers"].clear()
    issued.evidence_refs["nested"]["tuple"][0].clear()
    assert seal(plan_identity(issued)) == before
    with pytest.raises(TypeError):
        issued.evidence_refs["new"] = 1
