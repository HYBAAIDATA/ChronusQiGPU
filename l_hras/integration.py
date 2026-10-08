"""Integration — Part XII: SIEM, SOAR, TI feeds, SSO, policy engine.

Endpoints are optional. A null endpoint is a real decision in the
blueprint (``IF siem is null: RETURN``), implemented here as recording
adapters that keep the emitted payload — the emission itself is the
integration contract; transport is declared by the endpoint scheme.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Iterable, Iterator, Optional

from .result import Ok, Result
from .types import PolicyBundle, SSOConfig


class SIEM:
    """Refusal sink — receives every refused request + reason."""

    def __init__(self, endpoint: Optional[str]):
        self.endpoint = endpoint
        self.sent: list[dict[str, Any]] = []

    def send(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)
        if self.endpoint and self.endpoint.startswith("http"):
            body = json.dumps(payload, default=str).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint, data=body, headers={"Content-Type": "application/json"}
            )
            try:
                urllib.request.urlopen(req, timeout=5).close()
            except OSError:
                pass  # emission is recorded; transport is best-effort


class SOAR:
    """Escalation sink — invokes declared playbooks on escalation."""

    def __init__(self, endpoint: Optional[str]):
        self.endpoint = endpoint
        self.playbooks: list[dict[str, Any]] = []

    def playbook(self, escalation: Any, context: dict[str, Any]) -> None:
        call = {"escalation": getattr(escalation, "value", escalation), **context}
        self.playbooks.append(call)
        if self.endpoint and self.endpoint.startswith("http"):
            body = json.dumps(call, default=str).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint, data=body, headers={"Content-Type": "application/json"}
            )
            try:
                urllib.request.urlopen(req, timeout=5).close()
            except OSError:
                pass


class TIFeed:
    """Threat-intelligence feed — ``next()`` yields indicators."""

    def __init__(self, url: str, indicators: Optional[Iterable[Any]] = None):
        self.url = url
        self._indicators: Iterator[Any] = iter(indicators or [])

    def next(self) -> Any:
        return next(self._indicators, None)


def open_siem(endpoint: Optional[str]) -> Optional[SIEM]:
    return None if endpoint is None else SIEM(endpoint)


def open_soar(endpoint: Optional[str]) -> Optional[SOAR]:
    return None if endpoint is None else SOAR(endpoint)


def open_feed(url: str, indicators: Optional[Iterable[Any]] = None) -> TIFeed:
    return TIFeed(url, indicators)


def siem_emit(siem: Optional[SIEM], event: Any, reason: str, instance_id: str = "") -> None:
    if siem is None:
        return
    siem.send(
        {
            "event": (
                event.canonical_payload() if hasattr(event, "canonical_payload") else str(event)
            ),
            "reason": reason,
            "instance": instance_id,
        }
    )


def soar_invoke(soar: Optional[SOAR], escalation: Any, adversary: Any, profile: Any) -> None:
    if soar is None:
        return
    soar.playbook(
        escalation,
        {
            "adversary": vars(adversary) if adversary is not None else None,
            "profile": vars(profile) if profile is not None else None,
        },
    )


def ingest_ti_feeds(feeds: list[TIFeed], joint: Any, limit: int = 1000) -> int:
    """One ingestion pass over every feed — bounded so the loop is
    testable; the blueprint's forever-loop is a scheduled caller."""
    ingested = 0
    for feed in feeds:
        for _ in range(limit):
            indicator = feed.next()
            if indicator is None:
                break
            joint.ti_cache.append(indicator)
            ingested += 1
    return ingested


def sso_authenticate(provider: SSOConfig, token: str) -> bool:
    return provider.verify(token)


# ---------------------------------------------------------------------------
# Policy engine (PB1–PB2)
# ---------------------------------------------------------------------------


class PolicyEngine:
    """Deny-overrides-allow rule engine over the signed bundle."""

    def __init__(self, bundle: PolicyBundle):
        self.bundle = bundle

    @classmethod
    def load(cls, bundle: PolicyBundle) -> "PolicyEngine":
        return cls(bundle)

    def allows(self, request: Any) -> bool:
        denies = [r for r in self.bundle.rules if r.effect == "deny" and r.matches(request)]
        if denies:
            return False
        allows = [r for r in self.bundle.rules if r.effect == "allow" and r.matches(request)]
        if allows:
            return True
        # No matching allow is a denial unless the signed policy bundle
        # explicitly opts into default-allow.  In particular, an empty rule
        # set must never become an accidental allow-all policy.
        return bool(self.bundle.default_allow)

    def throttle_mode_for(self, reason: str, scope: str) -> Optional[dict[str, Any]]:
        modes = self.bundle.throttle_modes
        return modes.get(f"{reason}:{scope}") or modes.get(reason)

    def authorize(self, actor: str, action: str, resource: str) -> bool:
        shadow = _AuthRequest(actor=actor, action=action, resource=resource)
        return self.allows(shadow)

    def subset(self, tenant_id: str) -> "PolicyEngine":
        return PolicyEngine(self.bundle.subset(tenant_id))


class _AuthRequest:
    """Authorization queries evaluated through the same rule surface."""

    def __init__(self, actor: str, action: str, resource: str):
        from .types import AdversaryClass, RequestKind

        self.actor = actor
        self.action = action
        self.resource = resource
        self.scope = "global"
        self.kind = RequestKind.BENIGN
        self.adversary_class = AdversaryClass.BENIGN


def open_policy_engine(bundle: PolicyBundle) -> Result[PolicyEngine]:
    return Ok(PolicyEngine.load(bundle))


def policy_bundle_valid(bundle: Optional[PolicyBundle]) -> bool:
    if bundle is None:
        return False
    return (
        bundle.version is not None
        and bundle.signatures_verified
        and bundle.compliance_mappings_valid()
    )


def authorize(lhras: Any, actor: str, action: str, resource: str) -> bool:
    return lhras.policy.authorize(actor, action, resource)
