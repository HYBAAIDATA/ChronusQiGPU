"""Unit and integration tests for Cryptographic Proof & Verifier Engines.

Tests:
- NIST FIPS 204 ML-DSA (CRYSTALS-Dilithium) signer and verifier
- ZKSTARKVerifier executable FRI-based polynomial quotient verifier
- AIR constraint evaluation, vanishing polynomial Z_H(x), and Merkle tree proofs
- Tamper detection and proof validation round-trips
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from chronus.security.signers import ML_DSA_PARAMS, ML_DSA_Q, MLDSASigner
from chronus.security.stark import (
    MODULUS,
    ZKSTARKVerifier,
    _merkle_path,
    _merkle_root,
    _mod_inv,
)


class TestMLDSASigner(unittest.TestCase):
    """Test NIST FIPS 204 ML-DSA lattice signature implementation."""

    def test_security_levels_initialization(self):
        """Verify initialization across supported security levels."""
        for level in (2, 3, 5):
            signer = MLDSASigner(security_level=level)
            self.assertEqual(signer.security_level, level)
            self.assertIn("ML-DSA", signer.algorithm)
            self.assertEqual(signer.fips_standard, "NIST FIPS 204")
            self.assertIsNotNone(signer.get_public_key())

        with self.assertRaises(ValueError):
            MLDSASigner(security_level=1)

    def test_sign_and_verify_roundtrip(self):
        """Test standard signing and verification cycle."""
        signer = MLDSASigner(security_level=3)
        message = b"Production transaction payload hash"
        signature = signer.sign(message)

        # Signature must be valid hex and 192 bytes (384 hex characters)
        self.assertEqual(len(bytes.fromhex(signature)), 192)
        self.assertTrue(signer.verify(message, signature))

    def test_tamper_detection(self):
        """Verify tampering with message or signature fails verification."""
        signer = MLDSASigner(security_level=3)
        message = b"Genuine execution payload"
        signature = signer.sign(message)

        # Tampered message
        tampered_msg = b"Tampered execution payload"
        self.assertFalse(signer.verify(tampered_msg, signature))

        # Tampered signature byte
        sig_bytes = bytearray(bytes.fromhex(signature))
        sig_bytes[10] ^= 0xFF
        tampered_sig = sig_bytes.hex()
        self.assertFalse(signer.verify(message, tampered_sig))

        # Malformed signature length
        self.assertFalse(signer.verify(message, "deadbeef"))
        self.assertFalse(signer.verify(message, "invalid_non_hex"))

    def test_explicit_keypair_injection(self):
        """Test constructing MLDSASigner with explicit keypair."""
        signer1 = MLDSASigner(security_level=2)
        pk_hex, sk_hex = signer1.generate_keypair()

        signer2 = MLDSASigner(
            security_level=2,
            public_key=bytes.fromhex(pk_hex),
            private_key=bytes.fromhex(sk_hex),
        )
        msg = b"Injected keypair verification"
        sig = signer2.sign(msg)
        self.assertTrue(signer1.verify(msg, sig))
        self.assertTrue(signer2.verify(msg, sig))


class TestZKSTARKVerifier(unittest.TestCase):
    """Test FRI-based ZK-STARK polynomial quotient verifier."""

    def test_prime_field_inversion(self):
        """Test finite field arithmetic modulo p = 2013265921."""
        self.assertEqual((17 * _mod_inv(17, MODULUS)) % MODULUS, 1)
        self.assertEqual((12345678 * _mod_inv(12345678, MODULUS)) % MODULUS, 1)

    def test_merkle_tree_construction_and_path(self):
        """Test Merkle tree root and authentication path generation."""
        leaves = [f"leaf_{i}".encode("utf-8") for i in range(8)]
        root = _merkle_root(leaves)
        self.assertIsInstance(root, str)
        self.assertEqual(len(root), 64)

        # Path for leaf 0
        path = _merkle_path(leaves, 0)
        self.assertEqual(len(path), 3)  # log2(8) = 3 levels

    def test_proof_generation_and_verification(self):
        """Test generating and successfully verifying an AIR STARK proof."""
        verifier = ZKSTARKVerifier(security_level=128)
        trace_steps = [1, 2, 3, 4, 5, 6, 7, 8]
        proof = verifier.generate_proof(trace_steps)

        self.assertIn("trace_commitment", proof)
        self.assertIn("quotient_commitment", proof)
        self.assertIn("fri_layers", proof)

        # Verifier confirms proof
        self.assertTrue(verifier.verify_proof(proof))

        # Verifier checks public input boundary
        self.assertTrue(verifier.verify_proof(proof, public_input={"start": 1, "end": 8}))
        self.assertFalse(verifier.verify_proof(proof, public_input={"start": 99, "end": 8}))

    def test_proof_rejection_on_tampering(self):
        """Test that invalid or tampered STARK proofs are rejected."""
        verifier = ZKSTARKVerifier()
        trace_steps = [1, 2, 3, 4, 5, 6, 7, 8]
        proof = verifier.generate_proof(trace_steps)

        # 1. Tampered trace commitment
        tampered_proof_1 = dict(proof)
        tampered_proof_1["trace_commitment"] = "00" * 32
        self.assertFalse(verifier.verify_proof(tampered_proof_1))

        # 2. Tampered quotient root
        tampered_proof_2 = dict(proof)
        tampered_proof_2["quotient_commitment"] = "ff" * 32
        self.assertFalse(verifier.verify_proof(tampered_proof_2))

        # 3. Corrupted query evaluation
        tampered_proof_3 = dict(proof)
        bad_queries = [dict(q) for q in proof["queries"]]
        if bad_queries:
            bad_queries[0]["p_eval"] = (bad_queries[0]["p_eval"] + 1) % MODULUS
            tampered_proof_3["queries"] = bad_queries
            self.assertFalse(verifier.verify_proof(tampered_proof_3))

        # 4. Empty / malformed proof dict
        self.assertFalse(verifier.verify_proof({}))
        self.assertFalse(verifier.verify_proof(None))


if __name__ == "__main__":
    unittest.main()
