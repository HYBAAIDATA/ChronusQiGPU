"""Canonical AEAD helpers for AL HARAS memory/communication protection.

Replaces the broken HMAC-SHA256 repeating-XOR "quantum-resistant obfuscation"
in pythia_mining/quantum_defense_integration.py.

Wire format (v1):
    magic (4) | version (1) | nonce (12) | ciphertext+tag

- Algorithm: ChaCha20-Poly1305 (IETF)
- Key: 32 bytes derived via HKDF-SHA256 from caller key material
- Nonce: 12 random bytes per seal (never reused under same key)
- AAD: optional context string (binds ciphertext to purpose)

This is classical AEAD, not a post-quantum KEM. Do not label it
"quantum-resistant" without a PQC KEM/hybrid envelope. Integrity + confidentiality
are real; quantum resistance is a separate claim lane.
"""
from __future__ import annotations

import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"AH1\0"
VERSION = 1
NONCE_LEN = 12
KEY_LEN = 32
_HKDF_INFO = b"al-haras-memory-aead-v1"


class AeadError(ValueError):
    """Raised on decrypt/authenticate failure or malformed payload."""


def derive_aead_key(key_material: bytes, *, salt: bytes = b"") -> bytes:
    if not key_material:
        raise AeadError("empty key material")
    return HKDF(
        algorithm=SHA256(),
        length=KEY_LEN,
        salt=salt or None,
        info=_HKDF_INFO,
    ).derive(key_material)


def seal(plaintext: bytes, key_material: bytes, *, aad: bytes = b"") -> bytes:
    """Encrypt and authenticate plaintext. Returns versioned ciphertext blob."""
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError("plaintext must be bytes")
    key = derive_aead_key(bytes(key_material))
    nonce = os.urandom(NONCE_LEN)
    ct = ChaCha20Poly1305(key).encrypt(nonce, bytes(plaintext), aad or None)
    return MAGIC + bytes([VERSION]) + nonce + ct


def open_sealed(blob: bytes, key_material: bytes, *, aad: bytes = b"") -> bytes:
    """Decrypt and verify. Raises AeadError on any authentication failure."""
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("blob must be bytes")
    blob = bytes(blob)
    min_len = 4 + 1 + NONCE_LEN + 16  # magic + ver + nonce + tag
    if len(blob) < min_len:
        raise AeadError("ciphertext too short")
    if blob[:4] != MAGIC:
        raise AeadError("unknown ciphertext magic (legacy XOR payload?)" )
    if blob[4] != VERSION:
        raise AeadError(f"unsupported AEAD version: {blob[4]}")
    nonce = blob[5 : 5 + NONCE_LEN]
    ct = blob[5 + NONCE_LEN :]
    key = derive_aead_key(bytes(key_material))
    try:
        return ChaCha20Poly1305(key).decrypt(nonce, ct, aad or None)
    except Exception as exc:  # InvalidTag and peers
        raise AeadError("authentication failed") from exc


def is_aead_blob(blob: bytes) -> bool:
    return isinstance(blob, (bytes, bytearray)) and bytes(blob)[:4] == MAGIC


# Drop-in method bodies for QuantumDefenseSystem
# ------------------------------------------------
# def _obfuscate(self, data: bytes, key: bytes, *, context: str = "") -> bytes:
#     aad = context.encode("utf-8") if context else b""
#     return seal(data, key, aad=aad)
#
# def _deobfuscate(self, data: bytes, key: bytes, *, context: str = "") -> bytes:
#     aad = context.encode("utf-8") if context else b""
#     return open_sealed(data, key, aad=aad)
