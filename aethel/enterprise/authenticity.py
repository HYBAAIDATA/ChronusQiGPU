"""Integrity (SHA-256) vs authenticity (HMAC-SHA256) helpers.

Integrity
    content_digest / envelope SHA-256 detects accidental corruption.

Authenticity
    mac_create / mac_verify — HMAC-SHA256 over canonical manifest with an
    explicit custody key. Key material is never defaulted for production use;
    Theseus does not embed AL HARAS policy.

Key identifier / rotation
    Callers pass key_id alongside raw key bytes. Rotation is additive: verify
    may try a list of keys (current + previous) while seal always uses the
    active key. Policy for which key is allowed remains outside Theseus
    (ops / AL HARAS).
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Optional, Sequence, Union

from .errors import AuthenticityError
from .schema import CustodyEnvelope, canonical_manifest_bytes


def content_digest(data: bytes) -> str:
    """SHA-256 hex digest — integrity only."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("content_digest requires bytes")
    return hashlib.sha256(bytes(data)).hexdigest()


@dataclass(frozen=True)
class CustodyKey:
    """Keyed authenticity material with stable identifier for rotation."""

    key_id: str
    key: bytes
    version: int = 1

    def __post_init__(self) -> None:
        if not self.key_id or not str(self.key_id).strip():
            raise AuthenticityError("custody key_id must be non-empty")
        if not isinstance(self.key, (bytes, bytearray)) or len(self.key) < 16:
            raise AuthenticityError(
                "custody key must be >= 16 bytes (fail-closed; no silent short key)"
            )


INSECURE_DEV_KEY_MARKERS = (
    b"enterprise-dev-key-change-me",
    b"change-me",
    b"test",
    b"",
)


def is_insecure_dev_key(key: bytes) -> bool:
    if not key:
        return True
    if key in INSECURE_DEV_KEY_MARKERS:
        return True
    low = key.lower()
    if low in {b"secret", b"password", b"hmac-key"}:
        return True
    if len(key) < 16:
        return True
    return False


def mac_create(key: bytes, envelope: Union[CustodyEnvelope, bytes]) -> str:
    """HMAC-SHA256 hex over canonical manifest (authenticity)."""
    if not key:
        raise AuthenticityError(
            "HMAC key missing — authenticity required, fail-closed"
        )
    if isinstance(envelope, CustodyEnvelope):
        msg = canonical_manifest_bytes(envelope)
    else:
        msg = bytes(envelope)
    return hmac.new(bytes(key), msg, hashlib.sha256).hexdigest()


def mac_verify(
    key: bytes,
    envelope: Union[CustodyEnvelope, bytes],
    mac_hex: str,
    *,
    previous_keys: Optional[Sequence[bytes]] = None,
) -> bool:
    """Verify HMAC; optionally accept previous keys (rotation path)."""
    candidates: list[bytes] = []
    if key:
        candidates.append(bytes(key))
    if previous_keys:
        candidates.extend(bytes(k) for k in previous_keys if k)
    if not candidates:
        raise AuthenticityError("no HMAC keys available — fail-closed")
    if not mac_hex or not isinstance(mac_hex, str):
        return False
    for k in candidates:
        expected = mac_create(k, envelope)
        if hmac.compare_digest(expected, mac_hex):
            return True
    return False


__all__ = [
    "content_digest",
    "mac_create",
    "mac_verify",
    "CustodyKey",
    "is_insecure_dev_key",
    "INSECURE_DEV_KEY_MARKERS",
]
