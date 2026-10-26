"""Unit tests for Golden Quantum Ontology Transform (hardware RTL parity).

Tests:
  - Fibonacci basis exact integer recurrence
  - Binet recurrence closure invariant
  - Cassini identity invariant
  - Orthogonality bound verification
  - Dual-limb real and imaginary forward butterfly transform
  - Exact rational inverse butterfly transform with bit-exact roundtrip
  - GoldenOntologyTransform class stateful parity
  - Lucas bound on transform route
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from src.golden_ontology_transform import (
    GoldenOntologyTransform,
    compute_fibonacci_basis,
    fibonacci_butterfly,
    inverse_fibonacci_butterfly,
    lucas_bound,
    verify_binet_closure,
    verify_cassini_identity,
    verify_orthogonality_bound,
    witness_orthogonality_bound,
)


def test_fibonacci_basis_generation():
    """Verify exact integer generation for various N."""
    assert compute_fibonacci_basis(0) == []
    assert compute_fibonacci_basis(1) == [0]
    assert compute_fibonacci_basis(2) == [0, 1]
    basis_8 = compute_fibonacci_basis(8)
    assert basis_8 == [0, 1, 1, 2, 3, 5, 8, 13]

    basis_256 = compute_fibonacci_basis(256)
    assert len(basis_256) == 256
    assert basis_256[7] == 13
    assert basis_256[-1].bit_length() == 176


def test_binet_closure_invariant():
    """Verify Binet closure F_j == F_{j-1} + F_{j-2}."""
    basis = compute_fibonacci_basis(256)
    assert verify_binet_closure(basis) is True

    # Corrupt one entry
    corrupted = list(basis)
    corrupted[10] += 1
    assert verify_binet_closure(corrupted) is False


def test_cassini_identity_invariant():
    """Verify Cassini identity F_{m+1}*F_{m-1} - F_m^2 == (-1)^m."""
    basis = compute_fibonacci_basis(256)
    assert verify_cassini_identity(basis) is True

    # Corrupt one entry
    corrupted = list(basis)
    corrupted[5] += 1
    assert verify_cassini_identity(corrupted) is False


def test_orthogonality_bound_small_n():
    """Verify orthogonality bound holds strictly for small N matching RTL threshold."""
    for n in (2, 3, 4, 5, 6, 7):
        basis = compute_fibonacci_basis(n)
        assert verify_orthogonality_bound(basis) is True
        witness = witness_orthogonality_bound(basis)
        assert witness["passed"] is True
        assert witness["max_dot"] <= witness["threshold"]


def test_orthogonality_bound_custom_threshold():
    """Verify orthogonality check with explicit custom threshold."""
    basis = compute_fibonacci_basis(8)
    witness = witness_orthogonality_bound(basis)
    # With large enough threshold, it must pass
    assert verify_orthogonality_bound(basis, threshold=witness["max_dot"] + 10) is True
    # With small threshold, it must fail
    assert verify_orthogonality_bound(basis, threshold=witness["max_dot"] - 1) is False


def test_forward_butterfly_manual():
    """Verify forward butterfly against manual calculation for N=3."""
    # N=3: F_0=0, F_1=1, F_2=1
    # x = [2, 3, 5]
    # k=0: x[0]*F_0 + x[1]*F_1 + x[2]*F_2 = 2*0 + 3*1 + 5*1 = 8
    # k=1: x[0]*F_1 + x[1]*F_2 + x[2]*F_0 = 2*1 + 3*1 + 5*0 = 5
    # k=2: x[0]*F_2 + x[1]*F_0 + x[2]*F_1 = 2*1 + 3*0 + 5*1 = 7
    x_re = [2, 3, 5]
    x_im = [1, 4, 2]
    # For imag:
    # k=0: 1*0 + 4*1 + 2*1 = 6
    # k=1: 1*1 + 4*1 + 2*0 = 5
    # k=2: 1*1 + 4*0 + 2*1 = 3
    y_re, y_im = fibonacci_butterfly(x_re, x_im, n=3)
    assert y_re == [8, 5, 7]
    assert y_im == [6, 5, 3]


def test_exact_roundtrip_reversibility():
    """Verify bit-exact algebraic inverse roundtrip x == inverse(forward(x))."""
    for n in (2, 3, 4, 7, 8, 16):
        x_re = [(i * 3 + 1) % 19 - 9 for i in range(n)]
        x_im = [(i * 5 + 2) % 17 - 8 for i in range(n)]

        y_re, y_im = fibonacci_butterfly(x_re, x_im, n=n)
        rec_re, rec_im = inverse_fibonacci_butterfly(y_re, y_im, n=n)

        assert rec_re == x_re
        assert rec_im == x_im


def test_golden_ontology_transform_class():
    """Verify GoldenOntologyTransform class attributes and methods."""
    got = GoldenOntologyTransform(n=8, width=256)
    assert got.n == 8
    assert got.width == 256
    assert got.binet_ok is True
    assert got.cassini_ok is True
    assert len(got.fib_basis) == 8

    # Invariant dict
    invs = got.verify_all_invariants()
    assert invs["binet_ok"] is True
    assert invs["cassini_ok"] is True

    # Roundtrip test helper
    assert got.roundtrip_test() is True

    # Metadata dictionary
    meta = got.to_dict()
    assert meta["n"] == 8
    assert meta["binet_ok"] is True


def test_lucas_bound_transform_route():
    """Verify Lucas bound L_15 = 1364."""
    assert lucas_bound(15) == 1364
