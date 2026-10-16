"""Unit tests for substrate registry, isolation criteria, and differential experimentation."""

import pytest
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.substrate.isolation import SubstrateIndependenceVerifier
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.substrate.registry import SubstrateRegistry
from euclid.emergence.substrate.harness import TIER_1


class MockArchitecture:
    def decide(self, task: str, iteration: int):
        if iteration % 10 == 0:
            return ["explore", "evaluate", "emergent_tool"]
        return ["explore", "evaluate"]

    def act(self, decisions):
        return decisions


def test_substrate_registration_and_evidence_custody():
    registry = SubstrateRegistry()
    sid1 = registry.register(
        executor_type="sync_vm",
        observation_latency=5.0,
        action_granularity="atomic",
        compute_substrate="vm_x86_64",
    )
    assert sid1.startswith("sub_sync_vm_")

    props = registry.get_properties(sid1)
    assert props is not None
    assert props.observation_latency == 5.0

    evidence_hash = "abc123evidencehash"
    registry.attach_evidence_custody(sid1, evidence_hash)
    assert registry.verify_custody(sid1, evidence_hash)
    assert not registry.verify_custody("sub_non_existent", evidence_hash)


def test_substrate_isolation_verification():
    prop_a = SubstrateProperties(
        executor_type="sync_executor",
        observation_latency=5.0,
        action_granularity="atomic",
        compute_substrate="vm_x86",
        sandbox_id="box_a",
    )
    prop_b = SubstrateProperties(
        executor_type="async_executor",
        observation_latency=25.0,
        action_granularity="batched",
        compute_substrate="container_arm",
        sandbox_id="box_b",
    )

    exec_a = StandardSyncExecutor(prop_a)
    exec_b = AsyncIsolatedExecutor(prop_b)

    is_isolated, violations = SubstrateIndependenceVerifier.verify_isolation(prop_a, prop_b, exec_a, exec_b)
    assert is_isolated
    assert len(violations) == 0

    is_isolated_ident, violations_ident = SubstrateIndependenceVerifier.verify_isolation(prop_a, prop_a, exec_a, exec_a)
    assert not is_isolated_ident

    exec_b.state_store = exec_a.state_store
    is_isolated_shared, violations_shared = SubstrateIndependenceVerifier.verify_isolation(prop_a, prop_b, exec_a, exec_b)
    assert not is_isolated_shared


def test_differential_experiment():
    registry = SubstrateRegistry()
    architecture = MockArchitecture()
    tasks = ["task_alpha", "task_beta"]

    variants = [
        SubstrateProperties(
            executor_type="sync_test",
            observation_latency=2.0,
            action_granularity="atomic",
            compute_substrate="vm_x86_64",
            sandbox_id="sandbox_1",
        ),
        SubstrateProperties(
            executor_type="async_test",
            observation_latency=20.0,
            action_granularity="batched",
            compute_substrate="container_arm64",
            sandbox_id="sandbox_2",
        ),
    ]

    # A decision-only fixture has no observation provider; no synthetic evidence.
    with pytest.raises(TypeError, match="real decide/act/observe"):
        registry.differential_experiment(
            architecture=architecture, task_suite=tasks,
            substrate_variants=variants, tiers=[30])
