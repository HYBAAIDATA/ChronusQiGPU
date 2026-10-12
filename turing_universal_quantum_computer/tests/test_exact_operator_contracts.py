"""Exact operator contracts: no float coercion, nonunitary phases or disabled checks."""

from fractions import Fraction
import os
from pathlib import Path
import subprocess
import sys

import pytest
import sympy as sp

from turing_universal_quantum_computer.hilbert import (
    ExactComplex,
    GroverExact,
    QSqrt2,
    QuantumRegister,
    hadamard_matrix,
    phase_s_matrix,
    phase_t_matrix,
    verify_unitary,
)
from turing_universal_quantum_computer.quantum_library import ExactLaneError, QuantumLibrary


@pytest.mark.parametrize("value", [0.5, True, sp.Float("0.5"), "0.5", "1e-3"])
def test_scalar_constructors_refuse_inexact_or_untyped_values(value):
    with pytest.raises((TypeError, ValueError)):
        ExactComplex(value)
    with pytest.raises((TypeError, ValueError)):
        QSqrt2(value)


@pytest.mark.parametrize("value", [0.5, True, sp.Float("0.5"), "0.5", "1/0"])
def test_facade_refuses_float_angle_admission(value):
    with pytest.raises(ExactLaneError):
        QuantumLibrary.qpe(value, counting_qubits=1)


@pytest.mark.parametrize("value", [ExactComplex(2), sp.sqrt(2), sp.Float(1)])
def test_literal_nonunitary_or_float_phase_is_rejected_before_mutation(value):
    register = QuantumRegister(1, basis=1)
    before = dict(register.amplitudes)
    with pytest.raises((TypeError, ValueError)):
        register.apply_phase(0, value)
    assert register.amplitudes == before


def test_rational_turns_and_literal_unit_phases_remain_exact():
    for phase in (Fraction(1, 7), sp.Rational(1, 7), ExactComplex(0, 0, 1), sp.I):
        register = QuantumRegister(1, basis=1)
        register.apply_phase(0, phase)
        assert register.assert_normalized()
    register = QuantumRegister(1, basis=1)
    register.apply_phase(0, 2)
    assert register.amplitudes == {1: ExactComplex(1)}


@pytest.mark.parametrize("q", [-1, 2, True, 0.5])
@pytest.mark.parametrize("gate", ["apply_h", "apply_x", "apply_z", "apply_s", "apply_t"])
def test_gate_indices_reject_before_mutation(q, gate):
    register = QuantumRegister(2)
    before = dict(register.amplitudes)
    with pytest.raises((TypeError, ValueError, IndexError)):
        getattr(register, gate)(q)
    assert register.amplitudes == before


def test_cnot_and_oracle_validate_complete_inputs_before_mutation():
    register = QuantumRegister(2, basis=1)
    before = dict(register.amplitudes)
    with pytest.raises((TypeError, ValueError, IndexError)):
        register.apply_cnot(0, 2)
    assert register.amplitudes == before
    with pytest.raises((TypeError, ValueError, IndexError)):
        register.apply_grover_oracle([1, 4])
    assert register.amplitudes == before
    with pytest.raises((TypeError, ValueError, IndexError)):
        register.apply_grover_oracle([1, 1])
    assert register.amplitudes == before


@pytest.mark.parametrize("width,basis", [(True, 0), (2, True), (2, 0.5)])
def test_register_rejects_noninteger_domain(width, basis):
    with pytest.raises((TypeError, ValueError)):
        QuantumRegister(width, basis=basis)


def test_exact_gate_unitarity_and_bell_born_distribution():
    for matrix in (hadamard_matrix(), phase_s_matrix(), phase_t_matrix()):
        assert verify_unitary(matrix)
    register = QuantumRegister(2)
    register.apply_h(0)
    register.apply_cnot(0, 1)
    assert register.distribution() == {0: Fraction(1, 2), 3: Fraction(1, 2)}
    assert register.assert_normalized()
    register.apply_cnot(0, 1)
    register.apply_h(0)
    assert register.amplitudes == {0: ExactComplex(1)}


def test_first_grover_peak_uses_exact_recurrence_not_float_rounding():
    for width in range(1, 11):
        grover = GroverExact(width)
        k = grover.optimal_iterations()
        assert type(k) is int
        p = grover.success_probability(k)
        assert p >= grover.success_probability(k + 1)
        if k:
            assert p > grover.success_probability(k - 1)
        if width > 1:
            assert p > Fraction(9, 10)
    # Small independent register evolution reproduces the closed recurrence.
    for width in range(2, 5):
        grover = GroverExact(width, marked=1)
        k = grover.optimal_iterations()
        register = grover.run_register(k)
        assert register.distribution()[1] == grover.success_probability(k)


def test_default_grover_controller_has_no_float_or_transcendental_calls():
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(GroverExact.optimal_iterations)))
    assert not any(
        isinstance(node, ast.Constant) and isinstance(node.value, float) for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Attribute) and node.attr in {"asin", "sqrt", "pi", "evalf"}
        for node in ast.walk(tree)
    )


def test_invariants_cannot_be_disabled_by_python_optimization():
    code = """
from turing_universal_quantum_computer.hilbert import ExactComplex, QuantumRegister, verify_unitary
r = QuantumRegister(1)
r.amplitudes = {0: ExactComplex(2)}
for verify in (r.assert_normalized, lambda: verify_unitary([[ExactComplex(2)]])):
    try:
        verify()
    except AssertionError:
        pass
    else:
        raise RuntimeError('invalid quantum invariant passed under -O')
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-O", "-c", code], env=env, text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("iterations", [True, 1.5, -1])
def test_grover_facade_does_not_truncate_invalid_iteration_counts(iterations):
    with pytest.raises((TypeError, ValueError)):
        QuantumLibrary.grover(2, 1, iterations=iterations)
