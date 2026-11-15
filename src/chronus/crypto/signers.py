"""Dual-signature providers. Unsupported ML-DSA fails closed."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
try:
    from cryptography.hazmat.primitives.asymmetric import ml_dsa
except ImportError:
    ml_dsa = None

ML_DSA_65_PK_SIZE = 1952
ML_DSA_65_SIG_SIZE = 3309

class SignerUnavailable(RuntimeError):
    pass

@runtime_checkable
class Signer(Protocol):
    algorithm: str
    key_id: str
    def sign(self, message: bytes) -> bytes: ...
    def public_bytes(self) -> bytes: ...

@dataclass(frozen=True)
class Ed25519Signer:
    algorithm: str
    key_id: str
    _key: ed25519.Ed25519PrivateKey

    @classmethod
    def generate(cls, key_id: str) -> "Ed25519Signer":
        return cls("Ed25519", key_id, ed25519.Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, key_id: str, raw: bytes) -> "Ed25519Signer":
        return cls("Ed25519", key_id, ed25519.Ed25519PrivateKey.from_private_bytes(raw))

    def sign(self, message: bytes) -> bytes:
        return self._key.sign(message)

    def public_bytes(self) -> bytes:
        return self._key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)

@dataclass(frozen=True)
class MlDsa65Signer:
    algorithm: str
    key_id: str
    _key: object

    @classmethod
    def generate(cls, key_id: str) -> "MlDsa65Signer":
        if ml_dsa is None:
            raise SignerUnavailable("ML-DSA-65 unavailable in this cryptography/OpenSSL stack")
        return cls("ML-DSA-65", key_id, ml_dsa.MLDSA65PrivateKey.generate())

    def sign(self, message: bytes) -> bytes:
        return self._key.sign(message)

    def public_bytes(self) -> bytes:
        return self._key.public_key().public_bytes_raw()

def ml_dsa_available() -> bool:
    return ml_dsa is not None

def verify(algorithm: str, public_bytes: bytes, message: bytes, signature: bytes) -> None:
    if algorithm == "Ed25519":
        ed25519.Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, message)
        return
    if algorithm == "ML-DSA-65":
        if ml_dsa is None:
            raise SignerUnavailable("ML-DSA-65 unavailable")
        ml_dsa.MLDSA65PublicKey.from_public_bytes(public_bytes).verify(signature, message)
        return
    raise ValueError("unknown algorithm")

@dataclass(frozen=True)
class DualSigner:
    inner: Ed25519Signer
    outer: MlDsa65Signer

    @property
    def key_id(self) -> str:
        return self.inner.key_id + "+" + self.outer.key_id

    def sign(self, message: bytes) -> dict[str, bytes]:
        inner_signature = self.inner.sign(message)
        envelope = hashlib.sha256(b"CHRONUS-V2-OUTER-v1\0" + message + inner_signature).digest()
        return {"Ed25519": inner_signature, "ML-DSA-65": self.outer.sign(envelope)}

    def verify_all(self, message: bytes, signatures: dict[str, bytes]) -> None:
        verify("Ed25519", self.inner.public_bytes(), message, signatures["Ed25519"])
        envelope = hashlib.sha256(b"CHRONUS-V2-OUTER-v1\0" + message + signatures["Ed25519"]).digest()
        verify("ML-DSA-65", self.outer.public_bytes(), envelope, signatures["ML-DSA-65"])
