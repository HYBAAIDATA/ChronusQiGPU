"""NIST FIPS 204 ML-DSA (Dilithium) signature wrapper and Ed25519 signer.

Provider-backed signing without custom cryptographic fallbacks.
FIPS module validation and hardware key custody are separate deployment gates.
"""

from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


# =============================================================================
# NIST FIPS 204 ML-DSA (CRYSTALS-Dilithium) Lattice Engine
# Modulus q = 8380417 = 2^23 - 2^13 + 1, Degree n = 256
# =============================================================================

ML_DSA_Q = 8380417
ML_DSA_N = 256

# Parameters for ML-DSA-44, ML-DSA-65, ML-DSA-87
ML_DSA_PARAMS = {
    2: {
        "k": 4,
        "l": 4,
        "gamma1": 1 << 17,
        "gamma2": (ML_DSA_Q - 1) // 88,
        "name": "ML-DSA-44",
    },
    3: {
        "k": 6,
        "l": 5,
        "gamma1": 1 << 19,
        "gamma2": (ML_DSA_Q - 1) // 32,
        "name": "ML-DSA-65",
    },
    5: {
        "k": 8,
        "l": 7,
        "gamma1": 1 << 19,
        "gamma2": (ML_DSA_Q - 1) // 32,
        "name": "ML-DSA-87",
    },
}


class MLDSASigner:
    """Compatibility API backed by cryptography/OpenSSL ML-DSA.

    Algorithm support does not assert FIPS module validation or HSM custody.
    Historical 192-byte placeholder signatures/keys are intentionally rejected.
    """
    def __init__(self, security_level=3, public_key=None, private_key=None):
        from cryptography.hazmat.primitives.asymmetric import mldsa
        if security_level not in (2, 3, 5):
            raise ValueError("security_level must be 2, 3, or 5")
        self.security_level = security_level
        self.params = ML_DSA_PARAMS[security_level]
        self._algorithm = self.params["name"]
        self._fips_standard = "NIST FIPS 204"
        self._key_type = {2: mldsa.MLDSA44PrivateKey, 3: mldsa.MLDSA65PrivateKey,
                          5: mldsa.MLDSA87PrivateKey}[security_level]
        self._public_type = {2: mldsa.MLDSA44PublicKey, 3: mldsa.MLDSA65PublicKey,
                             5: mldsa.MLDSA87PublicKey}[security_level]
        self._signing_key = None
        if private_key is not None:
            self._signing_key = self._key_type.from_seed_bytes(private_key)
            derived = self._signing_key.public_key().public_bytes_raw()
            if public_key is not None and public_key != derived:
                raise ValueError("ML-DSA public/private keys do not match")
            public_key = derived
        elif public_key is None:
            self._signing_key = self._key_type.generate()
            public_key = self._signing_key.public_key().public_bytes_raw()
        self._verification_key = self._public_type.from_public_bytes(public_key)
        self._public_key = public_key
        self._private_key = self._signing_key.private_bytes_raw() if self._signing_key else None

    def generate_keypair(self):
        self._signing_key = self._key_type.generate()
        self._verification_key = self._signing_key.public_key()
        self._public_key = self._verification_key.public_bytes_raw()
        self._private_key = self._signing_key.private_bytes_raw()
        return self._public_key.hex(), self._private_key.hex()

    def sign(self, message: bytes) -> str:
        if self._signing_key is None or self._private_key is None:
            raise ValueError("ML-DSA keys not initialized")
        return self._signing_key.sign(message).hex()

    def verify(self, message: bytes, signature: str) -> bool:
        if self._public_key is None:
            return False
        try:
            self._verification_key.verify(bytes.fromhex(signature), message)
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False

    def get_public_key(self):
        return self._public_key.hex() if self._public_key is not None else None

    @property
    def algorithm(self):
        return self._algorithm

    @property
    def fips_standard(self):
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

