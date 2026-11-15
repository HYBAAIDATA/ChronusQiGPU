"""Tenant lease, issued by scripts/licensing/issue_lease.py.

The file format is deliberately minimal so it can be swapped for whatever the
licensing scripts actually emit. Missing file means unmanaged, not expired.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import Depends

from chronus.service.api.errors import ApiError
from chronus.service.api.schemas import Lease
from chronus.service.api.security import Principal, current_principal


def load_lease(tenant_id: str) -> Lease:
    path = os.getenv("CHRONUS_LEASE_FILE", "")
    if not path:
        return Lease(tenant_id=tenant_id, tier="unmanaged", entitlements=[], expires_at=None)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ApiError(500, "lease_unreadable", "Lease unreadable", str(exc))
    if raw.get("tenant_id") != tenant_id:
        raise ApiError(403, "lease_tenant_mismatch", "Lease is for another tenant")
    expires = raw.get("expires_at")
    return Lease(
        tenant_id=tenant_id, tier=str(raw.get("tier", "unmanaged")),
        entitlements=list(raw.get("entitlements", [])),
        expires_at=datetime.fromisoformat(expires) if expires else None,
        revoked=bool(raw.get("revoked", False)),
    )


async def current_lease(principal: Principal = Depends(current_principal)) -> Lease:
    lease = load_lease(principal.tenant_id)
    if lease.revoked:
        raise ApiError(403, "lease_revoked", "Lease revoked")
    if lease.expires_at and lease.expires_at <= datetime.now(timezone.utc):
        raise ApiError(403, "lease_expired", "Lease expired",
                       f"Expired {lease.expires_at.isoformat()}.")
    return lease
