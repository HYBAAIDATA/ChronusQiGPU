"""Discovery -> self-optimisation integration contract."""
from __future__ import annotations

import math

import numpy as np
import pytest

from euclid.explorer import TheoreticalSpaceExplorer
from salamander.control_plane import ActionRegistry, AutonomicControlPlane
from salamander.discovery_optimisation import (
    DiscoveryOptimisationBridge,
    DiscoveryOptimisationCandidate,
    DiscoveryRefused,
    SOURCE_KINDS,
    higher_is_better,
)
from salamander.models import DatasetPartition, PolicyLifecycle


def _candidate(**overrides):
    values = {
        "source_kind": "complexity_scaling",
        "discovery_id": "disc-1",
        "discovery_passed": True,
        "baseline_measurements": {"throughput": 10.0},
        "candidate_measurements": {"throughput": 12.0},
        "sample_count": 8,
        "evidence_ref": "discovery:evidence:1",
        "temporal_lineage": "window-1",
        "partition": DatasetPartition.TEMPORAL_HOLDOUT,
        "source_payload": {"kind": "test"},
    }
    values.update(overrides)
    return DiscoveryOptimisationCandidate(**values)


@pytest.mark.parametrize("source_kind", sorted(SOURCE_KINDS))
def test_all_four_frontiers_construct(source_kind):
    assert _candidate(source_kind=source_kind).source_kind == source_kind


def test_failed_discovery_refused():
    with pytest.raises(DiscoveryRefused):
        _candidate(discovery_passed=False)


@pytest.mark.parametrize("partition", [DatasetPartition.TRAIN, DatasetPartition.INCIDENT])
def test_non_holdout_partitions_refused(partition):
    with pytest.raises(DiscoveryRefused):
        _candidate(partition=partition)


@pytest.mark.parametrize(
    "baseline,candidate",
    [
        ({}, {}),
        ({"a": 1.0}, {"b": 2.0}),
    ],
)
def test_measurement_keys_must_match(baseline, candidate):
    with pytest.raises(DiscoveryRefused):
        _candidate(baseline_measurements=baseline, candidate_measurements=candidate)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True])
def test_non_finite_or_boolean_measurements_refused(bad):
    with pytest.raises(DiscoveryRefused):
        _candidate(
            baseline_measurements={"throughput": 1.0},
            candidate_measurements={"throughput": bad},
        )


@pytest.mark.parametrize(
    "metric",
    [
        "sha256d",
        "target",
        "share_validation",
        "credentials",
        "submission",
        "pool_acknowledgement",
        "nonce_semantics",
        "bitcoin_header",
    ],
)
def test_forbidden_mining_truth_metrics_refused(metric):
    with pytest.raises(DiscoveryRefused):
        _candidate(
            baseline_measurements={metric: 1.0},
            candidate_measurements={metric: 2.0},
        )


@pytest.mark.parametrize(
    "metric",
    ["latency_ms", "error_rate", "cost", "rmse", "stale_ratio", "temperature_c"],
)
def test_lower_is_better_heuristic(metric):
    assert higher_is_better(metric) is False


@pytest.mark.parametrize("metric", ["throughput", "yield", "availability", "quality"])
def test_higher_is_better_default(metric):
    assert higher_is_better(metric) is True


def test_trial_ids_are_content_derived():
    first = _candidate().build_trial()
    second = _candidate().build_trial()
    assert first[0].policy_id == second[0].policy_id
    assert first[1].trial_id == second[1].trial_id


def test_accepted_trial_walks_complete_lifecycle():
    cp = AutonomicControlPlane(registry=ActionRegistry())
    bridge = DiscoveryOptimisationBridge(cp)
    result = bridge.evaluate(
        _candidate(),
        lambda _trial: {"verified": True, "evidence_ref": "independent:ok"},
    )
    assert result["accepted"] is True
    assert result["policy_lifecycle"] == PolicyLifecycle.PROMOTED.value
    assert cp.ledger.verify()


def test_rejected_trial_rolls_back():
    cp = AutonomicControlPlane(registry=ActionRegistry())
    bridge = DiscoveryOptimisationBridge(cp)
    result = bridge.evaluate(
        _candidate(candidate_measurements={"throughput": 8.0}),
        lambda _trial: {"verified": True, "evidence_ref": "independent:regression"},
    )
    assert result["accepted"] is False
    assert result["policy_lifecycle"] == PolicyLifecycle.ROLLED_BACK.value


def test_independent_evidence_required():
    cp = AutonomicControlPlane(registry=ActionRegistry())
    bridge = DiscoveryOptimisationBridge(cp)
    with pytest.raises(Exception):
        bridge.evaluate(
            _candidate(),
            lambda _trial: {"verified": True, "evidence_ref": ""},
        )


def test_latency_improvement_is_accepted():
    cp = AutonomicControlPlane(registry=ActionRegistry())
    bridge = DiscoveryOptimisationBridge(cp)
    result = bridge.evaluate(
        _candidate(
            baseline_measurements={"latency_ms": 10.0},
            candidate_measurements={"latency_ms": 8.0},
        ),
        lambda _trial: {"verified": True, "evidence_ref": "independent:latency"},
    )
    assert result["accepted"] is True


def test_multiple_metrics_require_no_regression():
    cp = AutonomicControlPlane(registry=ActionRegistry())
    bridge = DiscoveryOptimisationBridge(cp)
    result = bridge.evaluate(
        _candidate(
            baseline_measurements={"throughput": 10.0, "latency_ms": 10.0},
            candidate_measurements={"throughput": 12.0, "latency_ms": 9.0},
        ),
        lambda _trial: {"verified": True, "evidence_ref": "independent:multi"},
    )
    assert result["accepted"] is True


def test_complexity_explorer_output_can_feed_trial():
    explorer = TheoreticalSpaceExplorer()
    evidence = explorer.verify_complexity_evidence(
        [1, 2, 4, 8],
        [1, 4, 16, 64],
        [1, 2, 4, 8],
    )
    candidate = DiscoveryOptimisationCandidate.from_output(
        "complexity_scaling",
        evidence,
        discovery_passed=True,
        baseline_measurements={"verification_cost": 10.0},
        candidate_measurements={"verification_cost": 8.0},
        sample_count=4,
        evidence_ref="euclid:complexity",
        temporal_lineage="complexity-heldout-1",
    )
    assert candidate.source_payload["preferred_empirical_model"] in {
        "polynomial",
        "exponential",
    }


def test_validated_discovery_can_feed_trial():
    explorer = TheoreticalSpaceExplorer(seed=7)
    validation = explorer.validate_discovery(
        [2.0, 2.1, 2.2, 2.15],
        [1.0, 1.0, 1.0, 1.0],
        permutations=200,
        min_effect=0.1,
        max_p_value=1.0,
        min_reproducibility=0.0,
    )
    candidate = DiscoveryOptimisationCandidate.from_output(
        "emergence",
        validation,
        discovery_passed=validation.passed_pre_registered_thresholds,
        baseline_measurements={"quality": 1.0},
        candidate_measurements={"quality": 1.1},
        sample_count=4,
        evidence_ref=validation.protocol_hash,
        temporal_lineage="emergence-heldout-1",
    )
    assert candidate.discovery_passed is True


def test_quantum_frontier_payload_is_data_not_authority():
    explorer = TheoreticalSpaceExplorer()
    states = []
    for theta in (0.0, 0.5, 1.0):
        psi = np.array([np.cos(theta), 0.0, 0.0, np.sin(theta)], dtype=complex)
        psi /= np.linalg.norm(psi)
        states.append(np.outer(psi, psi.conjugate()))
    report = explorer.detect_quantum_phase_transitions(states, [0.0, 0.5, 1.0], (2, 2))
    candidate = DiscoveryOptimisationCandidate.from_output(
        "quantum_information",
        report,
        discovery_passed=True,
        baseline_measurements={"model_quality": 1.0},
        candidate_measurements={"model_quality": 1.1},
        sample_count=3,
        evidence_ref="euclid:quantum-sim",
        temporal_lineage="quantum-heldout-1",
    )
    assert "not proof" in candidate.source_payload["claim_boundary"].lower()


def test_compression_frontier_payload_can_feed_candidate():
    evidence = TheoreticalSpaceExplorer.compression_evidence({"a": [1, 2, 3]})
    candidate = DiscoveryOptimisationCandidate.from_output(
        "algorithmic_information",
        evidence,
        discovery_passed=True,
        baseline_measurements={"storage_cost": 100.0},
        candidate_measurements={"storage_cost": 90.0},
        sample_count=3,
        evidence_ref=evidence["sha256"],
        temporal_lineage="compression-heldout-1",
    )
    assert candidate.source_payload["compressed_bytes"] > 0
