"""Golden-ratio-weighted defensive triage primitives for HYBA.

Ranks already-authorized defensive observations for analyst review. It does not
detect attacks by itself, grant authority, change policy, or execute remediation.
Phi is a scheduling/weighting heuristic, not a security primitive.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Iterable

try:
    from hyba_substrate.golden_ratio_library import PHI
except ImportError:
    PHI = (1.0 + math.sqrt(5.0)) / 2.0

INV_PHI = 1.0 / PHI
SCHEMA = "hyba.phi_defensive_triage/v1"


@dataclass(frozen=True)
class DefensiveSignal:
    """Normalized defensive evidence supplied by trusted adapters."""

    signal_id: str
    severity: float
    exposure: float
    confidence: float
    age_units: float = 0.0
    evidence_ref: str = ""

    def validate(self) -> None:
        if not isinstance(self.signal_id, str) or not self.signal_id.strip():
            raise ValueError("signal_id is required and must be a non-empty string")
        for name in ("severity", "exposure", "confidence"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number in [0, 1]")
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be a finite number in [0, 1]")
        if (
            isinstance(self.age_units, bool)
            or not isinstance(self.age_units, (int, float))
            or not math.isfinite(self.age_units)
            or self.age_units < 0.0
        ):
            raise ValueError("age_units must be a finite non-negative number")


def score_signal(signal: DefensiveSignal) -> dict[str, object]:
    """Return a bounded priority score, never an allow/deny decision.

    freshness_weight = phi ** (-age_units). age_units is an application-defined,
    documented age unit and must not be inferred silently from wall-clock time.
    """
    signal.validate()
    freshness_weight = PHI ** (-float(signal.age_units))
    score = (
        float(signal.severity)
        * float(signal.exposure)
        * float(signal.confidence)
        * freshness_weight
    )
    return {
        "signal_id": signal.signal_id,
        "priority_score": score,
        "components": {
            "severity": float(signal.severity),
            "exposure": float(signal.exposure),
            "confidence": float(signal.confidence),
            "age_units": float(signal.age_units),
            "phi_freshness_weight": freshness_weight,
        },
        "evidence_ref": signal.evidence_ref or None,
        "recommendation_only": True,
        "action_authorized": False,
        "actuation_performed": False,
    }


def rank_signals(signals: Iterable[DefensiveSignal]) -> dict[str, object]:
    """Rank deterministically; duplicate IDs and malformed values fail closed."""
    scored = [score_signal(signal) for signal in signals]
    ids = [str(item["signal_id"]) for item in scored]
    if len(ids) != len(set(ids)):
        raise ValueError("signal_id values must be unique within one ranking")
    ranked = sorted(
        scored,
        key=lambda item: (-float(item["priority_score"]), str(item["signal_id"])),
    )
    canonical = json.dumps(ranked, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema": SCHEMA,
        "status": "available",
        "ranking": ranked,
        "ranking_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "method": "severity_x_exposure_x_confidence_x_phi_freshness",
        "phi": PHI,
        "inverse_phi": INV_PHI,
        "recommendation_only": True,
        "action_authorized": False,
        "actuation_performed": False,
        "limitations": [
            "Scores are heuristic priorities, not calibrated attack probabilities.",
            "Input normalization and freshness units require domain validation.",
            "The ranking cannot bypass AL HARAS/L-HRAS policy or human approval.",
        ],
    }


def allocate_review_slots(priorities: Iterable[str], slot_count: int) -> dict[str, int]:
    """Allocate review slots using deterministic phi-to-negative-rank weights.

    Largest-remainder apportionment ensures integer allocations sum exactly to
    slot_count. Earlier priorities receive more weight.
    """
    names = list(priorities)
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("priority names must be non-empty strings")
    if len(names) != len(set(names)):
        raise ValueError("priority names must be unique")
    if isinstance(slot_count, bool) or not isinstance(slot_count, int) or slot_count < 0:
        raise ValueError("slot_count must be a non-negative integer")
    if not names:
        if slot_count:
            raise ValueError("cannot allocate non-zero slots to an empty priority list")
        return {}
    if slot_count == 0:
        return {name: 0 for name in names}

    weights = [PHI ** (-index) for index in range(len(names))]
    total = sum(weights)
    exact = [slot_count * weight / total for weight in weights]
    base = [math.floor(value) for value in exact]
    remaining = slot_count - sum(base)
    order = sorted(range(len(names)), key=lambda i: (-(exact[i] - base[i]), i))
    for index in order[:remaining]:
        base[index] += 1
    return dict(zip(names, base))
