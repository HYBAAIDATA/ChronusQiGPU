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
            if len(signature) != self._SIG_BYTES[self.security_level]:
                return False
            self._PUBLIC[self.security_level].from_public_bytes(
                self._public_key
            ).verify(signature, message)
            return True
        except (ValueError, InvalidSignature, UnsupportedAlgorithm):
            return False


class MlDsaSigner:
    """Removed legacy bespoke signer contract.

    Retained only so old imports fail closed instead of silently changing
    algorithm semantics.
    """

    conformant = False

    def sign(self, _payload: bytes) -> bytes:
        raise RuntimeError("Legacy MlDsaSigner is unavailable; use MLDSASigner")

    def verify(self, _payload: bytes, _signature: bytes) -> bool:
        return False
