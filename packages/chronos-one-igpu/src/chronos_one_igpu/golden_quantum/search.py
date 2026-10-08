"""Budgeted classical search and exact Grover amplitude amplification.

``simulate_grover`` with the default phase pi executes the Grover iteration
in exact rational arithmetic: each amplitude is tracked as r_i / sqrt(N)
with r_i a Fraction, the oracle phase flip is exact multiplication by -1,
and the diffusion step r_i -> 2*mean(r) - r_i preserves rationals. Exact Born
weights are returned via ``probabilities_exact`` on the result.

A non-pi phase cannot be represented exactly; requesting one raises
ValueError naming the explicitly non-production ``simulate_grover_reference``.
``simulate_golden_feedback`` is a compatibility facade over the exact
engine; its transcendental golden-angle feedback is retained only as the
explicitly named non-production ``simulate_golden_feedback_reference``.
"""
from dataclasses import dataclass
from fractions import Fraction
import math

import numpy as np

from .constants import GoldenConstants
from .quantum_state import MathematicalQuantumState


@dataclass(frozen=True)
class SearchResult:
    candidate: object
    success: bool
    evaluations: int
    oracle_calls: int
    amplitudes: tuple = ()
    backend: str = "cpu_reference"
    probabilities_exact: tuple = ()


def _exact_grover(size, marked, iterations):
    """Exact Grover iteration: amplitudes r_i/sqrt(size), r_i rational."""
    n = size
    r = [Fraction(1)] * n
    inv_n = Fraction(1, n)
    for _ in range(iterations):
        for i in range(n):
            if marked[i]:
                r[i] = -r[i]
        mean = sum(r) * inv_n
        r = [2 * mean - v for v in r]
    return r


class MathematicalQuantumSearchEngine:
    def search(self, candidates, predicate, max_evaluations=4096):
        if type(max_evaluations) is not int or not 0 <= max_evaluations <= 65536:
            raise ValueError("bounded evaluation budget required")
        import itertools
        for i, candidate in enumerate(itertools.islice(candidates, max_evaluations), 1):
            if predicate(candidate):
                return SearchResult(candidate, True, i, i)
        return SearchResult(None, False, i if 'i' in locals() else 0, i if 'i' in locals() else 0)

    def simulate_grover(self, size, oracle, iterations=1, phase=math.pi):
        if type(size) is not int or not 1 <= size <= 4096 or type(iterations) is not int \
                or not 0 <= iterations <= 64 or not math.isfinite(phase):
            raise ValueError("bounded simulation required")
        # Evaluating the complete oracle mask on a CPU is O(N) work and is counted.
        marked = np.array([bool(oracle(i)) for i in range(size)])
        if phase != math.pi:
            raise ValueError(
                "exact Grover requires phase pi; for other phases call "
                "simulate_grover_reference (non-production FP64 reference)")
        r = _exact_grover(size, marked, iterations)
        probs_exact = tuple(v * v / size for v in r)
        amplitudes = tuple(complex(float(v) / math.sqrt(size)) for v in r)
        indices = np.flatnonzero(marked)
        if len(indices):
            best = max(indices, key=lambda i: probs_exact[i])
            candidate = int(best)
            success = True
        else:
            candidate = None
            success = False
        return SearchResult(candidate, success, size, size, amplitudes,
                            "cpu_exact", probs_exact)

    def simulate_grover_reference(self, size, oracle, iterations=1, phase=math.pi):
        """NON-PRODUCTION FP64 reference implementation of the Grover iteration."""
        if type(size) is not int or not 1 <= size <= 4096 or type(iterations) is not int \
                or not 0 <= iterations <= 64 or not math.isfinite(phase):
            raise ValueError("bounded simulation required")
        marked = np.array([bool(oracle(i)) for i in range(size)])
        a = np.full(size, 1 / math.sqrt(size), dtype=np.complex128)
        for _ in range(iterations):
            a[marked] *= np.exp(1j * phase)
            a = 2 * a.mean() - a
        state = MathematicalQuantumState(a)
        candidate = int(np.argmax(state.probabilities))
        return SearchResult(candidate if marked[candidate] else None, bool(marked[candidate]),
                            size, size, tuple(complex(x) for x in state.amplitudes),
                            "fp64_reference_nonproduction")


class GoldenQuantumComputer(MathematicalQuantumSearchEngine):
    def prioritize(self, candidates):
        values = list(candidates)
        # Exact golden ordering: key = frac(n / phi^2).  1/phi^2 = 2 - phi
        # exactly, so the fractional part lives in Q(phi) and comparisons are
        # exact integer arithmetic — no floating point anywhere in the sort.
        return sorted(values, key=lambda n: (_PhiFracKey(_phi_frac_key(n)), n))

    def simulate_golden_feedback(self, size, oracle, iterations=4):
        """Compatibility facade: exact amplitude amplification.

        The historical transcendental golden-angle feedback is replaced by the
        exact Grover engine; the contract (bounded SearchResult over the oracle)
        is preserved and strengthened. The FP64 feedback stays available only as
        simulate_golden_feedback_reference.
        """
        if type(size) is not int or not 1 <= size <= 4096 or type(iterations) is not int \
                or not 1 <= iterations <= 64:
            raise ValueError('bounded golden phase search required')
        marked = np.array([bool(oracle(i)) for i in range(size)])
        r = _exact_grover(size, marked, iterations)
        probs_exact = tuple(v * v / size for v in r)
        amplitudes = tuple(complex(float(v) / math.sqrt(size)) for v in r)
        indices = np.flatnonzero(marked)
        if len(indices):
            candidate = int(max(indices, key=lambda i: probs_exact[i]))
        else:
            candidate = None
        return SearchResult(candidate, candidate is not None, size, size,
                            amplitudes, "cpu_exact", probs_exact)

    def simulate_golden_feedback_reference(self, size, oracle, iterations=4):
        """NON-PRODUCTION FP64 golden-angle phase feedback (transcendental)."""
        if type(size) is not int or not 1 <= size <= 4096 or type(iterations) is not int \
                or not 1 <= iterations <= 64:
            raise ValueError('bounded golden phase search required')
        marked = np.array([bool(oracle(i)) for i in range(size)])
        a = np.full(size, 1 / math.sqrt(size), dtype=np.complex128)
        angle = GoldenConstants().golden_angle
        for step in range(iterations):
            marked_probability = float(np.sum(np.abs(a[marked]) ** 2))
            feedback = (1 - marked_probability) * math.sin((step + 1) * angle) / GoldenConstants().phi
            a[marked] *= np.exp(1j * (math.pi + feedback))
            a = 2 * a.mean() - a
            if abs(float(np.vdot(a, a).real) - 1) > 1e-10:
                raise ValueError('phase feedback norm invariant failed')
        indices = np.flatnonzero(marked)
        candidate = int(indices[np.argmax(np.abs(a[indices]) ** 2)]) if len(indices) else None
        return SearchResult(candidate, candidate is not None, size, size,
                            tuple(complex(x) for x in a), "fp64_reference_nonproduction")


def _ceil_n_phi(n):
    """Smallest integer m with m > n*phi, by exact integer arithmetic.

    n*phi < m  <=>  n*sqrt(5) < 2m - n.  With t = 2m - n (same parity as n),
    t is the smallest integer congruent to n (mod 2) satisfying t^2 > 5n^2.
    """
    t = math.isqrt(5 * n * n) + 1
    if (t - n) % 2:
        t += 1
    assert t * t > 5 * n * n
    return (t + n) // 2


def _phi_frac_key(n):
    """Exact representative of frac(n / phi^2) = frac(n(2 - phi)).

    n(2 - phi) = 2n - n*phi; its floor is 2n - ceil(n*phi) since n*phi is
    irrational. So frac = ceil(n*phi) - n*phi, which lives in Q(phi) as
    a + b*phi with a = ceil(n*phi), b = -n.
    """
    return (_ceil_n_phi(n), -n)


def _phi_compare(key1, key2):
    """Compare a1 + b1*phi vs a2 + b2*phi exactly.

    a + b*phi > 0  <=>  2a + b > -b*sqrt5.  Compare signs exactly via squares.
    """
    a = key1[0] - key2[0]
    b = key1[1] - key2[1]
    lhs = 2 * a + b  # compare lhs vs -b*sqrt(5)
    rhs_coeff = -b
    if lhs >= 0 and rhs_coeff <= 0:
        return 1 if lhs > 0 or rhs_coeff < 0 else 0
    if lhs <= 0 and rhs_coeff >= 0:
        return -1 if lhs < 0 or rhs_coeff > 0 else 0
    # same-sign sides: compare lhs^2 vs 5*rhs_coeff^2, sign by sign(lhs)
    diff = lhs * lhs - 5 * rhs_coeff * rhs_coeff
    if lhs > 0:
        return 1 if diff > 0 else (-1 if diff < 0 else 0)
    return -1 if diff > 0 else (1 if diff < 0 else 0)


class _PhiFracKey:
    """Sortable wrapper performing exact Q(phi) comparisons."""
    __slots__ = ("key",)

    def __init__(self, key):
        self.key = key

    def __lt__(self, other):
        return _phi_compare(self.key, other.key) < 0

    def __eq__(self, other):
        return self.key == other.key
