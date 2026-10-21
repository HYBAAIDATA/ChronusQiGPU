"""Exactness tests for mtheory.hilbert — the 11-qubit register over C^2048.

Every assertion is over exact algebraic objects (Fraction / QSqrt2 /
QSqrt / ExactComplex / sympy algebraic numbers).  No float comparison is
used anywhere except where explicitly sanity-checking an exact value
against a documented decimal magnitude.
"""
# LUCAS WIRING: mtheory
# Substrate route: mtheory

from fractions import Fraction

import sympy as sp

from mtheory.hilbert import (
    EC_I,
    EC_INV_SQRT2,
    EC_T_PHASE,
    ExactComplex,
    GroverExact,
    QuantumRegister,
    QSqrt2,
    cnot_matrix,
    fourier_matrix,
    hadamard_matrix,
    matrices_equal,
    matmul,
    pauli_x_matrix,
    pauli_z_matrix,
    qft,
    reduced_density_matrix,
    verify_unitary,
    von_neumann_entropy_exact,
)


# ---------------------------------------------------------------------------
# Exact scalar types
# ---------------------------------------------------------------------------


def test_exact_complex_arithmetic():
    sqrt2 = ExactComplex(0, 1)  # sqrt(2)
    assert sqrt2 * sqrt2 == ExactComplex(2)
    assert EC_I * EC_I == ExactComplex(-1)
    assert EC_INV_SQRT2 * EC_INV_SQRT2 == ExactComplex(Fraction(1, 2))
    # T phase squared == i  (e^{i pi/4} is a primitive 8th root)
    assert EC_T_PHASE * EC_T_PHASE == EC_I
    # (1 + sqrt(2)) * (1 - sqrt(2)) = -1
    assert (ExactComplex(1, 1) * ExactComplex(1, -1)) == ExactComplex(-1)


def test_abs2_exact():
    a = ExactComplex(Fraction(1, 2), Fraction(1, 4), 0, Fraction(1, 8))
    # |a|^2 = (1/2 + sqrt2/4)^2 + (sqrt2/8)^2
    #       = 1/4 + 2/16 + 2/64 + (2*1/2*1/4)sqrt2 = 13/32 + sqrt2/4
    assert a.abs2() == QSqrt2(Fraction(13, 32), Fraction(1, 4))


# ---------------------------------------------------------------------------
# Gates: exactness, unitarity, normalization
# ---------------------------------------------------------------------------


def test_hzh_equals_x_matrix_identity():
    """H Z H = X as an exact matrix identity over Q(i, sqrt(2))."""
    H = hadamard_matrix()
    Z = pauli_z_matrix()
    X = pauli_x_matrix()
    assert matrices_equal(matmul(matmul(H, Z), H), X)


def test_gate_matrices_unitarity():
    for M in (
        hadamard_matrix(),
        pauli_x_matrix(),
        pauli_z_matrix(),
        cnot_matrix(),
    ):
        assert verify_unitary(M)


def test_gate_unitarity_on_2qubit_register():
    """Every implemented gate is exactly unitary on the 2-qubit register."""
    gates = [
        lambda r: r.apply_h(0),
        lambda r: r.apply_h(1),
        lambda r: r.apply_x(0),
        lambda r: r.apply_x(1),
        lambda r: r.apply_z(0),
        lambda r: r.apply_z(1),
        lambda r: r.apply_s(0),
        lambda r: r.apply_s(1),
        lambda r: r.apply_t(0),
        lambda r: r.apply_t(1),
        lambda r: r.apply_cnot(0, 1),
        lambda r: r.apply_cnot(1, 0),
        lambda r: r.apply_phase(0, Fraction(1, 8)),
        lambda r: r.apply_phase(1, Fraction(3, 8)),
    ]
    for g in gates:
        U = QuantumRegister.operator_matrix(2, g)
        assert verify_unitary(U)


def test_normalization_after_gate_sequence():
    r = QuantumRegister(3)
    r.assert_normalized()
    seq = [
        lambda: r.apply_h(0),
        lambda: r.apply_h(1),
        lambda: r.apply_h(2),
        lambda: r.apply_cnot(0, 1),
        lambda: r.apply_s(2),
        lambda: r.apply_t(1),
        lambda: r.apply_z(0),
        lambda: r.apply_x(2),
        lambda: r.apply_cnot(2, 0),
        lambda: r.apply_phase(0, Fraction(5, 8)),
        lambda: r.apply_h(1),
        lambda: r.apply_cnot(1, 2),
        lambda: r.apply_s(0),
        lambda: r.apply_h(0),
        lambda: r.apply_h(2),
    ]
    for step in seq:
        step()
        assert r.assert_normalized()
    assert r.norm_squared() == 1


def test_bell_state_exact_distribution():
    """|00> -> H(0) -> CNOT(0->1) gives (|00> + |11>)/sqrt(2)."""
    r = QuantumRegister(2)
    r.apply_h(0)
    r.apply_cnot(0, 1)
    d = r.distribution()
    assert d == {0: Fraction(1, 2), 3: Fraction(1, 2)}
    # amplitudes themselves are exactly sqrt(2)/2
    assert r.amplitudes[0] == EC_INV_SQRT2
    assert r.amplitudes[3] == EC_INV_SQRT2


def test_phase_gate_exact_amplitude():
    r = QuantumRegister(1, basis=1)
    r.apply_t(0)
    assert r.amplitudes[1] == EC_T_PHASE
    r.apply_s(0)
    assert r.amplitudes[1] == EC_T_PHASE * EC_I  # e^{i pi/4} * i
    # phases do not change the Born-rule distribution
    assert r.distribution() == {1: 1}


def test_apply_phase_turns_and_sympy():
    r = QuantumRegister(1, basis=1)
    r.apply_phase(0, Fraction(1, 4))  # e^{2 pi i /4} = i
    assert r.amplitudes[1] == EC_I
    # denominator not dividing 8 -> exact sympy cyclotomic
    r2 = QuantumRegister(1, basis=1)
    r2.apply_phase(0, sp.exp(sp.pi * sp.I / 3))
    assert sp.simplify(r2.amplitudes[1] - sp.exp(sp.pi * sp.I / 3)) == 0
    assert r2.assert_normalized()


def test_measure_is_seeded_classical_sampling():
    r = QuantumRegister(2)
    r.apply_h(0)
    r.apply_cnot(0, 1)
    for seed in range(20):
        assert r.measure(seed) in (0, 3)


# ---------------------------------------------------------------------------
# GroverExact — exact amplitude amplification
# ---------------------------------------------------------------------------


def test_grover_n4_exact_subspace():
    """AGENTS.md section 2.1: N=4, |w>=|11>, one iterate -> Pr(w) = 1."""
    g = GroverExact(2, marked=3)
    a, b = g.iterate(1)
    assert a == 1  # a_1 = sin(3 arcsin(1/2)) = 1 exactly
    assert b == 0
    assert g.success_probability(1) == Fraction(1)
    assert g.distribution(1) == {"marked": Fraction(1), "each_unmarked": Fraction(0)}
    assert g.optimal_iterations() == 1


def test_grover_n4_register_level():
    """Register-level Grover on N=4: distribution is exactly |11>."""
    g = GroverExact(2, marked=3)
    r = g.run_register(1)
    d = r.distribution()
    assert d[3] == 1
    assert all(d.get(i, 0) == 0 for i in range(4) if i != 3)
    assert r.assert_normalized()


def test_grover_n16_three_iterations_exact():
    """sin^2(7 arcsin(1/4)) = 63001/65536 ~= 0.9610 — asserted exactly."""
    g = GroverExact(4, marked=5)
    p = g.success_probability(3)
    assert p == Fraction(63001, 65536)
    assert Fraction(96, 100) < p < 1  # ~0.9610
    # register-level run agrees exactly
    r = g.run_register(3)
    d = r.distribution()
    assert d[5] == p
    others = {d[i] for i in range(16) if i != 5}
    assert len(others) == 1
    (q,) = others
    assert q == g.distribution(3)["each_unmarked"]
    assert r.assert_normalized()


def test_grover_n2048_register_run():
    """Full 11-qubit Grover run on C^2048 — the "11D Hilbert space"."""
    marked = 1379
    g = GroverExact(11, marked=marked)
    r_opt = g.optimal_iterations()
    assert r_opt == 35  # round(pi/(4 arcsin(1/sqrt(2048))) - 1/2)
    reg = g.run_register(r_opt)
    reg.assert_normalized()
    d = reg.distribution()
    assert len(d) == 2048
    # marked probability equals the exact subspace prediction
    assert d[marked] == g.success_probability(r_opt)
    # essentially deterministic: > 99.9% success, still exact
    assert d[marked] > Fraction(999, 1000)
    # every unmarked amplitude has the same exact probability
    unmarked = {d[i] for i in range(2048) if i != marked}
    assert len(unmarked) == 1
    (q,) = unmarked
    assert q == g.distribution(r_opt)["each_unmarked"]
    # total probability is exactly 1
    assert sum(d.values()) == 1


def test_grover_amplitudes_match_register_n16():
    g = GroverExact(4, marked=7)
    reg = g.run_register(2)
    a, b = g.iterate(2)
    # register amplitude of marked = a (a QSqrt value), verify via abs2
    assert reg.amplitudes[7].abs2() == a.square().as_fraction()
    assert reg.amplitudes[0].abs2() == b.square().as_fraction()


# ---------------------------------------------------------------------------
# Exact QFT
# ---------------------------------------------------------------------------


def test_fourier_matrix_unitary_exact():
    """F F^dagger = I exactly, on every dimension supported in Q(zeta_8)."""
    for m in (2, 4, 8):
        F = fourier_matrix(m)
        assert verify_unitary(F)


def test_qft_on_basis_state_uniform_probabilities():
    """QFT|j> on a 3-qubit subregister: |amp|^2 = 1/8 on every basis state."""
    r = QuantumRegister(3)
    r.apply_x(0)  # |1>
    qft(r, [0, 1, 2])
    d = r.distribution()
    assert d == {i: Fraction(1, 8) for i in range(8)}
    r.assert_normalized()


def test_qft_on_zero_is_uniform_amplitudes():
    r = QuantumRegister(2)
    qft(r, [0, 1])
    for i in range(4):
        assert r.amplitudes[i] == ExactComplex(Fraction(1, 2))


def test_qft_inverse_roundtrip():
    r = QuantumRegister(2)
    r.apply_h(0)
    r.apply_x(1)
    before = dict(r.amplitudes)
    qft(r, [0, 1])
    qft(r, [0, 1], inverse=True)
    assert r.amplitudes == before


# ---------------------------------------------------------------------------
# Exact entanglement entropy
# ---------------------------------------------------------------------------


def test_bell_half_entropy_exactly_one_bit():
    r = QuantumRegister(2)
    r.apply_h(0)
    r.apply_cnot(0, 1)
    rho = reduced_density_matrix(r, [0])
    assert rho == sp.Matrix(
        [[sp.Rational(1, 2), 0], [0, sp.Rational(1, 2)]]
    )
    assert rho.eigenvals() == {sp.Rational(1, 2): 2}
    s = von_neumann_entropy_exact(r, [0])
    assert s == 1  # exactly one bit, not 0.999...


def test_product_state_entropy_zero():
    r = QuantumRegister(2)
    r.apply_x(0)
    rho = reduced_density_matrix(r, [0])
    assert rho.eigenvals() == {sp.Rational(1): 1, sp.Rational(0): 1}
    assert von_neumann_entropy_exact(r, [0]) == 0
