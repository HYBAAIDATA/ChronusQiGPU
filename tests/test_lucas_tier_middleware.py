import concurrent.futures
import dataclasses
import tempfile
import unittest
from pathlib import Path

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from Intelligence.lucas_tier_middleware import (
    ComputeRequest,
    ProductionLucasTierMiddleware,
    SQLiteAuditStore,
    TokenBucketLimiter,
    _tensor_digest,
)


class MiddlewareV43Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "audit.sqlite3"
        self.key = Ed25519PrivateKey.generate()
        self.entitlements = {"tenant-a": "free", "tenant-b": "pro"}
        self.middleware = self.make_middleware()

    def tearDown(self):
        self.tmp.cleanup()

    def make_middleware(self, path=None):
        return ProductionLucasTierMiddleware(
            signing_key=self.key,
            entitlements=self.entitlements,
            audit_store=SQLiteAuditStore(path or self.db_path),
            max_payload_elements=1000,
            max_payload_bytes=8000,
        )

    def request(self, payload=None, depth=5, tier="free", provenance="exact_integer", rid="r-1"):
        if payload is None:
            payload = np.array([3, 7, 11], dtype=np.int64)
        return ComputeRequest("tenant-a", rid, tier, depth, payload, provenance)

    def submit(self, request):
        # In production, this value comes from authenticated server context,
        # never from the request body.
        return self.middleware.process_workload(
            request, authenticated_tenant_id=request.tenant_id)

    def test_package_lazy_export_points_to_middleware_module(self):
        from Intelligence import ProductionLucasTierMiddleware as exported
        self.assertIs(exported, ProductionLucasTierMiddleware)

    def test_tier_is_derived_from_trusted_entitlements(self):
        with self.assertRaises(PermissionError):
            self.submit(self.request(tier="unbounded"))
        with self.assertRaises(PermissionError):
            self.middleware.process_workload(
                self.request(), authenticated_tenant_id="tenant-b")
        unknown = ComputeRequest("attacker", "r", "free", 3,
                                 np.array([1], dtype=np.int64))
        with self.assertRaises(PermissionError):
            self.submit(unknown)

    def test_full_verification_passes_including_odd_tail(self):
        payload = np.array([3, 7, 11], dtype=np.int64)
        response = self.submit(self.request(payload=payload))
        self.assertEqual(self.middleware.verify_signed_response(response, payload), (True, []))

    def test_verifier_rejects_wrong_shape_and_wrong_trailing_element(self):
        payload = np.array([3, 7, 11], dtype=np.int64)
        response = self.submit(self.request(payload=payload))
        shorter = response.processed_tensor[:-1].copy()
        short_response = dataclasses.replace(
            response, processed_tensor=shorter,
            output_tensor_digest=_tensor_digest(shorter),
        )
        ok, failures = self.middleware.verify_claims(short_response, payload)
        self.assertFalse(ok)
        self.assertTrue(any("shape mismatch" in f for f in failures))

        altered = response.processed_tensor.copy()
        altered[-1] = (int(altered[-1]) + 1) % 256
        tail_response = dataclasses.replace(
            response, processed_tensor=altered,
            output_tensor_digest=_tensor_digest(altered),
        )
        ok, failures = self.middleware.verify_claims(tail_response, payload)
        self.assertFalse(ok)
        self.assertTrue(any("trailing element mismatch" in f for f in failures))

    def test_signature_binds_security_relevant_response_fields_and_tensor(self):
        response = self.submit(self.request())
        self.assertTrue(self.middleware.verify_signature(response))
        changed = dataclasses.replace(response, tier_enforced="Tier 5: Infinite Unbounded")
        self.assertFalse(self.middleware.verify_signature(changed))
        tensor = response.processed_tensor.copy()
        tensor[0] = (int(tensor[0]) + 1) % 256
        changed_tensor = dataclasses.replace(
            response, processed_tensor=tensor,
            output_tensor_digest=_tensor_digest(tensor),
        )
        self.assertFalse(self.middleware.verify_signature(changed_tensor))

    def test_depth_and_payload_validation(self):
        with self.assertRaises(ValueError):
            self.submit(self.request(depth=-1))
        with self.assertRaises(ValueError):
            self.submit(self.request(depth=2.5))
        with self.assertRaises(ValueError):
            self.submit(self.request(
                payload=np.array([256], dtype=np.int64)))
        with self.assertRaises(ValueError):
            self.submit(self.request(
                payload=np.array([2**62], dtype=np.int64)))
        with self.assertRaises(ValueError):
            self.submit(self.request(
                payload=np.array([1.0, 2.0]), provenance="exact_integer"))

    def test_float_derived_requires_real_integral_residues(self):
        payload = np.array([1.0, 2.0, 255.0], dtype=np.float64)
        response = self.submit(self.request(
            payload=payload, provenance="float_derived"))
        self.assertTrue(self.middleware.verify_signed_response(response, payload)[0])
        for bad in (np.array([1.5]), np.array([np.nan]), np.array([256.0]),
                    np.array([1 + 2j]), np.array(["1"])):
            with self.subTest(bad=bad.dtype):
                with self.assertRaises(ValueError):
                    self.submit(self.request(
                        payload=bad, provenance="float_derived"))

    def test_ingress_preflight_and_processing_caps(self):
        self.middleware.preflight_content_length(8000, 8000)
        with self.assertRaises(ValueError):
            self.middleware.preflight_content_length(8001, 8000)
        with self.assertRaises(ValueError):
            self.submit(self.request(
                payload=np.arange(1001, dtype=np.int64)))

    def test_receipt_tampering_is_detected(self):
        response = self.submit(self.request())
        original = response.depth_clamp_receipt
        changed = dataclasses.replace(
            original, witness={**original.witness, "enforced_n": 999})
        altered = dataclasses.replace(response, depth_clamp_receipt=changed)
        self.assertFalse(self.middleware.verify_receipts(altered)[0])
        self.assertFalse(self.middleware.verify_signature(altered))

    def test_token_bucket_state_is_bounded_and_idle_tenants_expire(self):
        now = [0.0]
        limiter = TokenBucketLimiter(clock=lambda: now[0], max_tenants=1)
        self.assertTrue(limiter.try_consume("a", 1, 10, 60)[0])
        with self.assertRaises(RuntimeError):
            limiter.try_consume("b", 1, 10, 60)
        now[0] = 60.0
        self.assertTrue(limiter.try_consume("b", 1, 10, 60)[0])
        self.assertEqual(limiter.tenant_count, 1)

    def test_chain_survives_restart_with_same_key_and_persistent_store(self):
        first = self.submit(self.request(rid="first"))
        restarted = self.make_middleware()
        second = restarted.process_workload(self.request(rid="second"), authenticated_tenant_id="tenant-a")
        self.assertEqual(second.parent_certificate_hash, first.output_certificate_hash)
        self.assertEqual(restarted.verify_certificate_chain(), (True, []))

    def test_concurrent_requests_append_a_single_valid_chain(self):
        def run(i):
            return self.submit(self.request(rid=f"parallel-{i}"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(run, range(24)))
        self.assertEqual(len(responses), 24)
        self.assertEqual(len(self.middleware.audit_store.entries()), 24)
        self.assertEqual(self.middleware.verify_certificate_chain(), (True, []))

    def test_matrix_order_constant_is_minimal_and_correct(self):
        self.assertEqual(self.middleware.M_ORDER, 384)
        self.assertTrue(self.middleware._assert_M_order(384))
        self.assertFalse(self.middleware._assert_M_order(768))

    def test_cassini_fast_producer_is_correct_over_supported_range(self):
        for n in range(124):
            with self.subTest(n=n):
                receipt = self.middleware._cassini_receipt(n)
                self.assertTrue(receipt.verify())
                self.assertTrue(self.middleware._slow_cassini_valid(n))

    def test_verifier_bounds_adversarial_depth(self):
        response = self.submit(self.request())
        huge = dataclasses.replace(response, enforced_n=10**12)
        ok, failures = self.middleware.verify_claims(huge, response.processed_tensor)
        self.assertFalse(ok)
        self.assertTrue(any("verification bound" in f or "tier cap" in f for f in failures))


if __name__ == "__main__":
    unittest.main(verbosity=2)
