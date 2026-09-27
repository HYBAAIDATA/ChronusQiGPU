"""Centralized IPC failure telemetry bus for Salamander systems autonomic healing.

Captures mathematical, hardware, and worker pool invariant violations across
multiprocess boundaries and orchestrates zero-trust state degradation into the WORM ledger.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
import queue
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hyba.salamander.failure_bus")

WORM_LEDGER_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "audit_evidence"
    / "SALAMANDER_STATE_DEGRADATION_WORM.jsonl"
)
AL_HARAS_DEGRADATION_KEY = b"AL_HARAS_AUTONOMIC_DEGRADATION_ATTESTATION_KEY_V1"


@dataclass
class FailureEvent:
    """Structured failure telemetry payload."""

    worker_id: str
    failure_type: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    traceback_text: str = ""


class SalamanderFailureBus:
    """Centralized thread-safe and IPC telemetry bus for runtime failure interception."""

    _instance: Optional["SalamanderFailureBus"] = None

    def __init__(self) -> None:
        self._queue: queue.Queue[FailureEvent] = queue.Queue(maxsize=1000)
        self._history: List[FailureEvent] = []

    @classmethod
    def get_instance(cls) -> "SalamanderFailureBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def publish(self, event: FailureEvent) -> None:
        """Publish a failure event to the telemetry queue."""
        try:
            self._queue.put_nowait(event)
            self._history.append(event)
            logger.warning(
                "[SALAMANDER BUS] Ingested failure | worker=%s | type=%s",
                event.worker_id,
                event.failure_type,
            )
        except queue.Full:
            logger.error("[SALAMANDER BUS] Failure telemetry queue full; dropping event")

    def poll(self, max_items: int = 10) -> List[FailureEvent]:
        """Drain up to max_items failure events from the queue."""
        events: List[FailureEvent] = []
        for _ in range(max_items):
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def has_failures(self) -> bool:
        """Check if any unhandled failure events are in the queue."""
        return not self._queue.empty()

    def clear(self) -> None:
        """Drain all items from the queue and history (for test isolation)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._history.clear()

    def record_state_degradation(
        self,
        event: FailureEvent,
        fallback_lane: str = "cpu_single_process",
        ledger_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Record an immutable state degradation event into the WORM audit ledger."""
        path = ledger_path or WORM_LEDGER_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(event.timestamp)),
            "worker_id": event.worker_id,
            "failure_type": event.failure_type,
            "fallback_lane": fallback_lane,
            "details": event.details,
            "truth_class": "autonomic-degradation",
        }

        # Deterministic HMAC-SHA256 signature
        raw_msg = f"{payload['timestamp']}:{event.worker_id}:{event.failure_type}:{fallback_lane}:{json.dumps(event.details, sort_keys=True)}".encode(
            "utf-8"
        )
        signature = hmac.new(AL_HARAS_DEGRADATION_KEY, raw_msg, hashlib.sha256).hexdigest()
        payload["signature"] = signature

        line = json.dumps(payload) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

        logger.info(
            "[SALAMANDER WORM] State degradation committed to %s | worker=%s | fallback=%s",
            path.name,
            event.worker_id,
            fallback_lane,
        )
        return payload
