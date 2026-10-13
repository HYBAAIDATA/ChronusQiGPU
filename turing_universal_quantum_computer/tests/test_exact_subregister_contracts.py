"""Exact subregister admission, Fourier action and materialization contracts."""

from fractions import Fraction

import pytest
import sympy as sp

import turing_universal_quantum_computer.hilbert as h


@pytest.mark.parametrize("selection", [(0, 0), (-1,), (2,), (True,), (0.5,), ("0",)])
@pytest.mark.parametrize("operator", ["qft", "density", "entropy"])
def test_subregister_domain_is_validated_before_execution(selection, operator):
    register = h.QuantumRegister(2, basis=1)
    before = dict(register.amplitudes)
    with pytest.raises((TypeError, ValueError, IndexError)):
        if operator == "qft":
            h.qft(register, selection)
        elif operator == "density":
            h.reduced_density_matrix(register, selection)
        else:
            h.von_neumann_entropy_exact(register, selection)
    assert register.amplitudes == before


@pytest.mark.parametrize("dimension", [0, -1, True, 2.0, Fraction(2), "2"])
def test_fourier_dimension_is_an_exact_positive_integer(dimension):
    with pytest.raises((TypeError, ValueError)):
        h.fourier_matrix(dimension)


@pytest.mark.parametrize("root", [0, -2, True, 2.9, Fraction(2), "2"])
def test_quadratic_radicand_is_an_exact_positive_integer(root):
    with pytest.raises((TypeError, ValueError)):
        h.QSqrt(0, 1, root)


@pytest.mark.parametrize("flag", [0, 1, "false", None])
@pytest.mark.parametrize("operator", ["matrix", "qft"])
def test_inverse_is_boolean_not_a_truthy_label(flag, operator):
    with pytest.raises(TypeError):
        if operator == "matrix":
            h.fourier_matrix(2, inverse=flag)
        else:
            h.qft(h.QuantumRegister(1), [0], inverse=flag)


def test_qft_support_refusal_preserves_original_state():
    register = h.QuantumRegister(2, basis=1, max_amplitudes=2)
    before = dict(register.amplitudes)
    with pytest.raises(MemoryError, match="budget"):
        h.qft(register, [0, 1])
    assert register.amplitudes == before


def test_dense_distribution_refuses_before_materialization():
    register = h.QuantumRegister(4, max_amplitudes=2)
    with pytest.raises(MemoryError, match="budget"):
        register.distribution(include_zeros=True)
    assert register.distribution() == {0: Fraction(1)}


def test_fourier_matrix_refuses_before_symbolic_allocation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("oversized Fourier construction started")

    monkeypatch.setattr(h.sp, "exp", forbidden)
    with pytest.raises(MemoryError, match="budget"):
        h.fourier_matrix(2048)


def test_density_refuses_before_dense_allocation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("oversized density allocation started")

    monkeypatch.setattr(h.sp, "zeros", forbidden)
    with pytest.raises(MemoryError, match="budget"):
        h.reduced_density_matrix(h.QuantumRegister(30), range(30))


def test_qft_does_not_materialize_a_fourier_matrix(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("QFT allocated a dense Fourier matrix")

    monkeypatch.setattr(h, "fourier_matrix", forbidden)
    register = h.QuantumRegister(3, basis=3)
    h.qft(register, [0, 1, 2])
    assert register.assert_normalized()


def test_qft_work_budget_refuses_before_mutation():
    register = h.QuantumRegister(2, basis=1)
    before = dict(register.amplitudes)
    with pytest.raises(MemoryError, match="budget"):
        h.qft(register, [0, 1], max_terms=3)
    assert register.amplitudes == before


@pytest.mark.parametrize("budget", [True, 0, -1, 3.5, "16"])
def test_explicit_budgets_require_exact_positive_integers(budget):
    with pytest.raises((TypeError, ValueError)):
        h.fourier_matrix(2, max_entries=budget)
    with pytest.raises((TypeError, ValueError)):
        h.qft(h.QuantumRegister(2), [0], max_terms=budget)
    with pytest.raises((TypeError, ValueError)):
        h.reduced_density_matrix(h.QuantumRegister(2), [0], max_entries=budget)


@pytest.mark.parametrize("width", [1, 2, 3])
def test_fourier_action_matches_independent_exact_definition(width):
    dimension = 1 << width
    for basis in range(dimension):
        register = h.QuantumRegister(width, basis=basis)
        h.qft(register, range(width))
        for k in range(dimension):
            actual = h._to_sympy(register.amplitudes[k])
            expected = sp.exp(2 * sp.pi * sp.I * sp.Rational(k * basis, dimension)) / sp.sqrt(
                dimension
            )
            assert sp.simplify(sp.expand_complex(actual - expected)) == 0
        assert register.assert_normalized()
        h.qft(register, range(width), inverse=True)
        assert register.amplitudes == {basis: h.EC_ONE}


def test_noncontiguous_qft_keeps_environment_bits_and_roundtrips():
    register = h.QuantumRegister(4, basis=2, max_amplitudes=16)
    register.apply_h(3)
    before = dict(register.amplitudes)
    h.qft(register, [2, 0])
    assert all(index & 2 for index in register.amplitudes)
    assert register.assert_normalized()
    h.qft(register, [0, 2], inverse=True)
    assert register.amplitudes == before


def test_empty_subsystem_and_exact_density_entropy():
    register = h.QuantumRegister(2)
    register.apply_h(0)
    register.apply_cnot(0, 1)
    before = dict(register.amplitudes)
    assert h.qft(register, []) is register
    assert register.amplitudes == before
    assert h.reduced_density_matrix(register, []) == sp.Matrix([[1]])
    assert h.reduced_density_matrix(register, [0]) == sp.eye(2) / 2
    assert h.von_neumann_entropy_exact(register, [0]) == 1
    assert h.von_neumann_entropy_exact(register, [0, 1]) == 0


def test_matrix_budget_boundary_and_nonbinary_fourier_unitarity():
    assert h.verify_unitary(h.fourier_matrix(3, max_entries=9))
    with pytest.raises(MemoryError, match="budget"):
        h.fourier_matrix(3, max_entries=8)
    register = h.QuantumRegister(2)
    assert h.reduced_density_matrix(register, [0], max_entries=4).trace() == 1
    with pytest.raises(MemoryError, match="budget"):
        h.reduced_density_matrix(register, [0], max_entries=3)


def test_sympy_integer_admission_and_perfect_square_radicand():
    assert h.QSqrt(1, 2, sp.Integer(9)).as_fraction() == 7
    assert h.verify_unitary(h.fourier_matrix(sp.Integer(2)))
    register = h.QuantumRegister(2)
    h.qft(register, [sp.Integer(1)])
    assert register.assert_normalized()


def test_larger_cyclotomic_roundtrip_uses_mathematical_equality():
    register = h.QuantumRegister(4, basis=5)
    h.qft(register, range(4))
    assert register.assert_normalized()
    h.qft(register, range(4), inverse=True)
    assert set(register.amplitudes) == {5}
    # Sympy cyclotomics and ExactComplex use different stored representations.
    assert sp.simplify(sp.expand_complex(h._to_sympy(register.amplitudes[5]) - 1)) == 0
    assert register.assert_normalized()


def test_qft_internal_failure_is_transactional(monkeypatch):
    register = h.QuantumRegister(2, basis=1)
    before = dict(register.amplitudes)
    original = h._phase_factor
    calls = 0

    def fail_late(turns):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("injected contraction failure")
        return original(turns)

    monkeypatch.setattr(h, "_phase_factor", fail_late)
    with pytest.raises(RuntimeError, match="injected"):
        h.qft(register, [0, 1])
    assert register.amplitudes == before


@pytest.mark.parametrize("q,s,root,expected", [(0, 1, 4, 2), (1, -1, 9, -2)])
def test_square_radicand_equality_respects_rational_field_collapse(q, s, root, expected):
    value = h.QSqrt(q, s, root)
    rational_form = h.QSqrt(expected, 0, root)
    assert value == rational_form
    assert hash(value) == hash(rational_form) == hash(Fraction(expected))
    assert len({value, rational_form}) == 1
