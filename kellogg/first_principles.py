"""First-principles dynamical substrate.

Quantum structure in this repository is mathematics on a substrate. Nothing
here chooses a device. Floating-point diagnostics (Lyapunov exponents,
numerical residues, gap statistics of irrationals) are marked as such.
Exact claims use ``int`` or ``Fraction``.

The four probes are:

* P4 — Chirikov standard map. ``std(p)`` cannot separate a mode-locked
  island from a KAM torus. The maximal Lyapunov exponent separates chaos
  from both. Greene's residue of the golden-mean periodic approximants
  tends to 0 when the golden torus exists and leaves the critical band
  near 1/4 when it breaks. Action variance saturates on a torus and grows
  in the chaotic sea.
* P3 — circle packing by a constant angle. A coarse angular grid can tie
  137° with the golden angle. The continuous gap (the circle's Delaunay
  edge, and the Voronoi cell) does not. Past one full period the rational
  angle's covering excess grows like N; the golden excess stays bounded.
* P1 — quasi-Monte Carlo. Dimension 1 uses the golden ratio. Dimension d
  uses the generalized golden ratio, the positive root of
  ``x^{d+1} = x + 1``. The plastic number is that root at d = 2. Three
  plastic powers are linearly dependent and are rejected for the unit
  cube. A Fibonacci–Korobov lattice is the two-dimensional golden rule.
* Execution — fractional parts that must not drift are integer modular
  arithmetic. Z-order layout is an integer locality key. The operation
  count and the modeled miss cost are an Aethel overhead ledger; they are
  not a measured device throughput.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Callable, Sequence

import numpy as np

# Greene's numerical threshold for the golden invariant curve of the
# standard map. It is a probe value from the literature, not a theorem
# proved in this module.
GOLDEN_KAM_CRITICAL_K = 0.971635406

_TWO_PI = 2.0 * math.pi


class ConvergenceError(RuntimeError):
    """A periodic-orbit solver failed to close."""


def fibonacci_number(n: int) -> int:
    """Return F_n with F_0 = 0, F_1 = 1."""
    if n < 0:
        raise ValueError("n must be non-negative")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def generalized_golden(dimension: int) -> float:
    """Positive root of x^{d+1} = x + 1.

    d = 1 is the golden ratio. d = 2 is the plastic number. d = 3 is the
    generator whose first three negative powers fill the unit cube.
    """
    if dimension < 1:
        raise ValueError("dimension must be positive")
    # Newton on f(x) = x^{d+1} - x - 1. The root lies in (1, 2).
    value = 1.5
    for _ in range(60):
        power = value**dimension
        function = value * power - value - 1.0
        derivative = (dimension + 1) * power - 1.0
        value -= function / derivative
    return value


def plastic_number() -> float:
    """The plastic number, generalized_golden(2)."""
    return generalized_golden(2)


def golden_ratio() -> float:
    """(1 + sqrt(5)) / 2, the same root as generalized_golden(1)."""
    return (1.0 + math.sqrt(5.0)) / 2.0


def golden_turn() -> float:
    """Circle fraction 1/φ², the golden angle as a turn in [0, 1)."""
    phi = golden_ratio()
    return 1.0 / (phi * phi)


# ---------------------------------------------------------------------------
# P4. Standard map, Lyapunov, Greene residue, action variance.


def standard_map_step(K: float, theta: float, momentum: float) -> tuple[float, float]:
    """One step of the Chirikov standard map on the lift of momentum."""
    momentum = momentum + (K / _TWO_PI) * math.sin(_TWO_PI * theta)
    theta = (theta + momentum) % 1.0
    return theta, momentum


def maximal_lyapunov(
    K: float,
    theta: float,
    momentum: float,
    steps: int,
    tangent: tuple[float, float] = (1.0, 1.0),
) -> float:
    """Finite-time maximal Lyapunov exponent of the standard map.

    Diagnostic float. Renormalized tangent growth. For the integrable
    map K = 0 a generic tangent grows linearly, so this average tends to 0
    as ``steps`` increases. A chaotic orbit converges to a positive value.
    """
    if steps < 1:
        raise ValueError("steps must be positive")
    v_theta, v_momentum = tangent
    total = 0.0
    for _ in range(steps):
        cosine = K * math.cos(_TWO_PI * theta)
        v_momentum = v_momentum + cosine * v_theta
        v_theta = v_theta + v_momentum
        norm = math.hypot(v_theta, v_momentum)
        if norm == 0.0:
            raise ConvergenceError("tangent collapsed")
        total += math.log(norm)
        v_theta /= norm
        v_momentum /= norm
        theta, momentum = standard_map_step(K, theta, momentum)
    return total / steps


def shear_monodromy(period: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """q-th power of the K = 0 Jacobian [[1, 1], [0, 1]], exactly [[1, q], [0, 1]]."""
    if period < 1:
        raise ValueError("period must be positive")
    return ((1, period), (0, 1))


def residue_from_trace(trace: int) -> Fraction:
    """Greene residue (2 - Tr) / 4."""
    return Fraction(2 - trace, 4)


def elliptic_island_residue(K: float) -> float:
    """Residue of the period-1 elliptic point (θ, p) = (1/2, 0).

    The Jacobian trace is 2 - K, so R = K/4. This is the mode-locked
    residue: it does not tend to 0 when the golden approximants do.
    """
    return K / 4.0


def greene_residue(K: float, period: int, winding: int) -> tuple[float, float]:
    """Greene residue of the minimizing orbit with rotation winding/period.

    Returns ``(residue, closure_error)``. The configuration Newton solver
    starts from the integrable uniform advance. ``ConvergenceError`` is
    raised when the orbit does not close.
    """
    if period < 2:
        raise ValueError("period must be at least 2")
    if not 0 < winding < period:
        raise ValueError("winding must lie strictly between 0 and period")
    theta = np.array([i * winding / period for i in range(period)], dtype=float)
    scale = K / _TWO_PI
    residual = theta
    for _ in range(40):
        predecessor = np.empty(period)
        successor = np.empty(period)
        predecessor[0] = theta[-1] - winding
        predecessor[1:] = theta[:-1]
        successor[-1] = theta[0] + winding
        successor[:-1] = theta[1:]
        residual = successor - 2.0 * theta + predecessor - scale * np.sin(_TWO_PI * theta)
        if float(np.max(np.abs(residual))) < 1e-14:
            break
        jacobian = np.zeros((period, period))
        index = np.arange(period)
        jacobian[index, index] = -2.0 - K * np.cos(_TWO_PI * theta)
        jacobian[index, (index + 1) % period] += 1.0
        jacobian[index, (index - 1) % period] += 1.0
        step = np.linalg.solve(jacobian, residual)
        theta = theta - step
    closure = float(np.max(np.abs(residual)))
    if closure > 1e-8:
        raise ConvergenceError(
            f"golden approximant period {period} did not close (error {closure})"
        )
    monodromy = np.eye(2)
    for angle in theta:
        cosine = K * math.cos(_TWO_PI * float(angle))
        jacobian_step = np.array([[1.0 + cosine, 1.0], [cosine, 1.0]])
        monodromy = jacobian_step @ monodromy
    trace = float(monodromy[0, 0] + monodromy[1, 1])
    return (2.0 - trace) / 4.0, closure


def action_series(K: float, theta: float, momentum: float, steps: int) -> np.ndarray:
    """Lifted momentum samples. Diagnostic float. K = 0 is identically constant."""
    values = np.empty(steps, dtype=float)
    for index in range(steps):
        theta, momentum = standard_map_step(K, theta, momentum)
        values[index] = momentum
    return values


def action_variance(K: float, theta: float, momentum: float, steps: int) -> float:
    """Variance of the lifted action. Zero at K = 0."""
    return float(np.var(action_series(K, theta, momentum, steps)))


# ---------------------------------------------------------------------------
# P3. Continuous gaps on the circle. The grid score is the artifact.


def circle_gaps(alpha: float, count: int) -> tuple[float, float]:
    """Maximum and minimum arc between ``count`` points spaced by ``alpha``.

    On the circle these arcs are the Delaunay edges. Voronoi cell lengths
    are the sums of the two adjacent half-edges, so their variance is a
    function of this same multiset.
    """
    if count < 2:
        raise ValueError("count must be at least 2")
    placed = sorted((index * alpha) % 1.0 for index in range(count))
    gaps = [placed[index + 1] - placed[index] for index in range(count - 1)]
    gaps.append(placed[0] + 1.0 - placed[-1])
    return max(gaps), min(gaps)


def circle_gaps_exact(alpha: Fraction, count: int) -> tuple[Fraction, Fraction]:
    """Exact maximum and minimum arc for a rational turn."""
    if count < 2:
        raise ValueError("count must be at least 2")
    placed = sorted((Fraction(index) * alpha) % 1 for index in range(count))
    gaps = [placed[index + 1] - placed[index] for index in range(count - 1)]
    gaps.append(placed[0] + 1 - placed[-1])
    return max(gaps), min(gaps)


def covering_excess(alpha: float, count: int) -> float:
    """``count * max_gap``. Bounded for the golden turn; grows for a rational."""
    maximum, _minimum = circle_gaps(alpha, count)
    return count * maximum


def rational_saturated_excess(numerator: int, denominator: int, count: int) -> Fraction:
    """Covering excess once a coprime rational turn has filled its period.

    For N greater than or equal to the denominator, the distinct points are
    exactly the denominator equally spaced sites, so the max gap is
    1/denominator and the excess is N/denominator.
    """
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if math.gcd(numerator, denominator) != 1:
        raise ValueError("numerator and denominator must be coprime")
    if count < denominator:
        raise ValueError("saturation requires count >= denominator")
    return Fraction(count, denominator)


def grid_occupancy_std(alpha: float, count: int, bins: int) -> float:
    """Standard deviation of bin counts. This is the discrete-grid artifact."""
    if bins < 1:
        raise ValueError("bins must be positive")
    counts = [0] * bins
    for index in range(count):
        bucket = int(((index * alpha) % 1.0) * bins) % bins
        counts[bucket] += 1
    mean = count / bins
    variance = sum((seen - mean) ** 2 for seen in counts) / bins
    return math.sqrt(variance)


def golden_angle_degrees() -> float:
    """360 / φ². Diagnostic float, about 137.507764 degrees."""
    return 360.0 * golden_turn()


# ---------------------------------------------------------------------------
# P1. Kronecker sequences, generalized goldens, Fibonacci–Korobov lattice.


def kronecker_points(count: int, alphas: Sequence[float]) -> np.ndarray:
    """Rows ``({k α_1}, ..., {k α_d})`` for k = 0 .. count-1."""
    if count < 1:
        raise ValueError("count must be positive")
    coefficients = np.asarray(alphas, dtype=float)
    indices = np.arange(count, dtype=float)[:, None]
    return np.mod(indices * coefficients, 1.0)


def additive_recurrence(count: int, dimension: int) -> np.ndarray:
    """Kronecker sequence on the negative powers of the generalized golden root."""
    generator = generalized_golden(dimension)
    alphas = [generator ** (-index) for index in range(1, dimension + 1)]
    return kronecker_points(count, alphas)


def fibonacci_lattice(index: int) -> tuple[tuple[Fraction, Fraction], ...]:
    """Exact 2D Fibonacci–Korobov lattice at modulus F_index.

    Points are ``(k / F_n, {k F_{n-1} / F_n})``. This is the golden lattice
    that fills the square. It is not the sequence ``({k/φ}, {k/φ²})``, which
    lies on the line x + y ∈ ℤ because 1/φ + 1/φ² = 1.
    """
    if index < 3:
        raise ValueError("index must be at least 3")
    modulus = fibonacci_number(index)
    step = fibonacci_number(index - 1)
    points = []
    for k in range(modulus):
        points.append((Fraction(k, modulus), Fraction((k * step) % modulus, modulus)))
    return tuple(points)


def korobov_points(count: int, generator: int, dimension: int) -> tuple[tuple[Fraction, ...], ...]:
    """Exact Korobov lattice ``({k a^{i} / N})`` for i = 0 .. dimension-1."""
    if count < 2 or dimension < 1:
        raise ValueError("count and dimension must be positive")
    powers = []
    value = 1 % count
    for _ in range(dimension):
        powers.append(value)
        value = (value * generator) % count
    points = []
    for k in range(count):
        points.append(tuple(Fraction((k * power) % count, count) for power in powers))
    return tuple(points)


def integrate(points: np.ndarray, integrand: Callable[[np.ndarray], np.ndarray]) -> float:
    """Sample mean of ``integrand`` on rows of ``points``. Diagnostic float."""
    values = integrand(points)
    return float(np.mean(values))


def half_interval_count(alpha: float, count: int) -> int:
    """How many of ``{k α}``, k = 0 .. count-1, fall in [0, 1/2)."""
    return sum(1 for k in range(count) if (k * alpha) % 1.0 < 0.5)


def plastic_powers_dependent(samples: int = 8) -> bool:
    """True when 1/ψ² + 1/ψ³ is 1, the relation that collapses the 3-cube.

    From ψ³ = ψ + 1 one gets ψ^{-2} + ψ^{-3} = 1. A Kronecker sequence on
    three plastic powers therefore lies in a plane.
    """
    psi = plastic_number()
    total = psi ** -2 + psi ** -3
    return abs(total - 1.0) < 1e-9 and samples > 0


# ---------------------------------------------------------------------------
# Drift-free fractional parts, and the integer Z-order key.


def exact_fractional(count: int, numerator: int, modulus: int) -> Fraction:
    """``{count * numerator / modulus}`` with unbounded integers. No drift."""
    if modulus <= 0:
        raise ValueError("modulus must be positive")
    return Fraction((count * numerator) % modulus, modulus)


def bitwise_word(count: int, multiplier: int, bits: int) -> int:
    """Low ``bits`` of ``count * multiplier``. Identical to reduction mod 2^bits."""
    if bits < 1 or bits > 63:
        raise ValueError("bits must lie in 1..63")
    mask = (1 << bits) - 1
    return (count * multiplier) & mask


def float_fractional(count: int, alpha: float) -> float:
    """IEEE fractional part. Diagnostic. Drifts once ``count`` is not exact."""
    return math.modf(count * alpha)[0] % 1.0


def morton_encode(x: int, y: int, bits: int = 8) -> int:
    """Interleave the low ``bits`` of x and y. Z-order locality key."""
    if bits < 1 or bits > 16:
        raise ValueError("bits must lie in 1..16")
    limit = 1 << bits
    if not (0 <= x < limit and 0 <= y < limit):
        raise ValueError("coordinates do not fit in the bit width")
    code = 0
    for bit in range(bits):
        code |= ((x >> bit) & 1) << (2 * bit)
        code |= ((y >> bit) & 1) << (2 * bit + 1)
    return code


def morton_decode(code: int, bits: int = 8) -> tuple[int, int]:
    """Inverse of ``morton_encode``."""
    x = 0
    y = 0
    for bit in range(bits):
        x |= ((code >> (2 * bit)) & 1) << bit
        y |= ((code >> (2 * bit + 1)) & 1) << bit
    return x, y


def row_major_address(x: int, y: int, width: int) -> int:
    return y * width + x


__all__ = [
    "GOLDEN_KAM_CRITICAL_K",
    "ConvergenceError",
    "fibonacci_number",
    "generalized_golden",
    "plastic_number",
    "golden_ratio",
    "golden_turn",
    "standard_map_step",
    "maximal_lyapunov",
    "shear_monodromy",
    "residue_from_trace",
    "elliptic_island_residue",
    "greene_residue",
    "action_series",
    "action_variance",
    "circle_gaps",
    "circle_gaps_exact",
    "covering_excess",
    "rational_saturated_excess",
    "grid_occupancy_std",
    "golden_angle_degrees",
    "kronecker_points",
    "additive_recurrence",
    "fibonacci_lattice",
    "korobov_points",
    "integrate",
    "half_interval_count",
    "plastic_powers_dependent",
    "exact_fractional",
    "bitwise_word",
    "float_fractional",
    "morton_encode",
    "morton_decode",
    "row_major_address",
]
