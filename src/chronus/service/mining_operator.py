"""Fail-closed AL HARAS admission for shared mining administration controls.

Tenant credentials authenticate a tenant, not an operator. These global
controls require a verified JWT system-admin principal, explicit single-tenant
ownership, a subject allowlist and a durable THESEUS admission event.
Admission evidence is NOT evidence that the requested action succeeded.
"""
from __future__ import annotations

import json
import os
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


def get_mining_admin_operator(
    request: Request,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
) -> str:
    """Resolve trusted identity and persist an admission audit before handling.

    Fail closed for legacy static tenant tokens, dev-permissive JWTs, missing
    operator roster, cross-tenant requests and unavailable custody.
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
        custody = DurableTheseusService(audit_path)
        custody.append_journal_event(identity.tenant_id, _ADMISSION_EVENT, payload)
        if not custody.verify_journal_continuity(identity.tenant_id):
            raise RuntimeError("mining administration audit journal invalid")
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AL HARAS admission denied: durable audit unavailable",
        ) from exc
    return identity.tenant_id
