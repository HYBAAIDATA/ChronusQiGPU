"""Validate checkpoint envelopes before trusting their artifact references.

A seal detects corruption, not publisher authenticity or promotion approval.
This validator neither grants deployment authority nor proves training quality.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Mapping

MANIFEST_SCHEMA = "euclid.checkpoint-manifest/1"
SEAL_DOMAIN = "euclid.checkpoint-manifest.seal.v1"


def validate_manifest_envelope(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return an isolated JSON snapshot only after schema and seal checks."""
    if not isinstance(manifest, Mapping):
        raise ValueError("checkpoint manifest is not a JSON object")
    try:
        snapshot = json.loads(json.dumps(dict(manifest), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("checkpoint manifest must contain finite JSON values") from exc
    if snapshot.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unsupported checkpoint manifest schema")
    body = {key: value for key, value in snapshot.items() if key != "seal"}
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    expected = hashlib.sha256(SEAL_DOMAIN.encode() + b"\0" + canonical).hexdigest()
    supplied = snapshot.get("seal")
    if not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
        raise ValueError("checkpoint manifest seal mismatch")
    for section in ("task", "learner", "dataset", "dedup", "evidence"):
        if not isinstance(snapshot.get(section), dict):
            raise ValueError(f"checkpoint manifest section {section!r} missing")
    for field in ("source_revision", "policy_version"):
        if not isinstance(snapshot.get(field), str) or not snapshot[field].strip():
            raise ValueError(f"checkpoint manifest {field!r} is required")
    return snapshot


def require_sha256(value: Any, *, field: str) -> str:
    """Reject missing or malformed artifact commitments."""
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value
