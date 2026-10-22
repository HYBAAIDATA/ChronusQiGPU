"""Explicit, local-only signed authority for whole-organism test voyages."""
import time
from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims
from euclid.runtime import EuclidRuntime


def configured_authority(creator_id="creator-1"):
    issuer = SubscriptionAuthority({"organism-fixture": b"organism-fixture-signing-key-not-production"}, "organism-tests")
    allowed = {f"{organ}.{op}" for organ, spec in EuclidRuntime.ORGANISM_SPECIALISTS.items() for op in spec[3]}
    allowed.update({"aux-a.probe", "aux-b.probe", "salamander.requalify"})
    guardian = ALHaras(issuer, GuardianPolicy(version="organism-tests/2", allowed_operations=frozenset(allowed)), HashChainAudit())
    now = int(time.time())
    tokens = {tenant: issuer.issue(SubscriptionClaims(
        subscription_id="fixture-" + tenant, tenant_id=tenant, issuer="organism-tests",
        key_id="organism-fixture", capabilities=("hyba.security",), actors=("user-1",),
        not_before=now-10, expires_at=now+600,
    )) for tenant in {"tenant-a", creator_id}}
    def provider(tenant, actor):
        return tokens.get(tenant, "") if actor == "user-1" else ""
    return guardian, tokens["tenant-a"], provider
