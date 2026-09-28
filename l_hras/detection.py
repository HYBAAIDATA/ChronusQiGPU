"""Detection, throttle, and adversary tracking — Part X.

Anomaly classification is measured, not asserted (DET1): divergence from
the fidelity kernel drives nominal → suspicious → anomalous →
compromised. The purity/entropy gates throttle — they never let a
violation through (DET3, DET4).
"""

from __future__ import annotations

import time
from typing import Any

from . import store as aethel_store
from . import substrates
from .result import Ok, Result
from .types import (
    ESCALATION_CRITICAL,
    ESCALATION_HIGH,
    ESCALATION_MEDIUM,
    Adversary,
    AdversaryProfile,
    AnomalyClass,
    AnomalyReport,
    Escalation,
    ThrottleDecision,
)


def detect_anomaly(lhras: Any, event: Any) -> Result[AnomalyReport]:
    fidelity = substrates.fidelity_kernel(event.adversary_class, event)
    if fidelity.mean <= 0 or fidelity.samples <= 0:
        classification = AnomalyClass.COMPROMISED
        divergence = 1.0
    else:
        baseline = lhras.joint.baseline_distribution.get(event.adversary_class.value)
        base_mean = baseline.mean if baseline else 1.0
        divergence = 1.0 - (fidelity.mean / base_mean if base_mean else 0.0)
        divergence = max(0.0, min(1.0, divergence))
        if divergence > lhras.cfg.fidelity_threshold:
            classification = AnomalyClass.ANOMALOUS
        elif divergence > lhras.cfg.fidelity_threshold / 2:
            classification = AnomalyClass.SUSPICIOUS
        else:
            classification = AnomalyClass.NOMINAL
    return Ok(
        AnomalyReport(
            fidelity=fidelity,
            divergence=divergence,
            classification=classification,
            attestation=lhras.attester.attest(
                "anomaly", {"divergence": divergence, "class": classification.value}
            ),
        )
    )


def purity_gate_ok(lhras: Any, event: Any) -> bool:
    try:
        s = substrates.vn_entropy(event.state)
        p = substrates.purity(event.state)
    except Exception:
        return False
    if s > lhras.cfg.entropy_threshold:
        return False
    if p < lhras.cfg.purity_threshold:
        return False
    return True


def compute_blast_radius(mode: dict[str, Any], scope: str) -> float:
    factor = float(mode.get("factor", 1.0))
    scope_weight = {"global": 1.0, "tenant": 0.5, "session": 0.25}.get(scope, 0.5)
    return factor * scope_weight


def engage_throttle(lhras: Any, event: Any, reason: str) -> Result[ThrottleDecision]:
    mode = lhras.policy.throttle_mode_for(reason, event.scope)
    if mode is None:
        mode = {"type": "rate_reduction", "factor": lhras.cfg.default_throttle_factor}
    now = time.time()
    decision = ThrottleDecision(
        mode=mode,
        reason=reason,
        scope=event.scope,
        started_at=now,
        expires_at=now + lhras.cfg.throttle_duration,
        blast_radius=compute_blast_radius(mode, event.scope),
    )
    attest = lhras.attester.self_attest(
        {
            "event": "throttle_engaged",
            "decision": {
                "mode": decision.mode,
                "reason": decision.reason,
                "scope": decision.scope,
                "blast_radius": decision.blast_radius,
            },
        }
    )
    decision.attestation = attest
    written = aethel_store.aethel_write(
        lhras.aethel, aethel_store.throttle_certificate(decision), attest
    )
    if written.is_err:
        return written
    lhras.metrics.increment("lhras.throttle.engaged", 1)
    return Ok(decision)


# ---------------------------------------------------------------------------
# Adversary tracking / profiling / escalation (ADV1–ADV4)
# ---------------------------------------------------------------------------


def track_adversary(lhras: Any, event: Any) -> Result[Adversary]:
    adv_id = event.adversary_id or event.actor
    existing = lhras.joint.adversaries.get(adv_id)
    if existing is not None:
        existing.update(event)
        return Ok(existing)
    now = time.time()
    new_adv = Adversary(
        id=adv_id,
        first_seen=now,
        last_seen=now,
        events=[event],
        attribution=set(),
    )
    lhras.joint.adversaries[adv_id] = new_adv
    return Ok(new_adv)


def extract_tactics(events: list[Any]) -> list[str]:
    return sorted({e.action for e in events})


def extract_techniques(events: list[Any]) -> list[str]:
    techs: set[str] = set()
    for e in events:
        techs.update(str(k) for k in e.observation if str(k).startswith("T"))
    return sorted(techs)


def measure_persistence(adv: Adversary) -> float:
    """Longevity pressure: event count saturating at 10."""
    return min(1.0, len(adv.events) / 10.0)


def measure_lateral(adv: Adversary) -> float:
    """Distinct scopes touched, saturating at 5."""
    scopes = {e.scope for e in adv.events}
    return min(1.0, len(scopes) / 5.0)


def measure_escalation(adv: Adversary) -> float:
    """Weighted composite of persistence, lateral movement and severity —
    measured, so it can be driven either way by evidence."""
    severity = max((float(e.observation.get("severity", 0.0)) for e in adv.events), default=0.0)
    return min(
        1.0,
        0.4 * measure_persistence(adv) + 0.3 * measure_lateral(adv) + 0.3 * min(1.0, severity),
    )


def profile_adversary(adv: Adversary) -> Result[AdversaryProfile]:
    return Ok(
        AdversaryProfile(
            id=adv.id,
            first_seen=adv.first_seen,
            last_seen=adv.last_seen,
            event_count=len(adv.events),
            tactics=extract_tactics(adv.events),
            techniques=extract_techniques(adv.events),
            attribution=set(adv.attribution),
            persistence=measure_persistence(adv),
            lateral_score=measure_lateral(adv),
            escalation_score=measure_escalation(adv),
        )
    )


def evaluate_escalation(lhras: Any, adv: Adversary, profile: AdversaryProfile) -> Escalation:
    if profile.escalation_score > ESCALATION_CRITICAL:
        return Escalation.PAGE_ONCALL
    if profile.escalation_score > ESCALATION_HIGH:
        return Escalation.NOTIFY_SOC
    if profile.escalation_score > ESCALATION_MEDIUM:
        return Escalation.OPEN_TICKET
    return Escalation.NONE
