"""Experimental MPS tests, not the complete seven-class release suite."""
import unittest
from hypothesis import given, settings, strategies as st
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C
from chronus.tensor.exact_mps import contract, MAX_SITES
import pytest

pytestmark = pytest.mark.real

def v(n): return C(n,0,0,0)
def product(a,b): return [[[v(a)], [v(b)]]]

class ExactMPSTests(unittest.TestCase):
    def test_unit_single_site(self):
        self.assertEqual(contract([product(2,3)]),(v(2),v(3)))
    def test_invariant_scalar_is_same_ring(self):
        a,b=C.phi(),C.zeta()
        self.assertEqual(contract([[[[a]]], [[[b]]]]),(a*b,))
    @settings(max_examples=100, deadline=None, derandomize=True)
    @given(st.integers(-1000,1000),st.integers(-1000,1000),st.integers(-1000,1000),st.integers(-1000,1000))
    def test_property_product(self,a,b,c,d):
        self.assertEqual(contract([product(a,b),product(c,d)]),(v(a*c),v(a*d),v(b*c),v(b*d)))
    def test_edge_refusal(self):
        for bad in ([], [product(1,1)]*(MAX_SITES+1), [[[[]]]], [[[[v(1),v(2)]]]], [[[[v(1)],[v(2),v(3)]]]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError): contract(bad)
        with self.assertRaises(TypeError): contract([[[[1.0]]]])
        with self.assertRaises(ValueError): contract([[]])
        with self.assertRaises(ValueError): contract([[[[v(1)]]], [[[v(1)]], [[v(1)]]]])
        with self.assertRaises(ValueError): contract([[[[v(1),v(1)]]], [[[v(1)]], [[v(1)],[v(1)]]]])
    def test_integration_artin_action(self):
        from chronus.quantum.geometric_polychoron import CyclotomicBraidCompiler
        b=CyclotomicBraidCompiler(); l=b.compile_word([1,2,1]); r=b.compile_word([2,1,2]);
        for i in range(2):
            for j in range(2): self.assertEqual(contract([[[[l[i][j]]]]]), (r[i][j],))
    def test_e2e_bounded_product_workflow(self):
        out=contract([product(1,1)]*5)
        self.assertEqual(len(out),32); self.assertTrue(all(x==C.one() for x in out))
    def test_adversarial_dimensions(self):
        with self.assertRaisesRegex(ValueError, 'output dimension'): contract([[[[v(1)],[v(1)],[v(1)]]]]*11)

if __name__ == '__main__': unittest.main()
