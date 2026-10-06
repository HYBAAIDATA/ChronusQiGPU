"""QuantumCoherenceAnalyzer — the solve-vs-fallback gate (S3).

Per the runtime hierarchy, solving intelligence runs BEFORE brute-force:
the coherence gate decides whether the structured solve path (folded-state
candidates, manifold orderings, anchored pre-passes) is in a high-quality
regime and may lead the cycle, or whether control falls through to the
fallback search path.

HONEST SCOPE
------------
"Coherence" here is a measured concentration statistic over the signals the
substrate actually produces — face-probability concentration, resonance
spread, and the observed share of solve-path candidates that survive local
validation. It is NOT a claim that the structure predicts winners. The gate
only decides WHO LOOKS FIRST. Every candidate from either path still
requires physical SHA-256d evaluation; the pool remains the sole accept
authority. The decision and every input metric are emitted as telemetry so
the gate's behavior is auditable and falsifiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# Gate constants — declared thresholds, not magic values:
#   CONCENTRATION_MIN: Herfindahl index of a uniform 32-face distribution is
#     1/32 = 0.03125. Requiring 2x uniform before trusting the solve path is
#     a deliberate, conservative floor.
#   MIN_SAMPLES: below this many observed outcomes, prior data is too thin to
#     arbitrate and the gate defaults to solve-first (the spec's default).
CONCENTRATION_MIN = 0.0625
MIN_SAMPLES = 8
SOLVE_REGIME = "solve"
FALLBACK_REGIME = "fallback"


@dataclass
class GateDecision:
    regime: str  # SOLVE_REGIME | FALLBACK_REGIME
    concentration: float
    observed_samples: int
    solve_path_hit_rate: Optional[float]
    reason: str
    truth_label: str = "coherence-gate"


class QuantumCoherenceAnalyzer:
    """Assess solve-regime quality and emit a deterministic gate decision.

    Inputs are measured quantities only:
      * face_probs: current 32-face probability/affinity distribution
      * solve_path_outcomes: recent booleans — did a solve-path candidate
        survive local SHA-256d validation? (True/False history)
      * resonance_scores: optional per-candidate resonance values

    The gate falls back when (a) the face distribution is effectively
    uniform (structure carries no information this cycle) AND (b) measured
    solve-path hit rate is no better than the window base rate. Otherwise
    the solve path leads. Deterministic: identical inputs -> identical
    regime.
    """

    truth_label = "coherence-gate"

    def __init__(
        self,
        concentration_min: float = CONCENTRATION_MIN,
        min_samples: int = MIN_SAMPLES,
    ) -> None:
        self.concentration_min = float(concentration_min)
        self.min_samples = int(min_samples)

    @staticmethod
    def concentration(face_probs: List[float]) -> float:
        """Herfindahl concentration index of the face distribution.

        Uniform 32-face => 0.03125; a single dominant face => 1.0. Pure
        function of the supplied distribution.
        """
        total = sum(face_probs)
        if total <= 0.0:
            return 0.0
        return sum((p / total) ** 2 for p in face_probs)

    def decide(
        self,
        face_probs: Optional[List[float]] = None,
        solve_path_outcomes: Optional[List[bool]] = None,
        resonance_scores: Optional[List[float]] = None,
        base_hit_rate: float = 0.0,
    ) -> GateDecision:
        concentration = self.concentration(face_probs or [1.0 / 32.0] * 32)
        outcomes = [bool(x) for x in (solve_path_outcomes or [])]
        samples = len(outcomes)
        hit_rate = (sum(outcomes) / samples) if samples else None

        # Resonance spread is advisory evidence: a degenerate (all-equal)
        # score distribution carries no ordering signal.
        resonance_informative = True
        if resonance_scores:
            rs = [float(x) for x in resonance_scores]
            spread = (max(rs) - min(rs)) if len(rs) > 1 else 0.0
            resonance_informative = spread > 1e-12

        if concentration < self.concentration_min and not resonance_informative:
            return GateDecision(
                regime=FALLBACK_REGIME,
                concentration=concentration,
                observed_samples=samples,
                solve_path_hit_rate=hit_rate,
                reason="uniform_face_distribution_and_flat_resonance",
            )
        if (
            samples >= self.min_samples
            and hit_rate is not None
            and hit_rate <= base_hit_rate
        ):
            return GateDecision(
                regime=FALLBACK_REGIME,
                concentration=concentration,
                observed_samples=samples,
                solve_path_hit_rate=hit_rate,
                reason="measured_solve_path_no_better_than_base_rate",
            )
        return GateDecision(
            regime=SOLVE_REGIME,
            concentration=concentration,
            observed_samples=samples,
            solve_path_hit_rate=hit_rate,
            reason="structured_regime" if concentration >= self.concentration_min
            else "insufficient_evidence_default_solve_first",
        )

    def telemetry(self, decision: GateDecision) -> Dict[str, object]:
        return {
            "regime": decision.regime,
            "concentration": decision.concentration,
            "observed_samples": decision.observed_samples,
            "solve_path_hit_rate": decision.solve_path_hit_rate,
            "reason": decision.reason,
            "truth_label": self.truth_label,
            "claim_boundary": (
                "gate decides ordering only; every candidate still requires "
                "physical SHA-256d evaluation and pool acceptance"
            ),
        }
