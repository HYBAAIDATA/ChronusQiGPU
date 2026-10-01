"""Fail-closed Guardian policy and evidence evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping

from .audit import HashChainAudit, canonical_json, digest
from .entitlements import SubscriptionAuthority, SubscriptionError
from .models import Admission, GuardianRequest, GuardianVerdict

DEFAULT_ALLOWED_OPERATIONS: frozenset[str] = frozenset(
    {
        "analytics.predict",
        "analytics.explain",
        "analytics.graph.execute",
        "mining.observe",
        "security.evaluate",
        "toe.collapse",
    }
)


@dataclass(frozen=True)
class GuardianPolicy:
    version: str
    capability: str = "hyba.security"
    allowed_operations: frozenset[str] = DEFAULT_ALLOWED_OPERATIONS
    max_payload_bytes: int = 1_048_576
    require_intelligence_evidence: bool = False


class ALHaras:
    """Subscription-gated, tenant-bound Guardian decision boundary.

    ``audit`` is the durable ledger for post-authentication decisions
    (admissions, denials of entitled requests, evidence outcomes). Pre-
    authentication boundary denials — bad or missing credentials — are
    attacker-influenceable and therefore go to ``boundary_audit``, a
    volatile in-memory chain kept for observability only. If no separate
    boundary chain is supplied, boundary denials share the durable ledger.
    """

    def __init__(
        self,
        authority: SubscriptionAuthority,
        policy: GuardianPolicy,
        audit: HashChainAudit,
        boundary_audit: HashChainAudit | None = None,
    ) -> None:
        self.authority = authority
        self.policy = policy
        self.audit = audit
        self.boundary_audit = boundary_audit if boundary_audit is not None else audit

    def record_boundary_verdict(
        self,
        request: GuardianRequest,
        *,
        allowed: bool,
        reason: str,
        subscription_id: str | None,
        payload_hash: str,
        evaluated_at: int,
        intelligence_evidence: Mapping[str, Any] | None = None,
        durable: bool = True,
    ) -> GuardianVerdict:
        evidence_hash = digest(intelligence_evidence) if intelligence_evidence is not None else None
        event = {
            "schema_version": "al-haras.decision.v1",
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
            "actor": request.actor,
            "operation": request.operation,
            "resource": request.resource,
            "payload_hash": payload_hash,
            "intelligence_evidence_hash": evidence_hash,
            "allowed": allowed,
            "reason": reason,
            "subscription_id": subscription_id,
            "policy_version": self.policy.version,
            "evaluated_at": evaluated_at,
        }
        record = (self.audit if durable else self.boundary_audit).append(event)
        return GuardianVerdict(
            allowed=allowed,
            reason=reason,
            evidence_id=record["record_hash"],
            tenant_id=request.tenant_id,
            operation=request.operation,
            payload_hash=payload_hash,
            evaluated_at=evaluated_at,
            subscription_id=subscription_id,
            policy_version=self.policy.version,
            intelligence_evidence_hash=evidence_hash,
        )

    def preflight(
        self,
        request: GuardianRequest,
        *,
        subscription_token: str,
        now: int | None = None,
    ) -> tuple[Admission | None, GuardianVerdict | None]:
        evaluated_at = int(time.time() if now is None else now)
        payload_hash = digest(request.payload)
        claims = None
        try:
            claims = self.authority.verify(
                subscription_token,
                tenant_id=request.tenant_id,
                actor=request.actor,
                capability=self.policy.capability,
                now=evaluated_at,
            )
            payload_size = len(canonical_json(request.payload))
            size_limit = min(self.policy.max_payload_bytes, claims.max_payload_bytes)
            if request.operation not in self.policy.allowed_operations:
                reason = "OPERATION_NOT_ALLOWED"
            elif payload_size > size_limit:
                reason = "PAYLOAD_LIMIT_EXCEEDED"
            else:
                # Consume the token's replay identifier (if any) before
                # admitting: a presented-but-rejected request never burns
                # the token's jti for a retry.
                self.authority.consume(claims, now=evaluated_at)
                return (
                    Admission(
                        request=request,
                        subscription_id=claims.subscription_id,
                        payload_hash=payload_hash,
                        evaluated_at=evaluated_at,
                    ),
                    None,
                )
        except SubscriptionError as exc:
            reason = f"SUBSCRIPTION_DENIED:{exc}"
        verdict = self.record_boundary_verdict(
            request,
            allowed=False,
            reason=reason,
            subscription_id=claims.subscription_id if claims else None,
            payload_hash=payload_hash,
            evaluated_at=evaluated_at,
            durable=claims is not None,
        )
        return None, verdict

    def complete(
        self,
        admission: Admission,
        *,
        intelligence_evidence: Mapping[str, Any] | None = None,
        intelligence_error: str | None = None,
    ) -> GuardianVerdict:
        if intelligence_error:
            allowed, reason = False, f"INTELLIGENCE_UNAVAILABLE:{intelligence_error}"
        elif self.policy.require_intelligence_evidence and not intelligence_evidence:
            allowed, reason = False, "INTELLIGENCE_EVIDENCE_REQUIRED"
        else:
            allowed, reason = True, "ALLOWED"
        return self.record_boundary_verdict(
            admission.request,
            allowed=allowed,
            reason=reason,
            subscription_id=admission.subscription_id,
            payload_hash=admission.payload_hash,
            evaluated_at=admission.evaluated_at,
            intelligence_evidence=intelligence_evidence,
        )

    def evaluate(
        self,
        request: GuardianRequest,
        *,
        subscription_token: str,
        intelligence_evidence: Mapping[str, Any] | None = None,
        now: int | None = None,
    ) -> GuardianVerdict:
        admission, denial = self.preflight(
            request,
            subscription_token=subscription_token,
            now=now,
        )
        if denial is not None:
            return denial
        if admission is None:  # pragma: no cover - defensive invariant.
            raise RuntimeError("preflight produced neither admission nor denial")
        return self.complete(
            admission,
            intelligence_evidence=intelligence_evidence,
        )
