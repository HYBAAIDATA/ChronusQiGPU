"""M3 fail-closed production coordinator.

This module adds the M3 closure gates without changing PYTHIA's canonical
search architecture.  It wraps the existing production coordinator so live
submission additionally requires:

* a runtime AL HARAS authorisation decision bound to the current Stratum work;
* a THESEUS-custodied verified-proof record before any pool write; and
* fail-closed storage health when M3 strict mode is enabled.

Shadow mining remains available when live submission is not intended.  A stale
generation is a refused transition, not a process-fatal exception.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from .causal import CausalCoordinate
from .cycle_fsm import MiningCycleState
from .geodesic_support import PythiaProductionMiningCoordinator
from .search_plan import PoolOutcome
from .storage_recorder import M3StorageError
from .stratum_adapter import StaleJobError

LOG = logging.getLogger(__name__)


class M3PythiaProductionMiningCoordinator(PythiaProductionMiningCoordinator):
    """PYTHIA production coordinator with optional strict M3 closure gates."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._m3_required = bool(kwargs.pop("m3_required", False))
        self._m3_gate = kwargs.pop("m3_gate", None)
        self._m3_blocked_reason: str | None = None
        self._last_m3_gate: dict[str, Any] | None = None
        self._last_m3_lease_gate: dict[str, Any] | None = None
        self._m3_authorized_identity_key: Any | None = None
        super().__init__(*args, **kwargs)

    def m3_status(self) -> dict[str, Any]:
        fabric = dict(getattr(self, "_chronus_fabric_state", {}) or {})
        return {
            "schema": "pythia.m3-runtime/1",
            "required": self._m3_required,
            "blocked": self._m3_blocked_reason is not None,
            "reason": self._m3_blocked_reason,
            "gate_configured": self._m3_gate is not None,
            "search_authority": "PYTHIA",
            "search_algorithm": getattr(self, "_nonce_order", None),
            "search_architecture_ready": getattr(self, "pythia_search_precompute", None) is not None,
            "chronus_fabric": fabric,
            "last_lease_gate": self._last_m3_lease_gate,
            "last_submission_gate": self._last_m3_gate,
        }

    def _block_m3(self, reason: str) -> None:
        self._m3_blocked_reason = str(reason)
        self.mining_enabled = False
        self._last_pool_outcome = PoolOutcome.NOT_SUBMITTED
        LOG.error("M3 mining route blocked: %s", reason)

    def _m3_identity_context(self, identity: Any) -> dict[str, Any]:
        endpoint = getattr(getattr(self, "client", None), "endpoint", None)
        return {
            "pool_session_id": getattr(identity, "pool_session_id", None),
            "generation": getattr(identity, "generation", None),
            "job_id": getattr(identity, "job_id", None),
            "job_fingerprint": getattr(identity, "job_fingerprint", None),
            "target_generation": getattr(identity, "target_generation", None),
            "clean_jobs": getattr(identity, "clean_jobs", None),
            "endpoint": (
                f"{getattr(endpoint, 'host', '')}:{getattr(endpoint, 'port', '')}"
                if endpoint is not None
                else None
            ),
            "worker": self.username,
        }

    def _authorize_m3_identity(self, identity: Any) -> bool:
        """Authorize one live Stratum identity before any nonce lease is reserved."""
        if not self._m3_required:
            return True
        if self._m3_blocked_reason is not None or self._m3_gate is None:
            return False
        key = getattr(identity, "key", None)
        if key is not None and key == self._m3_authorized_identity_key:
            return True
        try:
            gate = dict(
                self._m3_gate.authorize_lease(
                    context=self._m3_identity_context(identity)
                )
            )
        except M3StorageError as exc:
            self._block_m3(f"THESEUS_CUSTODY_FAILURE:{exc}")
            return False
        self._last_m3_lease_gate = gate
        if gate.get("allowed") is not True:
            self._block_m3(str(gate.get("reason") or "M3_LEASE_DENIED"))
            return False
        self._m3_authorized_identity_key = key
        self.causal.record(
            "lease_authorized",
            CausalCoordinate(
                pool_session_id=getattr(identity, "pool_session_id", None),
                generation=getattr(identity, "generation", None),
                job_fingerprint=getattr(identity, "job_fingerprint", None),
                job_id=getattr(identity, "job_id", None),
            ),
            authorization_evidence_id=gate.get("authorization_evidence_id"),
            authorization_version_id=gate.get("authorization_version_id"),
            policy_version=gate.get("policy_version"),
        )
        return True

    def _build_plan(self, identity: Any):
        if not self._authorize_m3_identity(identity):
            return None
        return super()._build_plan(identity)

    async def submit_candidate(
        self,
        *,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce: int | str,
    ) -> bool:
        """Require AL HARAS + THESEUS before a live M3 pool write.

        The base coordinator still performs its independent proof, chain-tip,
        duplicate and submission checks immediately before the wire write.
        This preflight therefore strengthens the boundary; it does not replace
        the existing SHA256d or stale-work verifier.
        """
        if not self._m3_required or not self.submission_permitted():
            return await super().submit_candidate(
                job_id=job_id,
                extranonce2=extranonce2,
                ntime=ntime,
                nonce=nonce,
            )

        if self._m3_blocked_reason is not None:
            self._record_submission_gate("M3_ROUTE_BLOCKED", job_id)
            return False
        if self._m3_gate is None:
            self._block_m3("M3_SUBMISSION_GATE_UNAVAILABLE")
            self._record_submission_gate("M3_SUBMISSION_GATE_UNAVAILABLE", job_id)
            return False
        if self.client is None:
            raise ConnectionError("no active Stratum client")

        # Validate against the current adapter state before asking AL HARAS or
        # THESEUS to bless anything.  The base method validates again after
        # this preflight so a clean_jobs rotation in between still fails closed.
        self._last_pool_outcome = PoolOutcome.NOT_SUBMITTED
        try:
            proof = self.client.proof_adapter.validate_candidate(
                job_id=job_id,
                extranonce2=extranonce2,
                ntime=ntime,
                nonce=nonce,
            )
        except StaleJobError:
            self._last_pool_outcome = PoolOutcome.STALE
            raise
        identity = self.agentic.current_identity()
        correlation = dict(self._pending_correlation or {})
        endpoint = getattr(self.client, "endpoint", None)
        context = {
            "job_id": job_id,
            "job_fingerprint": correlation.get(
                "job_fingerprint",
                getattr(identity, "job_fingerprint", None),
            ),
            "generation": correlation.get("generation", getattr(identity, "generation", None)),
            "pool_session_id": correlation.get(
                "pool_session_id",
                getattr(identity, "pool_session_id", None),
            ),
            "plan_id": correlation.get("plan_id"),
            "lease_id": correlation.get("lease_id"),
            "execution_id": correlation.get("execution_id"),
            "candidate_id": correlation.get("candidate_id"),
            "endpoint": (
                f"{getattr(endpoint, 'host', '')}:{getattr(endpoint, 'port', '')}"
                if endpoint is not None
                else None
            ),
            "worker": self.username,
            "nonce": proof.nonce,
            "block_hash": proof.digest[::-1].hex(),
            "target": f"{proof.target:064x}",
        }
        gate = dict(self._m3_gate.authorize_and_custody(context=context, proof=proof))
        self._last_m3_gate = gate
        if gate.get("allowed") is not True:
            reason = str(gate.get("reason") or "AL_HARAS_DENIED")
            self._block_m3(reason)
            self._record_submission_gate(reason, job_id)
            self._last_pool_outcome = PoolOutcome.NOT_SUBMITTED
            self.cycle.try_transition(
                MiningCycleState.EVALUATE,
                event="refused",
                reason=reason,
                evidence={
                    "authorization_evidence_id": gate.get("authorization_evidence_id"),
                    "authorization_version_id": gate.get("authorization_version_id"),
                },
            )
            return False

        coordinate = CausalCoordinate(**correlation)
        self.causal.record(
            "submission_authorized",
            coordinate,
            authorization_evidence_id=gate.get("authorization_evidence_id"),
            authorization_version_id=gate.get("authorization_version_id"),
            verified_proof_id=gate.get("verified_proof_id"),
            verified_proof_version_id=gate.get("verified_proof_version_id"),
            policy_version=gate.get("policy_version"),
        )
        return await super().submit_candidate(
            job_id=job_id,
            extranonce2=extranonce2,
            ntime=ntime,
            nonce=nonce,
        )

    async def search_current_job(self) -> bool:
        """Turn stale/custody faults into explicit fail-closed runtime states."""
        try:
            if self._m3_required:
                identity = self.agentic.current_identity()
                if identity is not None and not self._authorize_m3_identity(identity):
                    return False
            return await super().search_current_job()
        except StaleJobError as exc:
            self._last_pool_outcome = PoolOutcome.STALE
            coordinate = CausalCoordinate(**dict(self._pending_correlation or {}))
            # This record is safe for an ordinary observer.  In strict M3 mode
            # a storage failure here is handled by the M3StorageError branch.
            try:
                self.causal.record(
                    "stale_generation_refused",
                    coordinate,
                    reason=str(exc),
                )
            except M3StorageError as storage_exc:
                self._block_m3(f"THESEUS_CUSTODY_FAILURE:{storage_exc}")
                return False
            self.agentic.clear_work("STALE_JOB")
            self.cycle.try_transition(
                MiningCycleState.EVALUATE,
                event="stale",
                reason="stale generation refused before pool write",
            )
            self.cycle.try_transition(
                MiningCycleState.NEXT_CYCLE,
                event="success",
                reason="stale generation closed; await current work",
            )
            self._precompute_wake.set()
            self._work_wake.set()
            return False
        except M3StorageError as exc:
            # The causal JSONL mirror is written before observer notification,
            # so the failed transition remains replayable.  Stop further mining
            # until a restart/recovery can reconcile THESEUS.
            self._block_m3(f"THESEUS_CUSTODY_FAILURE:{exc}")
            return False


__all__ = ["M3PythiaProductionMiningCoordinator"]
