"""Standard-library conformance tests, including independent small-domain checks."""
import json
import math
import time
import unittest
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace

# Pytest classification metadata when present; unittest needs no dependency.
try:
    import pytest
except ModuleNotFoundError:
    pytest=SimpleNamespace(mark=SimpleNamespace(real=None))
pytestmark = pytest.mark.real

from golden_ontology.filter import NonMonotoneWarpError,PisotFilter,ZeckendorfMap
from golden_ontology.fold import PeriodError,RangeError,fold_words,unfold_words
from golden_ontology.resonance import certify_pairwise_irrationality,phi_neg_power_cert
from golden_ontology.substrate import (
    PV_REGISTRY,UnregisteredFamilyError,fib_pair,generalized_pisano_period,
    get_family,lucas_uv,mat_identity,mat_pow,pisano_period_pow2,
)

VECTORS=Path(__file__).resolve().parents[1]/"spec/test_vectors.json"
ERRORS={c.__name__:c for c in (ValueError,RangeError,PeriodError,
                                 NonMonotoneWarpError,UnregisteredFamilyError)}

class TestNormativeVectors(unittest.TestCase):
    def test_accept(self):
        data=json.loads(VECTORS.read_text())
        self.assertTrue(data["accept"])
        for v in data["accept"]:
            with self.subTest(id=v["id"]):
                if v["op"]=="fold_words":
                    got=fold_words(v["input"],v["steps"],v["bits"],v["pisano_period"])
                    self.assertEqual(got,v["expected"])
                    self.assertEqual(unfold_words(got,v["steps"],v["bits"],v["pisano_period"]),v["input"])
                elif v["op"]=="phi_neg_power_cert":
                    c=phi_neg_power_cert(v["k"])
                    self.assertEqual({k:getattr(c,k) for k in v["expected"]},v["expected"])
                else:
                    self.fail("unknown accept operation")
    def test_reject(self):
        data=json.loads(VECTORS.read_text())
        self.assertTrue(data["reject"])
        for v in data["reject"]:
            with self.subTest(id=v["id"]):
                op=v["op"]
                if op=="unfold_verify":
                    self.assertTrue(v["expected_mismatch"])
                    self.assertNotEqual(unfold_words(v["tampered_folded"],v["steps"],v["bits"]),v["original"])
                    continue
                with self.assertRaises(ERRORS[v["expected_error"]]):
                    if op=="fold_words":
                        fold_words(v["input"],v["steps"],v["bits"],v.get("expected_period"))
                    elif op=="verify_monotone_warp":
                        ZeckendorfMap.verify_monotone_warp(v["original"],v["warped"])
                    elif op=="get_family":
                        get_family(v["family"])
                    else:
                        self.fail("unknown reject operation")

class TestExactSubstrate(unittest.TestCase):
    def test_4096_bit_roundtrip(self):
        b=4096
        p=pisano_period_pow2(b)
        x=[(1<<b)-1,(1<<2048)+99]
        t=time.perf_counter()
        y=fold_words(x,p-137,b)
        self.assertEqual(unfold_words(y,p-137,b),x)
        elapsed=time.perf_counter()-t
        print("4096-bit roundtrip seconds:",elapsed)
        self.assertLess(elapsed,1.0,"supplied 4096-bit measured threshold failed")
    def test_fold_period_minimal_small(self):
        for b in range(1,11):
            m=1<<b
            p=pisano_period_pow2(b)
            a,c=1,0
            for i in range(1,p+1):
                a,c=(a+c)%m,a
                if (a,c)==(1,0):
                    self.assertEqual(i,p)
                    break
            else:
                self.fail("period not reached")
    def test_pv_orders_and_exact_bounds(self):
        for name,fam in PV_REGISTRY.items():
            with self.subTest(family=name):
                self.assertTrue(fam.certify())
                self.assertIsInstance(fam.contraction_bound(4),Fraction)
                for m in (2,3,8):
                    p=generalized_pisano_period(name,m)
                    self.assertEqual(mat_pow(fam.companion,p,m),mat_identity(fam.degree))
                    self.assertTrue(all(mat_pow(fam.companion,k,m)!=mat_identity(fam.degree)
                                        for k in range(1,p)))
    def test_lucas_and_modulus(self):
        for n in (0,1,2,10,37):
            for m in (None,1,17):
                f,g=fib_pair(n,m)
                v=2*g-f
                self.assertEqual(lucas_uv(n,1,-1,m),(f,v if m is None else v%m))
        for n in (True,-1,1.0):
            with self.assertRaises(ValueError):
                fib_pair(n,8)
        with self.assertRaises(ValueError):
            generalized_pisano_period("golden",True)
        with self.assertRaises(UnregisteredFamilyError):
            generalized_pisano_period("unknown",1)

class TestResonanceFilter(unittest.TestCase):
    def test_norm(self):
        for k in range(65):
            c=phi_neg_power_cert(k)
            self.assertTrue(c.norm_certified)
            self.assertGreater(c.to_float(),0)
        self.assertEqual(len(certify_pairwise_irrationality([1,2,5,11])),6)
        with self.assertRaises(ValueError):
            certify_pairwise_irrationality([1,1])
    def test_filter(self):
        for name in PV_REGISTRY:
            f=PisotFilter(name,3)
            self.assertEqual(f.kernel,f.kernel[::-1])
            self.assertAlmostEqual(math.fsum(f.kernel),1)
            self.assertEqual(f.apply([]),[])
            self.assertTrue(all(abs(x-1)<1e-12 for x in f.apply([1]*9)))
            self.assertLess(f.certificate.bound_at_radius,1)
    def test_rank_ties_and_warps(self):
        x=[-1,0,0,2,3]
        for y in ([v**3 for v in x],[3*v+8 for v in x]):
            ZeckendorfMap.verify_monotone_warp(x,y)
            self.assertEqual(ZeckendorfMap.encode_ranks(x),ZeckendorfMap.encode_ranks(y))
        with self.assertRaises(NonMonotoneWarpError):
            ZeckendorfMap.encode_ranks([1,math.nan])

class TestGovernance(unittest.TestCase):
    def test_refuses_missing_duplicate_unknown_and_open(self):
        from governance.gate import validate
        good={"package":"golden_ontology","version":"2.0.0",
              "findings":[{"id":"QC-001","title":"QC","status":"OPEN","owner":"reviewer"}]}
        self.assertIn("QC-001",validate(good))
        for bad in ({},{**good,"findings":[]},{**good,"findings":[good["findings"][0]]*2},
                    {**good,"findings":[{**good["findings"][0],"id":"OTHER"}]},
                    {**good,"findings":[{**good["findings"][0],"status":"CLOSED"}]}):
            with self.assertRaises(ValueError):
                validate(bad)

if __name__=="__main__":
    unittest.main(verbosity=2)
