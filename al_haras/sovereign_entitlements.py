"""Provider-neutral sovereign entitlement verification boundary."""

from __future__ import annotations
from dataclasses import asdict, dataclass
import json
import time
from typing import Callable, Iterable


class SovereignEntitlementError(PermissionError):
    pass


@dataclass(frozen=True)
class SovereignEntitlement:
    issuer: str
    audience: str
    subject: str
    tenant: str
    capabilities: tuple[str, ...]
    token_id: str
    issued_at: int
    expires_at: int
    hsm_key_ref: str
    revocation_state: str = "ACTIVE"
    rotation_overlap: bool = False

    def canonical(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()


class ReplayCache:
    def __init__(self):
        self._ids: set[str] = set()

    def contains(self, jti: str) -> bool:
        return jti in self._ids

    def insert(self, jti: str) -> None:
        self._ids.add(jti)


def verify_sovereign_entitlement(
    entitlement: SovereignEntitlement,
    signature: bytes,
    *,
    verifier: Callable[[bytes, bytes, str, str], bool],
    service_audience: str,
    required_capability: str,
    replay_cache: ReplayCache,
    revoked: Iterable[str] = (),
    active_key_refs: Iterable[str] = (),
    now: int | None = None,
) -> SovereignEntitlement:
    current = int(time.time() if now is None else now)
    if entitlement.audience != service_audience:
        raise SovereignEntitlementError("audience mismatch")
    if entitlement.issued_at > current or entitlement.expires_at <= current:
        raise SovereignEntitlementError("entitlement outside validity window")
    if not entitlement.token_id or replay_cache.contains(entitlement.token_id):
        raise SovereignEntitlementError("token replay")
    if entitlement.token_id in set(revoked) or entitlement.revocation_state != "ACTIVE":
        raise SovereignEntitlementError("entitlement revoked")
    if entitlement.hsm_key_ref not in set(active_key_refs):
        raise SovereignEntitlementError("inactive hardware key reference")
    if required_capability not in entitlement.capabilities:
        raise SovereignEntitlementError("capability missing")
    if not verifier(
        entitlement.canonical(), signature, entitlement.issuer, entitlement.hsm_key_ref
    ):
        raise SovereignEntitlementError("invalid asymmetric signature")
    replay_cache.insert(entitlement.token_id)
    return entitlement
