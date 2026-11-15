"""Opaque cursor pagination."""

from __future__ import annotations

import base64
import binascii
import json

from chronus.service.api.errors import ApiError

DEFAULT_LIMIT = 25
MAX_LIMIT = 100


def clamp_limit(raw: int | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    if raw < 1:
        raise ApiError(400, "invalid_limit", "Invalid limit", "limit must be >= 1.")
    return min(raw, MAX_LIMIT)


def encode_cursor(payload: dict) -> str:
    blob = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")


def decode_cursor(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        padded = raw + "=" * (-len(raw) % 4)
        # A non-ASCII cursor raises UnicodeEncodeError here, not binascii.Error.
        value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (binascii.Error, ValueError, UnicodeEncodeError, json.JSONDecodeError):
        raise ApiError(400, "invalid_cursor", "Invalid cursor",
                       "Cursor is malformed. Restart from the first page.")
    if not isinstance(value, dict):
        raise ApiError(400, "invalid_cursor", "Invalid cursor", "Cursor is malformed.")
    return value
