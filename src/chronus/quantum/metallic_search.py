"""Metallic-family generalized search iterates over F_257.

Standard Grover applies the reflection a_i -> 2*mu - a_i after each oracle
flip: a rotation whose angle is fixed by the oracle, giving the quadratic
speedup. This module generalizes the reflection coefficient to c, so the
iterate is a_i -> c*mu - a_i, and drives c with metallic-family constants.

Over a finite field the operators are not unitary, so the unitary-model
optimality bound does not formally constrain these iterates; the trajectory
is exact algebraic dynamics. Whether a larger c reduces iteration count is
an empirical question this module answers by exact computation.

Magnitude note: a finite field has no canonical norm. Amplification is
measured with the symmetric representative |a| = min(a, P - a), an
operational metric documented as such, not a Born probability.
"""

from dataclasses import dataclass
from fractions import Fraction

from chronus.quantum.statevector import INV_SQRT2, P, StateVector


class QSqrt2:
    """Exact element (a + b*sqrt(2)) / 2**e of the silver field Q(sqrt(2)).

    Grover amplitudes over N = 2**n states live here exactly: the uniform
    amplitude 2**(-n/2) is rational for even n and rational/sqrt(2) for odd
    n. All oracle/diffusion operations are rational, so trajectories never
    leave the field and never touch floating point.
    """

    __slots__ = ("a", "b", "e")

    def __init__(self, a: int, b: int = 0, e: int = 0) -> None:
        self.a, self.b, self.e = a, b, e

    @classmethod
    def uniform_amplitude(cls, num_qubits: int) -> "QSqrt2":
        """2**(-n/2): rational for even n, sqrt(2)/2**((n+1)/2) for odd n."""
        if num_qubits % 2 == 0:
            return cls(1, 0, num_qubits // 2)
        return cls(0, 1, (num_qubits + 1) // 2)

    def _aligned(self, other: "QSqrt2") -> tuple[int, int, int, int, int]:
        e = max(self.e, other.e)
        return self.a << (e - self.e), self.b << (e - self.e), \
            other.a << (e - other.e), other.b << (e - other.e), e

    def add(self, other: "QSqrt2") -> "QSqrt2":
        a1, b1, a2, b2, e = self._aligned(other)
        return QSqrt2(a1 + a2, b1 + b2, e)

    def scale(self, factor: Fraction) -> "QSqrt2":
        """Multiply by an exact rational with power-of-two denominator."""
        if factor.denominator & (factor.denominator - 1):
            raise ValueError("factor denominator must be a power of two")
        shift = factor.denominator.bit_length() - 1
        return QSqrt2(self.a * factor.numerator, self.b * factor.numerator,
                      self.e + shift)

    def neg(self) -> "QSqrt2":
        return QSqrt2(-self.a, -self.b, self.e)

    def sign(self) -> int:
        """Exact sign of a + b*sqrt(2) without floating point."""
        if self.a == 0 and self.b == 0:
            return 0
        if self.a >= 0 and self.b >= 0:
            return 1
        if self.a <= 0 and self.b <= 0:
            return -1
        # Opposite signs: compare a^2 with 2*b^2 exactly.
        comparison = self.a * self.a - 2 * self.b * self.b
        if comparison == 0:
            raise ValueError("a + b*sqrt(2) cannot be zero for nonzero integers")
        if self.a > 0:  # a > 0 > b: positive iff a^2 > 2b^2
            return 1 if comparison > 0 else -1
        return -1 if comparison > 0 else 1

    def magnitude(self) -> "QSqrt2":
        return self.neg() if self.sign() < 0 else self

    def gt(self, other: "QSqrt2") -> bool:
        return self.add(other.neg()).sign() > 0

    def to_dict(self) -> dict:
        return {"a": self.a, "b": self.b, "denominator": 1 << self.e}


def phase_iterate(state: StateVector, marked: int, alpha: int, beta: int) -> StateVector:
    """Phase-matched iterate: oracle phase alpha, diffusion phase beta.

    Standard Grover is alpha = beta = -1 (phase flip). General phase pairs
    rotate the two-dimensional invariant subspace by angles set by the pair;
    phase matching can make convergence exact (marked amplitude precisely 1)
    when the field contains the required phases.
    """
    if not (0 <= marked < len(state.amplitudes)):
        raise ValueError("marked index out of range")
    for value in (alpha, beta):
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < P:
            raise ValueError("phases must be field elements in [0, 257)")
    state.amplitudes[marked] = (alpha * state.amplitudes[marked]) % P
    n = len(state.amplitudes)
    mean = (sum(state.amplitudes) * pow(n, -1, P)) % P
    state.amplitudes = [
        ((1 + beta) * mean - beta * a) % P for a in state.amplitudes
    ]
    return state


def jform_one_shot_phases(num_qubits: int, marked_count: int = 1) -> list[tuple[int, int]]:
    """Closed-form phases for the alternate operator family D = I + beta*J.

    With diffusion a_i -> a_i + beta*mu and oracle phase alpha, one iterate
    cancels unmarked states and lands marked amplitudes on +/-1 when

        alpha = 1 + v/u,   beta = -N*u / (N*u + r*v),   v = +/-1

    over F_257, requiring N*u + r*v invertible. Both families are the same
    algebraic system under different parameterizations; this form matches
    the D = I + beta*J convention used in external telemetry.
    """
    if not isinstance(num_qubits, int) or isinstance(num_qubits, bool) or num_qubits < 1:
        raise ValueError("num_qubits must be a positive integer")
    n = 1 << num_qubits
    if not isinstance(marked_count, int) or not 1 <= marked_count < n:
        raise ValueError("marked_count must be in [1, 2**num_qubits)")
    u = pow(INV_SQRT2, num_qubits, P)
    nu = (n * u) % P
    pairs = []
    for v in (1, P - 1):
        denominator = (nu + marked_count * v) % P
        if denominator == 0:
            continue
        alpha = (1 + v * pow(u, -1, P)) % P
        beta = (-nu) * pow(denominator, -1, P) % P
        pairs.append((alpha, beta))
    if not pairs:
        raise ValueError("field lacks the phases required for this size and count")
    return pairs


def jform_iterate(state: StateVector, marked: int, alpha: int, beta: int) -> StateVector:
    """One iterate of the D = I + beta*J family on a dense statevector."""
    if not 0 <= marked < len(state.amplitudes):
        raise ValueError("marked index out of range")
    state.amplitudes[marked] = (alpha * state.amplitudes[marked]) % P
    n = len(state.amplitudes)
    mean = (sum(state.amplitudes) * pow(n, -1, P)) % P
    state.amplitudes = [(a + beta * mean) % P for a in state.amplitudes]
    return state


def one_shot_phases(num_qubits: int) -> list[tuple[int, int]]:
    """Closed-form phase pairs for exact one-iteration search over F_257.

    Derivation. With uniform amplitude u, oracle phase alpha and diffusion
    phase beta, one iterate maps |s> to |marked> iff the unmarked amplitudes
    vanish and the marked amplitude is +/-1. Eliminating the mean gives
    alpha = N*beta/(1+beta) - (N-1) and 1 - alpha = N/(1+beta), so exact
    convergence reduces to beta/(1+beta) = +/-k with k = (N*u)^-1 (mod 257).

    The two solutions are beta = +/-k/(1 -/+ k), alpha = +/-N*k - (N-1),
    whenever 1 ∓ k is invertible (equivalently N*u not congruent to +/-1).
    This is exact algebraic dynamics, not unitary evolution: the unitary
    optimality bound does not apply, and the field supplies phases that do
    not exist over the reals.
    """
    if not isinstance(num_qubits, int) or isinstance(num_qubits, bool) or num_qubits < 1:
        raise ValueError("num_qubits must be a positive integer")
    n = 1 << num_qubits
    u = pow(INV_SQRT2, num_qubits, P)
    k = pow((n * u) % P, -1, P)
    pairs = []
    for sign in (1, -1):
        denominator = (1 - sign * k) % P
        if denominator == 0:
            continue
        beta = (sign * k) * pow(denominator, -1, P) % P
        alpha = (sign * n * k - (n - 1)) % P
        pairs.append((alpha, beta))
    if not pairs:
        raise ValueError("field lacks the phases required for this size")
    return pairs


def exact_search(num_qubits: int, marked: int) -> StateVector:
    """One exact iteration to the marked state; result verified by construction."""
    alpha, beta = one_shot_phases(num_qubits)[0]
    state = StateVector(num_qubits)
    for qubit in range(num_qubits):
        state.apply("H", qubit)
    phase_iterate(state, marked, alpha, beta)
    amps = state.amplitudes
    if not (amps[marked] in (1, P - 1)
            and all(a == 0 for i, a in enumerate(amps) if i != marked)):
        raise ArithmeticError("exact search failed to converge; field phases unsuitable")
    return state


def one_shot_phases_multi(num_qubits: int, marked_count: int) -> list[tuple[int, int]]:
    """Closed-form phase pairs for one-shot search with r marked states.

    With r marked items the invariant subspace is still two-dimensional
    (uniform-over-marked, uniform-over-unmarked), and the same elimination
    that produced the single-marked form generalizes:

        beta/(1+beta) = +/-r*k,   alpha = 1 - N/(r*(1+beta)),   k = (N*u)^-1

    After one iterate every unmarked amplitude is exactly 0 and every marked
    amplitude is exactly +/-1: the marked set is identified in full. A sign
    branch is dropped when its denominator vanishes (N*u congruent to +/-r),
    in which case one pair remains sufficient.
    """
    if not isinstance(marked_count, int) or isinstance(marked_count, bool) \
            or not 1 <= marked_count < (1 << num_qubits):
        raise ValueError("marked_count must be an integer in [1, 2**num_qubits)")
    n = 1 << num_qubits
    u = pow(INV_SQRT2, num_qubits, P)
    k = pow((n * u) % P, -1, P)
    pairs = []
    for sign in (1, -1):
        rk = (marked_count * k) % P
        denominator = (1 - sign * rk) % P
        if denominator == 0:
            continue
        beta = (sign * rk) * pow(denominator, -1, P) % P
        alpha = (1 - n * pow((marked_count * (1 + beta)) % P, -1, P)) % P
        pairs.append((alpha, beta))
    if not pairs:
        raise ValueError("field lacks the phases required for this size and count")
    return pairs


def phase_iterate_multi(
    state: StateVector, marked: set[int], alpha: int, beta: int
) -> StateVector:
    """Phase iterate with an oracle flipping every state in the marked set."""
    if not marked or not all(0 <= m < len(state.amplitudes) for m in marked):
        raise ValueError("marked must be a non-empty set of in-range indices")
    for value in (alpha, beta):
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < P:
            raise ValueError("phases must be field elements in [0, 257)")
    for index in marked:
        state.amplitudes[index] = (alpha * state.amplitudes[index]) % P
    n = len(state.amplitudes)
    mean = (sum(state.amplitudes) * pow(n, -1, P)) % P
    state.amplitudes = [
        ((1 + beta) * mean - beta * a) % P for a in state.amplitudes
    ]
    return state


def exact_search_multi(num_qubits: int, marked: set[int]) -> StateVector:
    """One exact iteration identifying every marked state simultaneously."""
    alpha, beta = one_shot_phases_multi(num_qubits, len(marked))[0]
    state = StateVector(num_qubits)
    for qubit in range(num_qubits):
        state.apply("H", qubit)
    phase_iterate_multi(state, marked, alpha, beta)
    amps = state.amplitudes
    if not (all(amps[i] in (1, P - 1) for i in marked)
            and all(amps[i] == 0 for i in range(len(amps)) if i not in marked)):
        raise ArithmeticError("multi-marked exact search failed to converge")
    return state


def phase_matched_sweep(
    num_qubits: int, marked: int, max_iterations: int = 64
) -> dict:
    """Sweep all phase pairs over F_257 for exact convergence.

    Returns the minimal iteration count and phase pairs whose trajectory
    reaches marked amplitude magnitude 1 with all other amplitudes 0.
    Exhaustive for the given size: this is discovery by exact enumeration,
    not sampling.
    """
    best: dict[int, list[tuple[int, int]]] = {}
    for alpha in range(1, P):
        for beta in range(1, P):
            state = StateVector(num_qubits)
            for qubit in range(num_qubits):
                state.apply("H", qubit)
            for iteration in range(1, max_iterations + 1):
                phase_iterate(state, marked, alpha, beta)
                amps = state.amplitudes
                if all(a == 0 for i, a in enumerate(amps) if i != marked) \
                        and amps[marked] in (1, P - 1):
                    best.setdefault(iteration, []).append((alpha, beta))
                    break
    minimal = min(best) if best else None
    return {
        "num_qubits": num_qubits,
        "states": 1 << num_qubits,
        "minimal_iterations": minimal,
        "phase_pairs_at_minimum": best.get(minimal, []) if minimal else [],
        "exact_convergence_found": minimal is not None,
    }


def algebraic_search(
    family: str, num_qubits: int, max_iterations: int = 100_000
) -> tuple[int, list[int]]:
    """Exact algebraic search trajectory over Q(sqrt(2)).

    Amplitudes of the marked state and the unmarked states evolve as exact
    silver-field elements; returns (iterations_to_peak, per-doubling data).
    The marked amplitude is tracked exactly and peak detection uses exact
    field sign comparisons.
    """
    c = METALLIC_COEFFICIENTS[family]
    n = 1 << num_qubits
    marked = QSqrt2.uniform_amplitude(num_qubits)
    unmarked = QSqrt2.uniform_amplitude(num_qubits)
    history = [marked.a or marked.b]  # compact magnitude trace proxy
    best = marked.magnitude()
    peak = 0
    for iteration in range(1, max_iterations + 1):
        marked = marked.neg()  # oracle flip
        # Exact mean over N states: ((N-1)*unmarked + marked) / N.
        total = unmarked.scale(Fraction(n - 1)).add(marked)
        mean = total.scale(Fraction(1, n))
        marked = mean.scale(Fraction(c)).add(marked.neg())
        unmarked = mean.scale(Fraction(c)).add(unmarked.neg())
        magnitude = marked.magnitude()
        history.append(marked.a or marked.b)
        if magnitude.gt(best):
            best, peak = magnitude, iteration
        elif iteration > peak:
            break  # past first peak
    return peak, history

GROVER_C = 2
METALLIC_COEFFICIENTS = {
    "grover": 2,
    "golden": 3,    # m=1 family: c = 1 + sigma_1 trace ratio step
    "silver": 4,    # m=2
    "bronze": 5,    # m=3
    "metallic-4": 6,
    "metallic-8": 10,
}


def _magnitude(a: int) -> int:
    return min(a, P - a)


def generalized_iterate(state: StateVector, marked: int, c: int) -> StateVector:
    """Oracle flip, then a_i -> c*mu - a_i with exact field mean mu."""
    if not isinstance(c, int) or isinstance(c, bool) or not 1 <= c < P:
        raise ValueError("c must be an integer in [1, 257)")
    if not 0 <= marked < len(state.amplitudes):
        raise ValueError("marked index out of range")
    state.amplitudes[marked] = (P - state.amplitudes[marked]) % P
    n = len(state.amplitudes)
    mean = (sum(state.amplitudes) * pow(n, -1, P)) % P
    state.amplitudes = [(c * mean - a) % P for a in state.amplitudes]
    return state


@dataclass(frozen=True)
class SearchResult:
    family: str
    c: int
    num_qubits: int
    iterations_to_peak: int
    peak_magnitude: int
    trajectory_magnitudes: tuple[int, ...]


def run_search(
    family: str, num_qubits: int, marked: int, max_iterations: int = 512
) -> SearchResult:
    """Iterate until the marked amplitude peaks, recording the exact count."""
    c = METALLIC_COEFFICIENTS[family]
    state = StateVector(num_qubits)
    for qubit in range(num_qubits):
        state.apply("H", qubit)
    magnitudes = [_magnitude(state.amplitudes[marked])]
    best, peak = magnitudes[0], 0
    for iteration in range(1, max_iterations + 1):
        generalized_iterate(state, marked, c)
        magnitude = _magnitude(state.amplitudes[marked])
        magnitudes.append(magnitude)
        if magnitude > best:
            best, peak = magnitude, iteration
        if magnitude < best and iteration > peak:
            break  # past the first peak
    return SearchResult(family, c, num_qubits, peak, best, tuple(magnitudes))


def scaling_sweep(
    num_qubits_range: range = range(1, 9), max_iterations: int = 512
) -> dict[str, list[SearchResult]]:
    """Run every family across sizes; iteration counts are exact, not sampled."""
    results: dict[str, list[SearchResult]] = {name: [] for name in METALLIC_COEFFICIENTS}
    for n in num_qubits_range:
        marked = (1 << n) - 1
        for name in METALLIC_COEFFICIENTS:
            results[name].append(run_search(name, n, marked, max_iterations))
    return results
