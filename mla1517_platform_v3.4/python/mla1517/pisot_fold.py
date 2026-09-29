"""Pisot fold — fold state while retaining everything needed to reconstruct.

A fold is a REPRESENTATION change, not a compression claim. What this
module guarantees is invertibility: given the folded state plus the retained
residual, the original exact integer is recovered bit-for-bit.

What it does NOT do, by design:
  * claim fewer physical bytes,
  * claim more logical state per physical byte,
  * discard the conjugate component needed for exact reconstruction.

The residual is the honest part. ``|psi| < 1`` means the Pisot conjugate
decays, so at high index the dominant term determines the integer and the
residual is exactly zero. This module REPORTS the residual rather than
assuming it, so "lossless" is measured, not asserted.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict

from .binet_view import binet_exact
from .fibonacci_store import fib_pair

__all__ = ["FoldState", "FoldResult", "pisot_fold", "pisot_unfold", "is_lossless"]


@dataclass(frozen=True)
class FoldState:
    """The folded representation plus everything required to invert it."""

    index: int
    exact_value: int
    dominant: Fraction
    conjugate: Fraction
    residual: Fraction
    family: str
    lossless: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "exact_value": self.exact_value,
            "family": self.family,
            "lossless": self.lossless,
            "residual_numerator": str(self.residual.numerator),
            "residual_denominator": str(self.residual.denominator),
        }


@dataclass(frozen=True)
class FoldResult:
    """Outcome of a fold, with the proof state attached."""

    folded: FoldState
    cassini_seal: int
    exactness_status: str

    def as_dict(self) -> Dict[str, Any]:
        d = self.folded.as_dict()
        d["cassini_seal"] = self.cassini_seal
        d["exactness_status"] = self.exactness_status
        return d


def pisot_fold(index: int, *, family: str = "fibonacci", lossless: bool = True) -> FoldResult:
    """Fold a Fibonacci state into its Pisot-dominant form.

    ``lossless=True`` retains the exact integer and the conjugate term, so
    the fold is reversible. ``lossless=False`` keeps only the dominant
    rational and the status reports the loss rather than hiding it.
    """
    from .constants import cassini_seal as expected_seal

    if index < 0:
        raise ValueError("index must be non-negative")
    view = binet_exact(index)
    exact_value = view.exact
    retained = lossless
    status = "exact" if view.residual == 0 else "bounded_residual"
    return FoldResult(
        folded=FoldState(
            index=index,
            exact_value=exact_value if retained else 0,
            dominant=view.dominant,
            conjugate=view.conjugate if retained else Fraction(0),
            residual=view.residual,
            family=family,
            lossless=retained,
        ),
        cassini_seal=expected_seal(index),
        exactness_status=status if retained else "approximate",
    )


def pisot_unfold(folded: FoldState) -> int:
    """Recover the exact integer from a folded state.

    Raises when the state was folded losslessly=False, because the
    information required to invert it was discarded by request. Returning a
    wrong integer here would be the worst possible failure mode.
    """
    if not folded.lossless:
        raise ValueError(
            "cannot unfold: the fold was not lossless, so the exact value " "was not retained"
        )
    recovered = fib_pair(folded.index)[0]
    if recovered != folded.exact_value:
        raise ValueError(
            f"fold/unfold mismatch at index {folded.index}: " f"{recovered} != {folded.exact_value}"
        )
    return recovered


def is_lossless(folded: FoldState) -> bool:
    """True when the folded state reconstructs exactly."""
    try:
        return pisot_unfold(folded) == folded.exact_value
    except ValueError:
        return False
