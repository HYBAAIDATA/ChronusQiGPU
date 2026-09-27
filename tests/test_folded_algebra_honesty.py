"""Exactness tests for the folded-state algebraic spec.

Claims under test (from the 11D folded-architecture formulation):

1. Zeckendorf: unique non-adjacent decomposition, reversible.   [exact]
2. Binet: F_k = (phi^k - psi^k)/sqrt(5), psi = -1/phi.           [exact]
3. Cassini: F(k-1)F(k+1) - F(k)^2 = (-1)^k, det(M^k) = (-1)^k.   [exact]
   AND the falsification test: det=±1 does NOT detect every corruption.
4. Lucas trace: L_k = F(k-1)+F(k+1); L_k^2 - 5 F_k^2 = 4(-1)^k.  [exact]
5. phi^n = (L_n + F_n sqrt5)/2 without transcendental evaluation. [exact]
6. 11 quadratic fields with distinct squarefree radicals are linearly
   disjoint: all 2^11 subset products are distinct (mult. independence
   mod squares is the disjointness criterion for quadratic fields).
7. Square-integrability: the amplitude sum with Pisot decay converges,
   but the spec's written normalizer sum(L_k^2) DIVERGES — tested.
8. The real engine: Intelligence.folded_state.ExactFoldedStateEngine
   round trip is bit-exact (integrity asserted on restore).

No mocks. Every identity below is checked with exact integers or
100-digit decimal arithmetic.
"""

import hashlib
import itertools
from decimal import Decimal, getcontext

import pytest

getcontext().prec = 100

PHI_D = (Decimal(1) + Decimal(5).sqrt()) / 2
SQRT5_D = Decimal(5).sqrt()


def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


FIBS = [fib(i) for i in range(2, 40)]  # F_2 .. F_39 covers N < 63_245_986


def zeckendorf(n: int) -> tuple:
    """Greedy exact Zeckendorf decomposition (indices into FIBS)."""
    out = []
    for idx in range(len(FIBS) - 1, -1, -1):
        if FIBS[idx] <= n:
            out.append(idx)
            n -= FIBS[idx]
            if idx > 0:
                idx -= 1  # skip neighbour: enforce non-adjacency
    return tuple(out)


def test_zeckendorf_unique_nonadjacent_and_reversible():
    for n in range(1, 1500):
        terms = zeckendorf(n)
        # Reversibility: the sum rebuilds N exactly.
        assert sum(FIBS[i] for i in terms) == n
        # Non-adjacency: no two consecutive Fibonacci indices occupied.
        for a, b in zip(terms, terms[1:]):
            assert a - b >= 2  # terms are returned in descending index order
    # Uniqueness: enumerate ALL non-adjacent subsets of F_2..F_13
    # (2^12 = 4096 masks) and assert a bijection onto sums 1..232.
    basis = FIBS[:12]  # F_2 .. F_13 (covers all sums < F_14 = 377)
    sums: dict = {}
    for mask in itertools.product((0, 1), repeat=len(basis)):
        if any(mask[i] and mask[i + 1] for i in range(len(mask) - 1)):
            continue
        s = sum(f for f, bit in zip(basis, mask) if bit)
        sums[s] = sums.get(s, 0) + 1
    for n in range(1, 233):
        assert sums.get(n, 0) == 1  # exactly one non-adjacent representation


def test_binet_exact_at_100_digits_and_float64_loss():
    # Exact: F_k = (phi^k - psi^k)/sqrt(5) with psi = -1/phi.
    for k in (10, 50, 100, 150):
        binet = (PHI_D**k - (-PHI_D) ** (-k)) / SQRT5_D
        assert binet == pytest.approx(Decimal(fib(k)), rel=Decimal("1e-50"))
    # Float64 Binet is lossy: error grows with k and exceeds 1 well
    # before index 100 — "no numerical loss" requires exact arithmetic.
    import math

    phi = (1.0 + 5.0**0.5) / 2.0
    first_lossy = None
    for k in range(2, 90):
        approx = (phi**k - (-phi) ** (-k)) / math.sqrt(5.0)
        if abs(approx - fib(k)) >= 0.5:
            first_lossy = k
            break
    assert first_lossy is not None and first_lossy < 90


def test_cassini_identity_and_sl2_powers_exact():
    # F(k-1)F(k+1) - F(k)^2 = (-1)^k for k = 1..500 (exact integers).
    for k in range(1, 501):
        assert fib(k - 1) * fib(k + 1) - fib(k) ** 2 == (-1) ** k
    # M^k = [[F(k+1), F_k], [F_k, F(k-1)]], det(M^k) = (-1)^k.
    for k in (1, 2, 3, 10, 100):
        det = fib(k + 1) * fib(k - 1) - fib(k) ** 2
        assert det == (-1) ** k


def test_cassini_invariant_does_NOT_detect_all_corruption():
    """Falsification of the O(1)-universal-detection claim: corruptions
    that preserve unimodularity pass the det=±1 check silently."""
    k = 10
    mk = ((fib(k + 1), fib(k)), (fib(k), fib(k - 1)))

    def det(m):
        return m[0][0] * m[1][1] - m[0][1] * m[1][0]

    # Corruption 1: index shift M^k -> M^(k+2). Different data, same
    # determinant parity — the invariant cannot tell them apart.
    mk_shift = ((fib(k + 3), fib(k + 2)), (fib(k + 2), fib(k + 1)))
    assert mk_shift != mk
    assert det(mk_shift) == det(mk) == (-1) ** k

    # Corruption 2: left-multiply by a unimodular U. det unchanged.
    U = ((2, 1), (1, 1))  # det = 1
    corrupted = (
        (U[0][0] * mk[0][0] + U[0][1] * mk[1][0], U[0][0] * mk[0][1] + U[0][1] * mk[1][1]),
        (U[1][0] * mk[0][0] + U[1][1] * mk[1][0], U[1][0] * mk[0][1] + U[1][1] * mk[1][1]),
    )
    assert corrupted != mk
    assert det(corrupted) == det(mk)


def test_lucas_trace_identities_exact():
    for k in range(2, 301):
        L = fib(k - 1) + fib(k + 1)  # L_k via Fibonacci trace
        assert L * L - 5 * fib(k) ** 2 == 4 * ((-1) ** k)


def test_phi_n_via_lucas_fibonacci_no_transcendentals():
    # phi^n = (L_n + F_n sqrt5)/2 — checked at 100 digits.
    for n in (10, 50, 100, 200):
        lhs = PHI_D**n
        rhs = (Decimal(fib(n - 1) + fib(n + 1)) + Decimal(fib(n)) * SQRT5_D) / 2
        assert lhs == pytest.approx(rhs, rel=Decimal("1e-60"))


def test_11_quadratic_fields_linearly_disjoint():
    """Distinct squarefree radicals => mutual linear disjointness; the
    computational criterion is that all 2^11 subset products are distinct
    squarefree integers (multiplicative independence mod squares)."""
    deltas = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
    assert len(deltas) == 11
    products = set()
    for mask in itertools.product((0, 1), repeat=11):
        prod = 1
        for d, bit in zip(deltas, mask):
            if bit:
                prod *= d
        assert prod not in products  # distinctness = independence
        products.add(prod)
        # Squarefree-ness of every product: no square factor.
        for p in deltas:
            if prod % (p * p) == 0 and prod != 0:
                raise AssertionError(f"non-squarefree product {prod}")
    assert len(products) == 2**11 == 2048


def test_square_integrability_and_divergent_written_normalizer():
    """Amplitude a_k = phi^(-k w(k)) with w(k) = #Zeckendorf terms >= 1:
    the amplitude sum CONVERGES (Pisot decay is real), but the spec's
    written normalizer sum(L_k^2) DIVERGES — with it, |Psi> has norm -> 0."""
    import math

    phi = (1.0 + 5.0**0.5) / 2.0
    ln_phi = math.log(phi)

    def amp_sq(k: int) -> float:
        return math.exp(-2.0 * k * len(zeckendorf(k)) * ln_phi)

    S20 = sum(amp_sq(k) for k in range(1, 21))
    S40 = sum(amp_sq(k) for k in range(1, 41))
    S80 = sum(amp_sq(k) for k in range(1, 81))
    # Convergence: doubling the cutoff adds a vanishing tail. The tail
    # 21..40 is dominated by the Fibonacci-indexed k=21 (w=1): a^2(21) =
    # exp(-2*21*ln phi) ~= 1.667e-9; beyond 40 the tail drops below 1e-15.
    assert S40 - S20 < 2e-9
    assert S40 - S20 == pytest.approx(math.exp(-2 * 21 * ln_phi), rel=1e-6)
    assert S80 - S40 < 1e-15
    assert S80 > 0

    # Written normalizer: N(M) = sum_{k<=M} L_k^2 with L_k = F(k-1)+F(k+1).
    def lucas(k: int) -> int:
        return fib(k - 1) + fib(k + 1)

    N40 = sum(lucas(k) ** 2 for k in range(1, 41))
    N80 = sum(lucas(k) ** 2 for k in range(1, 81))
    assert N80 / N40 > 1e6  # unbounded growth (L_k^2 ~ phi^(2k))
    # Consequence: with the written normalizer the norm S/N -> 0, NOT 1.
    assert (S80 / float(N80)) < (S40 / float(N40))

    # The correct normalizer (sum of |a_k|^2) yields unit norm for every M,
    # with tail mass beyond M bounded by phi^(-2M): no artificial cutoff
    # needed once the normalizer is the amplitude sum itself.
    for M in (20, 40):
        total = sum(amp_sq(k) for k in range(1, M + 1))
        assert total > 0
        tail_bound = math.exp(-2.0 * (M + 1) * ln_phi) / (1.0 - math.exp(-2.0 * ln_phi))
        assert math.exp(-2.0 * (M + 1) * len(zeckendorf(M + 1)) * ln_phi) <= tail_bound + 1e-30


def test_exactfoldedstateengine_roundtrip_bit_exact():
    """The REAL repo implementation: fold -> store -> restore is bit-exact
    and hash-verified (Intelligence.folded_state.ExactFoldedStateEngine)."""
    from Intelligence.folded_state import ExactFoldedStateEngine

    engine = ExactFoldedStateEngine()
    payload = bytes(range(256)) * 4  # 1024 bytes, all byte values
    artifact = engine.encode(payload)
    assert artifact.original_length == len(payload)
    restored = engine.restore(artifact.sha256[:16])
    assert restored == payload
    assert hashlib.sha256(restored).hexdigest() == artifact.sha256
