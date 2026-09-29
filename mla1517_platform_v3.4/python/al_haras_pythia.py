"""PYTHIPhiMiner-local AL HARAS wiring to the canonical TOE bridge."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

from al_haras.audit import HashChainAudit
from al_haras.entitlements import SubscriptionAuthority
from al_haras.guardian import ALHaras, GuardianPolicy
from al_haras.runtime import GuardianAPI, build_guardian
from al_haras.settings import ALHarasSettings


@lru_cache(maxsize=1)
def _toe_bridge():
    from toe.bridge import TOEBridge

    return TOEBridge()


def _toe_evidence(observation: Mapping[str, Any]) -> Mapping[str, Any]:
    bridge = _toe_bridge()
    result = bridge.predict(dict(observation))
    if not isinstance(result, Mapping) or not result.get("available", False):
        raise RuntimeError("TOE prediction unavailable")
    required = (
        "state_tomography",
        "trajectory_prediction",
        "causal_analysis",
        "causal_ladder",
        "exact_tensor",
    )
    unavailable = [
        name
        for name in required
        if not isinstance(result.get(name), Mapping) or not result[name].get("available", False)
    ]
    if unavailable:
        raise RuntimeError(f"TOE capabilities unavailable: {','.join(unavailable)}")
    execution = bridge.execution_evidence()
    if not isinstance(execution, Mapping):
        raise RuntimeError("TOE execution evidence unavailable")
    return {
        "schema_version": "pythia.toe.guardian-evidence.v1",
        "source": "toe.bridge.TOEBridge",
        "result": result,
        "execution_evidence": execution,
    }


@lru_cache(maxsize=1)
def pythia_guardian_api() -> GuardianAPI:
    """Build the guardian, degrading to an in-memory audit chain when the
    platform cannot provide POSIX file locking (e.g. Windows dev hosts).

    The degraded mode is explicit in ``public_status`` (``audit_durable``)
    so operators can see the ledger is volatile rather than durable. Real
    corruption still fails closed: a malformed existing chain without
    quarantine enabled raises, and the caller turns it into a 503.
    """
    settings = ALHarasSettings.from_env(service="pythia")
    try:
        guardian = build_guardian(settings)
    except RuntimeError:
        guardian = ALHaras(
            authority=SubscriptionAuthority(settings.keyring, settings.issuer),
            policy=GuardianPolicy(
                version=settings.policy_version,
                capability=settings.capability,
                max_payload_bytes=settings.max_payload_bytes,
                require_intelligence_evidence=settings.require_intelligence_evidence,
            ),
            audit=HashChainAudit(),
            boundary_audit=HashChainAudit(),
        )
    return GuardianAPI(
        guardian,
        settings,
        evidence_provider=_toe_evidence,
    )
