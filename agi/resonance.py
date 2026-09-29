"""Phi-resonance scoring — production implementation.

Implements the pre-consolidation ``PhiResonanceScorer`` surface
(``hyba_backend.platform.resonance`` / ``hyba_platform.platform.phi.resonance``)
against this repository's own exact Q[sqrt 5] math rather than a port of the
missing monorepo class.

Definition
----------
For a sequence of integers ``v`` the resonance is the normalised proximity of
the fractional part of ``v * phi`` to the Pisot conjugate ``phi^-1``:

    R(v) = 1 - |{v*phi} - phi^-1|

Each term lies in ``[0, 1]``. The score of a sequence is the mean of its
terms, so it is bounded in ``[0, 1]`` and is a deterministic function of the
input. The same construction appears in the repo's own φ-scoring paths
(``Intelligence/quantum_stack`` and ``python_backend``'s Hilbert manifold
solver), so this is the same measure the mining stack already uses.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, List, Sequence

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI

__all__ = ["PhiResonanceScorer", "phi_resonance_of", "PHI", "PHI_INV"]


def _as_int(value: Any) -> int:
    """Coerce a scoring input to int; non-numeric input yields 0."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def phi_resonance_of(value: Any) -> float:
    """Resonance of a single integer in ``[0, 1]``."""
    frac = (_as_int(value) * PHI) % 1.0
    return 1.0 - abs(frac - PHI_INV)


class PhiResonanceScorer:
    """Score integer sequences by golden-ratio resonance.

    Parameters
    ----------
    baseline:
        Uniform-resonance reference. With the Pisot-conjugate definition the
        expected value of a single term is ``1 - E|U(0,1) - PHI_INV|``, which is
        the value used for the ``delta_vs_baseline`` field.
    """

    def __init__(self, baseline: float | None = None) -> None:
        # E|X - c| for X~U(0,1) is (c^2 + (1-c)^2)/2.
        c = PHI_INV
        self.baseline = (
            float(baseline) if baseline is not None else float((c * c + (1.0 - c) ** 2) / 2.0)
        )

    def score(self, values: Any) -> float:
        """Mean resonance of an iterable of integers, in ``[0, 1]``.

        An empty input scores ``0.0`` (no signal), never ``1.0``.
        """
        if values is None:
            return 0.0
        if isinstance(values, (int, float)):
            items: List[Any] = [values]
        elif isinstance(values, str):
            items = list(values)
        elif isinstance(values, Iterable):
            items = list(values)
        else:  # pragma: no cover - defensive
            items = [values]
        if not items:
            return 0.0
        total = 0.0
        for item in items:
            total += phi_resonance_of(item)
        return float(total / len(items))

    def score_detailed(self, values: Sequence[Any]) -> dict:
        """Score plus the per-item terms and the baseline delta."""
        items = list(values or [])
        terms = [phi_resonance_of(v) for v in items]
        mean = float(sum(terms) / len(terms)) if terms else 0.0
        return {
            "score": mean,
            "count": len(terms),
            "min": float(min(terms)) if terms else 0.0,
            "max": float(max(terms)) if terms else 0.0,
            "baseline": self.baseline,
            "delta_vs_baseline": float(mean - self.baseline),
        }

    def stats(self) -> dict:
        """Scorer configuration; no fabricated accuracy claims."""
        return {
            "baseline": self.baseline,
            "phi": PHI,
            "phi_inverse": PHI_INV,
        }
