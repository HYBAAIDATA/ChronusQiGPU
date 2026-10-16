"""Unit tests for emergence analyzer, criticality signatures, and anti-smoothing logging."""

import pytest
from euclid.emergence.models.telemetry import TelemetryRecord, NoveltyReport
from euclid.emergence.analyzer.discontinuity import detect_discontinuities
from euclid.emergence.analyzer.criticality import criticality_indicators
from euclid.emergence.analyzer.information import integrated_information_proxy
from euclid.emergence.analyzer.complexity import neural_complexity_measure
from euclid.emergence.analyzer.emergence_analyzer import EmergenceAnalyzer


def make_dummy_record(iteration: int, novel_actions: list[str]) -> TelemetryRecord:
    report = NoveltyReport(unattributed=tuple(novel_actions)) if novel_actions else NoveltyReport()
    return TelemetryRecord(
        run_id="run_analyzer_test",
        substrate_id="sub_analyzer",
        iteration_index=iteration,
        task_signature="task_test",
        programmed_actions_used=("step",),
        novel_elements=report,
        invariant_violations=(),
        timestamps={"time": float(iteration)},
        seeds={"rng": 42},
        env_hash="hash",
    ).with_computed_hash()


def test_discontinuity_and_jump_points():
    curve = []
    for i in range(100):
        if i < 50:
            curve.append({"iteration": i, "rate": 2.0})
        elif i == 50:
            curve.append({"iteration": i, "rate": 50.0})
        else:
            curve.append({"iteration": i, "rate": 52.0})

    jump_points = detect_discontinuities(curve, threshold_multiplier=2.0)
    assert len(jump_points) > 0
    assert any(jp["iteration"] == 50 for jp in jump_points)


def test_criticality_indicators():
    records = []
    burst_pattern = [1, 1, 2, 1, 4, 1, 8, 2, 1, 3, 1, 12, 2, 1, 1]
    for i, burst in enumerate(burst_pattern):
        records.append(make_dummy_record(i * 2, [f"novel_action_{j}" for j in range(burst)]))
        records.append(make_dummy_record(i * 2 + 1, []))

    crit = criticality_indicators(records)
    assert "power_law_alpha" in crit
    assert "branching_ratio" in crit
    assert "ks_statistic" in crit
    assert crit["avalanche_count"] >= 10


def test_integrated_information_and_complexity():
    records = []
    for i in range(20):
        actions = ["explore_step", "evaluate_state"] if i % 2 == 0 else ["emergent_synthesis", "evaluate_state"]
        records.append(make_dummy_record(i, actions))

    phi = integrated_information_proxy(records)
    complexity = neural_complexity_measure(records)

    assert isinstance(phi, float)
    assert isinstance(complexity, float)


def test_anti_smoothing_logging_requirement():
    analyzer = EmergenceAnalyzer()
    records = [
        make_dummy_record(0, ["a"]),
        make_dummy_record(1, []),
        make_dummy_record(2, ["a", "b"]),
        make_dummy_record(3, []),
        make_dummy_record(4, ["a", "b", "c"]),
    ]

    scan_result = analyzer.phase_transition_scan([records])
    assert scan_result["runs_analyzed"] == 1
    assert len(analyzer.verbatim_audit_logs) == 1

    logged_run = analyzer.verbatim_audit_logs[0]
    assert logged_run["smoothing_applied"] is False
    assert "raw_curve" in logged_run
