"""Bounded public API and exact arithmetic checks on the entire source file."""
import importlib.util
import itertools
from pathlib import Path
import sys

import pytest
from hypothesis import given, settings, strategies as st

source = Path(__file__).resolve().parents[1] / 'src/chronus/quantum/geometric_polychoron.py'
spec = importlib.util.spec_from_file_location('ring_under_test', source)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
C, F = m.Cyclotomic5, m.F257Phi


def make(coefficients):
    return C(*coefficients)


def power(a, n):
    out = C.one()
    for _ in range(n): out = out*a
    return out


ring = st.tuples(*[st.integers(min_value=-1000000, max_value=1000000)]*4).map(make)


class TestInvariant:
    def test_bounded_exhaustive_addition_multiplication(self):
        samples = [C(*v) for v in itertools.product(range(-1, 2), repeat=4)]
        z = C.zero(); one = C.one()
        for a in samples:
            assert a+z == a and a*one == a and a+(-a) == z and a-a == z
            for b in samples: assert a*b == b*a

    def test_phi_and_zeta_across_integer_powers(self):
        phi, z, one = C.phi(), C.zeta(), C.one()
        assert phi*C.phi_inv() == one
        assert power(z, 5) == one
        assert sum_ring([power(z, i) for i in range(5)]) == C.zero()
        for n in range(101):
            p = power(phi, n)
            assert p*phi*phi == p*(phi+one)


def sum_ring(items):
    out = C.zero()
    for item in items: out = out+item
    return out


class TestProperty:
    @settings(max_examples=300, deadline=None, derandomize=True)
    @given(ring, ring, ring)
    def test_associative_and_distributive(self, a, b, c):
        assert (a*b)*c == a*(b*c)
        assert a*(b+c) == a*b+a*c
        assert (a+b)+c == a+(b+c)

    @settings(max_examples=100, deadline=None, derandomize=True)
    @given(st.integers(), st.integers(), st.integers(), st.integers())
    def test_projection_is_ring_homomorphism(self, a, b, c, d):
        x, y = C(a,0,-b,-b), C(c,0,-d,-d)
        assert (x+y).to_f257_phi() == x.to_f257_phi()+y.to_f257_phi()
        assert (x*y).to_f257_phi() == x.to_f257_phi()*y.to_f257_phi()


class TestAdversarial:
    def test_bad_coefficients_and_projection(self):
        for x in (0.5, 1.0, True, '1', None):
            with pytest.raises(TypeError): C(x,0,0,0)
        for x in (C.zeta(), C(0,0,1,0), C(0,1,1,1)):
            with pytest.raises(ValueError): x.to_f257_phi()
        with pytest.raises(ValueError): m.CyclotomicBraidCompiler().compile_word([3])
        with pytest.raises(ZeroDivisionError): F.zero().inverse()
        with pytest.raises(ValueError): m.QuantumGeometricTensor.evaluate([0], [1], [1])


class TestEdge:
    def test_unbounded_integers_and_zero(self):
        a = C(2**2048, -2**1024, 1, -1)
        assert a*C.one() == a and a*C.zero() == C.zero()
        assert F(257, 514).is_zero() and not F.one().is_zero()
        assert m.CyclotomicBraidCompiler().compile_word([]) == ((C.one(), C.zero()),(C.zero(),C.one()))
        assert m.PisotLucasStateCompression.fibonacci_pair(0) == (0,1)
        assert [m.PisotLucasStateCompression.lucas(i) for i in (0,1)] == [2,1]
        assert [m.PisotLucasStateCompression.lucas_mod(i) for i in (0,1)] == [2,1]


class TestUnit:
    def test_known_ring_and_field_values(self):
        assert C.zeta()*C.zeta()*C.zeta()*C.zeta() == C(-1,-1,-1,-1)
        assert C.phi()*C.phi() == C.phi()+C.one()
        assert F.phi()*F.phi() == F.phi()+F.one()
        assert F.phi()*F.phi_inv() == F.one()
        assert F(5,3)*F(5,3).inverse() == F.one()
        assert F(5,3)-F(5,3) == F.zero()
        assert F(5,3)+(-F(5,3)) == F.zero()

    def test_other_public_apis(self):
        assert len(m.Polychoron600Cell.generate_cyclotomic_vertices()) == 120
        assert len(m.Polychoron600Cell.generate_f257_vertices()) == 120
        assert m.Polychoron600Cell._permutation_parity([1,0,2,3]) == 1
        assert m.QuantumGeometricTensor.evaluate([1,0], [0,1], [0,1]) == (1,0,1)
        assert m.PisotLucasStateCompression.fibonacci_pair(10) == (55,89)
        assert m.PisotLucasStateCompression.lucas(10) == 123
        assert m.PisotLucasStateCompression.lucas_mod(10,7) == 123%7
        assert m.PisotLucasStateCompression.lucas_mod(11,7) == 199%7


class TestIntegration:
    def test_vertices_projection_and_braid(self):
        cvertices = m.Polychoron600Cell.generate_cyclotomic_vertices()
        projected = {tuple(x.to_f257_phi() for x in v) for v in cvertices}
        assert projected == set(m.Polychoron600Cell.generate_f257_vertices())
        compiler = m.CyclotomicBraidCompiler()
        assert compiler.verify_braid_relations()
        assert compiler.compile_word([1,2,1]) == compiler.compile_word([2,1,2])


class TestEndToEnd:
    def test_input_to_exact_result(self):
        z, one = C.zeta(), C.one()
        polynomial = power(z, 4)+power(z, 3)+power(z, 2)+z+one
        assert polynomial == C.zero()
        assert polynomial.to_f257_phi() == F.zero()
