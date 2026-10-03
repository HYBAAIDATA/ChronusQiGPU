"""Integrity (SHA-256) vs authenticity (HMAC-SHA256) helpers."""
from __future__ import annotations

import hashlib
import hmac
from typing import Union

from .schema import CustodyEnvelope, canonical_manifest_bytes


def content_digest(payload: bytes) -> str:
    """SHA-256 hex digest of raw payload bytes (integrity)."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("content_digest requires bytes")
    return hashlib.sha256(bytes(payload)).hexdigest()


def mac_create(key: bytes, envelope: Union[CustodyEnvelope, dict]) -> str:
    """HMAC-SHA256 hex over canonical manifest (authenticity)."""
    if not key:
        raise ValueError("HMAC key must be non-empty")
    msg = canonical_manifest_bytes(envelope)
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def mac_verify(key: bytes, envelope: Union[CustodyEnvelope, dict], mac: str) -> bool:
    """Constant-time HMAC verify over canonical manifest."""
    if not key or not mac:
        return False
    expected = mac_create(key, envelope)
    return hmac.compare_digest(expected, mac)


__all__ = ["content_digest", "mac_create", "mac_verify"]
