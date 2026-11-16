"""Exact software frontier witnesses; physical science claims remain unverified."""
from __future__ import annotations
from hashlib import sha256
from typing import Sequence

from chronus.geodesic.benchmarks import benchmark
from chronus.geodesic.discovery import MetricConstraint, ManifoldDiscovery, is_spd
from chronus.geodesic.problems import FiniteProblem
from chronus.storage.phyllotaxis import (
    fibonacci_cassini_witness, phyllotaxis_coordinate,
)


def logical_storage_witness(sequence: int, content: bytes, lanes: int = 32) -> dict:
    """Cassini and logical spiral coordinates; neither physical storage nor ECC."""
    if type(sequence) is not int or sequence < 1:
        raise ValueError("positive sequence required")
    if not isinstance(content, bytes) or not content:
        raise ValueError("nonempty source bytes required")
    if type(lanes) is not int or not 1 <= lanes <= 4096:
        raise ValueError("lane count outside policy")
    digest = sha256(content).digest()
    coordinate = phyllotaxis_coordinate(sequence, digest, lanes)
    identity = fibonacci_cassini_witness(sequence)
    if identity != (-1 if sequence % 2 else 1) or not 0 <= coordinate.lane < lanes:
        raise AssertionError("mathematical storage invariant failed")
    return {
        "schema": "chronus.frontier.logical-storage/1",
        "classification": "EXACT_LOGICAL_WITNESS",
        "source_sha256": digest.hex(),
        "coordinate": coordinate.to_dict(),
        "cassini_witness": identity,
        "physical_placement_verified": False,
        "payload_error_corrected": False,
        "phi_optimal_physical_packing_verified": False,
    }


def metric_descent_witness(
    constraints: Sequence[MetricConstraint], dimension: int, max_steps: int = 8,
) -> dict:
    """Reuse exact rational SPD metric learner; no global Riemannian-flow claim."""
    if type(dimension) is not int or not 1 <= dimension <= 11:
        raise ValueError("dimension outside bounded policy")
    result = ManifoldDiscovery(dimension).learn_metric(constraints, max_steps=max_steps)
    if not is_spd(result.metric) or result.objective > result.initial_objective:
        raise AssertionError("SPD descent invariant failed")
    return {
        "schema": "chronus.frontier.metric-descent/1",
        "classification": "EXACT_RATIONAL_CONSTANT_METRIC",
        "dimension": dimension,
        "input_constraint_count": len(constraints),
        "metric": [[str(c) for c in row] for row in result.metric],
        "objective": str(result.objective),
        "initial_objective": str(result.initial_objective),
        "steps": result.steps,
        "stationary": result.stationary,
        "spd_verified": True,
        "monotone_descent_verified": result.objective <= result.initial_objective,
        "arbitrary_riemannian_flow_claimed": False,
        "metric_optimality_proven": False,
    }


def finite_search_witness(
    problem: FiniteProblem, *, repetitions: int = 3,
    git_commit: str = "UNAVAILABLE",
) -> dict:
    """Equal-work exhaustive A/B; never claim O(log N) from reordering."""
    result = benchmark(
        problem, repetitions=repetitions, git_commit=git_commit,
        input_classification="OPERATOR_DECLARED_OR_EXPLICIT_TEST_FIXTURE",
    )
    n = problem.domain_size
    if not result["same_oracle_call_count_verified"]:
        raise AssertionError("equal oracle calls required")
    if any(trial["oracle_calls"] != n for trial in result["trials"]):
        raise AssertionError("exhaustive trial skipped candidates")
    return {
        "schema": "chronus.frontier.finite-search/1",
        "classification": "EXACT_EXHAUSTIVE_SOFTWARE_REFERENCE",
        "benchmark": result,
        "asymptotic_logarithmic_search_proven": False,
        "physical_quantum_advantage_proven": False,
        "unknown_target_geodesic_discovery_proven": False,
    }


def physical_claim_gate() -> dict:
    """Never fill physical evidence fields from software identities."""
    return {
        "schema": "chronus.frontier.physical-claims/1",
        "qualification": "UNAVAILABLE",
        "phi_optimal_physical_packing": "UNVERIFIED",
        "device_bound_phyllotaxis": "UNVERIFIED",
        "raw_physical_device_iops": "UNVERIFIED",
        "thermodynamic_entropy_per_operation": "UNVERIFIED",
        "h4_hardware_manifold": "UNVERIFIED",
        "quantum_decoherence": "NOT_APPLICABLE_TO_CLASSICAL_TABLEAU",
        "o_log_n_geodesic_search": "UNVERIFIED",
        "large_scale_universal_quantum_advantage": "UNVERIFIED",
        "evidence_must_be_actual_and_independently_verified": True,
    }
