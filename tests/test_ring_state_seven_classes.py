"""Tests of public exact coefficient and coordinate APIs."""
from pathlib import Path
import ast
import itertools
import pytest
from hypothesis import given, settings, strategies as st
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C
from chronus.quantum.ring_state import MAX_COORDINATES, scale_element, scale_vector

pytestmark = pytest.mark.real

ring = st.tuples(*[st.integers(-10000, 10000)]*4).map(lambda v: C(*v))


class TestInvariant:
    def test_scalar_vector_agreement_bounded_exhaustive(self):
        values = [C(i, j, 0, 0) for i,j in itertools.product(range(-2,3), repeat=2)]
        for a in values:
            for x in values:
                assert scale_vector(a, [x, C.zero()]) == (scale_element(a, x), C.zero())


class TestProperty:
    @settings(max_examples=200, deadline=None, derandomize=True)
    @given(ring, ring, ring, ring)
    def test_linearity_and_composition(self, a, b, x, y):
        assert scale_vector(a, [x+y]) == (scale_element(a,x)+scale_element(a,y),)
        assert scale_vector(a*b, [x,y]) == scale_vector(a, scale_vector(b,[x,y]))


class TestAdversarial:
    def test_invalid_inputs(self):
        with pytest.raises(TypeError): scale_element(1, C.one())
        with pytest.raises(TypeError): scale_element(C.one(), 1)
        with pytest.raises(TypeError): scale_vector(1, [C.one()])
        with pytest.raises(TypeError): scale_vector(C.one(), iter([C.one()]))
        with pytest.raises(TypeError): scale_vector(C.one(), [1])

    def test_no_float_or_complex_literals_in_module(self):
        tree = ast.parse(Path('src/chronus/quantum/ring_state.py').read_text())
        assert not any(isinstance(n,ast.Constant) and isinstance(n.value,(float,complex)) for n in ast.walk(tree))


class TestEdge:
    def test_bounds(self):
        with pytest.raises(ValueError): scale_vector(C.one(), [])
        with pytest.raises(ValueError): scale_vector(C.one(), [C.one()]*(MAX_COORDINATES+1))
        assert len(scale_vector(C.one(), [C.zero()]*MAX_COORDINATES)) == MAX_COORDINATES


class TestUnit:
    def test_known_values(self):
        z=C.zeta(); phi=C.phi()
        assert scale_element(phi, phi) == phi+C.one()
        assert scale_vector(z,[C.one(),z]) == (z,z*z)


class TestIntegration:
    def test_coordinate_projection(self):
        scalar = C.phi(); coords = [C.one(), C.phi_inv()]
        result = scale_vector(scalar, coords)
        assert tuple(v.to_f257_phi() for v in result) == tuple(scalar.to_f257_phi()*v.to_f257_phi() for v in coords)


class TestEndToEnd:
    def test_prepare_scale_verify(self):
        vector = [C.one(),C.zeta()]; phi=C.phi()
        assert scale_vector(phi, scale_vector(C.phi_inv(), vector)) == tuple(vector)
