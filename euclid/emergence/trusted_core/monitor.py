"""Divergence monitor for post-qualification continuous behavioral verification."""

from __future__ import annotations
from typing import Sequence, Dict, Any, Tuple, Optional
from collections import Counter

from ..models.candidate import EmergentCandidate
from ..models.telemetry import TelemetryRecord


class DivergenceMonitor:
    """Continuously evaluates operational telemetry for post-qualification behavioral drift."""

    def __init__(self, default_drift_threshold: float = 0.25):
        self.default_drift_threshold = default_drift_threshold

    @staticmethod
    def compute_total_variation_distance(dist_a: Dict[str, float], dist_b: Dict[str, float]) -> float:
        all_keys = set(dist_a.keys()).union(set(dist_b.keys()))
        if not all_keys:
            return 0.0

        sum_a = sum(dist_a.values()) or 1.0
        sum_b = sum(dist_b.values()) or 1.0

        tvd = 0.0
        for k in all_keys:
            pa = dist_a.get(k, 0.0) / sum_a
            pb = dist_b.get(k, 0.0) / sum_b
            tvd += abs(pa - pb)

        return round(0.5 * tvd, 4)

    def divergence_detected(
        self,
        candidate_or_window: Any = None,
        window: Optional[Sequence[TelemetryRecord]] = None,
        baseline_profile: Optional[Dict[str, float]] = None,
        drift_threshold: Optional[float] = None,
        *,
        candidate: Optional[Any] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        threshold = drift_threshold if drift_threshold is not None else self.default_drift_threshold

        cand = candidate if candidate is not None else (candidate_or_window if window is not None else None)
        if window is not None:
            actual_window = window
        else:
            actual_window = candidate_or_window if isinstance(candidate_or_window, (list, tuple)) else []

        claimed_sig = getattr(cand, "claimed_behavior_signature", "emergent_behavior") if cand else "emergent_behavior"

        if not actual_window:
            return False, {"note": "Empty monitoring window, no divergence detected"}

        total_violations = sum(len(rec.invariant_violations) for rec in actual_window)
        if total_violations > 0:
            return True, {
                "divergence_metric": "invariant_violations",
                "divergence_value": float(total_violations),
                "threshold": 0.0,
                "reason": f"Observed {total_violations} invariant violations in monitoring window",
            }

        observed_actions: Counter[str] = Counter()
        for rec in actual_window:
            for action in rec.programmed_actions_used:
                observed_actions[action] += 1
            for novel_act in rec.novel_elements.unattributed:
                observed_actions[novel_act] += 1

        total_acts = sum(observed_actions.values())
        if total_acts == 0:
            return False, {"note": "No actions recorded in window"}

        observed_dist = {k: v / total_acts for k, v in observed_actions.items()}
        effective_baseline = baseline_profile or {
            claimed_sig: 0.8,
            "explore": 0.2,
        }

        drift = self.compute_total_variation_distance(observed_dist, effective_baseline)
        claimed_observed = observed_actions.get(claimed_sig, 0)
        capability_dropped = (claimed_observed == 0 and len(actual_window) >= 5)

        if capability_dropped:
            return True, {
                "divergence_metric": "capability_extinction",
                "divergence_value": 1.0,
                "threshold": threshold,
                "reason": f"Claimed behavior '{claimed_sig}' vanished from operational window",
            }

        if drift > threshold:
            return True, {
                "divergence_metric": "total_variation_drift",
                "divergence_value": drift,
                "threshold": threshold,
                "reason": f"Behavioral drift {drift:.4f} exceeds threshold {threshold:.4f}",
            }

        return False, {
            "divergence_metric": "total_variation_drift",
            "divergence_value": drift,
            "threshold": threshold,
            "reason": "Within acceptable operational envelope",
        }
