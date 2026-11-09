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
