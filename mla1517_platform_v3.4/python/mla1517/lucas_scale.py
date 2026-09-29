"""Lucas scale engine — exact transitions between ladder rungs.

Two complementary roles, kept distinct because conflating them is how
these systems mislead:

  Lucas  the DISCRETE, exact scale ladder. L_n is an exact integer.
  Pisot the CONVERGENCE behaviour of the conjugate term under that ladder.

A transition is ACCEPTED only when the proof and residual contracts pass.
A rejected transition returns a reason, never a degraded approximation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .constants import LADDER, cassini_seal
from .core import fib, lucas

__all__ = ["ScaleTransition", "next_ladder_index", "climb", "transition", "authorise"]


class ScaleRejected(RuntimeError):
    """A requested scale transition was refused, with a stated reason."""


@dataclass(frozen=True)
class ScaleTransition:
    """One rung-to-rung transition and the evidence that accepted it."""

    source_scale: int
    requested_scale: int
    accepted: bool
    reason: Optional[str]
    lucas_source: int
    lucas_target: int
    fib_source: int
    fib_target: int
    cassini_before: int
    cassini_after: int
    exactness_status: str

    @property
    def lucas_ratio(self) -> Optional[Any]:
        """Exact ratio L_target / L_source as a Fraction, or None at zero."""
        if self.lucas_source == 0:
            return None
        from fractions import Fraction

        return Fraction(self.lucas_target, self.lucas_source)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_scale": self.source_scale,
            "requested_scale": self.requested_scale,
            "accepted": self.accepted,
            "reason": self.reason,
            "lucas_source": self.lucas_source,
            "lucas_target": self.lucas_target,
            "fib_source": self.fib_source,
            "fib_target": self.fib_target,
            "cassini_before": self.cassini_before,
            "cassini_after": self.cassini_after,
            "exactness_status": self.exactness_status,
        }


def next_ladder_index(index: int, ladder: Tuple[int, ...] = LADDER) -> Optional[int]:
    """Next rung strictly above ``index``, or None at the top."""
    for rung in ladder:
        if rung > index:
            return rung
    return None


def climb(index: int, ladder: Tuple[int, ...] = LADDER) -> int:
    """Advance one rung. Stays at the top rather than overflowing."""
    nxt = next_ladder_index(index, ladder)
    return nxt if nxt is not None else index


def transition(source: int, target: int) -> ScaleTransition:
    """Evaluate a scale transition and attach its proof state.

    This does not refuse: it reports. :func:`authorise` is the gate.
    """
    if source < 0 or target < 0:
        raise ValueError("scale indices must be non-negative")
    seal_b = cassini_seal(source)
    seal_a = cassini_seal(target)
    f_s, f_t = fib(source), fib(target)
    l_s, l_t = lucas(source), lucas(target)
    # The Cassini identity must hold at both ends of the transition.
    holds = (l_s * l_s - 5 * f_s * f_s == 4 * seal_b) and (l_t * l_t - 5 * f_t * f_t == 4 * seal_a)
    return ScaleTransition(
        source_scale=source,
        requested_scale=target,
        accepted=holds and target > 0,
        reason=None if holds else "cassini_identity_failed",
        lucas_source=l_s,
        lucas_target=l_t,
        fib_source=f_s,
        fib_target=f_t,
        cassini_before=seal_b,
        cassini_after=seal_a,
        exactness_status="exact" if holds else "unknown",
    )


def authorise(
    source: int,
    target: int,
    *,
    ladder: Tuple[int, ...] = LADDER,
    max_index: int = 10**6,
    max_bit_length: int = 1 << 20,
    allow_off_ladder: bool = False,
) -> ScaleTransition:
    """Gate a transition against the declared budgets.

    Refusals are explicit and named, matching the declared vocabulary:
    ``index_out_of_bounds``, ``bit_budget_exceeded``, ``scale_program_too_long``.
    """
    t = transition(source, target)
    if target <= 0:
        return _replace(t, accepted=False, reason="index_out_of_bounds")
    if target > max_index:
        return _replace(t, accepted=False, reason="index_out_of_bounds")
    if len(ladder) > 0 and not allow_off_ladder and target not in ladder:
        return _replace(t, accepted=False, reason="family_not_allowed")
    if target.bit_length() > max_bit_length:
        return _replace(t, accepted=False, reason="bit_budget_exceeded")
    if not t.accepted:
        return t
    return t


def _replace(t: ScaleTransition, **changes: Any) -> ScaleTransition:
    """Return a copy of ``t`` with the named fields replaced."""
    return ScaleTransition(
        source_scale=t.source_scale,
        requested_scale=t.requested_scale,
        accepted=changes.get("accepted", t.accepted),
        reason=changes.get("reason", t.reason),
        lucas_source=t.lucas_source,
        lucas_target=t.lucas_target,
        fib_source=t.fib_source,
        fib_target=t.fib_target,
        cassini_before=t.cassini_before,
        cassini_after=t.cassini_after,
        exactness_status=t.exactness_status,
    )
