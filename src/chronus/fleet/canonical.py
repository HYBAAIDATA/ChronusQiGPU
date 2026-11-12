# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Canonical encodings, digests and timestamps shared by the fleet.

Signed and hashed objects are serialised as canonical JSON: keys sorted,
no insignificant whitespace, UTF-8, and no NaN or infinity values. The fleet
keeps signed content integer- and string-valued so that the same object hashes
identically on every platform.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Sequence

_LEAF = b"\x00"
_NODE = b"\x01"


def canonical_json(obj: Any) -> bytes:
    """Serialise obj deterministically for hashing and signing."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json(obj: Any) -> str:
    """SHA-256 of the canonical JSON encoding of obj."""
    return sha256_hex(canonical_json(obj))


def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64decode(text: str) -> bytes:
    """Strict base64 decoding; malformed input raises ValueError."""
    if not isinstance(text, str):
        raise ValueError("base64 field must be a string")
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError("invalid base64 field") from exc


def is_hex_digest(value: Any, length: int = 64) -> bool:
    if not isinstance(value, str) or len(value) != length:
        return False
    return all(ch in "0123456789abcdef" for ch in value)


def merkle_root(leaf_digests: Sequence[str]) -> str:
    """Binary Merkle root over hex leaf digests with leaf/node domain separation.

    An odd node at any level is promoted unchanged. The root of an empty
    sequence is the SHA-256 of the empty leaf marker.
    """
    level = [hashlib.sha256(_LEAF + bytes.fromhex(d)).digest() for d in leaf_digests]
    if not level:
        return hashlib.sha256(_LEAF).hexdigest()
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level) - 1, 2):
            nxt.append(hashlib.sha256(_NODE + level[i] + level[i + 1]).digest())
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0].hex()


def utc_now_ns() -> int:
    """Wall-clock time in integer nanoseconds since the Unix epoch."""
    return time.time_ns()


def iso_utc(ns: int | None = None) -> str:
    """ISO 8601 UTC timestamp with microsecond precision and a Z suffix."""
    if ns is None:
        ns = utc_now_ns()
    seconds, remainder = divmod(int(ns), 1_000_000_000)
    stamp = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
        microsecond=remainder // 1000
    )
    return stamp.isoformat(timespec="microseconds").replace("+00:00", "Z")


def monotonic_ns() -> int:
    """Monotonic clock for deadlines and durations (never wall-clock)."""
    return time.monotonic_ns()


def per_second(count: int, elapsed_ns: int) -> int:
    """Integer rate count / elapsed, floored; 0 when nothing was timed."""
    if elapsed_ns <= 0:
        return 0
    return (int(count) * 1_000_000_000) // int(elapsed_ns)


def deterministic_bytes(label: str, length: int) -> bytes:
    """Reproducible test and benchmark input: SHA-256 in counter mode over label."""
    out = bytearray()
    counter = 0
    seed = label.encode("utf-8")
    while len(out) < length:
        out += hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        counter += 1
    return bytes(out[:length])
