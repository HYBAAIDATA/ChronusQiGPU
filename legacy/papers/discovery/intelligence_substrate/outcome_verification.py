"""Outcome verification and economic evidence framework for HYBA agreements.

This module is intentionally conservative: it records observations, computes
comparisons, and classifies claims from evidence. It never treats an asserted
improvement as real unless a reproducible baseline, intervention, measurement,
and economic model support it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json
import math
import statistics
from typing import Any, Dict, Mapping


class ClaimClass(str, Enum):
    PROVEN = "PROVEN"
    MEASURED = "MEASURED"
    SUPPORTED = "SUPPORTED"
    HYPOTHESIS = "HYPOTHESIS"
    UNTESTED = "UNTESTED"
    DISPROVEN = "DISPROVEN"


@dataclass(frozen=True)
class MeasurementSeries:
    name: str
    unit: str
    samples: tuple[float, ...]

    def stats(self, confidence: float = 0.95) -> dict[str, float | int | None]:
        if not self.samples:
            return {
                "n": 0,
                "mean": None,
                "median": None,
                "variance": None,
                "ci_low": None,
                "ci_high": None,
                "p95": None,
            }
        values = sorted(self.samples)
        n = len(values)
        mean = statistics.fmean(values)
        variance = statistics.variance(values) if n > 1 else 0.0
        z = 1.96 if confidence == 0.95 else 1.0
        half_width = z * math.sqrt(variance / n) if n > 1 else 0.0
        p95_index = min(n - 1, math.ceil(0.95 * n) - 1)
        return {
            "n": n,
            "mean": mean,
            "median": statistics.median(values),
            "variance": variance,
            "ci_low": mean - half_width,
            "ci_high": mean + half_width,
            "p95": values[p95_index],
        }


@dataclass(frozen=True)
class BaselineDefinition:
    time_period: str
    workload: str
    dataset: str
    environment: str
    hardware: str
    software_versions: Mapping[str, str]
    configuration: Mapping[str, Any]
    measurement_method: str

    def missing_fields(self) -> list[str]:
        required = {
            "time_period": self.time_period,
            "workload": self.workload,
            "dataset": self.dataset,
            "environment": self.environment,
            "hardware": self.hardware,
            "measurement_method": self.measurement_method,
        }
        return [name for name, value in required.items() if not value]


@dataclass(frozen=True)
class InterventionDefinition:
    description: str
    hyba_components: tuple[str, ...]
    change_window: str
    configuration_delta: Mapping[str, Any]
    operator: str


@dataclass(frozen=True)
class ExperimentDesign:
    design_type: str
    comparison_method: str
    confounders: tuple[str, ...] = ()
    independent_verification_path: str = ""


@dataclass(frozen=True)
class EconomicModel:
    storage: float = 0.0
    compute: float = 0.0
    network: float = 0.0
    operations: float = 0.0
    licensing: float = 0.0
    other: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.storage
            + self.compute
            + self.network
            + self.operations
            + self.licensing
            + self.other
        )


@dataclass(frozen=True)
class OutcomeAgreement:
    agreement_id: str
    agreed_percentage: float
    baseline: BaselineDefinition
    intervention: InterventionDefinition
    experiment: ExperimentDesign
    baseline_cost: EconomicModel
    hyba_cost: EconomicModel
    assumptions: tuple[str, ...] = ()

    def verified_savings(self) -> float:
        return self.baseline_cost.total - self.hyba_cost.total

    def outcome_fee(self) -> float:
        return max(0.0, self.agreed_percentage * self.verified_savings())


@dataclass
class EvidencePackage:
    agreement: OutcomeAgreement
    baseline_measurements: list[MeasurementSeries]
    hyba_measurements: list[MeasurementSeries]
    methodology: str
    raw_measurement_refs: list[str]
    limitations: list[str] = field(default_factory=list)
    claim_definitions: dict[str, str] = field(default_factory=dict)

    def comparison(self) -> dict[str, dict[str, Any]]:
        hyba_by_name = {m.name: m for m in self.hyba_measurements}
        out: dict[str, dict[str, Any]] = {}
        for base in self.baseline_measurements:
            if base.name not in hyba_by_name:
                continue
            base_stats = base.stats()
            hyba_stats = hyba_by_name[base.name].stats()
            base_mean = base_stats["mean"]
            hyba_mean = hyba_stats["mean"]
            delta = None if base_mean is None or hyba_mean is None else base_mean - hyba_mean
            reduction = None if not base_mean or delta is None else delta / base_mean
            out[base.name] = {
                "unit": base.unit,
                "baseline": base_stats,
                "hyba": hyba_stats,
                "delta": delta,
                "relative_reduction": reduction,
            }
        return out

    def classify_claim(self, claim_name: str, expected_direction: str = "decrease") -> ClaimClass:
        if claim_name not in self.comparison():
            return ClaimClass.UNTESTED
        if self.agreement.baseline.missing_fields() or not self.raw_measurement_refs:
            return ClaimClass.HYPOTHESIS
        result = self.comparison()[claim_name]
        delta = result["delta"]
        if delta is None:
            return ClaimClass.UNTESTED
        improved = delta > 0 if expected_direction == "decrease" else delta < 0
        if not improved:
            return ClaimClass.DISPROVEN
        if self.agreement.experiment.confounders:
            return ClaimClass.MEASURED
        if self.agreement.experiment.independent_verification_path:
            return ClaimClass.PROVEN
        return ClaimClass.SUPPORTED

    def report(self) -> dict[str, Any]:
        payload = {
            "agreement": asdict(self.agreement),
            "baseline_completeness_errors": self.agreement.baseline.missing_fields(),
            "methodology": self.methodology,
            "claim_definitions": self.claim_definitions,
            "comparison": self.comparison(),
            "confounders": list(self.agreement.experiment.confounders),
            "financial_translation": {
                "baseline_cost": self.agreement.baseline_cost.total,
                "hyba_cost": self.agreement.hyba_cost.total,
                "verified_savings": self.agreement.verified_savings(),
                "agreed_percentage": self.agreement.agreed_percentage,
                "commercial_amount_payable": self.agreement.outcome_fee(),
                "assumptions": list(self.agreement.assumptions),
            },
            "limitations": self.limitations,
            "claim_classification": {
                name: self.classify_claim(name).value for name in self.comparison()
            },
        }
        payload["signature"] = sign_report(payload)
        return payload

    def to_evidence_event(
        self, tenant_id: str = "tenant-default", entitlement_id: str = "ent-unbound"
    ) -> Any:
        from al_haras_assurance.core import EvidenceEvent

        rep = self.report()
        return EvidenceEvent(
            tenant_id=tenant_id,
            event_type="workload_event",
            actor="outcome_verification_engine",
            subject=self.agreement.agreement_id,
            action="verify_outcome",
            capability="outcome_verification",
            configuration_ref=f"entitlement:{entitlement_id}",
            mechanism="EvidencePackage.to_evidence_event",
            owner="hyba_outcome_verification_plane",
            data={
                "agreement_id": self.agreement.agreement_id,
                "verified_savings": rep["financial_translation"]["verified_savings"],
                "commercial_payable": rep["financial_translation"]["commercial_amount_payable"],
                "claim_classification": rep["claim_classification"],
                "report_signature": rep.get("signature"),
            },
        )

    def export_to_ledger(
        self, ledger: Any, tenant_id: str = "tenant-default", entitlement_id: str = "ent-unbound"
    ) -> dict[str, Any]:
        event = self.to_evidence_event(tenant_id=tenant_id, entitlement_id=entitlement_id)
        return ledger.append(event)


def sign_report(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


DEFAULT_CLAIM_DEFINITIONS = {
    "lossless": "decoded(encode(x)) = x",
    "bit_exact": "bit_pattern(decoded(encode(x))) = bit_pattern(x)",
    "numerical": "||x - x_hat|| <= epsilon",
    "encoded_storage_reduction": "1 - encoded_bytes_hyba / encoded_bytes_baseline, measured on identical input corpus",
    "physical_storage_reduction": "1 - allocated_physical_bytes_hyba / allocated_physical_bytes_baseline, measured on the target storage layer",
    "tco_reduction": "1 - total_hyba_cost / total_baseline_cost, including integration and operations",
}


@dataclass(frozen=True)
class Dataset:
    size_bytes: int
    rows: int
    name: str = "dataset"


@dataclass(frozen=True)
class VerificationResult:
    classification: str
    reduction_ratio: float
    verified: bool
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def actual_ratio(self) -> float:
        return self.reduction_ratio


class OutcomeVerificationEngine:
    """Evaluates empirical datasets and classifies outcomes against claim boundaries."""

    def verify_storage_reduction(
        self, baseline: Dataset, folded: Dataset, claimed_reduction: float = 10.0
    ) -> VerificationResult:
        if baseline.size_bytes <= 0:
            return VerificationResult("UNTESTED", 0.0, False, {"error": "Invalid baseline size"})

        ratio = baseline.size_bytes / max(1, folded.size_bytes)
        verified = ratio >= claimed_reduction

        if verified and ratio >= 10.0:
            classification = "PROVEN"
        elif verified:
            classification = "MEASURED"
        else:
            classification = "DISPROVEN"

        return VerificationResult(
            classification=classification,
            reduction_ratio=ratio,
            verified=verified,
            details={
                "baseline_bytes": baseline.size_bytes,
                "folded_bytes": folded.size_bytes,
                "ratio": ratio,
            },
        )
