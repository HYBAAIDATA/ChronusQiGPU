"""Real-source admission regressions; no device, pool or deployment assertions."""
import dataclasses
import hashlib
import json
import math
import unittest

from chronus.exact_geometry import build_600_partition
from chronus.mla1517.mining.search_plan import WorkIdentity
from kellogg.ansatz_v3 import load_ansatz
from kellogg.mother_tensor import KelloggMotherTensor


class KelloggPlanAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks, cls.proof = build_600_partition(42, 601)
        cls.identity = WorkIdentity('test-session', 1, 'job', 'fingerprint', 0, True, 1.0)

    def state(self, **changes):
        values = dict(chunks=self.chunks, proof=self.proof, futures=('job',),
                      future_probabilities=(1.0,))
        values.update(changes)
        return KelloggMotherTensor(**values)

    def test_finite_probabilities_required(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.state(future_probabilities=(value,))

    def test_probability_range_required(self):
        with self.assertRaises(ValueError):
            self.state(futures=('a', 'b'), future_probabilities=(-0.5, 1.5))

    def test_boolean_probability_rejected(self):
        with self.assertRaises(ValueError):
            self.state(future_probabilities=(True,))

    def test_future_names_nonempty_unique_strings(self):
        for names in (('',), (' ',), (None,), ('a', 'a')):
            with self.subTest(names=names), self.assertRaises(ValueError):
                self.state(futures=names, future_probabilities=tuple(1/len(names) for _ in names))

    def test_normalization_still_required(self):
        with self.assertRaises(ValueError):
            self.state(future_probabilities=(0.5,))

    def test_missing_proof_fails_closed(self):
        with self.assertRaises(ValueError):
            self.state(proof=None).build_search_plan(self.identity)

    def test_bad_certificate_fails_closed(self):
        bad = dataclasses.replace(self.proof, certificate_sha256='0'*64)
        with self.assertRaises(ValueError):
            self.state(proof=bad).build_search_plan(self.identity)

    def test_foreign_proof_fails_closed(self):
        _, other = build_600_partition(100, 601)
        with self.assertRaises(ValueError):
            self.state(proof=other).build_search_plan(self.identity)

    def test_self_consistent_wrong_coverage_certificate_fails_closed(self):
        # An unkeyed metadata checksum can be recomputed by any caller. It
        # must not replace independent binding to the actual chunk coverage.
        payload = {key: value for key, value in self.proof.as_dict().items()
                   if key not in ('certificate_sha256', 'representation_labels')}
        payload['coverage_hash'] = '0' * 64
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        bad = dataclasses.replace(self.proof, coverage_hash=payload['coverage_hash'],
                                  certificate_sha256=digest)
        self.assertTrue(bad.verify())
        with self.assertRaises(ValueError):
            self.state(proof=bad).build_search_plan(self.identity)

    def test_failed_gauge_cannot_be_cached_as_passed(self):
        state = self.state(ansatz=dataclasses.replace(load_ansatz(), lanes=32),
                           yang_mills_enforced=True)
        with self.assertRaises(ArithmeticError):
            state.build_search_plan(self.identity)

    def test_chunk_overlap_fails_closed(self):
        chunks = list(self.chunks)
        chunks[1] = dataclasses.replace(chunks[1], base_step=42, nonces=(42,))
        with self.assertRaises(ValueError):
            self.state(chunks=tuple(chunks)).build_search_plan(self.identity)

    def test_mutable_nonce_container_rejected(self):
        chunks = list(self.chunks)
        chunks[0] = dataclasses.replace(chunks[0], nonces=list(chunks[0].nonces))
        with self.assertRaises(ValueError):
            self.state(chunks=tuple(chunks)).build_search_plan(self.identity)

    def test_bad_lane_identity_fails_closed(self):
        chunks = list(self.chunks)
        chunks[0] = dataclasses.replace(chunks[0], lane_id=1)
        with self.assertRaises(ValueError):
            self.state(chunks=tuple(chunks)).build_search_plan(self.identity)

    def test_bad_vertex_owner_fails_closed(self):
        chunks = list(self.chunks)
        chunks[0] = dataclasses.replace(chunks[0], vertex_id=chunks[1].vertex_id)
        with self.assertRaises(ValueError):
            self.state(chunks=tuple(chunks)).build_search_plan(self.identity)

    def test_bad_ray_fails_closed(self):
        chunks = list(self.chunks)
        chunks[0] = dataclasses.replace(chunks[0], ray_11d=chunks[1].ray_11d)
        with self.assertRaises(ValueError):
            self.state(chunks=tuple(chunks)).build_search_plan(self.identity)

    def test_nonce_order_tamper_fails_closed(self):
        chunks = list(self.chunks)
        chunks[0] = dataclasses.replace(chunks[0], nonces=tuple(reversed(chunks[0].nonces)))
        with self.assertRaises(ValueError):
            self.state(chunks=tuple(chunks)).build_search_plan(self.identity)

    def test_seed_mutation_fails_closed(self):
        state = self.state()
        state.seed += 1
        with self.assertRaises(ValueError):
            state.build_search_plan(self.identity)

    def test_dimension_mutation_fails_closed(self):
        state = self.state()
        state.future_probabilities = (math.nan,)
        with self.assertRaises(ValueError):
            state.build_search_plan(self.identity)

    def test_failed_contraction_cannot_be_cached_as_passed(self):
        ansatz = dataclasses.replace(load_ansatz(), phi_inv=1.0)
        state = self.state(ansatz=ansatz, yang_mills_enforced=True,
                           contraction_evidence={'contraction_verified': True})
        with self.assertRaises(ArithmeticError):
            state.build_search_plan(self.identity)

    def test_good_plan_retains_m32_compatibility_not_600_devices(self):
        plan = self.state().build_search_plan(self.identity)
        self.assertEqual(plan.lane_order, tuple(range(32)))
        self.assertEqual(plan.dispatch_breadth, 32)
        self.assertEqual(plan.window, 601)
        self.assertEqual(plan.base_step, 42)
        self.assertEqual(plan.evidence_refs['lanes'], 600)
        self.assertTrue(plan.evidence_refs['partition_proof_600']['is_disjoint'])
        self.assertTrue(plan.is_valid_for(self.identity))

    def test_window_boundary_cases(self):
        for base, window in ((0, 1), (0, 599), (0, 600), (0, 601), (0, 1237), (20, 4097), ((1<<32)-601, 601)):
            with self.subTest(base=base, window=window):
                chunks, proof = build_600_partition(base, window)
                plan = self.state(chunks=chunks, proof=proof).build_search_plan(self.identity)
                self.assertEqual((plan.base_step, plan.window), (base, window))

    def test_zero_window_not_executable(self):
        chunks, proof = build_600_partition(0, 0)
        with self.assertRaises(ValueError):
            self.state(chunks=chunks, proof=proof).build_search_plan(self.identity)

    def test_plan_evidence_detached_from_mutable_tensor(self):
        state = self.state()
        plan = state.build_search_plan(self.identity)
        state.contraction_evidence['phi_method']['status'] = 'MISSING'
        self.assertEqual(plan.evidence_refs['contraction']['phi_method']['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
