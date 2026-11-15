"""Ed25519 via maintained cryptography primitives; ML-DSA unavailable."""
from __future__ import annotations
import hashlib
import secrets
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

class Ed25519Signer:
    conformant = True

    def __init__(self, seed: bytes | None = None):
        if seed is None:
            seed = secrets.token_bytes(32)
        if len(seed) != 32:
            raise ValueError("seed must be 32 bytes")
        self._key = Ed25519PrivateKey.from_private_bytes(seed)
        self.public_key = self._key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        self.key_id = "ed25519:" + hashlib.sha256(self.public_key).hexdigest()[:16]

    def sign(self, message: bytes) -> bytes:
        return self._key.sign(message)

    @staticmethod
    def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
        if len(signature) != 64 or len(public_key) != 32:
            return False
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
            return True
        except (InvalidSignature, ValueError):
            return False

    def self_test(self) -> tuple[bool, str]:
        message = b"chronus-self-test"
        signature = self.sign(message)
        if not self.verify(message, signature, self.public_key):
            return False, "signature verification failed"
        if self.verify(message + b"!", signature, self.public_key):
            return False, "tampered message accepted"
        return True, "Ed25519 round-trip and tamper rejection pass"

class MlDsaSigner:
    conformant = False
    key_id = "ml-dsa-65:unavailable"

    def sign(self, message: bytes) -> bytes:
        raise NotImplementedError("ML-DSA-65 not implemented")

    def verify(self, message: bytes, signature: bytes) -> bool:
        raise NotImplementedError("ML-DSA-65 not implemented")
