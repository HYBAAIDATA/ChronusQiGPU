"""Canonical JSON for signed HYBA documents.

``canonical_bytes`` produces the exact bytes that are signed and verified:
JSON with object keys sorted by Unicode code point, separators ``(",", ":")``,
UTF-8 output and non-ASCII characters left unescaped (``ensure_ascii=False``).
Only objects with string keys, arrays, strings, integers in the interoperable
range +/-(2**53 - 1), booleans and null are accepted. Floats, NaN and every
other value type are rejected, so a signer and a verifier always agree on the
bytes. This is HYBA's canonical form; it is not RFC 8785 (JCS).

``loads_strict`` parses untrusted JSON text. It rejects duplicate object keys,
numbers with a fraction or exponent, the NaN/Infinity constants, invalid
UTF-8 and documents larger than ``MAX_DOCUMENT_BYTES``.
"""

from __future__ import annotations

import json

from .errors import MalformedLease

__all__ = ["MAX_DOCUMENT_BYTES", "MAX_SAFE_INTEGER", "canonical_bytes", "loads_strict"]

MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_DEPTH = 32


def canonical_bytes(value):
    """Return the canonical UTF-8 JSON encoding of ``value``.

    Raises MalformedLease for any value outside the permitted JSON subset.
    """
    _check_value(value, 0)
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        data = text.encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MalformedLease(f"document cannot be canonicalised: {exc}") from exc
    if len(data) > MAX_DOCUMENT_BYTES:
        raise MalformedLease(f"document exceeds {MAX_DOCUMENT_BYTES} bytes")
    return data


def loads_strict(data):
    """Parse untrusted JSON text (str or UTF-8 bytes) with strict rules."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        raw = bytes(data)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise MalformedLease(f"JSON text exceeds {MAX_DOCUMENT_BYTES} bytes")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MalformedLease("JSON text is not valid UTF-8") from exc
    elif isinstance(data, str):
        text = data
        if len(text) > MAX_DOCUMENT_BYTES:
            raise MalformedLease(f"JSON text exceeds {MAX_DOCUMENT_BYTES} characters")
    else:
        raise MalformedLease(f"expected JSON text, got {type(data).__name__}")
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except MalformedLease:
        raise
    except (ValueError, RecursionError) as exc:
        raise MalformedLease(f"invalid JSON: {exc}") from exc


def _check_value(value, depth):
    if depth > MAX_DEPTH:
        raise MalformedLease(f"document nesting exceeds {MAX_DEPTH} levels")
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        if -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            return
        raise MalformedLease("integer outside the interoperable range +/-(2**53 - 1)")
    if isinstance(value, float):
        raise MalformedLease("floating-point numbers are not permitted in signed documents")
    if isinstance(value, (list, tuple)):
        for item in value:
            _check_value(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise MalformedLease("object keys must be strings")
            _check_value(item, depth + 1)
        return
    raise MalformedLease(f"unsupported value type {type(value).__name__}")


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MalformedLease(f"duplicate object key {key[:64]!r}")
        result[key] = value
    return result


def _reject_float(text):
    raise MalformedLease("floating-point numbers are not permitted in signed documents")


def _reject_constant(name):
    raise MalformedLease(f"the JSON constant {name} is not permitted")
