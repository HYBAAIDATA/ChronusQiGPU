"""Reservation book: reserve against a quote, admit against a reservation.

Every rule fails closed:

  * a quote older than the current contract version must be re-quoted
  * a quote must match the live evidence hash, not just the version
  * one reservation binds one quote, one size, one expiry, one idempotency key
  * an expired, consumed or foreign reservation is refused
  * admission refuses when the actual size exceeds the reservation
  * the pool refuses when committed bytes would exceed it
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

LOG = logging.getLogger("chronus.procurement")

DEFAULT_TTL_S = 900.0
ADMISSION_GRACE = 1.02  # 2% tolerance before an overage refuses


class Refusal(Exception):
    """Fail-closed outcome. Carries a stable code for the client and the log."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def to_dict(self) -> dict[str, str]:
        return {"refused": self.code, "detail": self.detail}


@dataclass(frozen=True)
class Reservation:
    id: str
    quote_hash: str
    tier: str
    size: int
    space_bytes: int
    contract_version: str
    evidence_hash: str
    expires_at: float
    consumed: bool = False

    def expired(self, now: float) -> bool:
        return now >= self.expires_at


@dataclass
class Book:
    """Outstanding commitments against a declared pool."""

    pool_bytes: int
    ttl_s: float = DEFAULT_TTL_S
    pool_source: str = "undeclared"
    _by_key: dict[str, Reservation] = field(default_factory=dict)
    _live: dict[str, Reservation] = field(default_factory=dict)

    def outstanding(self, now: float) -> list[Reservation]:
        return [r for r in self._live.values() if not r.expired(now)]

    def committed(self, now: float) -> int:
        return sum(r.space_bytes for r in self.outstanding(now))

    def sweep(self, now: float) -> int:
        stale = [k for k, r in self._live.items() if r.expired(now)]
        for key in stale:
            self._live.pop(key, None)
        return len(stale)


def quote_hash(quote: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(quote, sort_keys=True, default=str).encode()
    ).hexdigest()


def reserve(
    book: Book,
    contract_version: str,
    evidence_hash: str,
    quote: dict[str, Any],
    idempotency_key: str,
    now: float | None = None,
) -> Reservation:
    now = time.time() if now is None else now
    book.sweep(now)
    if idempotency_key in book._by_key:
        return book._by_key[idempotency_key]  # replay returns the original

    if not quote.get("is_binding"):
        raise Refusal("quote_not_binding", f"verdict {quote.get('verdict')}")
    if int(quote.get("releases_old", 0) or 0) > 0:
        raise Refusal(
            "stale_envelope",
            f"{quote['releases_old']} release(s) old; re-quote",
        )
    if quote.get("contract_version") != contract_version:
        raise Refusal("version_mismatch", "quote is from a superseded contract")
    if quote.get("evidence_hash") != evidence_hash:
        raise Refusal("evidence_mismatch", "quote evidence is not the live evidence")

    size = int(quote["size"])
    space = int(quote["space_bytes"])
    if size <= 0 or space <= 0:
        raise Refusal("invalid_quote", "size and space_bytes must be positive")
    if book.committed(now) + space > book.pool_bytes:
        raise Refusal(
            "pool_exhausted",
            f"{book.committed(now) + space} > {book.pool_bytes}",
        )

    reservation = Reservation(
        id=str(uuid.uuid4()),
        quote_hash=quote_hash(quote),
        tier=str(quote["tier"]),
        size=size,
        space_bytes=space,
        contract_version=contract_version,
        evidence_hash=evidence_hash,
        expires_at=now + book.ttl_s,
    )
    book._by_key[idempotency_key] = reservation
    book._live[reservation.id] = reservation
    LOG.info(
        "reserved %s tier=%s size=%d space=%d pool_source=%s",
        reservation.id,
        reservation.tier,
        size,
        space,
        book.pool_source,
    )
    return reservation


def admit(
    book: Book,
    reservation_id: str,
    actual_size: int,
    now: float | None = None,
) -> dict[str, Any]:
    now = time.time() if now is None else now
    book.sweep(now)
    reservation = book._live.get(reservation_id)
    if reservation is None:
        raise Refusal("unknown_reservation", reservation_id)
    if reservation.consumed:
        raise Refusal("already_consumed", reservation_id)
    if reservation.expired(now):
        raise Refusal("expired", f"{now - reservation.expires_at:.0f}s past expiry")

    ceiling = int(reservation.size * ADMISSION_GRACE)
    if actual_size > ceiling:
        raise Refusal(
            "overage",
            f"actual {actual_size} exceeds reserved {reservation.size} by "
            f"{actual_size / reservation.size - 1:.1%}",
        )

    book._live[reservation_id] = Reservation(
        **{**asdict(reservation), "consumed": True}
    )
    utilisation = round(actual_size / reservation.size, 4) if reservation.size else 0.0
    return {
        "reservation": reservation_id,
        "tier": reservation.tier,
        "reserved": reservation.size,
        "actual": actual_size,
        "space_bytes": reservation.space_bytes,
        "utilisation": utilisation,
    }
