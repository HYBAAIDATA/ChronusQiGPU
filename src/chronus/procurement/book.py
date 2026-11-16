"""Reservation book: reserve against a quote, admit against a reservation.

Every rule fails closed. Quotes are rebuilt server-side before trust.
Reservations and idempotency keys are tenant-scoped.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from chronus.procurement.quote import build_quote, live_evidence_hash

LOG = logging.getLogger("chronus.procurement")

DEFAULT_TTL_S = 900.0
ADMISSION_GRACE = 1.02  # 2% tolerance before an overage refuses
IDEM_RETENTION_S = 3600.0  # keep expired idempotency entries briefly for clear refusals


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
    tenant_id: str
    quote_hash: str
    tier: str
    size: int
    space_bytes: int
    contract_version: str
    evidence_hash: str
    expires_at: float
    consumed: bool = False
    admission: dict[str, Any] | None = None

    def expired(self, now: float) -> bool:
        return now >= self.expires_at


@dataclass
class Book:
    """Outstanding commitments against a declared pool (single-process pilot)."""

    pool_bytes: int
    ttl_s: float = DEFAULT_TTL_S
    pool_source: str = "undeclared"
    _by_key: dict[tuple[str, str], Reservation] = field(default_factory=dict)
    _live: dict[str, Reservation] = field(default_factory=dict)

    def outstanding(self, now: float) -> list[Reservation]:
        return [r for r in self._live.values() if not r.expired(now) and not r.consumed]

    def committed(self, now: float) -> int:
        return sum(r.space_bytes for r in self.outstanding(now))

    def sweep(self, now: float, *, retain_until: float | None = None) -> int:
        """Drop expired/consumed entries past retention from live and idempotency maps."""
        cutoff = now if retain_until is None else retain_until
        removed = 0
        stale_live = [
            key
            for key, res in self._live.items()
            if (res.expired(now) or res.consumed) and res.expires_at < cutoff
        ]
        for key in stale_live:
            self._live.pop(key, None)
            removed += 1
        stale_keys = [
            key
            for key, res in self._by_key.items()
            if res.expires_at + IDEM_RETENTION_S < now
        ]
        for key in stale_keys:
            self._by_key.pop(key, None)
            removed += 1
        return removed


def quote_hash(quote: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(quote, sort_keys=True, default=str).encode()
    ).hexdigest()


def _parse_quote_inputs(quote: dict[str, Any]) -> tuple[int, str]:
    try:
        size = int(quote["size"])
        tier = str(quote["tier"])
    except (KeyError, TypeError, ValueError) as exc:
        raise Refusal("invalid_quote", f"size/tier missing or invalid: {exc}") from exc
    if size <= 0:
        raise Refusal("invalid_quote", "size must be positive")
    return size, tier


def _server_quote(
    quote: dict[str, Any],
    *,
    contract_version: str,
    evidence_hash: str,
) -> dict[str, Any]:
    """Rebuild the quote from size+tier; refuse if the client tampered with economics."""
    size, tier = _parse_quote_inputs(quote)
    rebuilt = build_quote(
        size,
        tier=tier,
        contract_version=contract_version,
        evidence_hash=evidence_hash,
        releases_old=0,
    )
    for key in (
        "size",
        "tier",
        "space_bytes",
        "is_binding",
        "contract_version",
        "evidence_hash",
        "verdict",
    ):
        if quote.get(key) != rebuilt.get(key):
            raise Refusal(
                "invalid_quote",
                f"quote field {key!r} does not match the server envelope",
            )
    if int(quote.get("releases_old", 0) or 0) != 0:
        raise Refusal("stale_envelope", f"{quote.get('releases_old')} release(s) old; re-quote")
    return rebuilt


def reserve(
    book: Book,
    contract_version: str,
    evidence_hash: str,
    quote: dict[str, Any],
    idempotency_key: str,
    *,
    tenant_id: str,
    now: float | None = None,
) -> Reservation:
    now = time.time() if now is None else now
    if not tenant_id:
        raise Refusal("invalid_quote", "tenant_id is required")
    book.sweep(now, retain_until=now - IDEM_RETENTION_S)

    key = (tenant_id, idempotency_key)
    existing = book._by_key.get(key)
    if existing is not None:
        if existing.expired(now):
            book._by_key.pop(key, None)
            book._live.pop(existing.id, None)
        else:
            return existing

    if evidence_hash != live_evidence_hash(contract_version=contract_version):
        # Defence in depth; callers should pass the live hash.
        raise Refusal("evidence_mismatch", "quote evidence is not the live evidence")

    try:
        trusted = _server_quote(
            quote, contract_version=contract_version, evidence_hash=evidence_hash
        )
    except Refusal:
        raise
    except Exception as exc:  # noqa: BLE001 — map any parse failure to invalid_quote
        raise Refusal("invalid_quote", str(exc)) from exc

    if not trusted.get("is_binding"):
        raise Refusal("quote_not_binding", f"verdict {trusted.get('verdict')}")
    if trusted.get("contract_version") != contract_version:
        raise Refusal("version_mismatch", "quote is from a superseded contract")
    if trusted.get("evidence_hash") != evidence_hash:
        raise Refusal("evidence_mismatch", "quote evidence is not the live evidence")

    size = int(trusted["size"])
    space = int(trusted["space_bytes"])
    if book.committed(now) + space > book.pool_bytes:
        raise Refusal(
            "pool_exhausted",
            f"{book.committed(now) + space} > {book.pool_bytes}",
        )

    reservation = Reservation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        quote_hash=quote_hash(trusted),
        tier=str(trusted["tier"]),
        size=size,
        space_bytes=space,
        contract_version=contract_version,
        evidence_hash=evidence_hash,
        expires_at=now + book.ttl_s,
    )
    book._by_key[key] = reservation
    book._live[reservation.id] = reservation
    LOG.info(
        "reserved %s tenant=%s tier=%s size=%d space=%d",
        reservation.id,
        tenant_id,
        reservation.tier,
        size,
        space,
    )
    return reservation


def admit(
    book: Book,
    reservation_id: str,
    actual_size: int,
    *,
    tenant_id: str,
    now: float | None = None,
) -> dict[str, Any]:
    now = time.time() if now is None else now
    if not tenant_id:
        raise Refusal("unknown_reservation", reservation_id)

    # Look up before sweeping this ID so expired returns the advertised code.
    reservation = book._live.get(reservation_id)
    if reservation is None:
        # May still be in idempotency map after live drop — treat as unknown.
        raise Refusal("unknown_reservation", reservation_id)
    if reservation.tenant_id != tenant_id:
        raise Refusal("unknown_reservation", reservation_id)
    if reservation.admission is not None:
        return reservation.admission  # idempotent retry after ledger hiccup
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

    utilised_bytes = int(
        reservation.space_bytes * actual_size / reservation.size
    ) if reservation.size else 0
    utilisation = actual_size / reservation.size if reservation.size else 0.0
    result = {
        "reservation": reservation_id,
        "tenant_id": tenant_id,
        "tier": reservation.tier,
        "reserved": reservation.size,
        "actual": actual_size,
        "space_bytes": reservation.space_bytes,
        "utilised_bytes": utilised_bytes,
        "utilisation": round(utilisation, 6),
    }
    book._live[reservation_id] = Reservation(
        **{**asdict(reservation), "consumed": True, "admission": result}
    )
    book.sweep(now, retain_until=now - IDEM_RETENTION_S)
    return result
