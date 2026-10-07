"""EUCLID discovery -> Salamander held-out optimisation bridge.

TheoreticalSpaceExplorer discovers candidates; Salamander owns bounded
self-optimisation. This bridge transfers evidence between those authorities
without letting discovery mutate production directly.

A discovery is never an optimisation merely because it exists. It must have
passed its discovery gate, carry measured baseline/candidate values on a
held-out partition, avoid PYTHIA-final domains, and be independently verified
by AutonomicControlPlane.evaluate_optimization().
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Callable, Mapping

from salamander.control_plane import AutonomicControlPlane
from salamander.models import (
    DatasetPartition,
    OptimizationTrial,
    PolicyLifecycle,
    PolicyVersion,
    digest,
)
from toe.intelligences.authority_boundary import (
    EUCLID_FORBIDDEN_DOMAINS,
    PYTHIA_FINAL_AUTHORITY,
)


class DiscoveryRefused(ValueError):
    """Raised when discovery evidence is insufficient or crosses authority."""


SOURCE_KINDS = frozenset(
    {
        "algorithmic_information",
        "quantum_information",
        "complexity_scaling",
        "emergence",
    }
)

_LOWER_IS_BETTER_TOKENS = (
    "latency",
    "time",
    "error",
    "cost",
    "rmse",
    "loss",
    "stale",
    "reject",
    "unknown",
    "temperature",
    "power",
)


def _normalise_metric(name: str) -> str:
    return str(name).strip().lower().replace("_", "-")


def _forbidden_metric(name: str) -> bool:
    metric = _normalise_metric(name)
    forbidden = EUCLID_FORBIDDEN_DOMAINS | PYTHIA_FINAL_AUTHORITY
    return any(
        metric == domain
        or metric.startswith(domain + "-")
        or metric.endswith("-" + domain)
        or ("-" + domain + "-") in metric
        for domain in forbidden
    )


def higher_is_better(metric: str) -> bool:
    """Conservative metric-direction heuristic recovered from the workstream."""
    name = _normalise_metric(metric)
    return not any(token in name for token in _LOWER_IS_BETTER_TOKENS)


def _payload(value: Any) -> Mapping[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {"value": repr(value)}


@dataclass(frozen=True)
class DiscoveryOptimisationCandidate:
    source_kind: str
    discovery_id: str
    discovery_passed: bool
    baseline_measurements: Mapping[str, float]
    candidate_measurements: Mapping[str, float]
    sample_count: int
    evidence_ref: str
    temporal_lineage: str
    partition: DatasetPartition = DatasetPartition.TEMPORAL_HOLDOUT
    source_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_kind not in SOURCE_KINDS:
            raise DiscoveryRefused(f"unsupported discovery source: {self.source_kind}")
        if not self.discovery_passed:
            raise DiscoveryRefused("failed discovery cannot enter optimisation")
        if not self.discovery_id or not self.evidence_ref or not self.temporal_lineage:
            raise DiscoveryRefused("discovery identity, evidence and temporal lineage are required")
        if self.partition not in {
            DatasetPartition.VALIDATION,
            DatasetPartition.FINAL_TEST,
            DatasetPartition.TEMPORAL_HOLDOUT,
        }:
            raise DiscoveryRefused("optimisation requires a held-out partition")
        if self.sample_count <= 0:
            raise DiscoveryRefused("optimisation requires measured samples")
        baseline = dict(self.baseline_measurements)
        candidate = dict(self.candidate_measurements)
        if not baseline or baseline.keys() != candidate.keys():
            raise DiscoveryRefused(
                "baseline and candidate measurements must be non-empty and identical"
            )
        # OptimizationTrial performs the finite/non-boolean check as well; do
        # it here so refusal occurs before policy construction/registration.
        import math

        for metric, value in {**baseline, **candidate}.items():
            if _forbidden_metric(metric):
                raise DiscoveryRefused(
                    f"metric {metric!r} crosses PYTHIA/consensus authority"
                )
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DiscoveryRefused("optimisation measurements must be finite numbers")
            if not math.isfinite(float(value)):
                raise DiscoveryRefused("optimisation measurements must be finite numbers")

    @classmethod
    def from_output(
        cls,
        source_kind: str,
        output: Any,
        *,
        discovery_passed: bool,
        baseline_measurements: Mapping[str, float],
        candidate_measurements: Mapping[str, float],
        sample_count: int,
        evidence_ref: str,
        temporal_lineage: str,
        partition: DatasetPartition = DatasetPartition.TEMPORAL_HOLDOUT,
        discovery_id: str | None = None,
    ) -> "DiscoveryOptimisationCandidate":
        payload = _payload(output)
        identity = discovery_id or (
            "discovery:"
            + digest(
                "euclid.discovery-output.v1",
                {"source_kind": source_kind, "payload": payload},
            )[:24]
        )
        return cls(
            source_kind=source_kind,
            discovery_id=identity,
            discovery_passed=bool(discovery_passed),
            baseline_measurements=dict(baseline_measurements),
            candidate_measurements=dict(candidate_measurements),
            sample_count=int(sample_count),
            evidence_ref=str(evidence_ref),
            temporal_lineage=str(temporal_lineage),
            partition=partition,
            source_payload=payload,
        )

    def build_trial(self) -> tuple[PolicyVersion, OptimizationTrial]:
        body = {
            "source_kind": self.source_kind,
            "discovery_id": self.discovery_id,
            "source_payload": dict(self.source_payload),
            "baseline": dict(self.baseline_measurements),
            "candidate": dict(self.candidate_measurements),
            "sample_count": self.sample_count,
            "partition": self.partition.value,
            "temporal_lineage": self.temporal_lineage,
        }
        identity = digest("euclid.discovery-optimisation.v1", body)
        policy = PolicyVersion(
            policy_id="euclid-discovery-" + identity[:24],
            artifact_sha256=digest(
                "euclid.discovery-policy-artifact.v1",
                {"discovery": self.discovery_id, "candidate": dict(self.candidate_measurements)},
            ),
            dataset_snapshot_sha256=digest(
                "euclid.discovery-policy-dataset.v1",
                {
                    "lineage": self.temporal_lineage,
                    "baseline": dict(self.baseline_measurements),
                    "sample_count": self.sample_count,
                },
            ),
        )
        trial = OptimizationTrial(
            trial_id="trial-" + identity[:24],
            policy_id=policy.policy_id,
            partition=self.partition,
            baseline_measurements=dict(self.baseline_measurements),
            candidate_measurements=dict(self.candidate_measurements),
            sample_count=self.sample_count,
            evidence_ref=self.evidence_ref,
            temporal_lineage=self.temporal_lineage,
        )
        return policy, trial


class DiscoveryOptimisationBridge:
    """Governed bridge from passed discoveries to held-out policy trials."""

    def __init__(self, control_plane: AutonomicControlPlane) -> None:
        self.control_plane = control_plane

    def evaluate(
        self,
        candidate: DiscoveryOptimisationCandidate,
        verifier: Callable[[OptimizationTrial], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        policy, trial = candidate.build_trial()
        cp = self.control_plane
        cp.register_policy(policy)
        cp.transition_policy(policy.policy_id, PolicyLifecycle.TRAINED, candidate.evidence_ref)
        cp.transition_policy(policy.policy_id, PolicyLifecycle.VALIDATED, candidate.evidence_ref)
        for metric, baseline in candidate.baseline_measurements.items():
            cp.set_baseline(
                metric,
                float(baseline),
                0.0,
                higher_is_better=higher_is_better(metric),
            )
        result = dict(cp.evaluate_optimization(trial, verifier))
        evaluation_ref = str(result.get("verifier_evidence_ref") or candidate.evidence_ref)
        if result.get("accepted") is True:
            for stage in (
                PolicyLifecycle.FINAL_TESTED,
                PolicyLifecycle.SHADOW,
                PolicyLifecycle.CANARY,
                PolicyLifecycle.PROMOTED,
            ):
                cp.transition_policy(policy.policy_id, stage, evaluation_ref)
        else:
            # evaluate_optimization quarantines an unpromoted rejected policy;
            # the intelligence-first contract records the terminal rollback
            # explicitly so a rejected candidate can never be mistaken for an
            # active policy.
            cp.transition_policy(policy.policy_id, PolicyLifecycle.ROLLED_BACK, evaluation_ref)
        return {
            **result,
            "source_kind": candidate.source_kind,
            "discovery_id": candidate.discovery_id,
            "policy_lifecycle": policy.lifecycle.value,
            "authority": "salamander.optimisation",
            "claim_boundary": (
                "discovery proposes; held-out measurement and independent "
                "verification decide; PYTHIA mining truth is untouched"
            ),
        }


__all__ = [
    "DiscoveryOptimisationBridge",
    "DiscoveryOptimisationCandidate",
    "DiscoveryRefused",
    "SOURCE_KINDS",
    "higher_is_better",
]
