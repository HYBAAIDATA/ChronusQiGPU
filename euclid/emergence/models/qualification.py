"""Reconstructed qualification outcomes, not independently certified receipts."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union
from .manifest import finite, freeze, plain


class QualificationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class GateResult:
    gate_name: str
    passed: bool
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return plain(self)


@dataclass(frozen=True)
class QualifiedEmergent:
    candidate_id: str
    capability_name: str
    score: float
    gate_1_reproduction: dict[str, Any]
    gate_2_stress_envelope: dict[str, Any]
    certification_token: str
    governance_signature: str
    status: QualificationStatus = field(default=QualificationStatus.QUALIFIED, init=False)

    def __post_init__(self):
        finite(self.score, "score")
        if self.score > 1:
            raise ValueError("score must be in [0,1]")
        for name in ("gate_1_reproduction", "gate_2_stress_envelope"):
            object.__setattr__(self, name, freeze(getattr(self, name)))

    def to_dict(self):
        return plain(self)


@dataclass(frozen=True)
class RejectedQualification:
    candidate_id: str
    capability_name: str
    gate_failed: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    status: QualificationStatus = field(default=QualificationStatus.REJECTED, init=False)

    def __post_init__(self):
        object.__setattr__(self, "evidence", freeze(self.evidence))

    def to_dict(self):
        return plain(self)


@dataclass(frozen=True)
class SuspendedQualification:
    candidate_id: str
    capability_name: str
    divergence_metric: str
    divergence_value: float
    threshold: float
    reason: str
    divergence_report: dict[str, Any] = field(default_factory=dict)
    status: QualificationStatus = field(default=QualificationStatus.SUSPENDED, init=False)

    def to_dict(self):
        return plain(self)


QualificationOutcome = Union[QualifiedEmergent, RejectedQualification, SuspendedQualification]
