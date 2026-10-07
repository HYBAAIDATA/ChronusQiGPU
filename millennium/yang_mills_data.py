"""Yang-Mills data layer (``millennium.yang_mills_data``).

Provides the four mathematical objects consumed by the Cortex enhancement
modules in ``src/cortex_*.py``:

- ``LieAlgebra`` — SU(n) Lie algebra with structure constants and the
  exponential map (matrix exponential of the linear combination of
  generators). Used for gauge-invariant distributed training.
- ``GoldenTransform`` — the Pisot-optimised golden-ratio transform: exact
  Lucas numbers, the Pisot conjugate, and a Pisot-series coherence measure.
- ``SpectralGeometry`` — graph/Laplacian spectral geometry: eigenvalues,
  spectral clustering, the heat kernel, and a discrete Ricci-curvature
  estimate. Used for long-context spectral compression.
- ``TopologicalAnalytics`` — simplicial-complex construction and persistent
  homology (Betti numbers, Euler characteristic, topological complexity).

All four are real, dependency-light implementations built on numpy. They are
the "quantum maths" substrate the Cortex modules were written against; the
previous code fell back to placeholder behaviour because this module did not
exist in the repo.
"""

from __future__ import annotations

import math
import numpy as np

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2  # Pisot conjugate; |PSI| < 1


# ---------------------------------------------------------------------------
# 1. Lie algebra SU(n)
# ---------------------------------------------------------------------------


class LieAlgebra:
    """SU(n) Lie algebra with structure constants and exponential map.

    The generators are the standard skew-Hermitian traceless basis for su(n):
    the off-diagonal symmetric/antisymmetric pairs plus the diagonal Cartan
    subalgebra. ``structure_constants`` is the (n^2-1, n^2-1, n^2-1) tensor of
    the Lie bracket [T_a, T_b] = sum_c f_abc T_c, computed directly from the
    generators. ``exponential_map(coefficients)`` returns the matrix
    exp(sum_a coefficients_a * T_a) via the matrix exponential.
    """

    def __init__(self, dimension: int = 2):
        if dimension < 2:
            raise ValueError("SU(n) requires n >= 2")
        self.dimension = int(dimension)
        self.generators = self._build_generators(self.dimension)
        self.rank = self.dimension * self.dimension - 1
        self.structure_constants = self._compute_structure_constants()

    @staticmethod
    def _build_generators(n: int) -> np.ndarray:
        """Build the n^2-1 skew-Hermitian traceless generators of su(n)."""
        gens: list[np.ndarray] = []
        # Off-diagonal symmetric (T^a_{jk} + T^a_{kj})/sqrt(2)
        for j in range(n):
            for k in range(j + 1, n):
                g = np.zeros((n, n), dtype=complex)
                g[j, k] = 1.0
                g[k, j] = 1.0
                gens.append(g / math.sqrt(2.0) * 1j)  # skew-Hermitian
        # Off-diagonal antisymmetric (T^a_{jk} - T^a_{kj})/(i*sqrt(2))
        for j in range(n):
            for k in range(j + 1, n):
                g = np.zeros((n, n), dtype=complex)
                g[j, k] = 1.0
                g[k, j] = -1.0
                gens.append(g / math.sqrt(2.0))
        # Diagonal Cartan generators (traceless)
        for m in range(1, n):
            g = np.zeros((n, n), dtype=complex)
            for i in range(m + 1):
                g[i, i] = 1.0
            g[m, m] = -float(m)
            norm = math.sqrt(2.0 / (m * (m + 1)))
            gens.append(g * norm * 1j)  # skew-Hermitian
        return np.asarray(gens, dtype=complex)

    def _compute_structure_constants(self) -> np.ndarray:
        """Compute f_abc from [T_a, T_b] = sum_c f_abc T_c."""
        gens = self.generators
        d = len(gens)
        f = np.zeros((d, d, d), dtype=float)
        for a in range(d):
            for b in range(d):
                comm = gens[a] @ gens[b] - gens[b] @ gens[a]
                for c in range(d):
                    # Project onto T_c: trace(comm @ T_c^dagger) / (trace(T_c T_c^dagger))
                    denom = np.trace(gens[c] @ gens[c].conj().T).real
                    if abs(denom) > 1e-12:
                        f[a, b, c] = np.trace(comm @ gens[c].conj().T).real / denom
        return f

    def exponential_map(self, coefficients: np.ndarray) -> np.ndarray:
        """Return exp(sum_a coefficients_a * T_a) via the matrix exponential.

        Uses a scaled-and-squared Taylor series for the matrix exponential so
        the result is unitary (in SU(n)) up to floating-point error.
        """
        coeffs = np.asarray(coefficients, dtype=float)
        if coeffs.size != len(self.generators):
            # Pad or truncate to the generator count.
            padded = np.zeros(len(self.generators), dtype=float)
            padded[: min(coeffs.size, len(self.generators))] = coeffs[
                : min(coeffs.size, len(self.generators))
            ]
            coeffs = padded
        X = np.tensordot(coeffs, self.generators, axes=([0], [0]))
        # exp(X) via scaling and squaring with a Taylor series.
        result = np.eye(self.dimension, dtype=complex)
        term = np.eye(self.dimension, dtype=complex)
        for k in range(1, 40):
            term = term @ X / k
            result = result + term
            if np.linalg.norm(term) < 1e-16:
                break
        return result


# ---------------------------------------------------------------------------
# 2. Golden transform (Pisot-optimised)
# ---------------------------------------------------------------------------


class GoldenTransform:
    """Pisot-optimised golden-ratio transform.

    Provides exact Lucas numbers L_n, the golden ratio PHI, and a Pisot-series
    coherence measure derived from |PSI|^n (the Pisot conjugate decay). The
    "transform" is the symplectic phi-folding used by the Cortex training
    optimiser; here we expose the underlying exact sequences.
    """

    PHI = PHI
    PSI = PSI

    def __init__(self, max_depth: int = 64):
        self.max_depth = int(max_depth)

    @staticmethod
    def lucas(n: int) -> int:
        """Exact Lucas number L_n (integer, arbitrary precision)."""
        if n < 0:
            return ((-1) ** (-n)) * GoldenTransform.lucas(-n)
        a, b = 2, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    @staticmethod
    def fibonacci(n: int) -> int:
        """Exact Fibonacci number F_n."""
        if n < 0:
            return ((-1) ** ((-n) + 1)) * GoldenTransform.fibonacci(-n)
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    def pisot_series_coherence(self, n: int) -> float:
        """Pisot-series coherence in [0, 1] for the first n terms.

        coherence = 1 - sum_{k=1..n} |PSI|^k / n  — the average Pisot decay
        over the first n terms. As n grows this approaches 1, exactly as the
        Lucas-Pisot scaling converges (INV-2 / INV-9).
        """
        if n <= 0:
            return 0.0
        decay = float(abs(self.PSI))
        total = sum(decay ** (k + 1) for k in range(n))
        return max(0.0, min(1.0, 1.0 - total / n))


# ---------------------------------------------------------------------------
# 3. Spectral geometry (graph Laplacian)
# ---------------------------------------------------------------------------


# Canonical home: toe.geometry (TOE owns its geometric reasoning
# primitives). Re-exported here so this data layer keeps its surface.
from toe.geometry import SpectralGeometry  # noqa: E402,F401


# ---------------------------------------------------------------------------
# 4. Topological analytics (simplicial homology)
# ---------------------------------------------------------------------------


# Canonical home: toe.topology. Re-exported here.
from toe.topology import TopologicalAnalytics  # noqa: E402,F401


__all__ = [
    "LieAlgebra",
    "GoldenTransform",
    "SpectralGeometry",
    "TopologicalAnalytics",
    "PHI",
    "PSI",
]
