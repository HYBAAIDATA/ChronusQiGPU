"""Host-composed tenant routing for the in-process unified platform.

The embedding host authenticates the actor BEFORE requesting a session. These
objects are not a login protocol, RPC dispatcher or adversarial Python/process
boundary. Tenant members receive detached data results, never a live runtime.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock

from .platform import UnifiedAnalyticsPlatform
from .security import AccessDenied, ROLES

# Explicit allowlist: new facade methods do not automatically become tenant APIs.
# Credential-bearing connector management stays in the trusted host control plane.
TENANT_OPERATIONS = frozenset(
    {
        "start",
        "catalog",
        "operations_note",
        "entities",
        "quality",
        "null_policy",
        "batches",
        "quarantine",
        "release",
        "batch_null_rate",
        "integrate",
        "ingest_rows",
        "export_records",
        "import_records",
        "govern",
        "train",
        "retrain",
        "predict",
        "transfer",
        "ask",
        "analyze",
        "analysis_receipts",
        "feedback",
        "dashboard_for",
        "health",
        "require_gate",
        "heal",
        "watch",
        "benchmark_processing",
        "optimize",
        "file_patent",
        "case_financial_services",
        "scale",
        "displacement",
        "retire",
        "economics",
        "scenario",
        "recognize_value",
        "industry",
        "run_application",
        "phases",
    }
)
_HOST_ACTOR = "__unified_tenant_host__"


def _name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or value != value.strip()
        or value.startswith("__unified_")
    ):
        raise ValueError(
            "identifier must be a nonempty, trimmed, non-reserved string <= 128 characters"
        )
    return value


@dataclass(frozen=True)
class TenantResult:
    tenant_id: str
    operation: str
    value: object


@dataclass(frozen=True)
class TenantSession:
    """A host-verified identity/scope selection, not an authentication credential.

    The host must not construct this from an unverified client actor parameter.
    Membership and current role are checked again for every invocation.
    """

    _gateway: TenantGateway = field(repr=False)
    tenant_id: str
    actor: str

    def call(self, operation: str, /, *args, **kwargs) -> TenantResult:
        return self._gateway._invoke(
            self.tenant_id, self.actor, operation, args, kwargs
        )


@dataclass
class _Tenant:
    platform: UnifiedAnalyticsPlatform
    members: set[str] = field(default_factory=set)
    lock: object = field(default_factory=RLock)


class TenantGateway:
    """Trusted composition root: provision/grant/revoke/configure are host-only.

    Each tenant owns a separate, enforced platform: data/indexes/policies/models,
    connectors, health/drift counters, governance state and receipt chains. Calls
    serialize per tenant so a completed revoke/downgrade cannot leave a later
    invocation running under an old grant. Different tenants have separate locks.
    This costs same-tenant throughput and provides no durable/distributed isolation.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._tenants: dict[str, _Tenant] = {}

    def provision(self, tenant_id: str) -> None:
        tenant_id = _name(tenant_id)
        with self._lock:
            if tenant_id in self._tenants:
                raise ValueError("tenant already provisioned")
            platform = UnifiedAnalyticsPlatform(
                security_enforced=True, tenant_id=tenant_id
            )
            platform.security.grant(_HOST_ACTOR, "admin")
            self._tenants[tenant_id] = _Tenant(platform)

    def _tenant(self, tenant_id: str) -> _Tenant:
        _name(tenant_id)
        with self._lock:
            tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise AccessDenied("tenant access denied")
        return tenant

    def grant(self, tenant_id: str, actor: str, role: str) -> None:
        actor = _name(actor)
        if role not in ROLES:
            raise ValueError("unknown role")
        tenant = self._tenant(tenant_id)
        with tenant.lock, tenant.platform.security.as_actor(_HOST_ACTOR):
            tenant.platform.security.grant(actor, role)
            tenant.members.add(actor)

    def revoke(self, tenant_id: str, actor: str) -> None:
        actor = _name(actor)
        tenant = self._tenant(tenant_id)
        with tenant.lock, tenant.platform.security.as_actor(_HOST_ACTOR):
            tenant.platform.security.revoke(actor)
            tenant.members.discard(actor)

    def session(self, *, tenant_id: str, verified_actor: str) -> TenantSession:
        actor = _name(verified_actor)
        tenant = self._tenant(tenant_id)
        with tenant.lock:
            if actor not in tenant.members:
                raise AccessDenied("tenant access denied")
        return TenantSession(self, tenant_id, actor)

    def configure_connector(
        self, tenant_id: str, connector_id: str, credentials: dict
    ) -> dict:
        """Bind host-approved credentials/transports; never return the live driver."""
        tenant = self._tenant(tenant_id)
        with tenant.lock, tenant.platform.security.as_actor(_HOST_ACTOR):
            bound = tenant.platform.connect(connector_id, credentials)
            return {
                "tenant_id": tenant_id,
                "connector_id": bound.spec.id,
                "protocol": bound.spec.protocol,
                "entities": list(bound.spec.entities),
            }

    def _invoke(
        self, tenant_id: str, actor: str, operation: str, args: tuple, kwargs: dict
    ) -> TenantResult:
        _name(actor)
        tenant = self._tenant(tenant_id)
        with tenant.lock:
            if actor not in tenant.members:
                raise AccessDenied("tenant access denied")
            if not isinstance(operation, str) or operation not in TENANT_OPERATIONS:
                raise AccessDenied("operation is not a tenant API")
            # Roles remain the canonical facade policy; do not duplicate them here.
            with tenant.platform.security.as_actor(actor):
                value = getattr(tenant.platform, operation)(*args, **kwargs)
                return TenantResult(tenant_id, operation, deepcopy(value))
