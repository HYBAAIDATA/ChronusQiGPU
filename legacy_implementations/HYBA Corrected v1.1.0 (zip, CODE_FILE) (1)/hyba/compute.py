"""
HYBA Compute — φ-Scaled Training & Inference (Corrected)

Bug 5 fix: compass_lift/compass_unlift enforce integer-only inputs.
  - Uses isinstance(x, Integral) check (works with numpy int64 too)
  - Raises TypeError on float inputs
  - Uses round-half-away-from-zero for deterministic reversibility

Efficiency fix: accel_collapse now documents that 'value' parameter is
  unused — it computes the Pisot sequence value, not a collapse of input.
"""

import math
from typing import Tuple, List, Optional, Dict, Any
from numbers import Integral

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _round_half_away_from_zero(x: float) -> int:
    """Deterministic rounding: round half away from zero.

    Python's built-in round() uses banker's rounding (round half to even),
    which can produce inconsistent results in lifting schemes.
    Round-half-away-from-zero is deterministic and reversible.
    """
    if x >= 0:
        return int(x + 0.5)
    else:
        return int(x - 0.5)


class HYBACompute:
    """
    HYBA Compute Substrate (Corrected)

    Provides:
    - Cortex: M_φ fold (exact integer invertibility)
    - Accel: x²−3x−1 Pisot collapse (12 multiplies for 1e-6)
    - Compass: Golden-angle lifting (integer-only, reversible)
    """

    def __init__(self):
        self._phi = (1 + math.sqrt(5)) / 2
        self._psi = (1 - math.sqrt(5)) / 2
        self._sqrt5 = math.sqrt(5)
        self._golden_angle = 2 * math.pi * (1 - 1 / self._phi)
        self._lucas_15 = self._lucas(15)  # 1364
        self._cos_ga = math.cos(self._golden_angle)
        self._sin_ga = math.sin(self._golden_angle)

    def _lucas(self, n: int) -> int:
        if n == 0:
            return 2
        if n == 1:
            return 1
        a, b = 2, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return a

    def _fibonacci(self, n: int) -> int:
        if n == 0:
            return 0
        if n == 1:
            return 1
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    # ─── Cortex: M_φ Fold ──

    def cortex_fold(self, x) -> list:
        """Apply M_φ fold to feature space."""
        if HAS_NUMPY:
            x = np.asarray(x, dtype=np.int64)
            folded = x.copy()
            for i in range(0, len(folded) - 1, 2):
                a, b = folded[i], folded[i+1]
                folded[i] = a + b
                folded[i+1] = a
            return folded
        else:
            folded = list(x)
            for i in range(0, len(folded) - 1, 2):
                a, b = folded[i], folded[i+1]
                folded[i] = a + b
                folded[i+1] = a
            return folded

    def cortex_unfold(self, y) -> list:
        """Exact inverse of M_φ fold."""
        if HAS_NUMPY:
            y = np.asarray(y, dtype=np.int64)
            unfolded = y.copy()
            for i in range(0, len(unfolded) - 1, 2):
                u, v = unfolded[i], unfolded[i+1]
                unfolded[i] = v
                unfolded[i+1] = u - v
            return unfolded
        else:
            unfolded = list(y)
            for i in range(0, len(unfolded) - 1, 2):
                u, v = unfolded[i], unfolded[i+1]
                unfolded[i] = v
                unfolded[i+1] = u - v
            return unfolded

    # ─── Accel: x²−3x−1 Pisot Collapse ──

    def accel_pisot(self, x: float, precision: float = 1e-6) -> int:
        """Pisot collapse using x²−3x−1. Returns iterations for precision."""
        root = (3 + math.sqrt(13)) / 2
        conj = (3 - math.sqrt(13)) / 2
        n = int(math.log(precision) / math.log(abs(conj))) + 1
        return max(1, n)

    def accel_multiplies(self, precision: float = 1e-6) -> int:
        """Number of multiplies needed for given precision."""
        return self.accel_pisot(0.0, precision)

    def accel_collapse(self, value: float, n: Optional[int] = None) -> int:
        """
        Compute the n-th term of the Pisot sequence for x²−3x−1.

        NOTE: The 'value' parameter is not used in this computation.
        The sequence is λ₃ⁿ + ψ₃ⁿ where λ₃ = (3+√13)/2 ≈ 3.303.
        For large n, ψ₃ⁿ → 0, so the result approaches λ₃ⁿ.

        This is a Pisot sequence computation, not a collapse of 'value'.
        """
        if n is None:
            n = self.accel_multiplies(1e-6)
        root = (3 + math.sqrt(13)) / 2
        conj = (3 - math.sqrt(13)) / 2
        result = root ** n + conj ** n
        return int(round(result))

    # ─── Compass: Golden-Angle Lifting (BUG 5 FIXED) ──

    def compass_lift(self, x, y) -> Tuple[int, int]:
        """
        Golden-angle 3-shear integer lifting transform.

        CORRECTED (Bug 5): Enforces integer-only inputs.
        - Accepts int, numpy.int64, and other Integral types
        - Raises TypeError on float inputs
        - Uses round-half-away-from-zero for deterministic reversibility

        Args:
            x, y: Integer coordinates.

        Returns:
            (x', y') — lifted integer coordinates.

        Raises:
            TypeError: if x or y is not an integer.
        """
        if not isinstance(x, Integral) or not isinstance(y, Integral):
            raise TypeError(
                f"Golden-angle lifting requires integer inputs, "
                f"got ({type(x).__name__}, {type(y).__name__})"
            )

        x = int(x)
        y = int(y)

        # Shear 1: x' = x + round(y * cos(θ))
        x1 = x + _round_half_away_from_zero(y * self._cos_ga)

        # Shear 2: y' = y + round(x' * sin(θ))
        y1 = y + _round_half_away_from_zero(x1 * self._sin_ga)

        # Shear 3: x'' = x' + round(y' * cos(θ))
        x2 = x1 + _round_half_away_from_zero(y1 * self._cos_ga)

        return (x2, y1)

    def compass_unlift(self, x, y) -> Tuple[int, int]:
        """
        Inverse golden-angle 3-shear lifting.

        CORRECTED (Bug 5): Enforces integer-only inputs.
        Reverses the shears in opposite order.

        Args:
            x, y: Lifted integer coordinates.

        Returns:
            (x_orig, y_orig) — original integer coordinates.

        Raises:
            TypeError: if x or y is not an integer.
        """
        if not isinstance(x, Integral) or not isinstance(y, Integral):
            raise TypeError(
                f"Golden-angle unlifting requires integer inputs, "
                f"got ({type(x).__name__}, {type(y).__name__})"
            )

        x = int(x)
        y = int(y)

        # Undo Shear 3: x' = x - round(y * cos(θ))
        x1 = x - _round_half_away_from_zero(y * self._cos_ga)

        # Undo Shear 2: y_orig = y - round(x' * sin(θ))
        y0 = y - _round_half_away_from_zero(x1 * self._sin_ga)

        # Undo Shear 1: x_orig = x' - round(y_orig * cos(θ))
        x0 = x1 - _round_half_away_from_zero(y0 * self._cos_ga)

        return (x0, y0)

    def get_stats(self) -> Dict[str, Any]:
        return {
            'golden_angle_deg': self._golden_angle * 180 / math.pi,
            'golden_angle_rad': self._golden_angle,
            'lucas_15': self._lucas_15,
            'phi': self._phi,
        }
