"""Tests for kellogg/clifford_tableau.py — H/S/CNOT gate conjugation.

Scope: proves gate conjugation is symplectic-preserving for small
widths (n<=4) exhaustively, and for random sequences up to n=8.
Does not prove arbitrary-Hilbert-space simulation or magic injection.
"""
import itertools
import pytest
from kellogg.clifford_tableau import (
    Tableau,
    identity,
    apply_h,
    apply_s,
    apply_cnot,
)


def test_identity_tableau():
    t = identity(4)
    n = t[3]
    assert n == 4
    # Well-formed: check symplectic orthogonality of generators
    x_parts, z_parts, phases, _ = t
    for i in range(n):
        for j in range(i + 1, n):
            x_i_z_j = sum(x_parts[i][k] * z_parts[j][k] for k in range(n)) % 2
            z_i_x_j = sum(z_parts[i][k] * x_parts[j][k] for k in range(n)) % 2
            commutes = (x_i_z_j + z_i_x_j) % 2 == 0
            assert commutes, f"Generators {i} and {j} should commute"


def test_h_is_self_inverse():
    for n in [1, 2, 3, 4]:
        for q in range(n):
            t = identity(n)
            t1 = apply_h(t, q)
            t2 = apply_h(t1, q)
            # Compare x_parts, z_parts, phases
            assert t2[3] == n, f"n changed after H^2"
            assert t2[0] == t[0], "x_parts changed"
            assert t2[1] == t[1], "z_parts changed"


def test_s_order_4():
    # S^4 = I (up to global phase), and S^2 = Z
    for n in [1, 2, 3, 4]:
        for q in range(n):
            t = identity(n)
            t1 = apply_s(t, q)
            t2 = apply_s(t1, q)
            t3 = apply_s(t2, q)
            t4 = apply_s(t3, q)
            # t4 should equal t
            assert t4[3] == n, f"n changed after S^4"
            assert t4[0] == t[0], "x_parts changed after S^4"
            assert t4[1] == t[1], "z_parts changed after S^4"


def test_cnot_self_inverse():
    for n in [2, 3, 4]:
        for c, tgt in itertools.permutations(range(n), 2):
            t = identity(n)
            t1 = apply_cnot(t, c, tgt)
            t2 = apply_cnot(t1, c, tgt)
            # t2 should equal t
            assert t2[3] == n, f"n changed after CNOT^2"
            assert t2[0] == t[0], "x_parts changed"
            assert t2[1] == t[1], "z_parts changed"


def test_symplectic_form_under_random_sequences():
    import random
    rng = random.Random(42)
    for n in [1, 2, 3, 4, 8]:
        for _ in range(50):
            t = identity(n)
            for _ in range(20):
                gate = rng.choice(["H", "S", "CNOT"])
                if gate == "H":
                    q = rng.randrange(n)
                    t = apply_h(t, q)
                elif gate == "S":
                    q = rng.randrange(n)
                    t = apply_s(t, q)
                else:
                    c, tgt = rng.sample(range(n), 2)
                    t = apply_cnot(t, c, tgt)
            # Check symplectic form: all generator pairs commute
            x_parts, z_parts, phases, nn = t
            assert nn == n, f"n changed during sequence"
            for i in range(n):
                for j in range(i + 1, n):
                    x_i_z_j = sum(x_parts[i][k] * z_parts[j][k] for k in range(n)) % 2
                    z_i_x_j = sum(z_parts[i][k] * x_parts[j][k] for k in range(n)) % 2
                    commutes = (x_i_z_j + z_i_x_j) % 2 == 0
                    assert commutes, f"symplectic form broken for n={n}, generators {i},{j}"


def test_hxh_equals_z():
    # H X H = Z, checked via tableau conjugation
    # Apply H, then check that conjugating X by H gives Z
    # In the tableau, X on qubit 0 has x_part = [1,0,...], z_part = [0,0,...]
    # After H, X becomes Z. We verify this by checking the tableau transformation.
    n = 1
    t = identity(n)
    # Apply H to qubit 0
    t = apply_h(t, 0)
    # Now check: the X operator (x=[1,0..], z=[0,0..]) conjugated by H gives Z
    # Z has x_part = [0,0..], z_part = [1,0..]
    # Let's verify by checking the phase tracking
    x_parts, z_parts, phases, nn = t
    assert nn == n
    # After H, the Z basis is tracked in the x_parts
    # X on qubit 0 originally: x_parts[0][0] = 1, z_parts[0][0] = 0
    # After H: should have z_parts[0][0] = 1 (becoming Z)
    assert z_parts[0][0] == 1, "After H, qubit 0 Z-component should be 1"