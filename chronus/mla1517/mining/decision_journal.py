"""Durable decision evidence for the production mining loop.

Every dispatch, routing and optimisation decision the coordinator makes is
recorded here before its effect, with the full contract fields:

    decision_id       stable id for this decision
    pool_session_id   the Stratum session the decision lives under
    generation        the job epoch the decision applies to
    job_id            pool job id
    job_fingerprint   fingerprint of the job the decision ran on
    observation       the measured state the decision observed
    available_actions the actions the policy was allowed to choose from
    selected_action   the action taken
    reason            the measured reason, never "heuristic said so"
    execution_target  the lane/route the decision ran on (filled on resolve)
    result            the measured outcome (filled on resolve)
    disposition       EXECUTED / REFUSED / STALE / OUTCOME_UNKNOWN
    timestamp         decision time
    software_revision the build that made the decision

Records mirror to the coordinator's causal ledger so a replayable JSONL
evidence trail exists without a second storage path.
"""

from __future__ import annotations

import importlib.metadata
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any, Callable

from Intelligence.lucas_scales import ladder_capacity

SCHEMA = "pythia.decision_journal/1"


class DecisionDisposition(StrEnum):
    EXECUTED = "EXECUTED"
    REFUSED = "REFUSED"
    STALE = "STALE"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    PENDING = "PENDING"


def _software_revision() -> str:
    """The build that made the decision; honest when uninstalled."""
    try:
        return f"hyba-pythia-mining@{importlib.metadata.version('hyba-pythia-mining')}"
    except importlib.metadata.PackageNotFoundError:
        return "hyba-pythia-mining@uninstalled"
    except Exception:
        return "hyba-pythia-mining@unknown"


SOFTWARE_REVISION = _software_revision()


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    pool_session_id: str | None
    generation: int | None
    job_id: str | None
    job_fingerprint: str | None
    observation: dict[str, Any]
    available_actions: list[str]
    selected_action: str
    reason: str
    timestamp: float
    software_revision: str = field(default=SOFTWARE_REVISION)
    execution_target: str | None = None
    result: dict[str, Any] | None = None
    disposition: str = DecisionDisposition.PENDING.value

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class DecisionJournal:
    """Bounded durable record of the loop's decisions.

    ``record`` appends a decision before its effect; ``resolve`` attaches
    the measured outcome to the matching decision id (a decision never
    appears resolved without a result). ``on_record`` mirrors each state
    of the record into the causal ledger.
    """

    def __init__(
        self,
        *,
        capacity: int = ladder_capacity(512),
        on_record: Callable[[DecisionRecord], None] | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._records: deque[DecisionRecord] = deque(maxlen=capacity)
        self._by_id: dict[str, DecisionRecord] = {}
        self._lock = threading.Lock()
        self._on_record = on_record

    def record(
        self,
        *,
        decision_id: str,
        pool_session_id: str | None,
        generation: int | None,
        job_id: str | None,
        job_fingerprint: str | None,
        observation: dict[str, Any],
        available_actions: list[str],
        selected_action: str,
        reason: str,
        execution_target: str | None = None,
        disposition: str = DecisionDisposition.PENDING.value,
    ) -> DecisionRecord:
        if not decision_id or not selected_action:
            raise ValueError("decision_id and selected_action are required")
        if not available_actions:
            raise ValueError("available_actions must name what was allowed")
        record = DecisionRecord(
            decision_id=decision_id,
            pool_session_id=pool_session_id,
            generation=generation,
            job_id=job_id,
            job_fingerprint=job_fingerprint,
            observation=observation,
            available_actions=list(available_actions),
            selected_action=selected_action,
            reason=reason,
            execution_target=execution_target,
            disposition=disposition,
            timestamp=time.time(),
        )
        with self._lock:
            self._records.append(record)
            self._by_id[decision_id] = record
        self._mirror(record)
        return record

    def resolve(
        self,
        decision_id: str,
        *,
        result: dict[str, Any],
        disposition: str,
        execution_target: str | None = None,
    ) -> DecisionRecord | None:
        """Attach the measured outcome to the recorded decision."""
        with self._lock:
            prior = self._by_id.get(decision_id)
            if prior is None:
                return None
            resolved = replace(
                prior,
                result=dict(result),
                disposition=disposition,
                execution_target=execution_target or prior.execution_target,
            )
            self._by_id[decision_id] = resolved
            self._records.append(resolved)
        self._mirror(resolved)
        return resolved

    def _mirror(self, record: DecisionRecord) -> None:
        if self._on_record is None:
            return
        try:
            self._on_record(record)
        except Exception:
            # Decision evidence must never break the mining loop.
            pass

    def snapshot(self, limit: int = 16) -> list[dict[str, Any]]:
        with self._lock:
            return [record.as_dict() for record in list(self._records)[-limit:]]
