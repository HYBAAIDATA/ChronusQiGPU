"""Lucas intelligence scale profile over the declared Lucas ladder.

The Lucas numbers are the prime-generating companion sequence to the
Fibonacci numbers, both governed by the golden ratio φ = (1+√5)/2. They
are the exact Q[√5] substrate of this repo (see ``turing_core.lucas`` and
``src/lib/m3_igpu_scaler.ts::ExactLucasEngine.lucas``).

This module defines a canonical **intelligence scale ladder** built on the
exact Lucas values::

    L_10 = 123
    L_12 = 322
    L_15 = 1364
    L_18 = 5778
    L_20 = 15127
    L_31 = 3010349
    L_50 = 28143753123
    L_76 = 7639424778862807

Each scale is a named intelligence "level" that is applied transparently
to intelligence-related quantities across the orchestrator:

- **Curriculum difficulty** — the PYTHIA learning curriculum advances
  through the Lucas scales; each level raises the task complexity.
- **Search resource budget** — the agentic controller allocates
  qubits/threads/hash budget proportional to the active Lucas scale.
- **Memory salience / retention** — the memory system weights salience
  and archival retention by the Lucas scale.
- **Multi-scale coherence probe** — the emergence observer measures
  coherence at each Lucas scale and reports whether coherence is
  scale-invariant (a genuine emergence signature) or scale-dependent.
- **Tensor layer weighting** — the grand unified tensor weights its
  institutional verification layers by the Lucas scale profile.

This is **not** a claim that multiplying by a Lucas number produces
intelligence. The scales are an observable, monotonic complexity ladder.
Whether intelligence emerges from climbing it is the falsifiable question
the self-test answers.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: trace

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("Intelligence.lucas_scales")

# The canonical intelligence scale ladder. Values are exact Lucas numbers
# computed from the Q[√5] recurrence L_n = L_{n-1} + L_{n-2}, L_0=2, L_1=1.
# They are written as literals (not computed) so the ladder is stable and
# auditable; ``validate_against_substrate`` confirms they match
# ``turing_core.lucas`` at runtime.
from lucas.core import lucas as _lucas_value
from lucas.ladder import CURRICULUM_RUNGS as _CURRICULUM_RUNGS
from lucas.ladder import FULL_LADDER as _FULL_LADDER
from lucas.ladder import PISOT_EXACT_N as _PISOT_EXACT_N
from lucas.ladder import SCALE_RUNGS as _SCALE_RUNGS

LUCAS_SCALE_LADDER: Dict[int, int] = {i: _lucas_value(i) for i in _FULL_LADDER}

# Ordered scale indices (ascending) — the five intelligence curriculum
# rungs. Mining rungs (31/50/76) live on IGPU_SCALE_RUNGS, not this profile.
SCALE_ORDER: Tuple[int, ...] = tuple(_CURRICULUM_RUNGS)

# Human-readable names for each scale level.
SCALE_NAMES: Dict[int, str] = {
    10: "L_10 · pattern",
    12: "L_12 · structure",
    15: "L_15 · coherence",
    18: "L_18 · abstraction",
    20: "L_20 · metacognition",
    31: "L_31 · mining",
    50: "L_50 · enterprise",
    76: "L_76 · Pisot collapse",
}

# Extended iGPU/mining scale rungs — sourced once from
# lucas.ladder.SCALE_RUNGS.
IGPU_SCALE_RUNGS: Tuple[int, ...] = tuple(_SCALE_RUNGS)
PISOT_EXACT_N: int = _PISOT_EXACT_N


def is_ladder_index(n: int) -> bool:
    """True iff n is a rung or a multiple of a rung (n = k·r)."""
    return n > 0 and any(n % r == 0 for r in IGPU_SCALE_RUNGS)


def ladder_multiples_of(n: int) -> List[int]:
    """Which rungs divide n (empty when n is off-ladder)."""
    return [r for r in IGPU_SCALE_RUNGS if n % r == 0]


def nearest_ladder_index(n: int, lo: int, hi: int) -> int:
    """Snap n to the nearest valid ladder index inside [lo, hi].

    Prefers the upward stop on ties (scale bias). Returns the clamped n
    unchanged when no ladder stop exists in range.
    """
    c = max(lo, min(hi, int(round(n))))
    if is_ladder_index(c):
        return c
    for d in range(1, max(hi - c, c - lo) + 1):
        if c + d <= hi and is_ladder_index(c + d):
            return c + d
        if c - d >= lo and is_ladder_index(c - d):
            return c - d
    return c


def next_ladder_index(n: int, direction: int, lo: int, hi: int) -> int:
    """Next ladder stop strictly beyond n in ``direction``, clamped to [lo,hi]."""
    step = 1 if direction >= 0 else -1
    m = n + step
    while lo <= m <= hi:
        if is_ladder_index(m):
            return m
        m += step
    return n


PHI = (1 + math.sqrt(5)) / 2


@dataclass
class LucasScaleLevel:
    """One rung of the Lucas intelligence scale ladder."""

    index: int  # n in L_n
    value: int  # exact L_n
    name: str  # human-readable label
    # Normalised [0, 1] position on the ladder (0 = L_10, 1 = top rung).
    ladder_position: float
    # log2(value) — the "bit-depth" of the scale, used for qubit budgets.
    bit_depth: float
    # φ^n — the Binet magnitude at this scale (Pisot convergence reference).
    binet_magnitude: float
    # Pisot drift |φ^n - L_n| = φ^{-n} (how exact the integer limb is).
    pisot_drift: float


@dataclass
class LucasScaleProfile:
    """The full Lucas intelligence scale profile."""

    levels: List[LucasScaleLevel] = field(default_factory=list)
    # Whether the ladder matched the exact turing_core substrate.
    substrate_validated: bool = False
    # Monotonicity check: L_n must strictly increase across the ladder.
    monotonic: bool = False
    # The ratio of the largest to smallest scale (complexity growth factor).
    complexity_growth: float = 1.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "levels": [
                {
                    "index": lv.index,
                    "value": lv.value,
                    "name": lv.name,
                    "ladder_position": lv.ladder_position,
                    "bit_depth": lv.bit_depth,
                    "binet_magnitude": lv.binet_magnitude,
                    "pisot_drift": lv.pisot_drift,
                }
                for lv in self.levels
            ],
            "substrate_validated": self.substrate_validated,
            "monotonic": self.monotonic,
            "complexity_growth": self.complexity_growth,
        }

    def values(self) -> List[int]:
        """Return the exact Lucas values in ladder order."""
        return [lv.value for lv in self.levels]

    def indices(self) -> List[int]:
        """Return the Lucas indices in ladder order."""
        return [lv.index for lv in self.levels]

    def level_for(self, scale_index: int) -> Optional[LucasScaleLevel]:
        """Return the level for a given Lucas index, or None."""
        for lv in self.levels:
            if lv.index == scale_index:
                return lv
        return None

    def interpolate_value(self, position: float) -> int:
        """Linearly interpolate a Lucas value for a [0,1] ladder position.

        Used to map a continuous confidence/progress measure onto the
        exact ladder without inventing a non-Lucas value (the result is
        rounded to the nearest exact L_n).
        """
        if not self.levels:
            return 1
        pos = max(0.0, min(1.0, position))
        scaled = pos * (len(self.levels) - 1)
        lo = int(math.floor(scaled))
        hi = min(lo + 1, len(self.levels) - 1)
        frac = scaled - lo
        # Round to the nearest exact level (never invent a non-Lucas value).
        return self.levels[hi if frac >= 0.5 else lo].value

    def budget_for(self, scale_index: int, base: int) -> int:
        """Scale a resource budget by L_n / L_10.

        ``base`` is the budget at L_10. Higher Lucas scales get
        proportionally more resources. The result is always an integer.
        """
        lv = self.level_for(scale_index)
        if lv is None or not self.levels:
            return base
        l10 = self.levels[0].value
        return max(1, int(base * lv.value / max(l10, 1)))

    def salience_weight(self, scale_index: int) -> float:
        """Return the salience/retention weight for a Lucas scale.

        Normalised so L_10 = 1.0 and the top rung is the complexity growth factor.
        Higher scales retain salience longer (archival bias).
        """
        lv = self.level_for(scale_index)
        if lv is None or not self.levels:
            return 1.0
        return lv.value / max(self.levels[0].value, 1)


def build_lucas_scale_profile() -> LucasScaleProfile:
    """Build the canonical Lucas intelligence scale profile.

    Validates the ladder against the exact ``turing_core.lucas`` substrate
    when available, so the profile is never a fabricated constant table.
    """
    levels: List[LucasScaleLevel] = []
    n_levels = len(SCALE_ORDER)
    for i, idx in enumerate(SCALE_ORDER):
        value = LUCAS_SCALE_LADDER[idx]
        levels.append(
            LucasScaleLevel(
                index=idx,
                value=value,
                name=SCALE_NAMES[idx],
                ladder_position=i / max(n_levels - 1, 1),
                bit_depth=math.log2(max(value, 1)),
                binet_magnitude=PHI**idx,
                pisot_drift=PHI ** (-idx),
            )
        )

    profile = LucasScaleProfile(
        levels=levels,
        substrate_validated=False,
        monotonic=all(levels[i].value < levels[i + 1].value for i in range(len(levels) - 1)),
        complexity_growth=(levels[-1].value / max(levels[0].value, 1) if levels else 1.0),
    )

    # Validate against the exact substrate.
    try:
        import turing_core

        ok = all(turing_core.lucas(idx) == LUCAS_SCALE_LADDER[idx] for idx in SCALE_ORDER)
        profile.substrate_validated = bool(ok)
        if not ok:
            logger.warning("Lucas scale ladder mismatch with turing_core substrate")
    except ImportError:
        logger.info("turing_core not available; ladder unvalidated")
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Lucas scale validation error: %s", e)

    return profile


def build_family_scale_profile(
    family: str,
    indices: Optional[Iterable[int]] = None,
) -> LucasScaleProfile:
    """Build a scale ladder for any member of the extended algebraic family.

    Same ladder structure as the canonical Lucas profile, but the rung
    values are the family's exact trace limb — Lucas / Pell-Lucas / Perrin /
    supergolden-trace / tribonacci-trace — pulled live from ``turing_core``,
    so the values ARE the substrate (nothing to validate against a constant
    table). Binet magnitude and Pisot drift use the family's own root and
    conjugate modulus.
    """
    import turing_core

    idx = list(indices) if indices is not None else list(SCALE_ORDER)
    limb = turing_core.FAMILY_TRACE_LIMBS[family]
    alpha = float(turing_core.family_root(family))
    mu = float(turing_core.family_pisot_modulus(family))
    levels = [
        LucasScaleLevel(
            index=i,
            value=limb(i),
            name=f"{family} T_{i}",
            ladder_position=k / max(len(idx) - 1, 1),
            bit_depth=math.log2(max(limb(i), 1)),
            binet_magnitude=alpha**i,
            pisot_drift=mu**i,
        )
        for k, i in enumerate(idx)
    ]
    return LucasScaleProfile(
        levels=levels,
        substrate_validated=True,
        monotonic=all(levels[k].value < levels[k + 1].value for k in range(len(levels) - 1)),
        complexity_growth=(levels[-1].value / max(levels[0].value, 1) if levels else 1.0),
    )


# ---------------------------------------------------------------------------
# Multi-scale coherence probe
# ---------------------------------------------------------------------------


def multiscale_coherence_probe(
    signal: List[float],
    profile: Optional[LucasScaleProfile] = None,
) -> Dict[str, Any]:
    """Probe a signal for coherence at each Lucas scale.

    For each L_n in the ladder, downsample the signal by averaging blocks
    of size L_n and measure the autocorrelation of the downsampled signal.
    A genuine emergence signature would show **scale-invariant** coherence
    (coherence that persists across all Lucas scales), not just coherence
    at one scale.

    This is a mathematical probe, not an intelligence test. Scale-invariant
    coherence is a *necessary* but not *sufficient* condition for
    emergence — it must be combined with the AGI/ASI requirements and the
    emergence observer to make any claim.
    """
    if profile is None:
        profile = build_lucas_scale_profile()
    if len(signal) < 2:
        return {
            "scale_invariant": False,
            "per_scale": {},
            "reason": "signal too short",
        }

    per_scale: Dict[str, Any] = {}
    coherences: List[float] = []
    for lv in profile.levels:
        block = max(lv.value, 1)
        # Downsample by non-overlapping block averaging.
        n_blocks = max(1, len(signal) // block)
        downsampled: List[float] = []
        for b in range(n_blocks):
            chunk = signal[b * block : (b + 1) * block]
            if chunk:
                downsampled.append(sum(chunk) / len(chunk))
        # Autocorrelation at lag 1 (normalised).
        if len(downsampled) > 1:
            mean = sum(downsampled) / len(downsampled)
            num = sum(
                (downsampled[i] - mean) * (downsampled[i + 1] - mean)
                for i in range(len(downsampled) - 1)
            )
            den = sum((x - mean) ** 2 for x in downsampled)
            ac1 = float(num / den) if den > 0 else 0.0
        else:
            ac1 = 0.0
        per_scale[lv.name] = {
            "index": lv.index,
            "value": lv.value,
            "autocorr_lag1": ac1,
            "n_blocks": n_blocks,
        }
        coherences.append(ac1)

    # Scale-invariance: low variance of coherence across scales.
    if coherences:
        mean_c = sum(coherences) / len(coherences)
        var_c = sum((c - mean_c) ** 2 for c in coherences) / len(coherences)
        scale_invariant = bool(var_c < 0.01 and mean_c > 0.3)
    else:
        mean_c = 0.0
        var_c = 0.0
        scale_invariant = False

    return {
        "scale_invariant": scale_invariant,
        "mean_coherence": mean_c,
        "coherence_variance": var_c,
        "per_scale": per_scale,
        "n_scales": len(coherences),
    }


__all__ = [
    "LUCAS_SCALE_LADDER",
    "SCALE_ORDER",
    "SCALE_NAMES",
    "IGPU_SCALE_RUNGS",
    "PISOT_EXACT_N",
    "is_ladder_index",
    "ladder_multiples_of",
    "nearest_ladder_index",
    "next_ladder_index",
    "LucasScaleLevel",
    "LucasScaleProfile",
    "build_lucas_scale_profile",
    "multiscale_coherence_probe",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (trace_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("trace_kernel")(np.array([[1, 1], [1, 0]], dtype=object), n)
    result["module"] = __name__
    return result
