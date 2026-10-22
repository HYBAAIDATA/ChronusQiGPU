"""Leased Octopus execution through the canonical governed submission authority.

No sockets, credentials, approvals or pool outcomes are invented here. The M3
coordinator retains AL HARAS, THESEUS, stale-work, chain-tip and single-writer
checks. Local shadow execution alone never establishes a live submission.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, replace
import uuid

from chronus.octopus_execution import OctopusCampaignReceipt, OctopusExecutionEngine
from .causal import CausalCoordinate
from .m3_coordinator import GovernedProductionMiningCoordinator
from .stratum_adapter import StaleJobError, StratumAdapterError


@dataclass(frozen=True)
class OctopusSubmissionReceipt:
    execution: OctopusCampaignReceipt
    pool_outcome: str
    accepted: bool
    wire_writes: int
    lease_id: str


class GovernedOctopusAdapter:
    """Opt-in bridge to a configured production M3 coordinator, shadow by default."""

    def __init__(
        self,
        coordinator: GovernedProductionMiningCoordinator,
        engine: OctopusExecutionEngine,
    ) -> None:
        if not isinstance(coordinator, GovernedProductionMiningCoordinator):
            raise TypeError("the governed production coordinator is required")
        if getattr(coordinator, "_asynchronous_submission", False):
            raise ValueError("Octopus adapter requires synchronous coordinator submission mode")
        self.coordinator = coordinator
        self.engine = engine

    async def search_current_job(
        self, *, window: int = 600, request_submission: bool = False
    ) -> OctopusSubmissionReceipt:
        if type(window) is not int or not 0 < window <= (1 << 20):
            raise ValueError("window must be a positive integer no greater than 2^20")
        if type(request_submission) is not bool:
            raise ValueError("request_submission must be boolean")
        coord = self.coordinator
        async with coord._search_lock:
            if not coord.mining_enabled or coord.work_throttled:
                raise PermissionError("mining is disabled or throttled")
            coord._refresh_governor()
            if not coord.governor.admit():
                raise PermissionError("hashrate governor deferred this campaign")
            identity = coord._refresh_work_identity()
            client = coord.client
            if identity is None or client is None:
                raise StaleJobError("a current authorized work identity is required")
            proof_adapter = client.proof_adapter
            job = proof_adapter.current_job
            if job is None or job.target is None:
                raise StaleJobError("a current job and negotiated target are required")
            if request_submission and not coord.submission_permitted():
                raise PermissionError("production submission authorization is unavailable")
            from chronus.mla1517_platform.python import runtime_config

            config = runtime_config.load()
            if config.get("_policy_error"):
                raise PermissionError("invalid persisted runtime policy; execution refused")
            if config["execution"]["mode"] == "scale_stack":
                raise PermissionError(
                    "Octopus CPU-reference executor cannot satisfy scale_stack policy"
                )
            if window > config["window"]:
                raise ValueError("campaign window exceeds runtime config")
            policy = {
                key: config[key]
                for key in ("solvers", "window", "hashrate", "execution", "intelligence")
            }
            policy_digest = hashlib.sha256(
                json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest()
            intelligence = config["intelligence"]
            lease = coord.agentic.reserve_fallback(window, proof_adapter.next_extranonce2)
            scanned = False
            execution = None
            try:
                lease = coord.agentic.begin_reserved(lease.lease_id)
                header = proof_adapter.build_header(job.job_id, lease.extranonce2, job.ntime, 0)
                coordinate = CausalCoordinate(
                    pool_session_id=identity.pool_session_id,
                    generation=identity.generation,
                    job_fingerprint=identity.job_fingerprint,
                    job_id=job.job_id,
                    plan_id=lease.lease_id,
                    lease_id=lease.lease_id,
                    execution_id=f"execution:{uuid.uuid4()}",
                )
                coord.causal.record(
                    "plan_created",
                    coordinate,
                    window=window,
                    nonce_start=lease.start,
                    route="cpu_reference",
                    policy="octopus.600lane.v1",
                    runtime_policy_digest=policy_digest,
                )
                coord.causal.record(
                    "execution_started",
                    coordinate,
                    extranonce2=lease.extranonce2,
                    nonce_start=lease.start,
                    window=window,
                    requested_route="cpu_reference",
                )
                task = asyncio.create_task(
                    asyncio.to_thread(
                        self.engine.run_campaign,
                        job_id=job.job_id,
                        job_fingerprint=identity.job_fingerprint,
                        header_prefix=header[:76],
                        target_int=job.target,
                        base_step=lease.start,
                        window=window,
                        work_identity=identity,
                        extranonce2=lease.extranonce2,
                        plan_id=lease.lease_id,
                        seed=intelligence["seed"],
                        worker_limit=intelligence["max_workers"],
                        max_nonces_per_arm=intelligence["max_nonces_per_arm"],
                        runtime_policy_digest=policy_digest,
                    )
                )
                # Never release a lease while its worker thread is still executing.
                try:
                    execution = await asyncio.shield(task)
                except asyncio.CancelledError:
                    try:
                        execution = await task
                        scanned = True
                    finally:
                        raise
                scanned = True
                outcome = "NO_CANDIDATE"
                writes = 0
                accepted = False
                current = coord._refresh_work_identity()
                stale = (
                    client is not coord.client
                    or proof_adapter.current_job != job
                    or current is None
                    or current.key != identity.key
                )
                winner = execution.winning_share
                if stale:
                    outcome = "STALE"
                elif winner is not None:
                    if not lease.start <= winner.nonce < lease.start + window:
                        raise StratumAdapterError("candidate escaped its nonce lease")
                    proof = proof_adapter.validate_candidate(
                        job_id=job.job_id,
                        extranonce2=lease.extranonce2,
                        ntime=job.ntime,
                        nonce=winner.nonce,
                    )
                    if (
                        proof.header[:76] != header[:76]
                        or proof.digest[::-1].hex() != winner.sha256d_hex
                        or proof.target != job.target
                        or winner.recheck_passed is not True
                    ):
                        raise StratumAdapterError(
                            "candidate does not match independent live-job proof"
                        )
                    coordinate = coordinate.extend(candidate_id=f"candidate:{uuid.uuid4()}")
                    coord.causal.record("candidate_found", coordinate, nonce=winner.nonce)
                    outcome = "SHADOW"
                    if request_submission:
                        counter = getattr(client, "wire_writes_for", None)
                        if not callable(counter):
                            raise PermissionError("transport wire-write receipts are required")
                        before = counter("mining.submit")
                        previous = coord._pending_correlation
                        coord._pending_correlation = {
                            k: v for k, v in coordinate.as_dict().items() if v is not None
                        }
                        try:
                            result = await coord.submit_candidate(
                                job_id=job.job_id,
                                extranonce2=lease.extranonce2,
                                ntime=job.ntime,
                                nonce=winner.nonce,
                                cycle_reporting=False,
                            )
                            writes = max(0, counter("mining.submit") - before)
                            accepted = result is True and writes > 0
                            outcome = (
                                "ACCEPTED"
                                if accepted
                                else (
                                    "REJECTED"
                                    if writes > 0 and result is False
                                    else "OUTCOME_UNKNOWN" if writes > 0 else "NOT_SUBMITTED"
                                )
                            )
                        except (ConnectionError, TimeoutError, OSError):
                            writes = max(0, counter("mining.submit") - before)
                            outcome = "OUTCOME_UNKNOWN" if writes else "NOT_SUBMITTED"
                            # A possibly-written share is never retried here.
                        finally:
                            coord._pending_correlation = previous
                coord.causal.record(
                    "octopus_outcome",
                    coordinate,
                    pool_outcome=outcome,
                    accepted=accepted,
                    wire_writes=writes,
                )
                return OctopusSubmissionReceipt(
                    replace(execution, submitted_live=writes > 0),
                    outcome,
                    accepted,
                    writes,
                    lease.lease_id,
                )
            finally:
                try:
                    if execution is not None:
                        coord.governor.record(
                            hashes=execution.nonces_evaluated,
                            share_target=job.target,
                            shares=int(execution.winning_share is not None),
                        )
                finally:
                    coord.agentic.finish_execution(lease.lease_id, scanned=scanned)
