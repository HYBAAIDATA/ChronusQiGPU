"""Production signature adapters.

Ed25519 and ML-DSA use pyca/cryptography. If the installed cryptographic
backend cannot provide an algorithm, construction fails closed; no HMAC or
SHAKE-based substitute is used.
"""

from __future__ import annotations

from typing import Optional

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa


class Ed25519Signer:
    """Ed25519 signing and verification using pyca/cryptography."""

    algorithm = "Ed25519"
    standard = "RFC 8032"

    def __init__(
        self,
        public_key: Optional[bytes] = None,
        private_key: Optional[bytes] = None,
    ):
        if private_key is None and public_key is None:
            private_obj = ed25519.Ed25519PrivateKey.generate()
            self._private_key = private_obj.private_bytes_raw()
            self._public_key = private_obj.public_key().public_bytes_raw()
            self._private_obj = private_obj
        elif private_key is not None:
            private_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
            derived_public = private_obj.public_key().public_bytes_raw()
            if public_key is not None and public_key != derived_public:
                raise ValueError("Ed25519 public key does not match private key")
            self._private_key = bytes(private_key)
            self._public_key = derived_public
            self._private_obj = private_obj
        else:
            self._private_key = None
            self._public_key = bytes(public_key)
            self._private_obj = None
            ed25519.Ed25519PublicKey.from_public_bytes(self._public_key)

    def generate_keypair(self) -> tuple[str, str]:
        return self._public_key.hex(), (self._private_key or b"").hex()

    def get_public_key(self) -> str:
        return self._public_key.hex()

    def sign(self, message: bytes) -> str:
        if self._private_obj is None:
            raise RuntimeError("Private key unavailable for signing")
        if not isinstance(message, bytes):
            raise TypeError("message must be bytes")
        return self._private_obj.sign(message).hex()

    def verify(self, message: bytes, signature_hex: str) -> bool:
        if not isinstance(message, bytes) or not isinstance(signature_hex, str):
            return False
        try:
            signature = bytes.fromhex(signature_hex)
            ed25519.Ed25519PublicKey.from_public_bytes(self._public_key).verify(
                signature, message
            )
            return True
        except (ValueError, InvalidSignature):
            return False


class MLDSASigner:
    """FIPS 204 ML-DSA adapter for levels 44, 65 and 87.

    Legacy callers use security levels 2, 3 and 5; these map to ML-DSA-44,
    ML-DSA-65 and ML-DSA-87 respectively.
    """

    fips_standard = "NIST FIPS 204"
    conformant = True

    _PRIVATE = {
        2: mldsa.MLDSA44PrivateKey,
        3: mldsa.MLDSA65PrivateKey,
        5: mldsa.MLDSA87PrivateKey,
    }
    _PUBLIC = {
        2: mldsa.MLDSA44PublicKey,
        3: mldsa.MLDSA65PublicKey,
        5: mldsa.MLDSA87PublicKey,
    }
    _NAMES = {2: "ML-DSA-44", 3: "ML-DSA-65", 5: "ML-DSA-87"}
    _SIG_BYTES = {2: 2420, 3: 3309, 5: 4627}

    def __init__(
        self,
        security_level: int = 3,
        public_key: Optional[bytes] = None,
        private_key: Optional[bytes] = None,
    ):
        if security_level not in self._PRIVATE:
            raise ValueError("ML-DSA security_level must be 2, 3, or 5")
        self.security_level = security_level
        self.algorithm = self._NAMES[security_level]
        private_cls = self._PRIVATE[security_level]
        public_cls = self._PUBLIC[security_level]

        try:
            if private_key is None and public_key is None:
                private_obj = private_cls.generate()
                self._private_key = private_obj.private_bytes_raw()
                self._public_key = private_obj.public_key().public_bytes_raw()
                self._private_obj = private_obj
            elif private_key is not None:
                private_obj = private_cls.from_seed_bytes(bytes(private_key))
                derived_public = private_obj.public_key().public_bytes_raw()
                if public_key is not None and bytes(public_key) != derived_public:
                    raise ValueError("ML-DSA public key does not match private seed")
                self._private_key = bytes(private_key)
                self._public_key = derived_public
                self._private_obj = private_obj
            else:
                self._private_key = None
                self._public_key = bytes(public_key)
                self._private_obj = None
                public_cls.from_public_bytes(self._public_key)
        except UnsupportedAlgorithm as exc:
            raise RuntimeError(
                f"{self.algorithm} unavailable in this cryptography backend"
            ) from exc

    def generate_keypair(self) -> tuple[str, str]:
        return self._public_key.hex(), (self._private_key or b"").hex()

    def get_public_key(self) -> str:
        return self._public_key.hex()

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def fips_standard(self) -> str:
        return self._fips_standard


class Ed25519Signer:
    """Ed25519 signer with current hex and legacy byte interfaces."""

    conformant = True

    def __init__(self, seed: Optional[bytes] = None) -> None:
        """Initialize from a 32-byte RFC 8032 seed or generate a fresh key."""
        if seed is not None and len(seed) != 32:
            raise ValueError("seed must be 32 bytes")
        self._algorithm = "Ed25519"
        self._return_bytes = seed is not None
        self._private_key: Optional[ed25519.Ed25519PrivateKey] = (
            ed25519.Ed25519PrivateKey.from_private_bytes(seed)
            if seed is not None
            else ed25519.Ed25519PrivateKey.generate()
        )
        self._public_key: Optional[ed25519.Ed25519PublicKey] = (
            self._private_key.public_key()
        )
        self.public_key = self._public_key.public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        )
        self.key_id = "ed25519:" + hashlib.sha256(self.public_key).hexdigest()[:16]

    def _generate_keypair(self) -> None:
        """Generate Ed25519 key pair."""
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        self.public_key = self._public_key.public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        )
        self.key_id = "ed25519:" + hashlib.sha256(self.public_key).hexdigest()[:16]

    def sign(self, message: bytes) -> str | bytes:
        """Sign a message, returning legacy bytes for seeded legacy callers."""
        if self._private_key is None:
            raise ValueError("Ed25519 private key not initialized")
        signature = self._private_key.sign(message)
        return signature if self._return_bytes else signature.hex()

    @staticmethod
    def _verify_with_key(
        message: bytes,
        signature: str | bytes,
        public_key: ed25519.Ed25519PublicKey | bytes,
    ) -> bool:
        try:
            sig_bytes = bytes.fromhex(signature) if isinstance(signature, str) else signature
            key = (
                ed25519.Ed25519PublicKey.from_public_bytes(public_key)
                if isinstance(public_key, bytes)
                else public_key
            )
            if len(sig_bytes) != 64:
                return False
            key.verify(sig_bytes, message)
            return True
        except (InvalidSignature, TypeError, ValueError):
            return False

    def verify(
        self,
        message: bytes,
        signature: str | bytes | None = None,
        public_key: bytes | None = None,
    ) -> bool:
        """Verify with this key, or support the legacy class-level call shape."""
        if not isinstance(self, Ed25519Signer):
            legacy_message = self
            legacy_signature = message
            legacy_public_key = public_key if public_key is not None else signature
            if not isinstance(legacy_public_key, bytes):
                return False
            return Ed25519Signer._verify_with_key(
                legacy_message, legacy_signature, legacy_public_key
            )
        if signature is None:
            return False
        key: ed25519.Ed25519PublicKey | bytes | None = (
            public_key if public_key is not None else self._public_key
        )
        if key is None:
            return False
        return self._verify_with_key(message, signature, key)

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

    def self_test(self) -> tuple[bool, str]:
        """Exercise a round-trip and explicit tamper rejection."""
        message = b"chronus-self-test"
        signature = self.sign(message)
        if not self.verify(message, signature):
            return False, "signature verification failed"
        if self.verify(message + b"!", signature):
            return False, "tampered message accepted"
        return True, "Ed25519 round-trip and tamper rejection pass"


class MlDsaSigner:
    """Legacy fail-closed placeholder; no conformant implementation is exposed."""

    conformant = False
    key_id = "ml-dsa-65:unavailable"

    def sign(self, message: bytes) -> bytes:
        raise NotImplementedError("ML-DSA-65 not implemented")

    def verify(self, message: bytes, signature: bytes) -> bool:
        raise NotImplementedError("ML-DSA-65 not implemented")


    Retained only so old imports fail closed instead of silently changing
    algorithm semantics.
    """

    conformant = False

    def sign(self, _payload: bytes) -> bytes:
        raise RuntimeError("Legacy MlDsaSigner is unavailable; use MLDSASigner")

    def verify(self, _payload: bytes, _signature: bytes) -> bool:
        return False
