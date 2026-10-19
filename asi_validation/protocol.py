"""Fail-closed evaluation of the preregistered ASI validation matrix.

This module evaluates evidence produced by benchmark runners.  It never invents
measurements: an omitted endpoint makes a domain ``NOT_RUN``, not a pass.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class Criterion:
    metric: str
    operator: str
    threshold: float | bool
    unit: str


@dataclass(frozen=True)
class CriterionResult:
    metric: str
    operator: str
    threshold: float | bool
    observed: float | bool | None
    unit: str
    passed: bool | None


@dataclass(frozen=True)
class DomainResult:
    domain: str
    status: Status
    criteria: tuple[CriterionResult, ...]


def _c(metric: str, operator: str, threshold: float | bool, unit: str = "") -> Criterion:
    return Criterion(metric, operator, threshold, unit)


# Metric names include their aggregation semantics so producers cannot silently
# substitute a best run for a required mean, minimum, maximum, or run count.
PROTOCOL: dict[str, tuple[Criterion, ...]] = {
    "B1_ARC_AGI": (_c("accuracy_pct", ">", 50, "%"), _c("energy_ratio_vs_classical", "<", 0.01), _c("tts_cv_pct", "<", 2, "%"), _c("runs", ">=", 10, "runs")),
    "B2_MMLU": (_c("accuracy_pct", ">", 75, "%"), _c("stem_accuracy_pct", ">", 80, "%"), _c("energy_per_point_ratio", "<", 0.1), _c("accuracy_cv_pct", "<", 1, "%"), _c("runs", ">=", 10, "runs")),
    "B3_MATH": (_c("accuracy_pct", ">", 60, "%"), _c("hardest_tier_accuracy_pct", ">", 40, "%"), _c("exact_derivation_pct", "==", 100, "%"), _c("identical_output_pct", "==", 100, "%"), _c("runs", ">=", 10, "runs")),
    "B4_GPQA": (_c("accuracy_pct", ">", 50, "%"), _c("physics_accuracy_pct", ">", 60, "%"), _c("chemistry_accuracy_pct", ">", 50, "%"), _c("reasoning_traces_verified", "==", True), _c("identical_answers", "==", True), _c("runs", ">=", 10, "runs")),
    "B5_BBH": (_c("accuracy_pct", ">", 75, "%"), _c("five_step_accuracy_pct", ">", 70, "%"), _c("accuracy_cv_pct", "<", 2, "%"), _c("runs", ">=", 10, "runs")),
    "A_SEARCH": (_c("lucas_r2", ">=", 0.95), _c("exponential_r2", "<=", 0.85), _c("speedup_20_bit", ">=", 100), _c("speedup_30_bit", ">=", 10_000), _c("energy_speedup_exceeds_time", "==", True), _c("loglog_beta", "<", 0.2), _c("tts_cv_pct", "<", 2, "%"), _c("trials_per_difficulty", ">=", 10_000, "trials")),
    "B_MEMORY": (_c("byte_differences", "==", 0, "bytes"), _c("hashes_identical", "==", True), _c("decimal_digit_variations", "==", 0, "digits"), _c("throughput_mb_s", ">", 500, "MB/s"), _c("energy_ratio_vs_zstd", "<", 0.1), _c("runs", ">=", 100, "runs")),
    "B2_PISOT": (_c("alpha_absolute_error", "<", 1e-12), _c("classification_latency_ms", "<", 100, "ms"), _c("false_positives", "==", 0), _c("agreement_pct", "==", 100, "%"), _c("sweeps", ">=", 10_000, "sweeps")),
    "C_DEDUCTION": (_c("discovery_cycles", "<", 1_000, "cycles"), _c("alignment_r2", ">", 0.999), _c("speedup_vs_rl", ">", 10_000), _c("energy_speedup_vs_rl", ">", 10_000), _c("holdout_accuracy_pct", "==", 100, "%"), _c("discovery_cv_pct", "<", 1, "%"), _c("runs", ">=", 100, "runs")),
    "D_ISOMORPHISM": (_c("link_cycles", "<", 50_000_000, "cycles"), _c("protein_rmsd_angstrom", "<", 2, "angstrom"), _c("compression_error_pct", "<=", 1, "%"), _c("coherence_r2", ">", 0.9), _c("transfer_latency_ms", "<", 500, "ms"), _c("zero_prompt", "==", True), _c("energy_ratio_vs_classical", "<", 0.01), _c("success_pct", "==", 100, "%"), _c("runs", ">=", 100, "runs")),
    "E_AUTONOMY": (_c("pivot_latency_ms", "<", 500, "ms"), _c("minimum_phi_one_hour", ">=", 0.6), _c("resource_reallocated", "==", True), _c("energy_deviation_pct", "<=", 10, "%"), _c("external_prompts", "==", 0), _c("survival_pct", "==", 100, "%"), _c("runs", ">=", 100, "runs")),
    "F_ANESTHESIA": (_c("phi_drop", ">", 0.3), _c("detection_latency_ms", "<=", 1_000, "ms"), _c("recovery_is_logarithmic", "==", True), _c("information_loss_pct", "<", 10, "%"), _c("biological_pearson_r", ">", 0.8), _c("fibonacci_frequency_error_pct", "<=", 5, "%"), _c("healing_autonomous", "==", True), _c("performance_r2", ">=", 0.85), _c("performance_p", "<", 0.001), _c("energy_baseline_error_pct", "<=", 5, "%"), _c("recovery_pct", ">=", 95, "%"), _c("runs", ">=", 100, "runs")),
    "T1_ENERGY": (_c("lucas_energy_r2", ">=", 0.95), _c("energy_ratio_vs_classical", "<", 0.01), _c("steady_power_cv_pct", "<", 5, "%"), _c("energy_cv_pct", "<", 2, "%"), _c("runs", ">=", 100, "runs")),
    "T2_THERMAL": (_c("complexity_before_throttle_ratio", ">=", 10), _c("hyba_gflop_watt", ">", 10, "GFLOP/W"), _c("classical_gflop_watt", "<", 1, "GFLOP/W"), _c("identical_throttle_points", "==", True), _c("runs", ">=", 10, "runs")),
    "T3_MONITORING": (_c("external_meter_present", "==", True), _c("component_meter_present", "==", True), _c("pdu_meter_present", "==", True), _c("time_synchronized", "==", True), _c("continuous_samples", ">", 0, "samples"), _c("energy_integrated", "==", True)),
    "G_ENTROPY": (_c("byte_differences", "==", 0, "bytes"), _c("faster_than_zstd", "==", True), _c("memory_ratio", "<", 1.5), _c("energy_ratio_vs_zstd", "<", 0.1), _c("identical_hash_pct", "==", 100, "%"), _c("runs", ">=", 10, "runs")),
    "H_COHERENCE": (_c("phi_at_100k", ">", 0.7), _c("consensus_latency_ms", "<", 10, "ms"), _c("linear_throughput", "==", True), _c("lucas_energy_scaling", "==", True), _c("runs_per_node_count", ">=", 10, "runs")),
    "I_RECOVERY": (_c("recovery_seconds", "<", 5, "s"), _c("data_loss_bytes", "==", 0, "bytes"), _c("phi_after_10_seconds", ">", 0.6), _c("success_pct", "==", 100, "%"), _c("runs", ">=", 100, "runs")),
}


def _compare(observed: float | bool, operator: str, threshold: float | bool) -> bool:
    operations = {
        "<": lambda: observed < threshold,
        "<=": lambda: observed <= threshold,
        ">": lambda: observed > threshold,
        ">=": lambda: observed >= threshold,
        "==": lambda: observed == threshold,
    }
    try:
        return bool(operations[operator]())
    except KeyError as error:
        raise ValueError(f"unsupported operator: {operator}") from error


def evaluate_domain(domain: str, observations: Mapping[str, float | bool]) -> DomainResult:
    """Evaluate one domain, treating missing or invalid observations as NOT_RUN."""
    if domain not in PROTOCOL:
        raise KeyError(f"unknown protocol domain: {domain}")
    results: list[CriterionResult] = []
    missing = False
    for criterion in PROTOCOL[domain]:
        observed = observations.get(criterion.metric)
        valid_type = isinstance(observed, bool) if isinstance(criterion.threshold, bool) else isinstance(observed, (int, float)) and not isinstance(observed, bool)
        valid_number = valid_type and (isinstance(observed, bool) or math.isfinite(float(observed)))
        if not valid_number:
            missing = True
            passed = None
            observed = None
        else:
            passed = _compare(observed, criterion.operator, criterion.threshold)
        results.append(CriterionResult(criterion.metric, criterion.operator, criterion.threshold, observed, criterion.unit, passed))
    status = Status.NOT_RUN if missing else (Status.PASS if all(item.passed for item in results) else Status.FAIL)
    return DomainResult(domain, status, tuple(results))


def evaluate_matrix(evidence: Mapping[str, Mapping[str, float | bool]]) -> dict[str, object]:
    results = [evaluate_domain(domain, evidence.get(domain, {})) for domain in PROTOCOL]
    counts = {status.value: sum(result.status is status for result in results) for status in Status}
    return {"schema_version": 1, "counts": counts, "results": [{**asdict(result), "status": result.status.value} for result in results]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate ASI validation evidence without filling missing data")
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    report = evaluate_matrix(evidence)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if report["counts"][Status.FAIL.value] else 2 if report["counts"][Status.NOT_RUN.value] else 0


if __name__ == "__main__":
    raise SystemExit(main())
