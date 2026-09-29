"""Runtime construction and HTTP-neutral request handling."""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping

from .audit import HashChainAudit, digest
from .entitlements import SubscriptionAuthority
from .guardian import ALHaras, GuardianPolicy
from .models import GuardianRequest
from .settings import ALHarasSettings

EvidenceProvider = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def build_guardian(settings: ALHarasSettings) -> ALHaras:
    return ALHaras(
        authority=SubscriptionAuthority(settings.keyring, settings.issuer),
        policy=GuardianPolicy(
            version=settings.policy_version,
            capability=settings.capability,
            max_payload_bytes=settings.max_payload_bytes,
            require_intelligence_evidence=settings.require_intelligence_evidence,
        ),
        audit=HashChainAudit(settings.audit_path),
    )


class GuardianAPI:
    """Framework-neutral API facade used in both repositories."""

    def __init__(
        self,
        guardian: ALHaras,
        settings: ALHarasSettings,
        evidence_provider: EvidenceProvider | None = None,
    ) -> None:
        self.guardian = guardian
        self.settings = settings
        self.evidence_provider = evidence_provider

    def public_status(self) -> dict[str, Any]:
        return {
            "service": "al-haras",
            "version": "1.0.1",
            "configured": bool(tuple(self.guardian.authority.active_key_ids())),
            "subscription_required": True,
            "subscription_url": self.settings.subscription_url,
            "capability": self.settings.capability,
            "raw_payload_persisted": False,
        }

    def evaluate(
        self,
        *,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        now: int | None = None,
        include_evidence: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        tenant_id = headers.get("x-hyba-tenant", "").strip()
        authorization = headers.get("authorization", "").strip()
        actor = headers.get("x-hyba-actor", "").strip()
        if not isinstance(body, Mapping):
            return self._boundary_denial(
                tenant_id=tenant_id or "UNKNOWN",
                actor=actor or "UNKNOWN",
                body={},
                reason="JSON_OBJECT_REQUIRED",
                status=400,
                now=now,
            )
        if not tenant_id or not actor:
            return self._boundary_denial(
                tenant_id=tenant_id or "UNKNOWN",
                actor=actor or "UNKNOWN",
                body=body,
                reason="TENANT_AND_ACTOR_REQUIRED",
                status=400,
                now=now,
            )
        try:
            request = GuardianRequest(
                tenant_id=tenant_id,
                operation=str(body.get("operation", "")).strip(),
                resource=str(body.get("resource", "")).strip(),
                payload=body.get("payload", {}),
                actor=actor,
                request_id=str(body.get("request_id", "")).strip()
                or __import__("uuid").uuid4().hex,
            )
        except ValueError as exc:
            return self._boundary_denial(
                tenant_id=tenant_id,
                actor=actor,
                body=body,
                reason=f"MALFORMED_REQUEST:{exc}",
                status=400,
                now=now,
            )
        if not authorization.startswith("Bearer "):
            verdict = self.guardian.evaluate(
                request,
                subscription_token="",
                now=now,
            )
            payload = verdict.to_dict()
            payload["subscription_url"] = self.settings.subscription_url
            return 402, payload
        admission, denial = self.guardian.preflight(
            request,
            subscription_token=authorization[7:].strip(),
            now=now,
        )
        if denial is not None:
            return 403, denial.to_dict()
        if admission is None:  # pragma: no cover - defensive invariant.
            raise RuntimeError("preflight produced neither admission nor denial")
        evidence = None
        observation = body.get("observation")
        if self.evidence_provider is not None:
            if not isinstance(observation, Mapping):
                verdict = self.guardian.complete(
                    admission,
                    intelligence_error="OBSERVATION_REQUIRED",
                )
                return 400, verdict.to_dict()
            try:
                evidence = self.evidence_provider(observation)
            except Exception as exc:
                verdict = self.guardian.complete(
                    admission,
                    intelligence_error=type(exc).__name__,
                )
                return 503, verdict.to_dict()
        verdict = self.guardian.complete(
            admission,
            intelligence_evidence=evidence,
        )
        status = 200 if verdict.allowed else 403
        response = verdict.to_dict()
        if verdict.allowed and include_evidence:
            response["intelligence_evidence"] = evidence
        return status, response

    def _boundary_denial(
        self,
        *,
        tenant_id: str,
        actor: str,
        body: Mapping[str, Any],
        reason: str,
        status: int,
        now: int | None,
    ) -> tuple[int, dict[str, Any]]:
        request = GuardianRequest(
            tenant_id=tenant_id,
            operation=str(body.get("operation") or "boundary.admission"),
            resource=str(body.get("resource") or "api/v1/security/evaluate"),
            payload=body.get("payload", {}) if isinstance(body.get("payload", {}), Mapping) else {},
            actor=actor,
        )
        evaluated_at = int(time.time() if now is None else now)
        verdict = self.guardian.record_boundary_verdict(
            request,
            allowed=False,
            reason=reason,
            subscription_id=None,
            payload_hash=digest(request.payload),
            evaluated_at=evaluated_at,
        )
        return status, verdict.to_dict()