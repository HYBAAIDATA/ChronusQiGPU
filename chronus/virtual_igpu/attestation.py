"""Replayable, optionally HMAC-authenticated hash-chain attestations."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Iterable, Sequence

from .abi import canonical_json

DOMAIN = b"chronus.virtual_igpu.attestation.v1"


def _body(previous: str, record: Any) -> bytes:
    prev = previous if previous else ("0" * 64)
    return DOMAIN + bytes.fromhex(prev) + canonical_json(record).encode("utf-8")


def extend_chain(
    previous_chain: Sequence[str] | Iterable[str],
    record: Any,
    key: bytes | None = None,
) -> tuple[str, ...]:
    prev_list = list(previous_chain)
    previous = prev_list[-1] if prev_list else ("0" * 64)
    digest = hashlib.sha256(_body(previous, record)).hexdigest()
    if key:
        digest = hmac.new(key, digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return tuple(prev_list + [digest])


def replay(records: Iterable[Any], key: bytes | None = None) -> tuple[str, ...]:
    """Build a full chain over records (test helper / replay)."""
    chain: tuple[str, ...] = ()
    for record in records:
        chain = extend_chain(chain, record, key)
    return chain


def verify(records: Iterable[Any], chain: Sequence[str], key: bytes | None = None) -> bool:
    """Verify chain matches records (constant-time compare per link)."""
    expected = replay(records, key)
    if len(expected) != len(chain):
        return False
    return all(
        hmac.compare_digest(a, b) for a, b in zip(expected, chain)
    )


__all__ = ["extend_chain", "replay", "verify", "DOMAIN"]
