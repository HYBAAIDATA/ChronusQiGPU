"""Evidence-first runtime state for the canonical Stratum V1 session."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from .stratum_adapter import StratumJob, SubscriptionState


class StratumPhase(str, Enum):
    CONFIGURED = "CONFIGURED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    SUBSCRIBING = "SUBSCRIBING"
    SUBSCRIBED = "SUBSCRIBED"
    AUTHORIZING = "AUTHORIZING"
    AUTHORIZED = "AUTHORIZED"
    WAITING_JOB = "WAITING_JOB"
    READY = "READY"
    AUTH_FAILED = "AUTH_FAILED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"


class SubmissionPhase(str, Enum):
    IDLE = "IDLE"
    SUBMITTING = "SUBMITTING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


@dataclass(frozen=True)
class StratumJobGeneration:
    generation_id: int
    pool_id: str
    job_id: str
    fingerprint: str
    received_at: float
    clean_jobs: bool
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: tuple[str, ...]
    version: str
    nbits: str
    ntime: str
    extranonce1: str
    extranonce2_size: int
    target: int | None
    target_generation: int
    difficulty: Any = None
    difficulty_source: str | None = None


def _fingerprint_payload(generation: StratumJobGeneration) -> dict[str, Any]:
    return {
        "pool_id": generation.pool_id,
        "job_id": generation.job_id,
        "prevhash": generation.prevhash,
        "coinb1": generation.coinb1,
        "coinb2": generation.coinb2,
        "merkle_branch": generation.merkle_branch,
        "version": generation.version,
        "nbits": generation.nbits,
        "ntime": generation.ntime,
        "extranonce1": generation.extranonce1,
        "extranonce2_size": generation.extranonce2_size,
        "target": generation.target,
        "target_generation": generation.target_generation,
    }


def _fingerprint(generation: StratumJobGeneration) -> str:
    encoded = json.dumps(
        _fingerprint_payload(generation),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class StratumRuntimeState:
    """Canonical evidence model; no state is inferred from configuration."""

    def __init__(self, *, pool_id: str, endpoint: str, worker: str) -> None:
        self.pool_id = pool_id
        self.endpoint = endpoint
        self.worker = worker
        self.phase = StratumPhase.CONFIGURED
        self.transport_connected = False
        self.subscribed = False
        self.authorized = False
        self.session_id: str | None = None
        self.connected_at: float | None = None
        self.last_message_at: float | None = None
        self.last_error: str | None = None
        self.subscription: SubscriptionState | None = None
        self.current_job: StratumJobGeneration | None = None
        self.last_job: StratumJobGeneration | None = None
        self.invalidated_generation: int | None = None
        self._generation = 0
        self.target: int | None = None
        self.target_generation = 0
        self.difficulty: Any = None
        self.difficulty_source: str | None = None
        self.difficulty_received_at: float | None = None
        self.submission_phase = SubmissionPhase.IDLE
        self.last_result: str | None = None
        self.last_submit_at: float | None = None
        self.last_response_at: float | None = None
        self.pending_generation: int | None = None
        self.pending_fingerprint: str | None = None
        self.pending_job_id: str | None = None
        self.submitted = 0
        self.accepted = 0
        self.rejected = 0
        self.unknown = 0
        self.jobs_received = 0
        self.jobs_invalidated = 0
        self.disconnects = 0

    @property
    def ready(self) -> bool:
        return (
            self.transport_connected
            and self.subscribed
            and self.authorized
            and self.target is not None
            and self.current_job is not None
        )

    def _reconcile_phase(self) -> None:
        if self.phase == StratumPhase.AUTH_FAILED:
            return
        if not self.transport_connected:
            self.phase = StratumPhase.DISCONNECTED
        elif self.authorized:
            self.phase = StratumPhase.READY if self.ready else StratumPhase.WAITING_JOB

    def connecting(self) -> None:
        self.session_id = None
        self.transport_connected = False
        self.subscribed = False
        self.authorized = False
        self.subscription = None
        self.target = None
        self.difficulty = None
        self.difficulty_source = None
        self.difficulty_received_at = None
        self._invalidate_current_job()
        self.phase = StratumPhase.CONNECTING
        self.last_error = None

    def connected(self) -> None:
        now = time.time()
        self.session_id = uuid.uuid4().hex
        self.transport_connected = True
        self.connected_at = now
        self.last_message_at = now
        self.phase = StratumPhase.CONNECTED

    def subscribing(self) -> None:
        self.phase = StratumPhase.SUBSCRIBING

    def subscription_confirmed(self, subscription: SubscriptionState) -> None:
        self.subscription = subscription
        self.subscribed = True
        self.phase = StratumPhase.SUBSCRIBED

    def authorizing(self) -> None:
        self.phase = StratumPhase.AUTHORIZING

    def authorization_confirmed(self) -> None:
        self.authorized = True
        self.phase = StratumPhase.AUTHORIZED
        self._reconcile_phase()

    def authorization_failed(self, reason: str) -> None:
        self.authorized = False
        self.phase = StratumPhase.AUTH_FAILED
        self.last_error = reason

    def extranonce_updated(self, subscription: SubscriptionState) -> None:
        self.subscription = subscription
        self._invalidate_current_job()
        self._reconcile_phase()

    def message_received(self) -> None:
        self.last_message_at = time.time()

    def target_updated(self, *, target: int, source: str, value: Any) -> None:
        self.target = target
        self.target_generation += 1
        self.difficulty_source = source
        self.difficulty = value if source == "mining.set_difficulty" else None
        self.difficulty_received_at = time.time()
        if self.current_job is not None:
            updated = replace(
                self.current_job,
                target=target,
                target_generation=self.target_generation,
                difficulty=self.difficulty,
                difficulty_source=source,
            )
            self.current_job = replace(updated, fingerprint=_fingerprint(updated))
            self.last_job = self.current_job
        self._reconcile_phase()

    def job_received(
        self,
        job: StratumJob,
        subscription: SubscriptionState,
    ) -> StratumJobGeneration:
        if job.clean_jobs:
            self._invalidate_current_job()
        self._generation += 1
        generation = StratumJobGeneration(
            generation_id=self._generation,
            pool_id=self.pool_id,
            job_id=job.job_id,
            fingerprint="",
            received_at=time.time(),
            clean_jobs=job.clean_jobs,
            prevhash=job.prevhash,
            coinb1=job.coinb1,
            coinb2=job.coinb2,
            merkle_branch=job.merkle_branch,
            version=job.version,
            nbits=job.nbits,
            ntime=job.ntime,
            extranonce1=subscription.extranonce1,
            extranonce2_size=subscription.extranonce2_size,
            target=job.target,
            target_generation=self.target_generation,
            difficulty=self.difficulty,
            difficulty_source=self.difficulty_source,
        )
        generation = replace(generation, fingerprint=_fingerprint(generation))
        self.current_job = generation
        self.last_job = generation
        self.jobs_received += 1
        self._reconcile_phase()
        return generation

    def submission_started(self, job_id: str) -> None:
        if self.submission_phase in {
            SubmissionPhase.SUBMITTING,
            SubmissionPhase.OUTCOME_UNKNOWN,
        }:
            raise RuntimeError("a Stratum submission is already unresolved")
        if not self.ready or self.current_job is None:
            raise RuntimeError("cannot submit without an active Stratum job")
        if job_id != self.current_job.job_id:
            raise RuntimeError(f"job {job_id!r} is not the active generation")
        self.submission_phase = SubmissionPhase.SUBMITTING
        self.last_result = None
        self.last_submit_at = time.time()
        self.last_response_at = None
        self.pending_generation = self.current_job.generation_id
        self.pending_fingerprint = self.current_job.fingerprint
        self.pending_job_id = job_id
        self.submitted += 1

    def submission_finished(self, result: Any) -> None:
        if self.submission_phase != SubmissionPhase.SUBMITTING:
            raise RuntimeError("no Stratum submission is pending")
        self.last_response_at = time.time()
        if result is True:
            self.submission_phase = SubmissionPhase.ACCEPTED
            self.last_result = "ACCEPTED"
            self.accepted += 1
        elif result is False:
            self.submission_phase = SubmissionPhase.REJECTED
            self.last_result = "REJECTED"
            self.rejected += 1
        else:
            self.submission_unknown("pool returned a non-boolean result")

    def submission_unknown(self, reason: str) -> None:
        if self.submission_phase != SubmissionPhase.SUBMITTING:
            return
        self.submission_phase = SubmissionPhase.OUTCOME_UNKNOWN
        self.last_result = "OUTCOME_UNKNOWN"
        self.last_response_at = None
        self.last_error = reason
        self.unknown += 1

    def disconnected(self, reason: str) -> None:
        if self.submission_phase == SubmissionPhase.SUBMITTING:
            self.submission_unknown(reason)
        if self.transport_connected:
            self.disconnects += 1
        self.session_id = None
        self.transport_connected = False
        self.subscribed = False
        self.authorized = False
        self.subscription = None
        self.target = None
        self.difficulty = None
        self.difficulty_source = None
        self.difficulty_received_at = None
        self._invalidate_current_job()
        if self.phase != StratumPhase.AUTH_FAILED:
            self.phase = StratumPhase.DISCONNECTED
            self.last_error = reason

    def _invalidate_current_job(self) -> None:
        if self.current_job is None:
            return
        self.invalidated_generation = self.current_job.generation_id
        self.last_job = self.current_job
        self.current_job = None
        self.jobs_invalidated += 1

    def snapshot(self, *, now: float | None = None) -> dict[str, Any]:
        observed_at = time.time() if now is None else now
        job = self.current_job or self.last_job
        job_active = self.current_job is not None
        age_ms = None
        if job is not None:
            age_ms = max(0, int((observed_at - job.received_at) * 1000))
        target = self.target
        return {
            "schema": "mla1517.stratum/1",
            "state": self.phase.value,
            "ready": self.ready,
            "connected": self.transport_connected,
            "status": self.phase.value.lower(),
            "primary": {
                "configured": True,
                "pool_id": self.pool_id,
                "transport": "CONNECTED" if self.transport_connected else "DISCONNECTED",
                "subscribed": self.subscribed,
                "authorized": self.authorized,
                "endpoint": self.endpoint,
                "worker": self.worker,
                "connected_at": self.connected_at,
                "last_message_at": self.last_message_at,
                "last_error": self.last_error,
            },
            "job": {
                "active": job_active,
                "generation": job.generation_id if job else None,
                "invalidated_generation": self.invalidated_generation,
                "job_id": job.job_id if job else None,
                "fingerprint": job.fingerprint if job else None,
                "received_at": job.received_at if job else None,
                "age_ms": age_ms,
                "clean_jobs": job.clean_jobs if job else None,
                "difficulty": self.difficulty,
                "difficulty_source": self.difficulty_source,
                "difficulty_received_at": self.difficulty_received_at,
                "share_target": f"{target:064x}" if target is not None else None,
                "target_generation": self.target_generation,
            },
            "submission": {
                "state": self.submission_phase.value,
                "last_result": self.last_result,
                "last_submit_at": self.last_submit_at,
                "last_response_at": self.last_response_at,
                "generation": self.pending_generation,
                "job_id": self.pending_job_id,
                "job_fingerprint": self.pending_fingerprint,
            },
            "counters": {
                "jobs_received": self.jobs_received,
                "jobs_invalidated": self.jobs_invalidated,
                "disconnects": self.disconnects,
                "submitted": self.submitted,
                "accepted": self.accepted,
                "rejected": self.rejected,
                "unknown": self.unknown,
            },
        }
