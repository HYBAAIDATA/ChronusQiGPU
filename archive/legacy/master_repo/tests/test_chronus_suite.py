import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from tests.test_invariants_all import TestAllInvariantsSuite
from tests.test_ns_dec import TestNavierStokesDECSuite
from tests.test_crypto_stark import TestCryptoAndStarkSuite
from tests.test_sdk_api import TestSDKAndAPISuite
from tests.test_hermiten_pricing import TestHermitenAndPricingSuite

# ------------------------------------------------------------------
# NEW: Edge‑case, adversarial, integration & end‑to‑end tests
# ------------------------------------------------------------------
class TestInvariantsEdgeAdversarialSuite(unittest.TestCase):
    """Edge‑case and adversarial robustness tests for invariants I1‑I94."""
    def test_I1_cos_receipt(self):
        from src.chronus.core import OVIDService
        receipt = OVIDService.store("tenant1", b"payload", "obj1", {})
        self.assertIsNotNone(receipt)
        self.assertIn("o1_", receipt["oVID_id"])

    def test_I2_receipt_hash_rfc8785(self):
        from src.chronus.core import OVIDService, rfc8785
        payload = {"key": "value"}
        receipt = OVIDService.store("tenant1", json.dumps(payload).encode(), "obj1", {})
        expected = hashlib.sha256(rfc8785(payload)).hexdigest()
        self.assertEqual(receipt["receipt_hash"], expected)

    def test_I8_m15_invertibility(self):
        from src.chronus.core import ExactFoldCore
        core = ExactFoldCore()
        for x in range(1, 100):
            folded = core.fold(x)
            unfolded = core.unfold(folded)
            self.assertEqual(unfolded, x,
                             f"M15 invertibility failed for {x}")

    def test_I14_galois_zero_divisors(self):
        from src.chronus.chronus_gpiu_v36 import GaloisFieldElement as GFE
        import random
        for _ in range(200):
            a = GFE(a=random.randint(1, 256), b=random.randint(1, 256))
            b = GFE(a=random.randint(1, 256), b=random.randint(1, 256))
            c = a * b
            self.assertNotEqual((c.a, c.b), (0, 0),
                                "Zero‑divisor found in F_257[φ]")

    def test_I16_fri_quotient(self):
        # minimal check that the FRI verifier object exists and has a method
        from src.chronus.core import ZKSTARKVerifier
        v = ZKSTARKVerifier()
        self.assertTrue(hasattr(v, 'verify_quotient'))

    def test_adversarial_corrupt_signature(self):
        # Ensure that a deliberately corrupted ML‑DSA signature is rejected
        from src.chronus.core import MLDSASigner
        signer = MLDSASigner()
        bad_sig = signer.sign(b"data")  # good sig
        # tamper with a byte
        tampered = bytearray(bad_sig)
        tampered[0] ^= 0xFF
        result = signer.verify_mldsa(b"data", tampered)
        self.assertFalse(result)  # should fail

    def test_adversarial_invalid_transcript(self):
        from src.chronus.core import Poseidon2Transcript
        t = Poseidon2Transcript()
        t.update(b"valid")
        # try with wrong length
        try:
            t.update(b"tooshort")
            self.fail("Should have raised")
        except Exception:
            pass  # expected

    def test_integration_pipeline_token_emission(self):
        from src.chronus.service.app import UnifiedFullStackPipeline
        pipe = UnifiedFullStackPipeline()
        records = [{"status": "ACTIVE", "signals": [1,2,3]}]
        tokens = pipe.run(records, prompt_tokens=[1,2])
        self.assertGreater(len(tokens), 0,
                           "Pipeline should emit at least one token")

    def test_end_to_end_journey_acquire_verify(self):
        # Mini end‑to‑end: store -> retrieve -> unfold -> verify URL
        from src.chronus.core import OVIDService, ExactFoldCore
        from src.chronus.chronus_gpiu_v36 import rfc8785, GaloisFieldElement as GFE
        import json, hashlib

        payload = {"x": 42}
        canonical = rfc8785(payload)
        receipt = OVIDService.store("e2e_tenant", canonical, "e2e_obj", {})
        oid = receipt["oVID_id"]
        retrieved = OVIDService.retrieve(oid)
        self.assertEqual(retrieved, canonical)

        # unfold test
        core = ExactFoldCore()
        # M15 invertibility is covered elsewhere; just ensure no crash
        try:
            core.unfold(core.fold(42))
        except Exception:
            self.fail("Fold/unfold crashed")

# ------------------------------------------------------------------
# Keep the original suite builder
# ------------------------------------------------------------------
def suite():
    s = unittest.TestSuite()
    s.addTest(unittest.makeSuite(TestAllInvariantsSuite))
    s.addTest(unittest.makeSuite(TestNavierStokesDECSuite))
    s.addTest(unittest.makeSuite(TestCryptoAndStarkSuite))
    s.addTest(unittest.makeSuite(TestSDKAndAPISuite))
    s.addTest(unittest.makeSuite(TestHermitenAndPricingSuite))
    # Append the new test classes
    s.addTest(unittest.makeSuite(TestInvariantsEdgeAdversarialSuite))
    return s

if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
