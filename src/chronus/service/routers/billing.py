"""Hermetic billing telemetry: signed per-tenant usage receipts.

Aggregates the authenticated tenant's workload usage from the store and
binds the usage digest to a process-local Ed25519 signature, verifiable via
the existing /verify receipt machinery. Receipts are process-local and are
not invoices; CCU pricing policy is a deployment decision.
"""

import hashlib
import json

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from chronus.service.dependencies import get_current_tenant
from chronus.service.routers import workloads
from chronus.service.routers.verify import _ed25519_signer

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/usage",
    summary="Signed usage receipt for the authenticated tenant",
    description="Aggregate workload usage and return it with an Ed25519-signed digest.",
)
async def usage_receipt(tenant_id: Optional[str] = Depends(get_current_tenant)) -> dict:
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid authentication token required for billing usage.",
        )
    items, total = workloads.workload_store.list_for_tenant(
        tenant_id, offset=0, limit=100
    )
    completed = [item for item in items if item.status == "COMPLETED"]
    ccu_total = sum(item.ccu_cost or 0.0 for item in completed)
    usage = {
        "tenant_id": tenant_id,
        "workloads_visible": total,
        "workloads_completed": len(completed),
        "ccu_total": ccu_total,
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
    }
