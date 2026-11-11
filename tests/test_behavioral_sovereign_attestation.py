"""
Behavioral Test Suite: Sovereign Capability Attestation & Proof of Execution Integrity.
Verifies the 6-pillar DIFC attestation, cryptographic seal integrity, and tamper detection.
"""

import hashlib
import hmac
import json
import os
import sys
import unittest
from decimal import Decimal

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "ci")
for p in (SRC_DIR, REPO_ROOT, SCRIPTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from sovereign_attestation import (
    ATTESTATION_SECRET_KEY,
    verify_al_haras_pillar,
    verify_theseus_ovid_pillar,
    verify_chronus_stratum_pillar,
    verify_millennium_pillar,
    verify_toe_quantum_pillar,
    verify_distribution_packages,
)


class TestBehavioralSovereignAttestation(unittest.TestCase):

    def test_pillar_1_al_haras_qualification(self):
        proof = verify_al_haras_pillar()
        self.assertEqual(proof["status"], "QUALIFIED")
        self.assertTrue(proof["invariants"]["sheaf_global_section_exact"])
        self.assertTrue(proof["invariants"]["sheaf_disagreement_detected_exact"])
        self.assertTrue(proof["invariants"]["reed_solomon_repair_verified"])
        self.assertTrue(proof["invariants"]["ramanujan_spectral_gap"])
        self.assertTrue(proof["invariants"]["anyon_cyclotomic_braid"])
        self.assertTrue(proof["invariants"]["hasse_bound_fingerprint"])
        # The figures are computed on this run, not stored.
        self.assertEqual(proof["measured"]["conflict_coboundary_norm_sq"], "2")
        self.assertGreaterEqual(proof["measured"]["symbol_errors_corrected"], 1)
        self.assertLess(Decimal(proof["measured"]["paley_lambda_2"]), Decimal(proof["measured"]["ramanujan_bound"]))

    def test_pillar_2_theseus_ovid_qualification(self):
        proof = verify_theseus_ovid_pillar()
        self.assertEqual(proof["status"], "QUALIFIED")
        self.assertTrue(proof["invariants"]["theseus_lossless_roundtrip"])
        self.assertTrue(proof["invariants"]["ovid_content_addressed_retrieval"])

    def test_pillar_3_chronus_stratum_qualification(self):
        proof = verify_chronus_stratum_pillar()
        self.assertEqual(proof["status"], "QUALIFIED")
        self.assertTrue(proof["invariants"]["f257_galois_phases"])
        self.assertTrue(proof["invariants"]["zeckendorf_conservation"])
        self.assertTrue(proof["invariants"]["binet_lucas_symbolic_exactness"])
        self.assertTrue(proof["invariants"]["endian_swapped_roundtrip"])

    def test_pillar_4_millennium_qualification(self):
        proof = verify_millennium_pillar()
        self.assertEqual(proof["status"], "QUALIFIED")
        self.assertEqual(
            set(proof["exact_checks_passed"]),
            {
                "ollivier_ricci_curvature_certified",
                "hodge_decomposition_identities",
                "p_adic_address_sets_disjoint",
                "buffer_zeroised_and_read_back",
            },
        )
        for check, status in proof["exact_checks_passed"].items():
            self.assertTrue(status, f"Exact check {check} failed")
        self.assertEqual(proof["not_implemented"], {"picard_lefschetz_anti_jamming": "NOT_IMPLEMENTED"})

    def test_pillar_5_toe_quantum_qualification(self):
        proof = verify_toe_quantum_pillar()
        self.assertEqual(proof["status"], "QUALIFIED")
        self.assertTrue(proof["invariants"]["f257_bell_state_evolution"])
        self.assertTrue(proof["invariants"]["exact_field_hadamard"])

    def test_pillar_6_distribution_packages_qualification(self):
        proof = verify_distribution_packages()
        self.assertIn(proof["status"], ("BUILT", "PENDING_BUILD"))
        if proof["status"] == "BUILT":
            self.assertGreaterEqual(proof["package_count"], 2)
        self.assertIn("chronus.security.al_haras", proof["contained_modules"])
        self.assertIn("chronus.storage.theseus", proof["contained_modules"])
        self.assertIn("chronus.security.ovid", proof["contained_modules"])
        self.assertIn("chronus.stratum", proof["contained_modules"])

    def test_attestation_file_tamper_evidence(self):
        attestation_path = os.path.join(REPO_ROOT, "SOVEREIGN_CAPABILITY_ATTESTATION.json")
        self.assertTrue(os.path.exists(attestation_path), "Attestation file missing.")

        with open(attestation_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        seal = data.get("cryptographic_attestation", {})
        original_digest = seal.get("hmac_digest")
        self.assertIsNotNone(original_digest)

        # Re-compute HMAC over payload without cryptographic_attestation key
        dossier_copy = dict(data)
        dossier_copy.pop("cryptographic_attestation", None)
        payload_bytes = json.dumps(dossier_copy, sort_keys=True, indent=2).encode("utf-8")
        computed_hmac = hmac.new(ATTESTATION_SECRET_KEY, payload_bytes, hashlib.sha256).hexdigest()

        self.assertEqual(computed_hmac, original_digest, "HMAC signature mismatch: attestation has been altered.")

        # Tamper check: modifying any single character in payload must break HMAC
        tampered_bytes = payload_bytes.replace(b"SOVEREIGN_QUALIFIED", b"COMPROMISED_STATUS_")
        tampered_hmac = hmac.new(ATTESTATION_SECRET_KEY, tampered_bytes, hashlib.sha256).hexdigest()
        self.assertNotEqual(tampered_hmac, original_digest, "Tamper evidence failure: modified data produced same HMAC.")


if __name__ == "__main__":
    unittest.main()

