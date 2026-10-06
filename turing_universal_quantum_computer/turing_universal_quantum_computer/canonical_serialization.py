"""Canonical, fail-closed serialization for exact mathematical evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from fractions import Fraction
from typing import Any

SCHEMA = "turing.canonical-json/v1"


class CanonicalSerializationError(TypeError):
    """Raised when a value has no unambiguous canonical representation."""


def canonical_value(value: Any) -> Any:
    """Normalize an exact value into the published canonical JSON data model."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        raise CanonicalSerializationError("floating-point values are forbidden")
    if isinstance(value, Fraction):
        return {
            "$rational": {
                "numerator": value.numerator,
                "denominator": value.denominator,
            }
        }
    if isinstance(value, bytes):
        return {"$bytes_hex": value.hex()}
    if isinstance(value, Enum):
        return canonical_value(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return canonical_value(asdict(value))
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalSerializationError("canonical object keys must be strings")
        return {key: canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    raise CanonicalSerializationError(
        f"unsupported canonical value: {type(value).__name__}"
    )


def canonical_serialize(value: Any) -> bytes:
    """Serialize with sorted keys, UTF-8, and no insignificant whitespace."""
    normalized = canonical_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_serialize(value)).hexdigest()


__all__ = [
    "CanonicalSerializationError",
    "SCHEMA",
    "canonical_serialize",
    "canonical_sha256",
    "canonical_value",
]