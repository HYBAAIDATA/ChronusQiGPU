"""AL HARAS authorization adapter for Salamander actuation.

SALAMANDER owns bounded diagnosis/healing/optimisation. AL HARAS owns
identity, entitlement and policy decisions. This module is the narrow seam
between those authorities: it obtains a signed AL HARAS verdict without ever
placing subscription credentials in Salamander evidence.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

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
    ) -> None:
        if not callable(token_provider):
            raise ValueError("token_provider must be callable")
        prefix = operation_prefix.strip().strip(".")
        if not prefix:
            raise ValueError("operation_prefix is required")
        self.guardian = guardian
        self.token_provider = token_provider
        self.evidence_provider = evidence_provider
        self.operation_prefix = prefix

    def __call__(self, request: ActionRequest) -> Mapping[str, Any]:
        operation = f"{self.operation_prefix}.{request.kind.value.lower()}"
        guardian_request = GuardianRequest(
            tenant_id=request.tenant_id,
            operation=operation,
            resource=request.target,
            actor=request.actor_id,
            payload={
                "action_id": request.action_id,
                "handler": request.handler,
                "reason": request.reason,
                "bounds": dict(request.bounds),
                "requires": list(request.requires),
                "idempotency_key": request.idempotency_key,
            },
        )

        try:
            token = str(self.token_provider(request) or "")
        except Exception as exc:
            token = ""
            provider_error = f"TOKEN_PROVIDER_ERROR:{type(exc).__name__}"
        else:
            provider_error = None

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
