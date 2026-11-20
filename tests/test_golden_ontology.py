"""Standard-library conformance tests, including independent small-domain checks."""
import json
from dataclasses import replace
import math
import time
import unittest
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import patch

# Pytest classification metadata when present; unittest needs no dependency.
try:
    import pytest
except ModuleNotFoundError:
    pytest=SimpleNamespace(mark=SimpleNamespace(real=None, simulated=None))

from governance import gate
from golden_ontology.filter import NonMonotoneWarpError,PisotFilter,ZeckendorfMap
from golden_ontology.fold import PeriodError,RangeError,fold_words,unfold_words
from golden_ontology.resonance import certify_pairwise_irrationality,phi_neg_power_cert
from golden_ontology.substrate import (
    PV_REGISTRY,UnregisteredFamilyError,fib_pair,generalized_pisano_period,
    get_family,lucas_uv,mat_identity,mat_mul,mat_pow,pisano_period_pow2,generalized_lucas,
    polynomial_value,
)
from verify import benchmark

VECTORS=Path(__file__).resolve().parents[1]/"spec/test_vectors.json"
ERRORS={c.__name__:c for c in (ValueError,RangeError,PeriodError,
                                 NonMonotoneWarpError,UnregisteredFamilyError)}

class TestNormativeVectors(unittest.TestCase):
    pytestmark = pytest.mark.real

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
    pytestmark = pytest.mark.real

    def test_empty_fold_still_validates_explicit_period(self):
        for operation in (fold_words, unfold_words):
            with self.subTest(operation=operation.__name__):
                self.assertEqual(operation((), 10**50, 1, 3), [])
                with self.assertRaises(PeriodError):
                    operation((), 0, 1, 3.0)

    def test_fold_matches_repeated_q_action_across_period_wrap(self):
        original = [0, 15, 15, 15, 7, 1]
        for steps in (0, 1, 2, 23, 24, 25, 49):
            with self.subTest(steps=steps):
                expected = []
                for x, y in zip(original[::2], original[1::2]):
                    for _ in range(steps):
                        x, y = (x + y) % 16, x
                    expected.extend((x, y))
                self.assertEqual(fold_words(original, steps, 4, 24), expected)
                self.assertEqual(unfold_words(expected, steps, 4, 24), original)

    def test_matrix_arithmetic_and_identity_modulo_one(self):
        shear = ((1, -2), (0, 1))
        swap = ((0, 1), (1, 0))
        self.assertEqual(mat_mul(shear, swap), ((-2, 1), (1, 0)))
        self.assertEqual(mat_mul(swap, shear, 5), ((0, 1), (1, 3)))
        self.assertEqual(mat_pow(shear, 7, 5), ((1, 1), (0, 1)))
        self.assertEqual(mat_pow(shear, 0, 1), ((0, 0), (0, 0)))
        for matrix in ((), ((1, 2),), ((True,),)):
            with self.subTest(matrix=matrix), self.assertRaises(ValueError):
                mat_pow(matrix, 0)
        with self.assertRaises(ValueError):
            mat_mul(shear, ((1,),))

    def test_generalized_period_search_bound_includes_the_last_step(self):
        # Silver modulo 2 swaps the coordinates, so its order is exactly two.
        self.assertEqual(generalized_pisano_period("silver", 1, max_steps=1), 1)
        self.assertEqual(generalized_pisano_period("silver", 2, max_steps=2), 2)
        with self.assertRaisesRegex(RuntimeError, "exceeds search bound"):
            generalized_pisano_period("silver", 2, max_steps=1)

    def test_root_refinement_preserves_exact_bracket(self):
        for family in PV_REGISTRY.values():
            with self.subTest(family=family.name):
                outer_lo, outer_hi = family.root_interval(4)
                lo, hi = family.root_interval(12)
                self.assertLessEqual(outer_lo, lo)
                self.assertLessEqual(hi, outer_hi)
                self.assertEqual(hi - lo, (3 - family.alpha_lower) / 2**12)
                self.assertLess(polynomial_value(family.polynomial, lo), 0)
                self.assertGreater(polynomial_value(family.polynomial, hi), 0)

    def test_certificate_rejects_invalid_family_data(self):
        golden = get_family("golden")
        for family, message in (
            (replace(golden, det=1), "non-unimodular"),
            (replace(golden, polynomial=(1, -2, -1)), "polynomial mismatch"),
            (replace(golden, mu_upper=Fraction(1, 2)), "conjugate bound"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ArithmeticError, message):
                family.certify()

    def test_sequence_and_width_contract(self):
        for width in (1,8,4097):
            x=range(2)
            self.assertEqual(unfold_words(fold_words(x,7,width),7,width),list(x))
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
    def test_generalized_lucas(self):
        for name,family in PV_REGISTRY.items():
            d=family.degree
            values=[generalized_lucas(name,n) for n in range(16)]
            self.assertEqual(values[0],d)
            for n in range(d,16):
                self.assertEqual(values[n],-sum(family.polynomial[k]*values[n-k] for k in range(1,d+1)))
                self.assertEqual(generalized_lucas(name,n,17),values[n]%17)
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
    pytestmark = pytest.mark.real

    def test_pairwise_witnesses_use_absolute_distance(self):
        self.assertEqual(certify_pairwise_irrationality([5, 0, 2]),
                         [(5, 0, 5), (5, 2, 2), (0, 2, 1)])
        self.assertEqual(certify_pairwise_irrationality([0]), [])

    def test_projection_rejects_conjugate_with_matching_norm(self):
        certificate = phi_neg_power_cert(7)
        forged = replace(certificate, q=-certificate.q)
        self.assertTrue(forged.norm_certified)
        with self.assertRaisesRegex(ValueError, "invalid algebraic certificate"):
            forged.to_float()

    def test_filter_clamps_edges_for_short_nonconstant_signal(self):
        filt = PisotFilter("silver", radius=2)
        inverse_root = math.sqrt(2) - 1
        outside = inverse_root + inverse_root**2
        height = 7
        left, right = filt.apply([0, height])
        self.assertAlmostEqual(left, height * outside / (1 + 2 * outside))
        self.assertAlmostEqual(right, height * (1 + outside) / (1 + 2 * outside))
        for invalid in (True, math.inf, -math.inf, math.nan):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                filt.apply([0, invalid])

    def test_dense_ranks_use_nonadjacent_fibonacci_terms(self):
        values = [60, 10, 30, 20, 50, 40, Fraction(30)]
        self.assertEqual(ZeckendorfMap.encode_ranks(values),
                         [(5, 1), (1,), (3,), (2,), (5,), (3, 1), (3,)])

    def test_warp_rejects_changes_to_order_or_tie_classes(self):
        original = [2, 1, 1, 3]
        ZeckendorfMap.verify_monotone_warp(original, [2, 0, 0, 3])
        for case, warped in (
            ("inversion", [4, 0, 0, 3]),
            ("split tie", [1, 0, 1, 3]),
            ("merged ranks", [1, 0, 0, 1]),
            ("length mismatch", [1, 0, 0]),
            ("nonfinite", [1, 0, 0, math.inf]),
        ):
            with self.subTest(case=case), self.assertRaises(NonMonotoneWarpError):
                ZeckendorfMap.verify_monotone_warp(original, warped)

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
            self.assertEqual(f.certificate.alpha_polynomial,f.family.polynomial)
            self.assertEqual(f.certificate.alpha_exponent,Fraction(-3,1 if f.family.degree==2 else 2))
            self.assertEqual(f.certificate.bound_at_radius,f.certificate.mu_upper**3)
    def test_rank_ties_and_warps(self):
        x=[-1,0,0,2,3]
        for y in ([v**3 for v in x],[3*v+8 for v in x]):
            ZeckendorfMap.verify_monotone_warp(x,y)
            self.assertEqual(ZeckendorfMap.encode_ranks(x),ZeckendorfMap.encode_ranks(y))
        with self.assertRaises(NonMonotoneWarpError):
            ZeckendorfMap.encode_ranks([1,math.nan])

class TestGovernance(unittest.TestCase):
    pytestmark = pytest.mark.real

    def test_refuses_missing_duplicate_unknown_and_open(self):
        good={"package":"golden_ontology","version":"2.0.0",
              "findings":[{"id":"QC-001","title":"QC","status":"OPEN","owner":"reviewer"}]}
        self.assertIn("QC-001",gate.validate(good))
        for bad in ({},{**good,"findings":[]},{**good,"findings":[good["findings"][0]]*2},
                    {**good,"findings":[{**good["findings"][0],"id":"OTHER"}]},
                    {**good,"findings":[{**good["findings"][0],"status":"CLOSED"}]}):
            with self.assertRaises(ValueError):
                gate.validate(bad)


class TestBenchmarkMetrics(unittest.TestCase):
    pytestmark = pytest.mark.real

    def test_rmse_uses_mean_squared_error_and_validates_shape(self):
        self.assertEqual(benchmark.rmse([0, 0, 0, 0], [2, 0, 0, 0]), 1)
        for left, right in (([], []), ([0], [0, 1])):
            with self.subTest(left=left, right=right), self.assertRaises(ValueError):
                benchmark.rmse(left, right)

    def test_centered_and_causal_baselines_have_distinct_impulse_responses(self):
        for method in (benchmark.savgol_5, benchmark.savgol_9, benchmark.zero_phase_sma):
            with self.subTest(method=method.__name__):
                self.assertAlmostEqual(benchmark.impulse_asymmetry(method), 0)
                for value in method([2] * 3):
                    self.assertAlmostEqual(value, 2)
        self.assertGreater(benchmark.impulse_asymmetry(benchmark.causal_ema), 0)

    def test_warp_report_preserves_ranks_but_records_nonlinear_drift(self):
        report = benchmark.run_warp_benchmark()
        self.assertEqual(set(report), {"unit_rescale", "cubic_x3", "exp", "arctan"})
        for name, metrics in report.items():
            with self.subTest(warp=name):
                self.assertEqual(metrics["zeckendorf_rank_drift"], 0)
        self.assertAlmostEqual(report["unit_rescale"]["standard_scaler_rmse_drift"], 0)
        self.assertGreater(report["cubic_x3"]["standard_scaler_rmse_drift"], 0)


class TestGovernanceApproval(unittest.TestCase):
    pytestmark = pytest.mark.simulated

    def setUp(self):
        self.record = {
            "id": "QC-001", "title": "QC", "status": "CLOSED", "owner": "auditor",
            "reviewer": "auditor", "reviewed_commit": "a" * 40, "review_id": 17,
            "spec_sha256": "b" * 64, "vectors_sha256": "c" * 64, "mismatch_count": 0,
            "evidence_url": "https://github.com/HYBAAIDATA/ChronusQiGPU/issues/1",
        }
        self.register = {
            "package": "golden_ontology", "version": "2.0.0", "findings": [self.record],
        }
        self.pr = {"user": {"login": "author"}}
        self.review = {
            "user": {"login": "Auditor"}, "state": "APPROVED",
            "commit_id": self.record["reviewed_commit"],
            "body": "\n".join(self.record[key] for key in
                              ("evidence_url", "spec_sha256", "vectors_sha256")),
        }
        self._start_patch(patch.dict("os.environ", {"GOLDEN_QC_REVIEWER": "auditor"}))
        digests = {"GOLDEN_ONTOLOGY.md": "b" * 64, "test_vectors.json": "c" * 64}
        self._start_patch(patch.object(gate, "_sha", side_effect=lambda path: digests[path.name]))
        self.diff = self._start_patch(patch.object(gate.subprocess, "run", return_value=SimpleNamespace(returncode=0)))
        responses = {"/pulls/207": self.pr, "/pulls/207/reviews/17": self.review}
        self.github = self._start_patch(patch.object(gate, "_github", side_effect=responses.__getitem__))

    def _start_patch(self, patcher):
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_accepts_matching_independent_approval(self):
        self.assertIsNone(gate.validate(self.register))
        self.assertEqual(self.github.call_count, 2)

    def test_rejects_changed_scope_before_reading_review(self):
        self.diff.return_value.returncode = 1
        with self.assertRaisesRegex(ValueError, "reviewed scope changed"):
            gate.validate(self.register)
        self.github.assert_not_called()

    def test_rejects_nonindependent_or_stale_review(self):
        cases = (
            (self.pr, "user", {"login": "AUDITOR"}),
            (self.review, "user", {"login": "another-reviewer"}),
            (self.review, "state", "COMMENTED"),
            (self.review, "commit_id", "d" * 40),
        )
        for source, field, value in cases:
            with self.subTest(field=field, value=value), patch.dict(source, {field: value}):
                with self.assertRaisesRegex(ValueError, "no matching independent GitHub approval"):
                    gate.validate(self.register)

    def test_approval_must_attest_each_piece_of_evidence(self):
        for field in ("evidence_url", "spec_sha256", "vectors_sha256"):
            with self.subTest(field=field):
                body = self.review["body"].replace(self.record[field], "")
                with patch.dict(self.review, {"body": body}):
                    with self.assertRaisesRegex(ValueError, "does not attest"):
                        gate.validate(self.register)

    def test_register_rejects_invalid_reconstruction_before_review_lookup(self):
        for edits, message in (
            ({"spec_sha256": "d" * 64}, "digest mismatch"),
            ({"mismatch_count": 1}, "zero-mismatch reconstruction"),
            ({"mismatch_count": False}, "zero-mismatch reconstruction"),
            ({"review_id": True}, "immutable review reference"),
        ):
            with self.subTest(edits=edits), patch.dict(self.record, edits):
                with self.assertRaisesRegex(ValueError, message):
                    gate.validate(self.register)
        self.github.assert_not_called()

    def test_closed_unknown_finding_requires_separate_validator(self):
        self.register["findings"].append({**self.record, "id": "QC-002"})
        with self.assertRaisesRegex(ValueError, "no authenticated validator"):
            gate.validate(self.register)
        self.github.assert_not_called()

if __name__=="__main__":
    unittest.main(verbosity=2)
