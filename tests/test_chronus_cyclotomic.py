from fractions import Fraction

import pytest
import sympy as sp

from kellogg.algebraic_field import Cyclotomic, cyclotomic_polynomial
from kellogg.cyclotomic import Q8
from chronus.virtual_igpu.exact_quantum import execute_quantum_program, verify_quantum_program
from turing_universal_quantum_computer.backends import Program, execute_certified


@pytest.mark.parametrize("order", range(1, 33))
def test_polynomial_matches_independent_symbolic_definition(order):
    x = sp.Symbol("x")
    ours = sum(
        sp.Rational(c.numerator, c.denominator) * x**i
        for i, c in enumerate(cyclotomic_polynomial(order))
    )
    assert sp.expand(ours - sp.cyclotomic_poly(order, x)) == 0
    z = Cyclotomic.root(order)
    assert (z**order).same_value(1)
    assert (z * z.conjugate()).same_value(1)
    value = z + 2
    assert (value * value.inverse()).same_value(1)


def test_composite_field_golden_and_q8_embeddings():
    phi = Cyclotomic.from_zphi(0, 1)
    assert (phi * phi - phi).same_value(1)
    q = Q8(3, -2, 4, 1, 7)
    a = Cyclotomic.from_q8(q, order=40)
    assert a * a.conjugate() == Cyclotomic.from_q8(q * q.conjugate(), order=40)
    assert (Cyclotomic.root(3) + Cyclotomic.root(8)).order == 24
    with pytest.raises(ValueError):
        Cyclotomic.root(251) + Cyclotomic.root(8)
    with pytest.raises(TypeError):
        Cyclotomic(8, (0.5,))
    with pytest.raises(ZeroDivisionError):
        Cyclotomic(8).inverse()


def test_rational_rotation_inverse_and_global_phase_through_certified_abi():
    program = Program(2).then("h", 0).then("cx", 0, 1).then("rz:1/3", 1).then("rz:-1/3", 1)
    result = execute_quantum_program({"program": program.to_dict()})
    assert verify_quantum_program({"program": program.to_dict()}, result) == []
    payload = result["execution"]["payload"]
    assert payload["conductor"] == 24
    half = Cyclotomic(24, (Fraction(1, 2),)).to_dict()
    assert payload["probabilities"] == [
        half,
        Cyclotomic(24).to_dict(),
        Cyclotomic(24).to_dict(),
        half,
    ]
    rotation = execute_certified(Program(1).then("rz:1/1", 0), prefer="exact_cyclotomic")
    assert rotation.result.payload["amplitudes"][0] == Cyclotomic(8, (-1,)).to_dict()
    phase = execute_certified(Program(1).then("phase:1/1", 0), prefer="exact_cyclotomic")
    assert phase.result.payload["amplitudes"][0] == Cyclotomic(8, (1,)).to_dict()


def test_magic_injection_both_corrected_branches_equal_t_on_entangled_input():
    prefix = Program(2).then("h", 0).then("cx", 0, 1)
    direct = execute_certified(prefix.then("t", 1), prefer="exact_cyclotomic")
    injected = execute_certified(prefix.then("magic_t", 1), prefer="exact_cyclotomic")
    assert direct.result.payload["amplitudes"] == injected.result.payload["amplitudes"]
    assert injected.result.payload["magic_injections"][0]["consumed"] == 1
    assert injected.certificate != direct.certificate
    request = {"program": prefix.then("magic_t", 1).to_dict()}
    assert verify_quantum_program(request, execute_quantum_program(request)) == []


@pytest.mark.parametrize("gate", ["rz:1/257", "rz:1/0", "rz:0.5", "phase:1/999999"])
def test_nonadmitted_rotations_refuse(gate):
    with pytest.raises((ValueError, MemoryError)):
        execute_quantum_program({"program": Program(1).then(gate, 0).to_dict()})
