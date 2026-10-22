"""Minimal delegation types for FederatedResonanceGate."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time

class EvidenceSource(Enum):
    INTERNAL_HEURISTIC = "internal_heuristic"
    EXTERNAL_SUBSYSTEM = "external_subsystem"
    NONE = "none"

class VetoCategory(Enum):
    CONFIDENCE_FAILURE = "confidence_failure"
    COHERENCE_FAILURE = "coherence_failure"
    TRUTH_FAILURE = "truth_failure"
    CAUSAL_FAILURE = "causal_failure"
    FEEDBACK_FAILURE = "feedback_failure"

@dataclass
class ValidationSignal:
    passed: bool = True
    evidence_source: EvidenceSource = EvidenceSource.EXTERNAL_SUBSYSTEM
    signal_strength: float = 0.80
    validator_identity: str = ""
    evidence_hash: str = ""
    reason: str = ""
    @property
    def is_external(self) -> bool: return self.evidence_source == EvidenceSource.EXTERNAL_SUBSYSTEM
    @property
    def is_internal(self) -> bool: return self.evidence_source == EvidenceSource.INTERNAL_HEURISTIC

@dataclass
class IntegrationAssessment:
    passed: bool
    veto_category: Optional[VetoCategory] = None
    reason: str = ""
    validation_signal: Optional[ValidationSignal] = None
    coherence_passed: bool = False
    truth_evidence_supplied: bool = False
    causal_attribution_supplied: bool = False
    feedback_processing_completed: bool = False
    assessed_at: float = field(default_factory=time.time)

class WorldIntegrationGate:
    """Minimal gate stub for FederatedResonanceGate compatibility."""
    def validate_integration(self, organ, result, validation_signal):
        return IntegrationAssessment(passed=True, reason="Base gate passed.", coherence_passed=True, truth_evidence_supplied=True, causal_attribution_supplied=True, feedback_processing_completed=True)
