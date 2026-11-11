"""Signed AL HARAS decision receipts: Ed25519 and ML-DSA-87, both required.

Every receipt carries two signatures over the same canonical JSON body:

* Ed25519 (RFC 8032).
* ML-DSA-87 (FIPS 204, NIST security category 5), signed with the FIPS 204
  context string ``RECEIPT_CONTEXT`` so that AL HARAS signatures cannot be
  replayed as signatures for another protocol.

``ReceiptSigner.verify`` accepts a receipt only when both signatures verify, so
a receipt stays unforgeable while either scheme remains secure. Both schemes
come from pyca/cryptography (version 48 or later, built on OpenSSL 3.5 or
later); this module implements neither algorithm itself.

Key custody: each key is generated in process memory at start-up, unless a
32-byte seed is supplied in ``CHRONUS_AL_HARAS_SIGNING_SEED_HEX`` (Ed25519) or
``CHRONUS_AL_HARAS_MLDSA_SEED_HEX`` (ML-DSA-87). Neither option is HSM-backed,
no FIPS 140-3 validated module is claimed, and every receipt states the
custody mode.
"""

import hashlib
import json
import os
import threading
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

SEED_ENV = "CHRONUS_AL_HARAS_SIGNING_SEED_HEX"
MLDSA_SEED_ENV = "CHRONUS_AL_HARAS_MLDSA_SEED_HEX"
RECEIPT_CONTEXT = b"chronus/al-haras/receipt/v1"
HYBRID_ALGORITHM = "Ed25519 + ML-DSA-87 (both must verify)"


def canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _key_id(public_key: bytes) -> str:
    return hashlib.sha256(public_key).hexdigest()[:16]


class ReceiptSigner:
    """Signs receipt bodies with Ed25519 and ML-DSA-87."""

    def __init__(self, seed: Optional[bytes] = None, mldsa_seed: Optional[bytes] = None) -> None:
        if seed is not None:
            if len(seed) != 32:
                raise ValueError("Ed25519 seed must be 32 bytes")
            self._key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
            ed_custody = "environment-supplied seed"
        else:
            self._key = ed25519.Ed25519PrivateKey.generate()
            ed_custody = "process memory, generated at start-up"
        if mldsa_seed is not None:
            if len(mldsa_seed) != 32:
                raise ValueError("ML-DSA-87 seed must be 32 bytes")
            self._pq_key = mldsa.MLDSA87PrivateKey.from_seed_bytes(mldsa_seed)
            pq_custody = "environment-supplied seed"
        else:
            self._pq_key = mldsa.MLDSA87PrivateKey.generate()
            pq_custody = "process memory, generated at start-up"
        self.custody = f"Ed25519: {ed_custody}; ML-DSA-87: {pq_custody} (not HSM-backed)"
        self.public_key = self._key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.key_id = _key_id(self.public_key)
        self.pq_public_key = self._pq_key.public_key().public_bytes_raw()
        self.pq_key_id = _key_id(self.pq_public_key)

    def sign(self, body: Dict[str, Any]) -> Dict[str, Any]:
        message = canonical_json(body)
        pq_signature = self._pq_key.sign(message, RECEIPT_CONTEXT)
        return {
            "algorithm": HYBRID_ALGORITHM,
            "key_id": self.key_id,
            "public_key_hex": self.public_key.hex(),
            "key_custody": self.custody,
            "body_sha256": hashlib.sha256(message).hexdigest(),
            "signature_hex": self._key.sign(message).hex(),
            "post_quantum": {
                "algorithm": "ML-DSA-87",
                "standard": "FIPS 204",
                "context": RECEIPT_CONTEXT.decode("ascii"),
                "key_id": self.pq_key_id,
                "public_key_hex": self.pq_public_key.hex(),
                "public_key_bytes": len(self.pq_public_key),
                "signature_hex": pq_signature.hex(),
                "signature_bytes": len(pq_signature),
            },
        }

    @staticmethod
    def verify_ed25519(body: Dict[str, Any], signature: Dict[str, Any]) -> bool:
        try:
            key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(signature["public_key_hex"]))
            key.verify(bytes.fromhex(signature["signature_hex"]), canonical_json(body))
            return True
        except (InvalidSignature, ValueError, KeyError, TypeError):
            return False

    @staticmethod
    def verify_ml_dsa(body: Dict[str, Any], signature: Dict[str, Any]) -> bool:
        try:
            pq = signature["post_quantum"]
            if pq.get("algorithm") != "ML-DSA-87":
                return False
            key = mldsa.MLDSA87PublicKey.from_public_bytes(bytes.fromhex(pq["public_key_hex"]))
            key.verify(bytes.fromhex(pq["signature_hex"]), canonical_json(body), RECEIPT_CONTEXT)
            return True
        except (InvalidSignature, ValueError, KeyError, TypeError, AttributeError):
            return False

    @classmethod
    def verify(cls, body: Dict[str, Any], signature: Dict[str, Any]) -> bool:
        """True only when both the Ed25519 and the ML-DSA-87 signature verify."""
        return cls.verify_ed25519(body, signature) and cls.verify_ml_dsa(body, signature)


_lock = threading.Lock()
_signer: Optional[ReceiptSigner] = None


def _seed_from_env(name: str) -> Optional[bytes]:
    seed_hex = os.environ.get(name, "").strip()
    return bytes.fromhex(seed_hex) if seed_hex else None


def default_signer() -> ReceiptSigner:
    global _signer
    with _lock:
        if _signer is None:
            _signer = ReceiptSigner(_seed_from_env(SEED_ENV), _seed_from_env(MLDSA_SEED_ENV))
        return _signer


def signed_receipt(body: Dict[str, Any]) -> Dict[str, Any]:
    signer = default_signer()
    return {"body": body, "signature": signer.sign(body)}
