"""Fail-closed AL HARAS admission for shared mining administration controls.

Tenant credentials authenticate a tenant, not an operator. These global
controls require a verified JWT system-admin principal, explicit single-tenant
ownership, a subject allowlist and a durable THESEUS admission event.
Admission evidence is NOT evidence that the requested action succeeded.
"""
from __future__ import annotations

import json
import os
import threading
import time

from fastapi import Depends, HTTPException, Request, status

from chronus.service.auth_middleware import (
    AuthenticatedIdentity,
    Role,
    get_current_identity,
)
from chronus.service.dependencies import auth_service
from chronus.storage.durable import DurableTheseusService

_ADMISSION_EVENT = "MINING_ADMIN_OPERATOR_ADMITTED"
_ADMISSION_SCHEMA = "chronus.mining-admin-admission/1"

# One durable-custody handle per audit path. Building DurableTheseusService per
# request re-ran bootstrap plus full store verification on every call - including
# GETs - and appended an admission event per status poll, so read traffic grew
# the custody journal. Reuse keeps admission fail-closed: custody availability
# and full store integrity are enforced when the handle is built, mutations
# verify journal continuity per request, and reads append nothing.
_CUSTODY_HANDLES: dict[str, DurableTheseusService] = {}
_CUSTODY_LOCK = threading.Lock()


def _get_custody(audit_path: str) -> DurableTheseusService:
    with _CUSTODY_LOCK:
        custody = _CUSTODY_HANDLES.get(audit_path)
        if custody is None:
            custody = DurableTheseusService(audit_path)
            _CUSTODY_HANDLES[audit_path] = custody
        return custody


def _reset_custody_cache() -> None:
    """Test hook: drop cached handles so each test starts from a fresh store."""
    with _CUSTODY_LOCK:
        _CUSTODY_HANDLES.clear()


def get_mining_admin_operator(
    request: Request,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
) -> str:
    """Resolve trusted identity and audit admission before handling.

    Mutating requests append a durable admission event and verify journal
    continuity per request. Reads require available, integrity-verified custody
    - ensured at handle construction - and append nothing, so status polls do
    not grow the custody journal. Fail closed for legacy static tenant tokens,
    dev-permissive JWTs, missing operator roster, cross-tenant requests and
    unavailable custody.
    """
    auth_service.check_rate_limit(identity.tenant_id)
    subjects_raw = os.getenv("CHRONUS_MINING_ADMIN_SUBJECTS", "")
    owning_tenant = os.getenv("CHRONUS_MINING_ADMIN_TENANT_ID", "")
    audit_path = os.getenv("CHRONUS_MINING_ADMIN_CUSTODY_PATH", "")
    stable_jwt_key = os.getenv("CHRONUS_JWT_SECRET", "")
    try:
        subjects = json.loads(subjects_raw)
    except (TypeError, ValueError):
        subjects = None

    approved = (
        identity.is_jwt is True
        and Role.SYSTEM_ADMIN in identity.roles
        and os.getenv("CHRONUS_DEV_JWT_PERMISSIVE", "0") != "1"
        and isinstance(stable_jwt_key, str) and len(stable_jwt_key) >= 32
        and isinstance(subjects, list)
        and bool(subjects)
        and all(isinstance(s, str) and s.strip() for s in subjects)
        and identity.user_id in subjects
        and bool(owning_tenant)
        and identity.tenant_id == owning_tenant
        and bool(audit_path)
    )
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AL HARAS mining administration admission denied",
        )

    payload = json.dumps(
        {
            "schema": _ADMISSION_SCHEMA,
            "actor_id": identity.user_id,
            "tenant_id": identity.tenant_id,
            "method": request.method,
            "path": request.url.path,
            "event": "OPERATOR_ADMITTED_NOT_ACTION_COMPLETED",
            "timestamp_ns": time.time_ns(),
        },
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    try:
        custody = _get_custody(audit_path)
        if request.method.upper() != "GET":
            custody.append_journal_event(identity.tenant_id, _ADMISSION_EVENT, payload)
            if not custody.verify_journal_continuity(identity.tenant_id):
                raise RuntimeError("mining administration audit journal invalid")
        # Reads: custody availability and full store integrity were enforced
        # when the handle was built; per-request continuity is a mutation
        # guarantee, and an empty journal on a fresh store must not fail a read.
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AL HARAS admission denied: durable audit unavailable",
        ) from exc
    return identity.tenant_id
