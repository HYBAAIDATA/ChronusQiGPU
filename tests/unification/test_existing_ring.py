"""Validate agreement with the actual existing ring source in the checkout."""
import importlib.util
from itertools import product
from pathlib import Path
from hyba.unification.field import QPhi

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'src/chronus/security/al_haras/engine.py'

def test_integer_embedding_is_ring_homomorphism():
    spec = importlib.util.spec_from_file_location('existing_engine', ENGINE)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    def ring(x): return engine.CyclotomicZ5(*x.integral_cyclotomic_coordinates())
    def coeffs(x): return x.c0,x.c1,x.c2,x.c3
    numbers = [QPhi(a,b) for a,b in product(range(-2,3), repeat=2)]
    for x,y in product(numbers,repeat=2):
        assert coeffs(ring(x)+ring(y)) == (x+y).integral_cyclotomic_coordinates()
        assert coeffs(ring(x)*ring(y)) == (x*y).integral_cyclotomic_coordinates()

def test_adapter_full_integer_ring_and_restrictions():
    from fractions import Fraction
    import pytest
    from hyba.unification.field import Zeta5
    spec = importlib.util.spec_from_file_location('existing_engine_adapter', ENGINE)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    B = engine.CyclotomicZ5
    zero, one = Zeta5((0,0,0,0), B), Zeta5((1,0,0,0), B)
    z = Zeta5((0,1,0,0), B)
    assert z**5 == one
    assert one + z + z**2 + z**3 + z**4 == zero
    assert z-z == zero and -z+z == zero
    p = QPhi(0,1)
    assert Zeta5.from_qphi(p, B).to_qphi() == p
    with pytest.raises(ValueError): z.to_qphi()
    with pytest.raises(ValueError): Zeta5.from_qphi(QPhi(Fraction(1,2),0), B)
    with pytest.raises(TypeError): Zeta5.from_qphi(1, B)
    for v in ((1.2,0,0,0), (True,0,0,0), ('1',0,0,0)):
        with pytest.raises(TypeError): Zeta5(v,B)
    for v in ([1,0,0,0], (1,0,0)):
        with pytest.raises(ValueError): Zeta5(v,B)
    with pytest.raises(TypeError): Zeta5((1,0,0,0),None)
    with pytest.raises(TypeError): z + 1
    with pytest.raises(TypeError): z * Zeta5((1,0,0,0), type('Other', (), {}))
    for n in (-1, True, 1.5):
        with pytest.raises(ValueError): z ** n


def test_generated_ring_associativity():
    from hypothesis import given, settings, strategies as st
    from hyba.unification.field import Zeta5
    spec = importlib.util.spec_from_file_location('existing_engine_properties', ENGINE)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    ints = st.tuples(*(st.integers(-10**6,10**6) for _ in range(4)))
    @settings(max_examples=200, derandomize=True, deadline=None)
    @given(ints, ints, ints)
    def check(a,b,c):
        x,y,z = (Zeta5(v,engine.CyclotomicZ5) for v in (a,b,c))
        assert (x*y)*z == x*(y*z)
        assert x*(y+z) == x*y+x*z
    check()
