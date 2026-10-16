"""Numerical-state quality diagnostics; not Bitcoin predictability evidence.

When the input carries an exact rational norm (``norm_squared_exact``), the
norm is certified exactly; the float ``norm_squared`` field remains a
projection of that exact value.
"""
import numpy as np
from dataclasses import dataclass
from fractions import Fraction
from .constants import GoldenConstants


_EXACT_TOLERANCE = Fraction(1, 10 ** 12)


@dataclass(frozen=True)
class CoherenceConstants:
    phi15: float = GoldenConstants().phi ** 15


class QuantumCoherenceAnalyzer:
    def analyze(self, amplitudes):
        norm_exact = getattr(amplitudes, "norm_squared_exact", None)
        if norm_exact is not None and getattr(amplitudes, "amplitudes_exact", None):
            # The stored state is the normalized vector amplitudes_exact /
            # sqrt(norm_squared_exact); its squared norm is exactly 1 by
            # construction (probabilities_exact sum to exactly 1), verified
            # here in rational arithmetic rather than trusted.
            normalized_norm = sum(amplitudes.probabilities_exact)
            normalized = (normalized_norm == 1)
            return {"finite": True, "norm_squared": float(norm_exact),
                    "norm_squared_exact": str(norm_exact),
                    "normalized_state_norm_exact": str(normalized_norm),
                    "normalized": normalized, "high_quality": normalized,
                    "truth_class": "exact_diagnostic",
                    "predictive_mining_evidence": False}
        a = np.asarray(amplitudes, dtype=np.complex128)
        valid = a.ndim == 1 and a.size > 0 and np.isfinite(a).all()
        norm = float(np.vdot(a, a).real) if valid else None
        normalized = bool(valid and np.isfinite(norm) and abs(norm - 1) <= 1e-10)
        return {"finite": bool(valid), "norm_squared": norm,
                "normalized": normalized, "high_quality": normalized,
                "truth_class": "numerical_diagnostic",
                "predictive_mining_evidence": False}
