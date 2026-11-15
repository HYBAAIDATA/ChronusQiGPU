"""Bearer-token authentication and scope enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from chronus.service.api.errors import ApiError

# Closed vocabulary. A typo in config is dropped, not silently accepted.
SCOPES = frozenset({
    "workloads:read", "workloads:write", "fleet:read", "evidence:read", "admin",
})

_bearer = HTTPBearer(auto_error=False, scheme_name="TenantToken")
_table_cache: dict[str, "Principal"] | None = None


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    scopes: frozenset[str]

    def require(self, scope: str) -> None:
        if "admin" in self.scopes or scope in self.scopes:
            return
        raise ApiError(
            403, "insufficient_scope", "Insufficient scope",
            f"This token lacks the '{scope}' scope.",
        )


def reset_token_cache() -> None:
    """Drop the parsed token table. Call after changing the environment."""
    global _table_cache
    _table_cache = None


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_table() -> dict[str, Principal]:
    global _table_cache
    if _table_cache is not None:
        return _table_cache

    raw = os.getenv("CHRONUS_TENANT_TOKENS", "").strip()
    if not raw:
        raise ApiError(500, "auth_not_configured", "Authentication is not configured",
                       "CHRONUS_TENANT_TOKENS is unset.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(500, "auth_not_configured", "Authentication is not configured",
                       f"CHRONUS_TENANT_TOKENS is not valid JSON: {exc.msg}.")

    # Accept {"<token>": {...}} or [{"token": ..., ...}].
    pairs: list[tuple[str | None, object]] = []
    if isinstance(data, dict):
        pairs = list(data.items())
    elif isinstance(data, list):
        pairs = [(item.get("token"), item) for item in data if isinstance(item, dict)]
    else:
        raise ApiError(500, "auth_not_configured", "Authentication is not configured",
                       "CHRONUS_TENANT_TOKENS must be an object or array.")

    table: dict[str, Principal] = {}
    for token, meta in pairs:
        if not token or not isinstance(meta, dict) or not meta.get("tenant_id"):
            continue
        scopes = frozenset(s for s in meta.get("scopes", []) if s in SCOPES)
        table[_digest(str(token))] = Principal(str(meta["tenant_id"]), scopes)

    if not table:
        raise ApiError(500, "auth_not_configured", "Authentication is not configured",
                       "No usable token entries found.")

    _table_cache = table
    return table


async def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or not credentials.credentials.strip():
        raise ApiError(401, "missing_token", "Missing bearer token",
                       "Send 'Authorization: Bearer <token>'.",
                       headers={"WWW-Authenticate": 'Bearer realm="chronus"'})

    presented = _digest(credentials.credentials.strip())
    for known, principal in _token_table().items():
        if secrets.compare_digest(presented, known):
            return principal

    raise ApiError(401, "invalid_token", "Invalid bearer token",
                   headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})


def require(scope: str):
    """Dependency factory: 401 if unauthenticated, 403 if the scope is missing."""
    async def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        principal.require(scope)
        return principal
    return dependency
