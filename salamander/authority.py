"""AL HARAS authorization adapter for Salamander actuation.

SALAMANDER owns bounded diagnosis/healing/optimisation. AL HARAS owns
identity, entitlement and policy decisions. This module is the narrow seam
between those authorities: it obtains a signed AL HARAS verdict without ever
placing subscription credentials in Salamander evidence.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping
import time
import threading

from al_haras.audit import digest as guardian_digest

from al_haras.guardian import ALHaras
from al_haras.models import GuardianRequest

from .models import ActionRequest

TokenProvider = Callable[[ActionRequest], str]
EvidenceProvider = Callable[[ActionRequest], Mapping[str, Any]]


class ALHarasActionAuthorizer:
    """Translate a bounded Salamander action into an AL HARAS decision.

    Credentials are supplied out-of-band by the token provider. They are
    never attached to ActionRequest and therefore never enter Salamander's
    hash-chained action ledger.
    """

    def __init__(
        self,
        guardian: ALHaras,
        token_provider: TokenProvider,
        *,
        evidence_provider: EvidenceProvider | None = None,
        operation_prefix: str = "salamander",
        max_pending_grants: int = 1024,
    ) -> None:
        if not callable(token_provider):
            raise ValueError("token_provider must be callable")
        prefix = operation_prefix.strip().strip(".")
        if not prefix:
            raise ValueError("operation_prefix is required")
        if type(max_pending_grants) is not int or max_pending_grants <= 0:
            raise ValueError("positive configured pending-grant budget required")
        self.max_pending_grants = max_pending_grants
        self.guardian = guardian
        self.token_provider = token_provider
        self.evidence_provider = evidence_provider
        self.operation_prefix = prefix
        self._grant_lock = threading.RLock()
        self._grants: dict[str, tuple[tuple[str, str, str, str], int]] = {}

    @staticmethod
    def _payload(request: ActionRequest) -> dict[str, Any]:
        return {
            "action_id": request.action_id, "handler": request.handler,
            "reason": request.reason, "bounds": dict(request.bounds),
            "requires": list(request.requires),
            "idempotency_key": request.idempotency_key,
        }

    def validate_decision(self, request: ActionRequest, decision: Mapping[str, Any]) -> bool:
        """Re-read AL HARAS's chain; a caller's ALLOW dictionary is not authority.

        The adapter, not SALAMANDER, binds receipts to entitled lifetime and the
        exact immutable action. Tokens remain out of the evidence ledger.
        """
        if decision.get("allowed") is not True or decision.get("authority") != "AL_HARAS":
            return False
        evidence_id = decision.get("evidence_id")
        grant = self._grants.get(str(evidence_id))
        if grant is None or int(time.time()) >= grant[1]:
            return False
        expected = guardian_digest(self._payload(request))
        if grant[0] != (request.tenant_id, request.actor_id, request.target, expected):
            return False
        operation = f"{self.operation_prefix}.{request.kind.value.lower()}"
        records = self.guardian.audit.records
        if not self.guardian.audit.verify(records):
            return False
        record = next((r for r in records if r.get("record_hash") == evidence_id), None)
        if record is None:
            return False
        event = record["event"]
        return all((
            event.get("allowed") is True,
            event.get("tenant_id") == request.tenant_id,
            event.get("actor") == request.actor_id,
            event.get("resource") == request.target,
            event.get("operation") == operation,
            event.get("payload_hash") == expected,
            event.get("policy_version") == self.guardian.policy.version,
            decision.get("policy_version") == event.get("policy_version"),
        ))

    def consume_decision(self, request: ActionRequest, decision: Mapping[str, Any]) -> bool:
        """One receipt authorises at most one dispatch, including direct calls."""
        with self._grant_lock:
            if not self.validate_decision(request, decision):
                return False
            self._grants.pop(str(decision["evidence_id"]), None)
            return True

    def __call__(self, request: ActionRequest) -> Mapping[str, Any]:
        with self._grant_lock:
            now = int(time.time())
            self._grants = {k: v for k, v in self._grants.items() if v[1] > now}
            if len(self._grants) >= self.max_pending_grants:
                return {"allowed": False, "authority": "AL_HARAS",
                        "actor": request.actor_id, "reason": "AUTHORIZATION_PENDING_BUDGET_EXHAUSTED"}
        operation = f"{self.operation_prefix}.{request.kind.value.lower()}"
        guardian_request = GuardianRequest(
            tenant_id=request.tenant_id,
            operation=operation,
            resource=request.target,
            actor=request.actor_id,
            payload=self._payload(request),
        )

        try:
            token = str(self.token_provider(request) or "")
        except Exception as exc:
            token = ""
            provider_error = f"TOKEN_PROVIDER_ERROR:{type(exc).__name__}"
        else:
            provider_error = None

        # Signed token verification supplies the real entitlement expiry. The
        # preflight below remains the sole admission/replay-consumption owner.
        try:
            claims = self.guardian.authority.verify(
                token, tenant_id=request.tenant_id, actor=request.actor_id,
                capability=self.guardian.policy.capability,
            )
        except Exception:
            claims = None
        admission, denial = self.guardian.preflight(
            guardian_request,
            subscription_token=token,
        )
        if denial is not None:
            result = denial.to_dict()
            if provider_error:
                result["reason"] = provider_error
            result["authority"] = "AL_HARAS"
            result["actor"] = request.actor_id
            return result
        if admission is None:
            raise RuntimeError("AL HARAS preflight returned no decision")

        evidence: Mapping[str, Any] | None = None
        evidence_error: str | None = None
        if self.evidence_provider is not None:
            try:
                evidence = dict(self.evidence_provider(request))
            except Exception as exc:
                evidence_error = f"{type(exc).__name__}: {exc}"

        verdict = self.guardian.complete(
            admission,
            intelligence_evidence=evidence,
            intelligence_error=evidence_error,
        )
        result = verdict.to_dict()
        result["authority"] = "AL_HARAS"
        result["actor"] = request.actor_id
        if verdict.allowed and claims is not None:
            self._grants[verdict.evidence_id] = (
                (request.tenant_id, request.actor_id, request.target,
                 guardian_digest(self._payload(request))), claims.expires_at,
            )
        return result


def build_authorized_control_plane(
    *,
    registry: Any,
    guardian: ALHaras,
    token_provider: TokenProvider,
    ledger: Any = None,
    clock_ns: Callable[[], int] | None = None,
    max_recoveries_per_target: int = 2,
    evidence_provider: EvidenceProvider | None = None,
    operation_prefix: str = "salamander",
):
    """Compose the canonical production Salamander actuation boundary.

    This helper exists so production composition roots cannot accidentally
    instantiate an actuator-capable control plane with authorization omitted.
    AL HARAS remains the security/governance authority; SALAMANDER remains the
    healing/optimisation authority.
    """
    from .control_plane import AutonomicControlPlane, EvidenceLedger

    kwargs: dict[str, Any] = {
        "registry": registry,
        "ledger": ledger or EvidenceLedger(),
        "max_recoveries_per_target": max_recoveries_per_target,
        "authorizer": ALHarasActionAuthorizer(
            guardian,
            token_provider,
            evidence_provider=evidence_provider,
            operation_prefix=operation_prefix,
        ),
        "require_authorization": True,
    }
    if clock_ns is not None:
        kwargs["clock_ns"] = clock_ns
    return AutonomicControlPlane(**kwargs)
