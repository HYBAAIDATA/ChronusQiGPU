"""Focused isolated regressions; not the full seven-class qualification suite."""
import importlib.util
import itertools
from pathlib import Path
import random
import sys
import unittest
import pytest

pytestmark = pytest.mark.real

path = Path(__file__).resolve().parents[1] / 'src/chronus/quantum/geometric_polychoron.py'
spec = importlib.util.spec_from_file_location('review_cyclotomic_source', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
C = module.Cyclotomic5
F = module.F257Phi

class RingRegressions(unittest.TestCase):
    def test_root_and_phi_identities(self):
        z, one, zero, phi = C.zeta(), C.one(), C.zero(), C.phi()
        self.assertEqual(z*z*z*z*z, one)
        self.assertEqual(one+z+z*z+z*z*z+z*z*z*z, zero)
        self.assertEqual(phi*phi, phi+one)

    def test_braid_relation(self):
        self.assertTrue(module.CyclotomicBraidCompiler().verify_braid_relations())

    def test_invalid_coefficients(self):
        for x in (0.5, 1.0, True, '1', None):
            with self.subTest(x=x), self.assertRaises(TypeError):
                C(x, 0, 0, 0)

    def test_nonreal_projection_refused(self):
        for x in (C.zeta(), C(0,0,1,0), C(0,1,1,1)):
            with self.assertRaises(ValueError): x.to_f257_phi()

    def test_projection_examples(self):
        for a,b in itertools.product(range(-5,6), repeat=2):
            x=C(a,0,-b,-b)
            self.assertEqual(x.to_f257_phi(), F(a,b))
        self.assertEqual(C.phi().to_f257_phi(), F.phi())

    def test_projection_preserves_operations_on_quadratic_subring(self):
        for a,b,c,d in itertools.product(range(-2,3), repeat=4):
            x,y=C(a,0,-b,-b), C(c,0,-d,-d)
            self.assertEqual((x+y).to_f257_phi(), x.to_f257_phi()+y.to_f257_phi())
            self.assertEqual((x*y).to_f257_phi(), x.to_f257_phi()*y.to_f257_phi())

    def test_seeded_sample_ring_associativity(self):
        rng=random.Random(20261109)
        for _ in range(1000):
            a,b,c=(C(*(rng.randint(-1000000,1000000) for _ in range(4))) for _ in range(3))
            self.assertEqual((a*b)*c, a*(b*c))
            self.assertEqual(a*(b+c), a*b+a*c)

if __name__ == '__main__': unittest.main()
