"""AL HARAS receipts: Ed25519 and ML-DSA-87 (FIPS 204), both required.

The ML-DSA-87 checks are computed, not asserted from labels:

* key and signature sizes are measured and compared with FIPS 204, Table 2;
* the message representative mu is recomputed here from the FIPS 204
  equations (tr = H(pk, 64); M' = 0 || |ctx| || ctx || M; mu = H(tr || M', 64))
  and the receipt signature must verify against that mu, while the same mu
  without the AL HARAS context must not;
* forged, stripped, swapped and tampered receipts are rejected.
"""

import hashlib

import pytest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import mldsa

from chronus.security.al_haras.autonomous_roe import AutonomousROEValidator, EngagementSimplex, ROECriterion
from chronus.security.al_haras.receipts import (
    HYBRID_ALGORITHM,
    RECEIPT_CONTEXT,
    ReceiptSigner,
    canonical_json,
    signed_receipt,
)

# FIPS 204, Table 2: ML-DSA-87 public key and signature sizes in bytes.
FIPS_204_ML_DSA_87_PUBLIC_KEY_BYTES = 2592
FIPS_204_ML_DSA_87_SIGNATURE_BYTES = 4627

BODY = {"decision": "ADMIT", "tenant": "tenant-a", "payload_sha256": hashlib.sha256(b"workload").hexdigest()}


def _mu(public_key: bytes, message: bytes, context: bytes) -> bytes:
    """FIPS 204 message representative for pure ML-DSA, computed independently of the library."""
    tr = hashlib.shake_256(public_key).digest(64)
    m_prime = bytes([0, len(context)]) + context + message
    return hashlib.shake_256(tr + m_prime).digest(64)


class TestHybridReceipt:
    def test_both_signatures_verify_and_sizes_match_fips_204(self):
        receipt = signed_receipt(BODY)
        signature = receipt["signature"]
        pq = signature["post_quantum"]
        assert signature["algorithm"] == HYBRID_ALGORITHM
        assert pq["algorithm"] == "ML-DSA-87" and pq["standard"] == "FIPS 204"
        assert len(bytes.fromhex(pq["public_key_hex"])) == pq["public_key_bytes"] == FIPS_204_ML_DSA_87_PUBLIC_KEY_BYTES
        assert len(bytes.fromhex(pq["signature_hex"])) == pq["signature_bytes"] == FIPS_204_ML_DSA_87_SIGNATURE_BYTES
        assert ReceiptSigner.verify_ed25519(receipt["body"], signature) is True
        assert ReceiptSigner.verify_ml_dsa(receipt["body"], signature) is True
        assert ReceiptSigner.verify(receipt["body"], signature) is True
        assert signature["body_sha256"] == hashlib.sha256(canonical_json(BODY)).hexdigest()

    def test_signature_matches_the_fips_204_message_representative(self):
        signer = ReceiptSigner(seed=bytes(range(32)), mldsa_seed=bytes(range(32, 64)))
        signature = signer.sign(BODY)
        pq = signature["post_quantum"]
        public_key = bytes.fromhex(pq["public_key_hex"])
        key = mldsa.MLDSA87PublicKey.from_public_bytes(public_key)
        message = canonical_json(BODY)
        sig = bytes.fromhex(pq["signature_hex"])
        key.verify_mu(sig, _mu(public_key, message, RECEIPT_CONTEXT))
        with pytest.raises(InvalidSignature):
            key.verify_mu(sig, _mu(public_key, message, b""))
        with pytest.raises(InvalidSignature):
            key.verify(sig, message)  # no context: a different FIPS 204 message

    def test_each_tampering_is_rejected(self):
        receipt = signed_receipt(BODY)
        body, signature = receipt["body"], receipt["signature"]
        altered = dict(body, decision="REJECT")
        assert ReceiptSigner.verify_ed25519(altered, signature) is False
        assert ReceiptSigner.verify_ml_dsa(altered, signature) is False
        assert ReceiptSigner.verify(altered, signature) is False

        stripped = {k: v for k, v in signature.items() if k != "post_quantum"}
        assert ReceiptSigner.verify_ed25519(body, stripped) is True
        assert ReceiptSigner.verify(body, stripped) is False

        flipped = bytearray(bytes.fromhex(signature["post_quantum"]["signature_hex"]))
        flipped[100] ^= 0x01
        bad_pq = dict(signature, post_quantum=dict(signature["post_quantum"], signature_hex=bytes(flipped).hex()))
        assert ReceiptSigner.verify(body, bad_pq) is False

        bad_ed = dict(signature, signature_hex=("00" * 64))
        assert ReceiptSigner.verify(body, bad_ed) is False

        wrong_algorithm = dict(signature, post_quantum=dict(signature["post_quantum"], algorithm="ML-DSA-65"))
        assert ReceiptSigner.verify(body, wrong_algorithm) is False

    def test_signing_is_hedged_and_keys_follow_their_seeds(self):
        a = ReceiptSigner(seed=bytes(32), mldsa_seed=bytes(range(32)))
        b = ReceiptSigner(seed=bytes(32), mldsa_seed=bytes(range(32)))
        c = ReceiptSigner(seed=bytes(32), mldsa_seed=bytes(range(1, 33)))
        assert a.pq_public_key == b.pq_public_key and a.public_key == b.public_key
        assert a.pq_public_key != c.pq_public_key
        first, second = a.sign(BODY), a.sign(BODY)
        assert first["post_quantum"]["signature_hex"] != second["post_quantum"]["signature_hex"]
        assert ReceiptSigner.verify(BODY, first) and ReceiptSigner.verify(BODY, second)
        with pytest.raises(ValueError):
            ReceiptSigner(mldsa_seed=bytes(31))
        with pytest.raises(ValueError):
            ReceiptSigner(seed=bytes(33))

    def test_custody_is_stated_for_both_keys(self):
        custody = signed_receipt(BODY)["signature"]["key_custody"]
        assert "Ed25519" in custody and "ML-DSA-87" in custody and "not HSM-backed" in custody


class TestPinnedReviewRecords:
    def _record(self):
        criteria = list(ROECriterion)
        request = EngagementSimplex(
            request_id="REQ-PQ-1",
            subject_commitment=hashlib.sha256(b"subject").hexdigest(),
            approvals={c: f"reviewer-{i}" for i, c in enumerate(criteria)},
            risk_score=10,
            risk_ceiling=25,
        )
        return AutonomousROEValidator().check_policy_completeness(request)["review_record"]

    def test_a_substituted_ml_dsa_key_is_rejected_even_with_valid_signatures(self):
        record = self._record()
        assert AutonomousROEValidator.verify_review_record(record) is True
        body, signature = record["body"], record["signature"]
        attacker = ReceiptSigner(mldsa_seed=bytes(range(32)))
        attacker_pq = attacker.sign(body)["post_quantum"]
        swapped = dict(signature, post_quantum=attacker_pq)
        # Both signatures are individually valid ...
        assert ReceiptSigner.verify(body, swapped) is True
        # ... but the ML-DSA-87 key is not the trusted one, so the record is rejected.
        assert AutonomousROEValidator.verify_review_record({"body": body, "signature": swapped}) is False
