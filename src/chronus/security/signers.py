"""Ed25519 receipt signing and an explicit unavailable ML-DSA interface."""

from typing import Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


class MLDSASigner:
    """Unavailable ML-DSA interface; no conformant implementation is bundled."""

    def __init__(self, security_level: int = 3) -> None:
        """Initialize ML-DSA signer.

        Args:
            security_level: Security level (2, 3, or 5 for ML-DSA-44/65/87).
        """
        if security_level not in (2, 3, 5):
            raise ValueError("security_level must be 2, 3, or 5")
        self.security_level = security_level
        self._algorithm = "ML-DSA-UNAVAILABLE"
        self._fips_standard = "FIPS 204 (not implemented)"

    def sign(self, message: bytes) -> str:
        raise NotImplementedError("A conformant ML-DSA provider is not configured")

    def verify(self, message: bytes, signature: str) -> bool:
        """Verify an ML-DSA signature.

        Args:
            message: Original message bytes.
            signature: Hex-encoded signature to verify.

        Returns:
            True if signature is valid, False otherwise.
        """
        return False

    def get_public_key(self) -> Optional[str]:
        """Get the hex-encoded public key."""
        return None

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