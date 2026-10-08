import unittest
from fractions import Fraction
from chronos import PhiElement,FibonacciOrbit,FamilyCertificate,triple_identity
from chronos.family_algebra import PHI
from chronos.lucas_engine import lucas,fibonacci_pair
class AlgebraTests(unittest.TestCase):
    def test_minimal_polynomial(self):self.assertEqual(PHI*PHI,PHI+1)
    def test_exact_inverse(self):self.assertEqual(PHI*PHI.inverse(),PhiElement(1))
    def test_conjugate(self):self.assertEqual(PHI+PHI.conjugate(),PhiElement(1))
    def test_negative_power(self):self.assertEqual(PHI**-15*(PHI**15),PhiElement(1))
    def test_exact_rational_closure(self):
        a=PhiElement(Fraction(1,3),Fraction(7,11));self.assertEqual(a*a.inverse(),PhiElement(1))
    def test_norm_multiplicative(self):
        a=PhiElement(3,5);b=PhiElement(7,-2);self.assertEqual((a*b).norm(),a.norm()*b.norm())
    def test_triples_exact(self):
        for n in range(101):self.assertEqual(triple_identity(n)['L_3n'],lucas(3*n))
    def test_pair_composition(self):
        for m in range(30):
            for n in range(30):self.assertEqual(FibonacciOrbit.at(m).compose(FibonacciOrbit.at(n)),FibonacciOrbit.at(m+n))
    def test_three_way_associativity(self):
        a,b,c=map(FibonacciOrbit.at,(15,31,50));self.assertEqual(a.compose(b).compose(c),a.compose(b.compose(c)))
    def test_family_mix(self):
        cert=FamilyCertificate.create([10,12,15]);self.assertTrue(FamilyCertificate.verify(cert));self.assertEqual(cert['lucas'],lucas(37))
    def test_cassini_pell(self):
        for n in range(128):self.assertEqual(FamilyCertificate.create([n])['pell_cassini_residual'],4*(-1)**n)
    def test_index_quota(self):
        with self.assertRaises(ValueError):FamilyCertificate.create([10000,1])
    def test_tamper(self):
        c=FamilyCertificate.create([15,20]);c['norm']=0
        with self.assertRaises(ValueError):FamilyCertificate.verify(c)
    def test_zero_inverse(self):
        with self.assertRaises(ZeroDivisionError):PhiElement().inverse()
    def test_field_does_not_accept_approximate_authority(self):
        with self.assertRaises(ValueError):PhiElement(0.1)
    def test_binet_core_agreement(self):
        for n in (0,1,2,15,50,110,1000):self.assertEqual((PHI**n).trace(),lucas(n))
if __name__=='__main__':unittest.main()

class PublicationChecks(unittest.TestCase):
    def test_derived_orbit_preserves_original_authority(self):
        c=FamilyCertificate.create([10,12,15,18,20]);self.assertEqual(c['fibonacci_pair'],list(fibonacci_pair(75)));self.assertEqual(c['authority'],'supplied_exact_lucas_engine')
    def test_signing_concurrent_evidence_chain(self):
        import concurrent.futures,time
        from chronos import OneIGPU
        from chronos.igpu import verify_evidence
        g=OneIGPU(evidence_key=bytes(range(32)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8)as pool:list(pool.map(lambda i:g.golden.attest('parallel',time.perf_counter(),details={'index':i}),range(100)))
        self.assertEqual(len(g.golden.events),100);self.assertTrue(verify_evidence(g.golden.events,bytes(range(32)),g.golden.events[-1]['digest']))
