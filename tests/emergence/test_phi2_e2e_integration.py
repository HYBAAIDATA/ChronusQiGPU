"""End-to-end integration test for the Philos (Phi-2) cognitive architecture and EQS pipeline."""

import pytest
from euclid.emergence.models.condensation import ColonyConfig, CondensationEvent
from euclid.emergence.models.manifest import CapabilityManifest
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.cultivator.colony import AgentColony, AgentColonies
from euclid.emergence.cultivator.cultivator import CondensationCultivator
from euclid.emergence.folding.recursive_folding import RecursiveFolding
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.substrate.registry import SubstrateRegistry
from euclid.emergence.trusted_core.access_control import GovernanceToken
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService
from euclid.emergence.condensation.condensation_monitor import CondensationMonitor
from euclid.emergence.condensation.governance import ConsortiumGovernance


def test_philos_phi2_full_condensation_pipeline():
    # 1. Initialize Substrate Registry and Trusted Core EQS
    registry = SubstrateRegistry()
    eq_service = EmergentQualificationService()
    gov_token = GovernanceToken.issue("assurance_officer_primary", eq_service.governance_secret_key)

    # 2. Register distinct substrate variants
    sid_sync = registry.register(
        executor_type="sync_metal",
        observation_latency=4.0,
        action_granularity="atomic",
        compute_substrate="baremetal_x86",
        sandbox_id="box_metal",
    )
    sid_async = registry.register(
        executor_type="async_distributed",
        observation_latency=20.0,
        action_granularity="compositional",
        compute_substrate="cloud_arm64",
        sandbox_id="box_cloud",
    )

    exec_sync = StandardSyncExecutor(registry.get_properties(sid_sync))
    exec_async = AsyncIsolatedExecutor(registry.get_properties(sid_async))

    # 3. Condensation Cultivator: initialize colonies across complexity axes
    cultivator = CondensationCultivator(registry=registry)
    colonies = AgentColonies([
        AgentColony(ColonyConfig("colony_alpha", interaction_topology="mesh")),
        AgentColony(ColonyConfig("colony_beta", interaction_topology="recursive_folding", observation_depth="depth_2_meta")),
    ])

    cultivated_population = cultivator.cultivate(colonies, generations=2, iterations_per_regime=25)
    assert len(cultivated_population) == 2

    # 4. Recursive Folding (Phi mechanism) with budgeted recursion
    top_colony = cultivated_population.colonies[0]
    folding = RecursiveFolding(eq_service=eq_service)
    fold_outcomes = list(folding.fold(
        agent=top_colony,
        depth=1,
        executor_A=exec_sync,
        executor_B=exec_async,
        governance_token=gov_token,
    ))
    assert len(fold_outcomes) > 0

    # 5. Condensation Monitor: watch telemetry stream
    monitor = CondensationMonitor(
        eq_service=eq_service,
        registry=registry,
        confidence_threshold=0.60,
    )

    # Verify stream scanning
    stream_events = list(monitor.watch(
        top_colony.telemetry_records,
        window_size=10,
        confirmed_substrates=[sid_sync, sid_async],
        colony_target=top_colony,
    ))
    assert len(stream_events) > 0

    # 6. Simulate Cross-Substrate Condensation Event & Consortium Governance Adjudication
    scan_evidence = monitor.analyzer.phase_transition_scan([top_colony.telemetry_records])
    condensation_event = CondensationEvent(
        evidence=scan_evidence,
        substrates=[sid_sync, sid_async],
    )

    consortium = ConsortiumGovernance(journal=eq_service.journal)
    verdict = consortium.adjudicate(
        event=condensation_event,
        reviewers=["dr_turing", "prof_neumann", "dr_shannon"],
        reviewer_votes=[True, True, True],
        notes="Verified multi-substrate phase-transition without Goodhart metric gaming",
    )

    assert verdict.confirmed is True
    assert verdict.promoted_status == "QUALIFIED_HYPOTHESIS"

    # 7. Verify Immutable Journal Chaining
    valid_chain, chain_err = eq_service.journal.verify_chain()
    assert valid_chain
    assert chain_err is None
    entries = eq_service.journal.get_entries()
    assert any(e.action == "ADJUDICATION_VERDICT" for e in entries)
