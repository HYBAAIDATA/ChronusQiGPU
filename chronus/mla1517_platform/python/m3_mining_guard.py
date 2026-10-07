"""M3 live-submission gate binding AL HARAS to THESEUS custody.

The control-plane guardian decides whether the exact live mining action is
authorised.  The decision receipt and independently checked proof are then
custodied by the M3 file plane before the coordinator may call mining.submit.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Mapping

from al_haras_pythia import pythia_guardian_api
from chronus.mla1517.mining.storage_recorder import M3StorageError


class M3MiningSubmissionGate:
    """Fail-closed AL HARAS + THESEUS gate for one mining runtime."""

    def __init__(
        self,
        recorder: Any,
        *,
        tenant: str,
        actor: str,
        subscription_token: str,
    ) -> None:
        if recorder is None:
            raise RuntimeError("M3 submission gate requires a THESEUS storage recorder")
        if not tenant.strip():
            raise RuntimeError("PYTHIA_M3_TENANT is required")
        if not actor.strip():
            raise RuntimeError("PYTHIA_M3_ACTOR is required")
        if not subscription_token.strip():
            raise RuntimeError("PYTHIA_M3_AL_HARAS_TOKEN is required")
        self.recorder = recorder
        self.tenant = tenant.strip()
        self.actor = actor.strip()
        self.subscription_token = subscription_token.strip()
        self.guardian_api = pythia_guardian_api()

    @classmethod
    def from_env(cls, recorder: Any) -> "M3MiningSubmissionGate":
        tenant = (
            os.getenv("PYTHIA_M3_TENANT", "").strip()
            or os.getenv("PYTHIA_STORAGE_TENANT", "").strip()
        )
        return cls(
            recorder,
            tenant=tenant,
            actor=os.getenv("PYTHIA_M3_ACTOR", "").strip(),
            subscription_token=os.getenv("PYTHIA_M3_AL_HARAS_TOKEN", "").strip(),
        )

    def configured(self) -> bool:
        status = self.guardian_api.public_status()
        return bool(
            status.get("configured")
            and status.get("audit_durable")
            and self.tenant
            and self.actor
            and self.subscription_token
        )

    def status(self) -> dict[str, Any]:
        public = self.guardian_api.public_status()
        return {
            "schema": "pythia.m3-authorization/1",
            "configured": self.configured(),
            "tenant_configured": bool(self.tenant),
            "actor_configured": bool(self.actor),
            "token_configured": bool(self.subscription_token),
            "guardian_configured": bool(public.get("configured")),
            "guardian_audit_durable": bool(public.get("audit_durable")),
            "policy_version": self.guardian_api.guardian.policy.version,
        }

    def _evaluate_guardian(
        self,
        *,
        operation: str,
        resource: str,
        payload: Mapping[str, Any],
        request_id: str,
    ) -> dict[str, Any]:
        """Use the canonical GuardianAPI so TOE/L-HRAS policy is not bypassed."""
        try:
            status, response = self.guardian_api.evaluate(
                headers={
                    "x-hyba-tenant": self.tenant,
                    "x-hyba-actor": self.actor,
                    "authorization": f"Bearer {self.subscription_token}",
                },
                body={
                    "operation": operation,
                    "resource": resource,
                    "payload": dict(payload),
                    "request_id": request_id,
                    # GuardianAPI owns the configured intelligence provider.
                    # The exact work identity is the observation supplied to it.
                    "observation": dict(payload),
                },
            )
        except Exception as exc:
            return {
                "allowed": False,
                "reason": f"AL_HARAS_UNAVAILABLE:{type(exc).__name__}",
                "http_status": 503,
            }
        verdict = dict(response)
        verdict["http_status"] = int(status)
        return verdict

    def authorize_lease(self, *, context: Mapping[str, Any]) -> Mapping[str, Any]:
        """Authorize one Stratum work identity before PYTHIA reserves leases."""
        storage_health = self.recorder.health(reconcile=True)
        if storage_health.get("healthy") is not True:
            return {
                "allowed": False,
                "reason": "THESEUS_STORAGE_UNHEALTHY",
                "storage_health": storage_health,
            }
        payload = {
            "pool_endpoint": context.get("endpoint"),
            "worker": context.get("worker"),
            "pool_session_id": context.get("pool_session_id"),
            "generation": context.get("generation"),
            "job_id": context.get("job_id"),
            "job_fingerprint": context.get("job_fingerprint"),
            "target_generation": context.get("target_generation"),
            "clean_jobs": context.get("clean_jobs"),
            "search_authority": "PYTHIA",
            "search_algorithm": "hendrix_coprime_stride",
        }
        request_id = (
            f"lease:{context.get('pool_session_id')}:"
            f"{context.get('generation')}:{context.get('job_fingerprint')}"
        )
        verdict_dict = self._evaluate_guardian(
            operation="mining.lease",
            resource=f"stratum://{context.get('endpoint') or 'unavailable'}",
            payload=payload,
            request_id=request_id,
        )
        try:
            version_id = self.recorder.persist_authorization(
                verdict_dict,
                context=payload,
            )
        except Exception as exc:
            raise M3StorageError(
                f"could not custody AL HARAS lease authorization: {type(exc).__name__}: {exc}"
            ) from exc
        return {
            "allowed": verdict_dict.get("allowed") is True,
            "reason": verdict_dict.get("reason"),
            "authorization_evidence_id": verdict_dict.get("evidence_id"),
            "authorization_version_id": version_id,
            "policy_version": verdict_dict.get("policy_version"),
            "intelligence_evidence_hash": verdict_dict.get("intelligence_evidence_hash"),
            "http_status": verdict_dict.get("http_status"),
        }

    def authorize_and_custody(
        self, *, context: Mapping[str, Any], proof: Any
    ) -> Mapping[str, Any]:
        # Reconcile immediately before an external side effect. Startup
        # readiness alone is insufficient because custody may degrade later.
        storage_health = self.recorder.health(reconcile=True)
        if storage_health.get("healthy") is not True:
            return {
                "allowed": False,
                "reason": "THESEUS_STORAGE_UNHEALTHY",
                "storage_health": storage_health,
            }

        payload = {
            "pool_endpoint": context.get("endpoint"),
            "worker": context.get("worker"),
            "pool_session_id": context.get("pool_session_id"),
            "generation": context.get("generation"),
            "job_id": context.get("job_id"),
            "job_fingerprint": context.get("job_fingerprint"),
            "plan_id": context.get("plan_id"),
            "lease_id": context.get("lease_id"),
            "execution_id": context.get("execution_id"),
            "candidate_id": context.get("candidate_id"),
            "nonce": context.get("nonce"),
            "block_hash": context.get("block_hash"),
            "target": context.get("target"),
        }
        verdict_dict = self._evaluate_guardian(
            operation="mining.submit",
            resource=f"stratum://{context.get('endpoint') or 'unavailable'}",
            payload=payload,
            request_id=str(context.get("candidate_id") or uuid.uuid4().hex),
        )

        try:
            authorization_version_id = self.recorder.persist_authorization(
                verdict_dict,
                context=payload,
            )
        except Exception as exc:
            raise M3StorageError(
                f"could not custody AL HARAS authorization: {type(exc).__name__}: {exc}"
            ) from exc
        if verdict_dict.get("allowed") is not True:
            return {
                "allowed": False,
                "reason": verdict_dict.get("reason"),
                "authorization_evidence_id": verdict_dict.get("evidence_id"),
                "authorization_version_id": authorization_version_id,
                "policy_version": verdict_dict.get("policy_version"),
                "intelligence_evidence_hash": verdict_dict.get(
                    "intelligence_evidence_hash"
                ),
                "http_status": verdict_dict.get("http_status"),
            }

        try:
            proof_record_id, proof_version_id = self.recorder.persist_verified_proof(
                context=payload,
                proof=proof,
                authorization_evidence_id=str(verdict_dict.get("evidence_id") or ""),
                authorization_version_id=authorization_version_id,
                policy_version=str(verdict_dict.get("policy_version") or ""),
            )
        except Exception as exc:
            if isinstance(exc, M3StorageError):
                raise
            raise M3StorageError(
                f"could not custody verified proof: {type(exc).__name__}: {exc}"
            ) from exc
        return {
            "allowed": True,
            "reason": verdict_dict.get("reason"),
            "authorization_evidence_id": verdict_dict.get("evidence_id"),
            "authorization_version_id": authorization_version_id,
            "verified_proof_id": proof_record_id,
            "verified_proof_version_id": proof_version_id,
            "policy_version": verdict_dict.get("policy_version"),
            "intelligence_evidence_hash": verdict_dict.get("intelligence_evidence_hash"),
            "http_status": verdict_dict.get("http_status"),
        }


__all__ = ["M3MiningSubmissionGate"]
