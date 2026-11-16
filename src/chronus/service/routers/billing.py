"""Tenant-scoped, evidence-first billing usage and opt-in Hermiten delivery.

The local usage receipt is process-signed, not an invoice or a proof of
hardware metering. The opt-in remote adapter requires explicit deployment
configuration and durable THESEUS custody; no test accounts, fabricated FLOPs
or assumed provider URL are supplied.
"""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from chronus.service.auth_middleware import (
    AuthenticatedIdentity,
    Role,
    require_roles,
)
from chronus.service.dependencies import get_current_tenant
from chronus.service.routers import workloads
from chronus.service.routers.verify import _ed25519_signer

router = APIRouter(prefix="/billing", tags=["billing"])

_PAGE_SIZE = 100
_MAX_BILLING_RECORDS = 100_000


def _workloads_for_tenant(tenant_id: str) -> tuple[list, int]:
    """Read every page; refuse an incomplete aggregation instead of underbilling."""
    first, total = workloads.workload_store.list_for_tenant(
        tenant_id, offset=0, limit=_PAGE_SIZE
    )
    if total > _MAX_BILLING_RECORDS:
        raise HTTPException(
            status_code=503, detail="Billing aggregation exceeds the configured scan limit."
        )
    records = list(first)
    while len(records) < total:
        batch, current_total = workloads.workload_store.list_for_tenant(
            tenant_id, offset=len(records), limit=_PAGE_SIZE
        )
        # The store exposes a paginated read, not an atomic billing snapshot.
        # A changing total must not silently produce a definitive aggregate.
        if current_total != total or not batch:
            raise HTTPException(
                status_code=409, detail="Workload ledger changed during billing aggregation; retry."
            )
        records.extend(batch)
    if len(records) != total:
        raise HTTPException(status_code=409, detail="Incomplete billing ledger scan.")
    return records, total


def _reported_ccu(value: object) -> Decimal:
    """Parse recorded CCU without treating an absent/invalid meter as zero."""
    if value is None or isinstance(value, bool):
        raise ValueError("No recorded CCU")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid recorded CCU") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Recorded CCU must be finite and nonnegative")
    return amount


@router.get(
    "/usage",
    summary="Signed usage receipt for the authenticated tenant",
    description="Tenant-scoped complete ledger count; metering is explicitly evidence-qualified.",
)
async def usage_receipt(tenant_id: Optional[str] = Depends(get_current_tenant)) -> dict:
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid authentication token required for billing usage.",
        )
    items, total = _workloads_for_tenant(tenant_id)
    completed = [item for item in items if item.status == "COMPLETED"]
    amounts = []
    missing = 0
    for item in completed:
        try:
            amounts.append(_reported_ccu(item.ccu_cost))
        except ValueError:
            missing += 1
    usage = {
        "tenant_id": tenant_id,
        "workloads_visible": total,
        "workloads_completed": len(completed),
        # Compatibility-only numeric representation. The exact decimal string
        # below must be used for reconciliation; this is not a FLOP counter.
        "ccu_total": float(sum(amounts, Decimal(0))),
        "ccu_total_decimal": str(sum(amounts, Decimal(0))),
        "ccu_records_present": len(amounts),
        "ccu_records_unavailable": missing,
        "meter_quality": "REPORTED_NOT_INDEPENDENTLY_VERIFIED",
        "flops_measured": False,
        "hardware_evidence": "UNAVAILABLE",
        "billing_completeness": "INCOMPLETE" if missing else "REPORTED_ONLY",
        "by_type": {},
    }
    for item in completed:
        key = str(item.workload_type)
        usage["by_type"][key] = usage["by_type"].get(key, 0) + 1
    digest = hashlib.sha256(
        json.dumps(usage, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "usage": usage,
        "digest": digest,
        "signature_algorithm": "Ed25519",
        "signature": _ed25519_signer.sign(digest.encode("ascii")),
        "receipt_scope": "process-local",
        "invoice": False,
        "aggregation_scope": "paginated-non-atomic",
    }


def _hermiten_config(tenant_id: str) -> tuple[str, str, str, str]:
    """Read trusted deployment configuration, never a client-supplied account."""
    if os.getenv("CHRONUS_HERMITEN_USAGE_ENABLED") != "1":
        raise HTTPException(status_code=503, detail="Hermiten usage delivery is disabled.")
    endpoint = os.getenv("CHRONUS_HERMITEN_USAGE_ENDPOINT", "").strip()
    token = os.getenv("CHRONUS_HERMITEN_API_TOKEN", "").strip()
    custody_path = os.getenv("CHRONUS_THESEUS_DB_PATH", "").strip()
    parts = urlsplit(endpoint)
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.fragment):
        raise HTTPException(status_code=503, detail="Verified HTTPS billing endpoint is not configured.")
    if not token or not custody_path:
        raise HTTPException(status_code=503, detail="Billing credentials or durable custody are not configured.")
    try:
        accounts = json.loads(os.getenv("CHRONUS_HERMITEN_ACCOUNT_MAP", ""))
    except (ValueError, TypeError):
        raise HTTPException(status_code=503, detail="Hermiten tenant account mapping is not configured.") from None
    if not isinstance(accounts, dict) or not isinstance(accounts.get(tenant_id), str):
        raise HTTPException(status_code=503, detail="No Hermiten account is bound to this tenant.")
    account = accounts[tenant_id].strip()
    if not account:
        raise HTTPException(status_code=503, detail="No Hermiten account is bound to this tenant.")
    return endpoint, token, custody_path, account


def _send_hermiten_usage(
    endpoint: str, api_token: str, payload: dict, idempotency_key: str
) -> dict:
    with httpx.Client(timeout=10.0, follow_redirects=False) as client:
        response = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Idempotency-Key": idempotency_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )
    response.raise_for_status()
    if response.status_code not in (200, 201, 202):
        raise ValueError("Unexpected billing provider response.")
    acknowledgement = response.json()
    if (not isinstance(acknowledgement, dict)
            or acknowledgement.get("account_id") != payload["account_id"]
            or not isinstance(acknowledgement.get("usage_receipt_id"), str)
            or not acknowledgement["usage_receipt_id"].strip()):
        raise ValueError("Billing provider did not return a verifiable account-bound acknowledgement.")
    return acknowledgement


@router.post(
    "/hermiten/usage/{workload_id}",
    summary="Deliver recorded workload CCU to a separately configured Hermiten provider",
    description="Requires AL HARAS tenant-admin authority, tenant isolation, and THESEUS custody. Not an invoice.",
)
async def deliver_hermiten_usage(
    workload_id: UUID,
    identity: AuthenticatedIdentity = Depends(
        require_roles(Role.TENANT_ADMIN, Role.SYSTEM_ADMIN)
    ),
) -> dict:
    tenant_id = identity.tenant_id
    record = workloads.workload_store.get(str(workload_id))
    if record is None or record.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workload is not visible to this tenant.")
    if record.status != "COMPLETED" or not record.verification_receipt:
        raise HTTPException(status_code=409, detail="Workload has no completed receipt reference.")
    try:
        reported_ccu = _reported_ccu(record.ccu_cost)
    except ValueError:
        raise HTTPException(status_code=409, detail="Recorded CCU is unavailable or invalid.") from None
    endpoint, api_token, custody_path, account_id = _hermiten_config(tenant_id)
    idempotency_key = hashlib.sha256(
        f"chronus.hermiten.usage/v1:{tenant_id}:{workload_id}".encode("utf-8")
    ).hexdigest()
    payload = {
        "schema": "chronus.hermiten.usage/v1",
        "tenant_id": tenant_id,
        "account_id": account_id,
        "workload_id": str(workload_id),
        "reported_ccu": str(reported_ccu),
        "workload_receipt_reference": str(record.verification_receipt),
        "meter_quality": "REPORTED_NOT_INDEPENDENTLY_VERIFIED",
        "hardware_flops": None,
        "invoice": False,
    }
    material = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    # Fail closed before the external side effect if durable custody is absent.
    # Retrying after a lost acknowledgement must use the same idempotency key.
    try:
        from chronus.storage.durable import DurableTheseusService

        custody = DurableTheseusService(custody_path)
        intent = {
            "schema": "chronus.hermiten.delivery-intent/v1",
            "account_id": account_id,
            "workload_id": str(workload_id),
            "payload_sha256": digest,
            "idempotency_key": idempotency_key,
        }
        custody.append_journal_event(
            tenant_id, "HERMITEN_USAGE_INTENT",
            json.dumps(intent, sort_keys=True).encode("utf-8"),
        )
    except Exception:
        raise HTTPException(status_code=503, detail="THESEUS custody is unavailable; no usage was sent.") from None
    try:
        acknowledgement = _send_hermiten_usage(
            endpoint, api_token, payload, idempotency_key
        )
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Hermiten delivery has no valid provider acknowledgement.") from None
    ack = {
        "schema": "chronus.hermiten.delivery-ack/v1",
        "account_id": account_id,
        "workload_id": str(workload_id),
        "payload_sha256": digest,
        "provider_receipt_id": acknowledgement["usage_receipt_id"],
    }
    try:
        journal = custody.append_journal_event(
            tenant_id, "HERMITEN_USAGE_ACK",
            json.dumps(ack, sort_keys=True).encode("utf-8"),
        )
    except Exception:
        # Provider may already have accepted the request. No false success:
        # return a custody failure and retain the stable retry key.
        raise HTTPException(status_code=503, detail="Provider acknowledged usage but THESEUS receipt custody failed.") from None
    return {
        "status": "PROVIDER_ACKNOWLEDGED",
        "account_id": account_id,
        "workload_id": str(workload_id),
        "provider_receipt_id": acknowledgement["usage_receipt_id"],
        "payload_sha256": digest,
        "theseus_entry_hash": journal.entry_hash,
        "meter_quality": "REPORTED_NOT_INDEPENDENTLY_VERIFIED",
        "invoice": False,
    }
