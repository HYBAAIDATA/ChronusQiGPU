from __future__ import annotations

from dataclasses import dataclass

import pytest

from salamander.control_plane import (
    ActionRegistry,
    AutonomicControlPlane,
    CircuitBreaker,
    EvidenceLedger,
    FailClosed,
    RecoveryPlan,
    RecoveryStep,
)
from salamander.models import (
    ActionKind,
    ActionRequest,
    AdmissionDecision,
    Availability,
    BackendLifecycle,
    CapabilityIdentity,
    CircuitState,
    DatasetPartition,
    HealthObservation,
    HealthState,
    OvidRecordIdentity,
    OptimizationTrial,
    PolicyLifecycle,
    PolicyVersion,
    RewardAuthority,
    TheseusProjection,
)


class Clock:
    def __init__(self) -> None:
        self.value = 1_000

    def __call__(self) -> int:
        self.value += 1
        return self.value


def request(action_id="a", handler="bounded", kind=ActionKind.REPLAN, dep=()):
    return ActionRequest(
        action_id, kind, handler, "tenant-a", "target", "test",
        {"max_attempts": 1}, dep, "idem:" + action_id,
    )


def plane(handler=None, verifier=None):
    registry = ActionRegistry()
    registry.register(
        "bounded",
        {
            ActionKind.REPLAN, ActionKind.THROTTLE, ActionKind.FAILOVER,
            ActionKind.REBUILD_PROJECTION, ActionKind.ROLLBACK,
        },
        handler or (lambda _: {"post_observation": "healthy"}),
        verifier_id="independent-test-probe",
        verifier=verifier or (lambda _request, response: {
            "verified": response.get("post_observation") == "healthy",
            "evidence_ref": "probe:healthy",
            "observations": {"health": response.get("post_observation")},
        }),
    )
    return AutonomicControlPlane(registry=registry, clock_ns=Clock())


def test_unknown_and_unavailable_are_not_fabricated_healthy():
    cp = plane()
    empty = cp.observe(())
    assert empty.state is HealthState.UNKNOWN
    unavailable = cp.observe(
        (
            HealthObservation(
                "chronus", "device", "tenant-a", 1, Availability.UNAVAILABLE,
                source="ExecutionRouter",
            ),
        )
    )
    assert unavailable.state is HealthState.UNAVAILABLE
    with pytest.raises(ValueError):
        HealthObservation("chronus", "temperature", "tenant-a", 1, Availability.NOT_MEASURED, 42)


def test_multidimensional_health_uses_explicit_dimensions_not_score():
    cp = plane()
    decision = cp.observe(
        (
            HealthObservation("ovid", "integrity", "tenant-a", 1, Availability.MEASURED, True),
            HealthObservation("theseus", "projection", "tenant-a", 2, Availability.MEASURED, "DEGRADED"),
        )
    )
    assert decision.state is HealthState.DEGRADED
    assert any("theseus.projection" in reason for reason in decision.reasons)


def test_capability_lifecycle_is_separate_and_expiry_quarantines():
    clock = Clock()
    cp = plane()
    cp.clock_ns = clock
    identity = CapabilityIdentity("opencl:0", "gpu0", "BINET_EXACT", "int", "a" * 64)
    cp.discover(identity)
    cp.qualify(identity, passed=True, evidence_ref="evidence:1", expires_at_ns=clock.value + 2)
    assert cp.capabilities[identity].lifecycle is BackendLifecycle.QUALIFIED
    clock.value += 10
    envelope = cp.chronus_envelope(identity, requested_operation="BINET_EXACT")
    assert envelope.state is HealthState.QUARANTINED
    assert envelope.prohibited_operations == ("BINET_EXACT",)
    assert envelope.constraints["opencl.BINET_EXACT"] == "UNSUPPORTED"


def test_declared_f64_boundary_is_preserved():
    cp = plane()
    identity = CapabilityIdentity("opencl:0", "gpu0", "TENSOR", "f64", "b" * 64)
    envelope = cp.chronus_envelope(identity, requested_operation="11D_SUBSTRATE")
    assert envelope.legal_operations == ()
    assert envelope.constraints["f64_boundary"] == "CPU_OR_EXACT_INTEGER_UNTIL_CERTIFIED_FP64"


def test_circuit_breaker_open_half_open_close():
    breaker = CircuitBreaker(failure_limit=2, cooldown_ns=10)
    assert breaker.admit(0)
    breaker.record(False, 1)
    assert breaker.state is CircuitState.CLOSED
    assert breaker.admit(2)
    breaker.record(False, 3)
    assert breaker.state is CircuitState.OPEN
    assert not breaker.admit(12)
    assert breaker.admit(13)
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.record(True, 14)
    assert breaker.state is CircuitState.CLOSED


def test_recovery_dag_is_bounded_ordered_and_verified():
    cp = plane()
    plan = RecoveryPlan(
        "r1", "tenant-a", "device:gpu0",
        (
            RecoveryStep("b", request("b"), ("a",)),
            RecoveryStep("a", request("a")),
        ),
        2,
        10_000,
    )
    results = cp.recover(plan)
    assert [result.action_id for result in results] == ["a", "b"]
    assert all(result.verified for result in results)
    cycle = RecoveryPlan(
        "r2", "tenant-a", "device:gpu1",
        (
            RecoveryStep("a", request("c"), ("b",)),
            RecoveryStep("b", request("d"), ("a",)),
        ),
        2,
        10_000,
    )
    with pytest.raises(FailClosed):
        cp.recover(cycle)


def test_action_handlers_are_registered_bounded_and_idempotent():
    cp = plane()
    first = cp.execute(request())
    second = cp.execute(request())
    assert first == second
    with pytest.raises(FailClosed):
        cp.execute(request("x", handler="shell"))


def test_unverified_action_is_not_recovery_proof():
    cp = plane(
        lambda _: {"verified": True, "post_observation": "claimed-healthy"},
        verifier=lambda _request, _response: {
            "verified": False, "error": "independent probe failed"
        },
    )
    result = cp.execute(request())
    assert result.status == "UNVERIFIED"
    assert not result.verified
    assert "independent probe failed" in result.error


def test_tenant_admission_and_isolation():
    cp = plane()
    cp.set_tenant_capacity("tenant-a", 1)
    assert cp.admit("tenant-a", "w1", "other:key").decision is AdmissionDecision.ISOLATE
    assert cp.admit("tenant-a", "w1", "tenant-a:key").decision is AdmissionDecision.ADMIT
    assert cp.admit("tenant-a", "w2", "tenant-a:key2").decision is AdmissionDecision.DEFER
    cp.release("tenant-a")
    assert cp.admit("tenant-a", "w2", "tenant-a:key2").decision is AdmissionDecision.ADMIT


def test_ovid_authority_is_independent_and_theseus_is_rebuildable():
    cp = plane()
    ovid = OvidRecordIdentity("tenant-a", "learning", "r1", "a" * 64, "aethel", 1)
    projection = TheseusProjection("p1", "tenant-a", ovid, "v1", "b" * 64, 1, 1, 1)
    ovid_verify = lambda _: {"valid": True, "payload_sha256": "a" * 64}
    status = cp.verify_theseus(
        projection,
        lambda: {"valid": True, "projection_sha256": "c" * 64},
        ovid_verify,
    )
    assert status["drift"] is True
    assert status["valid"] is False
    assert cp.verify_ovid(ovid, ovid_verify)["valid"] is True


def test_theseus_cannot_prove_ovid_payload():
    cp = plane()
    ovid = OvidRecordIdentity("tenant-a", "evidence", "r1", "a" * 64, "aethel", 1)
    projection = TheseusProjection("p1", "tenant-a", ovid, "v1", "b" * 64, 1, 1, 1)
    with pytest.raises(FailClosed):
        cp.verify_theseus(
            projection,
            lambda: {"valid": True, "projection_sha256": "b" * 64},
            lambda _: {"valid": False, "payload_sha256": "a" * 64},
        )


def test_observation_is_not_reward_and_partitions_are_explicit():
    cp = plane()
    exp = cp.form_experience(
        replay_id="stable:1",
        tenant_id="tenant-a",
        task="backend-selection",
        observation_ref="ovid:observation",
        action="defer",
        outcome_ref="ovid:outcome",
        reward_authority=RewardAuthority.NONE,
        reward=None,
        partition=DatasetPartition.INCIDENT,
        temporal_lineage="incident:2026-10-02",
    )
    assert exp.reward is None
    with pytest.raises(ValueError):
        cp.form_experience(
            replay_id="stable:2", tenant_id="tenant-a", task="x",
            observation_ref="o", action="a", outcome_ref="z",
            reward_authority=RewardAuthority.NONE, reward=1.0,
            partition=DatasetPartition.TRAIN, temporal_lineage="t",
        )


def test_policy_lifecycle_cannot_skip_evaluation_gates_and_rolls_back():
    cp = plane()
    policy = PolicyVersion("policy:1", "a" * 64, "b" * 64)
    cp.register_policy(policy)
    with pytest.raises(FailClosed):
        cp.transition_policy("policy:1", PolicyLifecycle.PROMOTED, "e:bad")
    for state in (
        PolicyLifecycle.TRAINED, PolicyLifecycle.VALIDATED,
        PolicyLifecycle.FINAL_TESTED, PolicyLifecycle.SHADOW,
        PolicyLifecycle.CANARY, PolicyLifecycle.PROMOTED,
    ):
        cp.transition_policy("policy:1", state, "e:" + state.value)
    cp.set_baseline("accepted_work", 100.0, 5.0)
    assert cp.rollback_on_regression("policy:1", {"accepted_work": 90.0}, "e:rollback")
    assert policy.lifecycle is PolicyLifecycle.ROLLED_BACK


def test_restart_reacquires_truth_and_marks_probe_failure_unavailable():
    cp = plane()
    state = cp.reacquire_truth(
        {
            "chronus": lambda: {"state": "HEALTHY"},
            "ovid": lambda: (_ for _ in ()).throw(RuntimeError("offline")),
        }
    )
    assert state["chronus"]["availability"] == "MEASURED"
    assert state["ovid"]["availability"] == "UNAVAILABLE"
    assert "offline" not in state["ovid"].values()


def test_mining_107_is_consumed_not_reimplemented():
    cp = plane()

    class Integration:
        def snapshot(self, **_):
            return {
                "schema": "chronus.production-mining-integration.v1",
                "recovery": {
                    "entrypoint": "IntelligentPoolCoordinator.apply_salamander_mode",
                    "authority": "recovery_governor",
                    "scope": "PRODUCTION_MINING_ONLY",
                },
            }

    snapshot = cp.mining107_snapshot(Integration(), hasher=object(), recovery=object())
    assert snapshot["recovery"]["authority"] == "recovery_governor"


def test_evidence_chain_detects_tamper_and_api_has_real_availability():
    ledger = EvidenceLedger()
    ledger.append("x", {"a": 1}, at_ns=1)
    assert ledger.verify()
    ledger._records[0]["payload"]["a"] = 2
    with pytest.raises(FailClosed):
        ledger.verify()
    snapshot = plane().api_snapshot()
    assert snapshot["routes"]["/api/salamander/evidence"] == "AVAILABLE"


def test_action_registration_requires_independent_verifier():
    registry = ActionRegistry()
    with pytest.raises((TypeError, ValueError)):
        registry.register("unsafe", {ActionKind.REPLAN}, lambda _: {"verified": True})


def test_evidence_checkpoint_round_trip_and_tamper_rejection():
    ledger = EvidenceLedger()
    ledger.append("observed", {"value": 1}, at_ns=1)
    payload = ledger.to_payload()
    restored = EvidenceLedger.from_payload(payload)
    assert restored.verify()
    assert restored.head == ledger.head
    tampered = dict(payload)
    tampered["head"] = "f" * 64
    with pytest.raises(FailClosed):
        EvidenceLedger.from_payload(tampered)


def test_optimization_requires_holdout_independent_proof_and_improvement():
    cp = plane()
    policy = PolicyVersion("policy:opt", "a" * 64, "b" * 64)
    cp.register_policy(policy)
    for state in (PolicyLifecycle.TRAINED, PolicyLifecycle.VALIDATED):
        cp.transition_policy(policy.policy_id, state, "e:" + state.value)
    cp.set_baseline("throughput", 100.0, 2.0, higher_is_better=True)
    cp.set_baseline("latency", 20.0, 1.0, higher_is_better=False)
    trial = OptimizationTrial(
        "trial:1", policy.policy_id, DatasetPartition.TEMPORAL_HOLDOUT,
        {"throughput": 100.0, "latency": 20.0},
        {"throughput": 110.0, "latency": 18.0},
        50, "ovid:trial-1", "holdout:2026-10-04",
    )
    result = cp.evaluate_optimization(
        trial, lambda _: {"verified": True, "evidence_ref": "independent:trial-1"}
    )
    assert result["accepted"] is True
    assert set(result["improvements"]) == {"throughput", "latency"}
    assert policy.lifecycle is PolicyLifecycle.VALIDATED


def test_optimization_regression_quarantines_candidate():
    cp = plane()
    policy = PolicyVersion("policy:bad", "a" * 64, "b" * 64)
    cp.register_policy(policy)
    for state in (PolicyLifecycle.TRAINED, PolicyLifecycle.VALIDATED):
        cp.transition_policy(policy.policy_id, state, "e:" + state.value)
    cp.set_baseline("throughput", 100.0, 2.0)
    trial = OptimizationTrial(
        "trial:bad", policy.policy_id, DatasetPartition.FINAL_TEST,
        {"throughput": 100.0}, {"throughput": 90.0},
        25, "ovid:trial-bad", "final:2026-10-04",
    )
    result = cp.evaluate_optimization(
        trial, lambda _: {"verified": True, "evidence_ref": "independent:bad"}
    )
    assert result["accepted"] is False
    assert result["regressions"] == ("throughput",)
    assert policy.lifecycle is PolicyLifecycle.QUARANTINED


def test_no_arbitrary_execution_surface():
    import inspect
    import salamander.control_plane as module

    source = inspect.getsource(module)
    assert "subprocess" not in source
    assert "shell=True" not in source
    assert "exec(" not in source
    assert "eval(" not in source
    assert "sqlite3" not in source
    assert "write_text" not in source