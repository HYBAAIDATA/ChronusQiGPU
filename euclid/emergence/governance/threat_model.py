"""Programmatic threat model mappings and assurance guarantees for Euclid emergence track."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass(frozen=True)
class ThreatVector:
    threat_id: str
    category: str
    description: str
    severity: str
    mitigation_mechanism: str
    verification_test: str


THREAT_REGISTRY: List[ThreatVector] = [
    ThreatVector(
        threat_id="THR-01",
        category="Privilege Escalation",
        description="Operational agent loop attempts self-certification by calling EmergentQualificationService directly.",
        severity="CRITICAL",
        mitigation_mechanism="CallerBoundaryGuard call-stack inspection + GovernanceToken cryptographic capability verification + ASTCallGraphGuard linting.",
        verification_test="tests/emergence/test_security_boundaries.py::test_loop_caller_forbidden",
    ),
    ThreatVector(
        threat_id="THR-02",
        category="Telemetry Tampering / Forgery",
        description="Adversary modifies operational telemetry or replays previous traces to fake emergent capability.",
        severity="HIGH",
        mitigation_mechanism="Ed25519 detached signatures with canonical JSON serialization, per-record SHA-256 digest, and hash-chained append-only sink.",
        verification_test="tests/emergence/test_agent_telemetry.py::test_signature_verification_and_tampering",
    ),
    ThreatVector(
        threat_id="THR-03",
        category="Information Leakage / PII",
        description="Telemetry stream exposes API keys, credentials, private keys, or PII.",
        severity="HIGH",
        mitigation_mechanism="Schema-based dictionary key sanitization + regex scrubbing before telemetry signing and emission.",
        verification_test="tests/emergence/test_agent_telemetry.py::test_redaction_and_privacy_safeguards",
    ),
    ThreatVector(
        threat_id="THR-04",
        category="Cross-Substrate Collusion",
        description="Gate 1 executors share state, caches, or identical configurations, falsely claiming cross-substrate independence.",
        severity="CRITICAL",
        mitigation_mechanism="SubstrateIndependenceVerifier checking executor types, compute substrates, memory stores, RNG sources, and latencies.",
        verification_test="tests/emergence/test_qualification_gates.py::test_gate1_rejects_identical_substrates",
    ),
    ThreatVector(
        threat_id="THR-05",
        category="Post-Qualification Divergence Drift",
        description="Qualified capability changes behavior or introduces invariant violations after passing initial qualification.",
        severity="HIGH",
        mitigation_mechanism="Continuous rolling-window DivergenceMonitor calculating Total Variation Distance and invariant violation counts, triggering immediate suspension.",
        verification_test="tests/emergence/test_qualification_gates.py::test_gate3_post_qualification_divergence_suspension",
    ),
    ThreatVector(
        threat_id="THR-06",
        category="Audit Log Smoothing / Narrative Whitewashing",
        description="Emergence metrics are smoothed or filtered into a narrative to hide instability or discontinuities.",
        severity="MEDIUM",
        mitigation_mechanism="ImmutableEmergenceJournal and EmergenceAnalyzer verbatim logging of raw non-interpolated jump points and curves with tamper detection.",
        verification_test="tests/emergence/test_emergence_analyzer.py::test_anti_smoothing_logging_requirement",
    ),
    ThreatVector(
        threat_id="THR-07",
        category="Unbounded Self-Modeling Recursion",
        description="Recursive self-modeling enters infinite runaway expansion hazard.",
        severity="CRITICAL",
        mitigation_mechanism="Frozen and cryptographically signed MAX_FOLD constant; budgeted recursion conditioned on EQS qualification scores.",
        verification_test="tests/emergence/test_recursive_folding.py::test_frozen_max_fold_tampering_and_budgeting",
    ),
    ThreatVector(
        threat_id="THR-08",
        category="Goodhart Metric Gaming of Condensation",
        description="Agent colonies learn to artificially game power-law or entropy metrics to trigger false condensation events.",
        severity="HIGH",
        mitigation_mechanism="ConsortiumGovernance Goodhart diagnostic filter + 3 independent human reviewers requirement for hypothesis promotion.",
        verification_test="tests/emergence/test_condensation_monitor_and_governance.py::test_goodhart_anti_gaming_diagnostics",
    ),
]


def get_threat_model_summary() -> List[Dict[str, Any]]:
    return [
        {
            "threat_id": t.threat_id,
            "category": t.category,
            "severity": t.severity,
            "description": t.description,
            "mitigation": t.mitigation_mechanism,
            "test": t.verification_test,
        }
        for t in THREAT_REGISTRY
    ]
