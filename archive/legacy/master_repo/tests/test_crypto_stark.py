import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from chronus.core import MLDSASigner, ZKSTARKVerifier, sign_ed25519, verify_ed25519

class TestCryptoAndStarkSuite(unittest.TestCase):
    def test_mldsa_sign_verify(self):
        msg = "Chronus_MLDSA_Test_Payload_v36"
        key = b"0" * 32
        sig = MLDSASigner.sign_mldsa(key, msg)
        self.assertTrue(sig.startswith("mldsa5_"))
        valid = MLDSASigner.verify_mldsa(key, msg, sig)
        self.assertTrue(valid)

    def test_mldsa_bytes_msg_handling(self):
        msg_bytes = b"Chronus_Bytes_Payload_Check"
        key = b"1" * 32
        sig = MLDSASigner.sign_mldsa(key, msg_bytes)
        valid = MLDSASigner.verify_mldsa(key, msg_bytes, sig)
        self.assertTrue(valid)

    def test_ed25519_fallback(self):
        key = "simple_test_key"
        msg = "test_message"
        sig = sign_ed25519(key, msg)
        self.assertEqual(len(sig), 64)
        valid = verify_ed25519(key, msg, sig)
        self.assertTrue(valid)

    def test_stark_proof_verification(self):
        trace = b"stark_execution_trace_payload_v36"
        proof = ZKSTARKVerifier.generate_stark_proof(trace)
        self.assertEqual(proof["proof_state"], "SIMULATED_STARK_PROOF_VERIFIED")
        self.assertTrue(proof["quotient_valid"])
        valid = ZKSTARKVerifier.verify_stark_proof(proof, proof["air_commitment"])
        self.assertTrue(valid)

if __name__ == "__main__":
    unittest.main()
