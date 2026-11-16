"""NIST FIPS 204 ML-DSA signature wrapper and Ed25519 signer.

ML-DSA operations are delegated to the maintained ``cryptography`` implementation
(OpenSSL backend). Key material is the 32-byte FIPS 204 seed; public-only
verifiers can be constructed from the published public key alone.
"""

import secrets
from typing import Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


# Security level -> (private key class name, public key class name, algorithm name)
ML_DSA_CLASSES = {
    2: ("MLDSA44PrivateKey", "MLDSA44PublicKey", "ML-DSA-44"),
    3: ("MLDSA65PrivateKey", "MLDSA65PublicKey", "ML-DSA-65"),
    5: ("MLDSA87PrivateKey", "MLDSA87PublicKey", "ML-DSA-87"),
}


class MLDSASigner:
    """NIST FIPS 204 ML-DSA signature provider (ML-DSA-44/65/87)."""

    def __init__(
        self,
        security_level: int = 3,
        public_key: Optional[bytes] = None,
        private_key: Optional[bytes] = None,
    ) -> None:
        """Initialize ML-DSA signer.

        Args:
            security_level: Security level (2, 3, or 5 for ML-DSA-44/65/87).
            public_key: Optional raw public key bytes (verification only).
            private_key: Optional 32-byte FIPS 204 seed for signing.
                If a public key is also supplied it must match the seed.
        """
        if security_level not in ML_DSA_CLASSES:
            raise ValueError("security_level must be 2, 3, or 5")
        self.security_level = security_level
        priv_name, pub_name, self._algorithm = ML_DSA_CLASSES[security_level]
        self._priv_cls = getattr(mldsa, priv_name)
        self._pub_cls = getattr(mldsa, pub_name)
        self._fips_standard = "NIST FIPS 204"
        self._seed: Optional[bytes] = None
        self._private: Optional[object] = None
        self._public: Optional[object] = None

        if private_key is not None:
            seed = bytes(private_key)
            self._private = self._priv_cls.from_seed_bytes(seed)
            self._seed = seed
            derived = self._private.public_key()
            if public_key is not None and bytes(public_key) != derived.public_bytes_raw():
                raise ValueError("public key does not match private key")
            self._public = derived
        elif public_key is not None:
            self._public = self._pub_cls.from_public_bytes(bytes(public_key))
        else:
            self._generate_keypair()

    def generate_keypair(self) -> Tuple[str, str]:
        """Generate and store a new keypair, returning (public_key_hex, private_key_hex)."""
        self._generate_keypair()
        return (self._public.public_bytes_raw().hex(), self._seed.hex())

    def _generate_keypair(self) -> None:
        """Generate a fresh FIPS 204 ML-DSA keypair from a CSPRNG seed."""
        seed = secrets.token_bytes(32)
        self._seed = seed
        self._private = self._priv_cls.from_seed_bytes(seed)
        self._public = self._private.public_key()

    def sign(self, message: bytes) -> str:
        """Sign a message using NIST FIPS 204 ML-DSA.

        Args:
            message: Raw message bytes to sign.

        Returns:
            Hex-encoded signature string.
        """
        if self._private is None:
            raise ValueError("ML-DSA private key not initialized")
        return self._private.sign(message).hex()

    def verify(self, message: bytes, signature: str) -> bool:
        """Verify an ML-DSA signature against the public key.

        Args:
            message: Original message bytes.
            signature: Hex-encoded signature.

        Returns:
            True if signature is valid, False otherwise.
        """
        if self._public is None:
            return False

        try:
            sig_bytes = bytes.fromhex(signature)
            self._public.verify(sig_bytes, message)
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False

    def get_public_key(self) -> Optional[str]:
        """Get the hex-encoded public key."""
        if self._public is None:
            return None
        return self._public.public_bytes_raw().hex()

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def fips_standard(self) -> str:
        return self._fips_standard


class Ed25519Signer:
    """Ed25519 Digital Signature Signer.

    Implements Edwards-curve Digital Signature Algorithm (Ed25519)
    for high-performance classical digital signatures.
    """

    def __init__(self) -> None:
        """Initialize Ed25519 signer."""
        self._algorithm = "Ed25519"
        self._private_key: Optional[ed25519.Ed25519PrivateKey] = None
        self._public_key: Optional[ed25519.Ed25519PublicKey] = None
        self._generate_keypair()

    def _generate_keypair(self) -> None:
        """Generate Ed25519 key pair."""
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    def sign(self, message: bytes) -> str:
        """Sign a message using Ed25519.

        Args:
            message: Message bytes to sign.

        Returns:
            Hex-encoded Ed25519 signature.
        """
        if self._private_key is None:
            raise ValueError("Ed25519 private key not initialized")

        signature = self._private_key.sign(message)
        return signature.hex()

    def verify(self, message: bytes, signature: str) -> bool:
        """Verify an Ed25519 signature.

        Args:
            message: Original message bytes.
            signature: Hex-encoded signature to verify.

        Returns:
            True if signature is valid, False otherwise.
        """
        if self._public_key is None:
            return False

        try:
            sig_bytes = bytes.fromhex(signature)
            self._public_key.verify(sig_bytes, message)
            return True
        except (InvalidSignature, ValueError):
            return False

    def self_test(self) -> tuple[bool, str]:
        """Exercise a round-trip and explicit tamper rejection."""
        message = b"chronus-self-test"
        signature = self.sign(message)
        if not self.verify(message, signature):
            return False, "signature verification failed"
        if self.verify(message + b"!", signature):
            return False, "tampered message accepted"
        return True, "Ed25519 round-trip and tamper rejection pass"

    def get_public_key(self) -> Optional[str]:
        """Get the hex-encoded public key."""
        if self._public_key is None:
            return None
        return self._public_key.public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        ).hex()

    @property
    def algorithm(self) -> str:
        return self._algorithm


class PostQuantumError(Exception):
    """Base exception for post-quantum cryptographic operations."""

    pass


class VerificationError(PostQuantumError):
    """Exception for signature verification failures."""

    pass


class MlDsaSigner:
    """Legacy fail-closed placeholder; no conformant implementation is exposed.

    Retained only so old imports fail closed instead of silently changing
    algorithm semantics.
    """

    conformant = False
    key_id = "ml-dsa-65:unavailable"

    def sign(self, message: bytes) -> bytes:
        raise NotImplementedError("ML-DSA-65 not implemented")

    def verify(self, message: bytes, signature: bytes) -> bool:
        raise NotImplementedError("ML-DSA-65 not implemented")
