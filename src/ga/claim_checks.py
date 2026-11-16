"""Named checks for every claim in mathcore docstrings. Registered via
ga.claims.claim; executed by the CLI and by tests/ga/test_claims.py."""

from .claims import claim
from .mathcore import (
    FIB_HASH_64,
    GALOIS,
    MASK64,
    SHAMIR,
    PhyllotaxisLattice,
    RicciFlowOptimizer,
    is_prime,
)


@claim("GF-01", "GF(2^16) satisfies the field axioms; PRIMITIVE_POLY is primitive")
def check_gf_axioms():
    assert GALOIS.mul(3, GALOIS.inv(3)) == 1
    assert GALOIS.mul(0x8000, 2) == 0x002D
    assert GALOIS.pow(GALOIS.ALPHA, 65535) == 1
    for r in (3, 5, 17, 257):
        assert GALOIS.pow(GALOIS.ALPHA, 65535 // r) != 1


@claim("GF-02", "trace is the Frobenius sum and maps GF(2^16) onto {0,1}")
def check_gf_trace():
    assert GALOIS.trace(0) == 0
    assert GALOIS.trace(1) == 0
    assert all(GALOIS.trace(a) in (0, 1) for a in range(1, 65536, 97))


@claim("SHAMIR-01", "k-of-n split/combine round-trips; fewer than k shares do not")
def check_shamir():
    shares = SHAMIR.split(b"abcdefghi", 3, 5)
    assert SHAMIR.combine(shares[:3], 9) == b"abcdefghi"
    assert SHAMIR.combine(shares[2:], 9) == b"abcdefghi"
    assert SHAMIR.combine(shares[:2], 9) != b"abcdefghi"


@claim("LAT-01", "lattice capacity is prime; composite capacity is refused")
def check_capacity():
    assert is_prime(1_000_003)
    assert not is_prime(1_000_019) and 1_000_019 == 47 * 21277
    assert not is_prime(1_000_000)
    try:
        PhyllotaxisLattice(capacity=1_000_000)
    except ValueError:
        pass
    else:
        raise AssertionError("composite capacity accepted")


@claim(
    "ZEK-01", "Zeckendorf coding has no adjacent Fibonacci indices and sums to input"
)
def check_zeckendorf():
    lattice = PhyllotaxisLattice(capacity=10_007)
    for v in (1, 2, 3, 4, 12, 100, 10**18 - 1):
        z = lattice._zeckendorf_index(v)
        assert z & (z >> 1) == 0
        fibs = lattice._fibonacci_up_to(v)
        assert sum(fibs[i] for i in range(z.bit_length()) if z >> i & 1) == v


@claim("RICCI-01", "augmented Forman curvature: K4 edges are 0, path edges are -1")
def check_forman():
    import numpy as np

    square = RicciFlowOptimizer(dim=2, k=3)
    square.set_points(np.array([[0, 0], [1, 0], [0, 1], [1, 1]]), steps=0)
    assert all(
        square.curvature(i, j) == 0
        for i in square.graph
        for j in square.graph[i]
        if i < j
    )
    path = RicciFlowOptimizer(dim=2, k=1)
    path.graph = {0: {1: 1.0}, 1: {0: 1.0, 2: 1.0}, 2: {1: 1.0}}
    assert all(
        path.curvature(i, j) == -1 for i in path.graph for j in path.graph[i] if i < j
    )


@claim("NONCE-01", "integer golden-nonce walk equals the float Weyl form within 1")
def check_nonce():
    for n in (1, 2, 1000, 99_999):
        exact = ((n * FIB_HASH_64) & MASK64) >> 32
        approx = int(((n * (1 + 5**0.5) / 2) % 1.0) * 2**32)
        assert abs(exact - approx) <= 1
