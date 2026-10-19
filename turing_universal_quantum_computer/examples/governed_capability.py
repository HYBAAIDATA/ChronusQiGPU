"""Host integration example for the installed local platform distribution set.

The host supplies the real guardian, custody key and credential provider. This
module issues no entitlements and creates no successful security/recovery mock.
It is not an unauthenticated HTTP endpoint or a replacement mathematical engine.
"""

from pathlib import Path
from typing import Callable


def run_governed_program(
    program,
    *,
    root: str | Path,
    custody_key: bytes,
    guardian,
    tenant_id: str,
    creator_id: str,
    actor_id: str,
    token_provider: Callable[[str, str], str],
) -> dict:
    from aethel.enterprise.production_organism import ProductionOrganism

    with ProductionOrganism(
        root,
        hmac_key=custody_key,
        guardian=guardian,
        tenant=tenant_id,
        creator_id=creator_id,
        subscription_token_provider=token_provider,
    ) as service:
        return service.euclid.route_specialist(
            {"operation": "run-program", "program": program.to_dict(), "prefer": "exact_algebraic"},
            tenant_id=tenant_id,
            actor=actor_id,
            subscription_token=token_provider(tenant_id, actor_id),
        )
