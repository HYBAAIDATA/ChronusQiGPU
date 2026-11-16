"""Sealed capacity procurement routes: quote → reserve → admit."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from chronus.core.seal import assert_sealed, seal_schema
from chronus.procurement import (
    Book,
    Refusal,
    UtilisationLedger,
    admit,
    build_quote,
    load_pool,
    reserve,
)
from chronus.procurement.quote import CONTRACT_VERSION, live_evidence_hash
from chronus.service.api.errors import ApiError
from chronus.service.api.security import Principal, require

LOG = logging.getLogger("chronus.procurement")
router = APIRouter()

_book: Book | None = None
_ledger: UtilisationLedger | None = None


def reset_procurement_state() -> None:
    """Test hook: drop the process-local book and ledger."""
    global _book, _ledger
    _book = None
    _ledger = None


def _book_singleton() -> Book:
    global _book
    if _book is None:
        pool = load_pool()
        _book = Book(
            pool_bytes=pool.pool_bytes,
            pool_source=pool.source,
            ttl_s=float(os.getenv("CHRONUS_PROCUREMENT_TTL_S", "900")),
        )
    return _book


def _ledger_singleton() -> UtilisationLedger:
    global _ledger
    if _ledger is None:
        path_raw = os.getenv("CHRONUS_PROCUREMENT_LEDGER")
        path = Path(path_raw) if path_raw else None
        _ledger = UtilisationLedger(path)
    return _ledger


def _refusal_to_api(exc: Refusal) -> ApiError:
    status = {
        "pool_exhausted": 409,
        "quote_not_binding": 409,
        "stale_envelope": 409,
        "version_mismatch": 409,
        "evidence_mismatch": 409,
        "unknown_reservation": 404,
        "already_consumed": 409,
        "expired": 409,
        "overage": 409,
        "invalid_quote": 400,
        "idempotency_conflict": 409,
    }.get(exc.code, 409)
    return ApiError(status, exc.code, "Reservation refused", exc.detail)


class QuoteRequest(BaseModel):
    size: int = Field(..., description="Requested work size in envelope units")
    tier: str = Field(
        default="TIER_POLYNOMIAL",
        description="Measured convergence class",
    )


class ReserveRequest(BaseModel):
    quote: dict[str, Any]
    idempotency_key: str = Field(..., min_length=1, max_length=128)


class AdmitRequest(BaseModel):
    reservation_id: str
    actual_size: int = Field(..., ge=0)


@router.get("/pool", summary="Declared procurement pool")
async def pool_status(_: Principal = Depends(require("workloads:read"))) -> dict[str, Any]:
    pool = load_pool()
    book = _book_singleton()
    payload = {
        **pool.to_public_dict(),
        "committed_bytes": book.committed(__import__("time").time()),
        "contract_version": CONTRACT_VERSION,
        "evidence_hash": live_evidence_hash(),
    }
    assert_sealed(str(payload), context="pool_status")
    return payload


@router.post("/quote", summary="Advisory capacity quote")
async def quote(
    body: QuoteRequest,
    _: Principal = Depends(require("workloads:write")),
) -> dict[str, Any]:
    try:
        return build_quote(body.size, tier=body.tier)
    except (ValueError, AssertionError) as exc:
        # Never echo seal/mechanism diagnostics to the client.
        LOG.info("quote refused: %s", exc)
        raise ApiError(
            400,
            "invalid_quote",
            "Invalid quote request",
            "size or tier is outside the sealed envelope",
        ) from exc


@router.post("/reserve", summary="Bind a reservation to a quote")
async def reserve_route(
    body: ReserveRequest,
    principal: Principal = Depends(require("workloads:write")),
) -> dict[str, Any]:
    book = _book_singleton()
    try:
        reservation = reserve(
            book,
            CONTRACT_VERSION,
            live_evidence_hash(),
            body.quote,
            body.idempotency_key,
            tenant_id=principal.tenant_id,
        )
    except Refusal as exc:
        raise _refusal_to_api(exc) from exc
    return {
        "id": reservation.id,
        "tenant_id": reservation.tenant_id,
        "tier": reservation.tier,
        "size": reservation.size,
        "space_bytes": reservation.space_bytes,
        "expires_at": reservation.expires_at,
        "quote_hash": reservation.quote_hash,
        "contract_version": reservation.contract_version,
        "evidence_hash": reservation.evidence_hash,
    }


@router.post("/admit", summary="Admit a run against a reservation")
async def admit_route(
    body: AdmitRequest,
    principal: Principal = Depends(require("workloads:write")),
) -> dict[str, Any]:
    book = _book_singleton()
    try:
        result = admit(
            book,
            body.reservation_id,
            body.actual_size,
            tenant_id=principal.tenant_id,
        )
    except Refusal as exc:
        raise _refusal_to_api(exc) from exc
    # Admission is already stored on the reservation for idempotent retry.
    # A durable ledger miss must not strand the client on already_consumed.
    try:
        _ledger_singleton().record(result, tenant_id=principal.tenant_id)
    except OSError:
        LOG.exception(
            "utilisation ledger write failed for %s; retry will re-record",
            body.reservation_id,
        )
    return result


CAPACITY_OPENAPI_PATHS = (
    "/v1/capacity/pool",
    "/v1/capacity/quote",
    "/v1/capacity/reserve",
    "/v1/capacity/admit",
)


def capacity_openapi_fragment(openapi: dict[str, Any]) -> dict[str, Any]:
    """Extract sealed capacity routes from a live OpenAPI document.

    Never hand-keep this map: the CI gate must seal what the app actually
    serves, or the fragment drifts and the gate passes on a stale copy.
    """
    paths = openapi.get("paths") or {}
    missing = [path for path in CAPACITY_OPENAPI_PATHS if path not in paths]
    if missing:
        raise AssertionError(f"live OpenAPI missing capacity routes: {missing}")
    fragment = {path: paths[path] for path in CAPACITY_OPENAPI_PATHS}
    seal_schema(fragment, context="procurement.live_capacity_openapi")
    return fragment


def openapi_fragment() -> dict[str, Any]:
    """Seal capacity routes from the live API app OpenAPI document."""
    # Local import: creating the app pulls auth env that tests may set late.
    from chronus.service.api.app import create_app

    return capacity_openapi_fragment(create_app().openapi())
