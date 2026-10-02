"""Replayable, optionally HMAC-authenticated hash-chain attestations."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Iterable

from .abi import canonical_json

DOMAIN = b"chronus-virtual-igpu-attestation-v1\0"


def extend_chain(chain: Iterable[str], record: Any, key: bytes | None = None) -> tuple[str, ...]:
    prior = tuple(chain)
    previous = prior[-1] if prior else "0" * 64
    body = DOMAIN + bytes.fromhex(previous) + canonical_json(record)
    token = (
        hmac.new(key, body, hashlib.sha256).hexdigest()
        if key is not None
        else hashlib.sha256(body).hexdigest()
    )
    return prior + (token,)


def replay(records: Iterable[Any], key: bytes | None = None) -> tuple[str, ...]:
    chain: tuple[str, ...] = ()
    for record in records:
        chain = extend_chain(chain, record, key)
    return chain


def verify(records: Iterable[Any], chain: Iterable[str], key: bytes | None = None) -> bool:
    expected = replay(records, key)
    supplied = tuple(chain)
    return len(expected) == len(supplied) and all(
        hmac.compare_digest(a, b) for a, b in zip(expected, supplied)
    )