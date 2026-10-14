"""Unit tests for EmergentQualificationService three-gate qualification pipeline."""

import pytest
from euclid.emergence.models.candidate import EmergentCandidate, DiscoveryEnvelope, ReproductionProtocol
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.models.qualification import QualificationStatus
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.trusted_core.access_control import GovernanceToken
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService
from euclid.emergence.models.telemetry import TelemetryRecord, NoveltyReport


def make_test_candidate(noise_tolerance=0.5, latency=10.0, compute_sec=0.5):
    envelope = DiscoveryEnvelope(
        max_observation_latency=latency,
        noise_tolerance=noise_tolerance,
        compute_budget_sec=compute_sec,
        parameter_bounds={"alpha": (0.0, 10.0)},
    )
    protocol = ReproductionProtocol(
        task_signature="synthesis_task",
        seed_suite=(42, 1337, 7777),
        manifest_hash="man_hash_123",
        environment_snapshot_hash="env_hash_456",
        required_observables=("emergent_synthesis",),
        statistical_tolerance=0.90,
    )
    return EmergentCandidate(
        candidate_id="cand_synth_01",
        capability_name="emergent_synthesis",
        discovery_substrate_id="sub_discovery_01",
        discovery_envelope=envelope,
        reproduction_steps=protocol,
        claimed_behavior_signature="emergent_synthesis",
        baseline_metrics={"accuracy": 0.95},
    )


def test_gate1_simulated_reproduction_rejected_despite_distinct_metadata(authorize_candidate):
    candidate = make_test_candidate()
    service, token = authorize_candidate(candidate)

    prop_a = SubstrateProperties(
        executor_type="sync_vm",
        observation_latency=5.0,
        action_granularity="atomic",
        compute_substrate="vm_x86_64",
        sandbox_id="box_a",
    )
    prop_b = SubstrateProperties(
        executor_type="async_container",
        observation_latency=15.0,
        action_granularity="batched",
        compute_substrate="container_arm64",
        sandbox_id="box_b",
    )

    exec_a = StandardSyncExecutor(prop_a)
    exec_b = AsyncIsolatedExecutor(prop_b)

    outcome = service.qualify(candidate, exec_a, exec_b, governance_token=token)
    assert outcome.status == QualificationStatus.REJECTED
    assert not service.is_qualified(candidate.candidate_id)
    assert "lacks measured reproduction" in outcome.reason


def test_gate1_rejects_identical_substrates(authorize_candidate):
    candidate = make_test_candidate()
    service, token = authorize_candidate(candidate)

    prop_same = SubstrateProperties(
        executor_type="sync_vm",
        observation_latency=5.0,
        action_granularity="atomic",
        compute_substrate="vm_x86_64",
        sandbox_id="same_box",
    )

    exec_a = StandardSyncExecutor(prop_same)
    exec_b = StandardSyncExecutor(prop_same)

    outcome = service.qualify(candidate, exec_a, exec_b, governance_token=token)
    assert outcome.status == QualificationStatus.REJECTED


def test_gate2_stress_envelope_rejection(authorize_candidate):
    candidate = make_test_candidate(noise_tolerance=0.95, latency=3000.0)
    service, token = authorize_candidate(candidate, margin=2.0)

    prop_a = SubstrateProperties(
        executor_type="sync_vm",
        observation_latency=5.0,
        action_granularity="atomic",
        compute_substrate="vm_x86_64",
        sandbox_id="box_a",
    )
    prop_b = SubstrateProperties(
        executor_type="async_container",
        observation_latency=15.0,
        action_granularity="batched",
        compute_substrate="container_arm64",
        sandbox_id="box_b",
    )

    exec_a = StandardSyncExecutor(prop_a)
    exec_b = AsyncIsolatedExecutor(prop_b)

    outcome = service.qualify(candidate, exec_a, exec_b, governance_token=token)
    assert outcome.status == QualificationStatus.REJECTED
    assert "lacks measured reproduction" in outcome.reason
    # The legacy stress heuristic is tested as a simulation, not as executed stress evidence.
    from euclid.emergence.trusted_core.stress import stress_test
    passed, details = stress_test(candidate, candidate.discovery_envelope.scale_margin(2.0), exec_a)
    assert not passed
    assert details["execution_kind"] == "SIMULATED"
    assert not details["executor_invoked"]


def test_divergence_suspension_remains_available_without_synthetic_qualification(authorize_candidate):
    candidate = make_test_candidate()
    service, token = authorize_candidate(candidate)

    prop_a = SubstrateProperties(
        executor_type="sync_vm",
        observation_latency=5.0,
        action_granularity="atomic",
        compute_substrate="vm_x86_64",
        sandbox_id="box_a",
    )
    prop_b = SubstrateProperties(
        executor_type="async_container",
        observation_latency=15.0,
        action_granularity="batched",
        compute_substrate="container_arm64",
        sandbox_id="box_b",
    )

    exec_a = StandardSyncExecutor(prop_a)
    exec_b = AsyncIsolatedExecutor(prop_b)

    outcome = service.qualify(candidate, exec_a, exec_b, governance_token=token)
    assert outcome.status == QualificationStatus.REJECTED
    assert "lacks measured reproduction" in outcome.reason
    assert not service.is_qualified(candidate.candidate_id)

    divergent_window = [
        TelemetryRecord(
            run_id="run_post_01",
            substrate_id="sub_prod",
            iteration_index=i,
            task_signature="synthesis_task",
            programmed_actions_used=("navigate", "idle"),
            novel_elements=NoveltyReport(),
            invariant_violations=(),
            timestamps={"time": 100.0 + i},
            seeds={"rng": i},
            env_hash="env_hash",
        ).with_computed_hash()
        for i in range(10)
    ]

    suspension = service.check_and_apply_divergence_suspension(candidate, divergent_window)
    assert suspension is not None
    assert suspension.status == QualificationStatus.SUSPENDED
    assert not service.is_qualified(candidate.candidate_id)
