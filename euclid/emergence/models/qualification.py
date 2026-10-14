"""Qualification outcome models and gate artifacts for trusted-core qualification."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Union


class QualificationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class GateResult:
    """Outcome of evaluating an individual qualification gate."""
    gate_name: str
    passed: bool
    details: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class QualifiedEmergent:
    """Certificate of qualification for an emergent capability."""
    candidate_id: str
    capability_name: str
    status: QualificationStatus = QualificationStatus.QUALIFIED
    score: float = 1.0  # Quality / stability score
    qualified_at: float = field(default_factory=time.time)
    gate_1_reproduction: dict[str, Any] = field(default_factory=dict)
    gate_2_stress_envelope: dict[str, Any] = field(default_factory=dict)
    certification_token: str = ""
    governance_signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "capability_name": self.capability_name,
            "status": self.status.value,
            "score": self.score,
            "qualified_at": self.qualified_at,
            "gate_1_reproduction": self.gate_1_reproduction,
            "gate_2_stress_envelope": self.gate_2_stress_envelope,
            "certification_token": self.certification_token,
            "governance_signature": self.governance_signature,
        }


@dataclass(frozen=True)
class RejectedQualification:
    """Artifact produced when an emergent candidate fails any gate."""
    candidate_id: str
    capability_name: str
    status: QualificationStatus = QualificationStatus.REJECTED
    rejected_at: float = field(default_factory=time.time)
    gate_failed: str = ""
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "capability_name": self.capability_name,
            "status": self.status.value,
            "rejected_at": self.rejected_at,
            "gate_failed": self.gate_failed,
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class SuspendedQualification:
    """Artifact produced when a previously qualified capability exhibits divergence."""
    candidate_id: str
    capability_name: str
    status: QualificationStatus = QualificationStatus.SUSPENDED
    suspended_at: float = field(default_factory=time.time)
    divergence_metric: str = ""
    divergence_value: float = 0.0
    threshold: float = 0.0
    reason: str = "post-qualification divergence"
    divergence_report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "capability_name": self.capability_name,
            "status": self.status.value,
            "suspended_at": self.suspended_at,
            "divergence_metric": self.divergence_metric,
            "divergence_value": self.divergence_value,
            "threshold": self.threshold,
            "reason": self.reason,
            "divergence_report": self.divergence_report,
        }


QualificationOutcome = Union[QualifiedEmergent, RejectedQualification, SuspendedQualification]
