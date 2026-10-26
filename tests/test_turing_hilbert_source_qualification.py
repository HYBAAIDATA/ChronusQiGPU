"""Standalone qualification of the canonical exact operator source.

Loads the real, dependency-light hilbert module directly; no substitute package
or mock arithmetic. This deliberately does not qualify the whole TURING facade.
"""
from fractions import Fraction
from pathlib import Path
import importlib.util
import sys
import pytest
import sympy as sp

SOURCE = Path(__file__).resolve().parents[1] / 'turing_universal_quantum_computer/turing_universal_quantum_computer/hilbert.py'
spec = importlib.util.spec_from_file_location('hyba_qualified_hilbert', SOURCE)
h = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = h
spec.loader.exec_module(h)

@pytest.mark.parametrize('width', [2, 3, 4, 8, 32, 1000, 10000])
def test_exact_sparse_entanglement_is_substrate_independent(width):
    r = h.QuantumRegister(width, max_amplitudes=2)
    r.apply_h(0)
    for q in range(1, width):
        r.apply_cnot(0, q)
    assert r.distribution() == {0: Fraction(1, 2), (1 << width)-1: Fraction(1, 2)}
    assert r.assert_normalized()
    assert len(r.amplitudes) == 2

@pytest.mark.parametrize('width', [1, 2, 3])
def test_exact_qft_round_trip(width):
    for basis in range(1 << width):
        r = h.QuantumRegister(width, basis=basis)
        h.qft(r, range(width))
        assert r.assert_normalized()
        h.qft(r, range(width), inverse=True)
        assert r.amplitudes == {basis: h.ExactComplex(1)}

@pytest.mark.parametrize('width', [2, 3, 4, 5])
def test_grover_register_matches_closed_exact_recurrence(width):
    g = h.GroverExact(width, marked=1)
    k = g.optimal_iterations()
    r = g.run_register(k)
    assert r.distribution()[1] == g.success_probability(k)
    assert r.assert_normalized()


def test_partial_trace_of_entangled_state_is_exact():
    r = h.QuantumRegister(2)
    r.apply_h(0); r.apply_cnot(0, 1)
    assert h.reduced_density_matrix(r, [0]) == sp.eye(2) / 2
    assert h.von_neumann_entropy_exact(r, [0]) == 1

@pytest.mark.parametrize('gate', ['apply_h', 'apply_x', 'apply_z', 'apply_s', 'apply_t'])
def test_domain_refusal_does_not_mutate_state(gate):
    r = h.QuantumRegister(2)
    before = dict(r.amplitudes)
    with pytest.raises((TypeError, ValueError, IndexError)):
        getattr(r, gate)(True)
    assert r.amplitudes == before


def test_qft_budget_refusal_is_atomic():
    r = h.QuantumRegister(4, max_amplitudes=2)
    before = dict(r.amplitudes)
    with pytest.raises(MemoryError):
        h.qft(r, range(4))
    assert r.amplitudes == before


def test_10000_qubit_exact_t_phase_and_reversal():
    r = h.QuantumRegister(10000, max_amplitudes=4)
    r.apply_h(0)
    for q in range(1, 10000):
        r.apply_cnot(0, q)
    for _ in range(8):
        r.apply_t(9999)
    for q in range(9999, 0, -1):
        r.apply_cnot(0, q)
    r.apply_h(0)
    assert r.amplitudes == {0: h.ExactComplex(1)}
    assert r.assert_normalized()
