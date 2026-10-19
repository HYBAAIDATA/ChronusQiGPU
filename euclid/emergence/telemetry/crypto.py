"""Cryptographic key management and detached signing for agent telemetry."""

from __future__ import annotations
import hashlib
import hmac
import time
from typing import Optional, Dict

from cryptography.hazmat.primitives.asymmetric import ed25519

from ..models.telemetry import TelemetryRecord, TelemetrySignatureInfo


class TelemetryKeyManager:
    """Key management service providing Ed25519 signing and verification.
    
    Provides key rotation, signer identity binding, detached signature generation,
    and verification APIs.
    """

    def __init__(self) -> None:
        self._private_keys: Dict[str, ed25519.Ed25519PrivateKey] = {}
        self._public_keys: Dict[str, ed25519.Ed25519PublicKey] = {}
        self._key_metadata: Dict[str, dict] = {}
        self._active_key_ids: Dict[str, str] = {}  # signer_identity -> key_id

    def generate_key_for_signer(self, signer_identity: str, key_id: Optional[str] = None) -> str:
        """Generate a new Ed25519 key pair for a given signer identity."""
        if not isinstance(signer_identity, str) or not signer_identity.strip():
            raise ValueError("non-empty signer identity is required")
        if key_id is not None and (not key_id or key_id in self._key_metadata):
            raise ValueError("key identifier must be non-empty and unique")
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        kid = key_id or f"key_{signer_identity}_{int(time.time())}_{len(self._private_keys)}"
        self._private_keys[kid] = private_key
        self._public_keys[kid] = public_key
        self._key_metadata[kid] = {
            "signer_identity": signer_identity,
            "created_at": time.time(),
            "algorithm": "Ed25519",
            "revoked": False,
        }
        self._active_key_ids[signer_identity] = kid
        return kid

    def rotate_key(self, signer_identity: str) -> str:
        """Rotate key for signer identity, maintaining previous public keys for verification."""
        return self.generate_key_for_signer(signer_identity)

    def revoke_key(self, key_id: str) -> None:
        """Revoke a compromised key."""
        if key_id in self._key_metadata:
            self._key_metadata[key_id]["revoked"] = True

    def get_active_key_id(self, signer_identity: str) -> str:
        if signer_identity not in self._active_key_ids:
            return self.generate_key_for_signer(signer_identity)
        return self._active_key_ids[signer_identity]

    def sign_record(
        self,
        record: TelemetryRecord,
        signer_identity: str,
        key_id: Optional[str] = None,
    ) -> TelemetrySignatureInfo:
        """Produce detached cryptographic signature over canonical telemetry record."""
        kid = key_id or self.get_active_key_id(signer_identity)
        if kid not in self._private_keys:
            raise ValueError(f"Private key for {kid} not found")
        if self._key_metadata[kid].get("revoked", False):
            raise PermissionError(f"Key {kid} is revoked")

        if self._key_metadata[kid]["signer_identity"] != signer_identity:
            raise PermissionError("key is not owned by the requested signer identity")

        canonical_bytes = record.canonical_json().encode("utf-8")
        payload_digest = hashlib.sha256(canonical_bytes).hexdigest()

        private_key = self._private_keys[kid]
        signature_bytes = private_key.sign(canonical_bytes)
        signature_hex = signature_bytes.hex()

        return TelemetrySignatureInfo(
            key_id=kid,
            signer_identity=signer_identity,
            signature_hex=signature_hex,
            algorithm="Ed25519",
            timestamp=time.time(),
            payload_digest=payload_digest,
        )

    def verify_signature(
        self,
        record: TelemetryRecord,
        signature_info: TelemetrySignatureInfo,
    ) -> bool:
        """Verify detached signature against canonical telemetry record."""
        kid = signature_info.key_id
        if kid not in self._public_keys:
            return False
        if self._key_metadata[kid].get("revoked", False):
            return False

        metadata = self._key_metadata[kid]
        if (signature_info.signer_identity != metadata["signer_identity"]
                or signature_info.algorithm != metadata["algorithm"]):
            return False

        # Verify digest first
        canonical_bytes = record.canonical_json().encode("utf-8")
        expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
        if not hmac.compare_digest(expected_digest, signature_info.payload_digest):
            return False

        # Verify Ed25519 asymmetric signature
        public_key = self._public_keys[kid]
        try:
            signature_bytes = bytes.fromhex(signature_info.signature_hex)
            public_key.verify(signature_bytes, canonical_bytes)
            return True
        except Exception:
            return False
