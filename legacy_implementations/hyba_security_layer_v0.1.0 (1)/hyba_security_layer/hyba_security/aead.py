"""HYBA / AL HARAS security layer - authenticated encryption primitive.

CLAIM LANE: classical AEAD (ChaCha20-Poly1305, IETF RFC 8439).
  - This is NOT post-quantum cryptography.
  - This is NOT a KEM, KEX, or signature scheme.
  - No 'unhackable', 'unbreakable', or 'quantum-resistant' claim attaches here.

Provenance: elevates P0-1 (XOR keystream = HMAC(key, plaintext)) closed in the
AL HARAS midas_backend crypto elevation, 20 Jul 2026.

Wire format (little-endian, fixed header):
    MAGIC(4) | VERSION(1) | NONCE(12) | CIPHERTEXT+TAG(n+16)
"""

from __future__ import annotations

import os
from typing import Final

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC: Final[bytes] = b"AH1\x00"
VERSION: Final[int] = 1
NONCE_LEN: Final[int] = 12
KEY_LEN: Final[int] = 32
TAG_LEN: Final[int] = 16
HEADER_LEN: Final[int] = len(MAGIC) + 1 + NONCE_LEN

CLAIM_LANE: Final[str] = "CLASSICAL_AEAD"
IS_POST_QUANTUM: Final[bool] = False


class AeadError(Exception):
    """Base error for the AEAD surface."""


class AeadFormatError(AeadError):
    """Wire format is not a recognised AH1 envelope."""


class AeadAuthError(AeadError):
    """Authentication failed: forged, tampered, or wrong context/key."""


def derive_key(key_material: bytes, context: str, salt: bytes = b"") -> bytes:
    """HKDF-SHA256 -> 32 bytes. Context is bound into `info` for key separation."""
    if not isinstance(key_material, (bytes, bytearray)):
        raise AeadError("key material must be bytes")
    if len(key_material) == 0:
        raise AeadError("empty key material rejected")
    if not context or not isinstance(context, str):
        raise AeadError("context (purpose) is required")
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LEN,
        salt=salt or None,
        info=b"hyba/al-haras/aead/v1/" + context.encode("utf-8"),
    )
    return kdf.derive(bytes(key_material))


def _aad(context: str) -> bytes:
    """Additional authenticated data binds the purpose to the ciphertext."""
    return b"hyba-aead-v1|" + context.encode("utf-8")


def seal(data: bytes, key_material: bytes, context: str = "memory") -> bytes:
    """Encrypt+authenticate `data`. Returns an AH1 envelope."""
    if not isinstance(data, (bytes, bytearray)):
        raise AeadError("data must be bytes")
    key = derive_key(key_material, context)
    nonce = os.urandom(NONCE_LEN)
    ct = ChaCha20Poly1305(key).encrypt(nonce, bytes(data), _aad(context))
    return MAGIC + bytes([VERSION]) + nonce + ct


def open_sealed(blob: bytes, key_material: bytes, context: str = "memory") -> bytes:
    """Verify+decrypt an AH1 envelope. Fail-closed on any deviation."""
    if not isinstance(blob, (bytes, bytearray)):
        raise AeadFormatError("blob must be bytes")
    blob = bytes(blob)
    if len(blob) < HEADER_LEN + TAG_LEN:
        raise AeadFormatError("blob shorter than minimum envelope")
    if blob[: len(MAGIC)] != MAGIC:
        raise AeadFormatError("bad magic: not an AH1 envelope (legacy blob?)")
    version = blob[len(MAGIC)]
    if version != VERSION:
        raise AeadFormatError(f"unsupported envelope version {version}")
    nonce = blob[len(MAGIC) + 1 : HEADER_LEN]
    ct = blob[HEADER_LEN:]
    key = derive_key(key_material, context)
    try:
        return ChaCha20Poly1305(key).decrypt(nonce, ct, _aad(context))
    except Exception as exc:  # noqa: BLE001 - normalise to fail-closed error
        raise AeadAuthError("authentication failed") from exc


def describe() -> dict:
    """Machine-readable claim record for evidence packs."""
    return {
        "algorithm": "ChaCha20-Poly1305",
        "kdf": "HKDF-SHA256",
        "key_bits": KEY_LEN * 8,
        "nonce_bytes": NONCE_LEN,
        "claim_lane": CLAIM_LANE,
        "post_quantum": IS_POST_QUANTUM,
        "unhackable": False,
        "aad_bound": True,
    }
