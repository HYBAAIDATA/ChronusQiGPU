# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Same-hash verification of fleet results against the pure-Python reference.

Every tile result is checked in at least one of these ways before a job's
receipt is signed:

* sampled: a tile is chosen by HMAC-SHA256 under a secret only the coordinator
  holds, so no worker can tell which of its tiles will be recomputed; at least
  one tile of every device that contributed to a job is always checked;
* on disagreement: two results for the same tile that differ, or a tile whose
  bytes do not match the digest the worker reported, are settled by the
  reference, and every other tile that device produced in the job is then
  recomputed as well;
* blind check: tiles re-executed after a fault go through the P2c channels in
  ``chronus.fleet.recovery``.

A device that returns one wrong answer is quarantined: it receives no further
leases until it rejoins and passes its self-test again.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import queue
import secrets
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from chronus.fleet.canonical import sha256_hex
from chronus.fleet.kernels import Kernel

logger = logging.getLogger(__name__)
PPM = 1_000_000


class SamplingPolicy:
    def __init__(self, rate_ppm: int = 125_000, secret: bytes | None = None) -> None:
        if not isinstance(rate_ppm, int) or not 0 <= rate_ppm <= PPM:
            raise ValueError("sample rate must be an integer number of parts per million in [0, 1000000]")
        self.rate_ppm = rate_ppm
        self._secret = secret if secret is not None else secrets.token_bytes(32)

    def sampled(self, job_id: str, tile_index: int) -> bool:
        if self.rate_ppm == 0:
            return False
        if self.rate_ppm == PPM:
            return True
        mac = hmac.new(self._secret, f"{job_id}:{tile_index}".encode("utf-8"), hashlib.sha256).digest()
        return int.from_bytes(mac[:8], "big") * PPM < self.rate_ppm * (1 << 64)

    def describe(self) -> dict[str, Any]:
        return {
            "sample_rate_ppm": self.rate_ppm,
            "min_checked_tiles_per_device_per_job": 1,
            "selection": "HMAC-SHA256 under a coordinator-only secret; workers cannot tell which tiles are checked",
            "reference_route": "reference (deterministic pure Python)",
            "on_disagreement": "reference arbitration, then every tile of the disagreeing device in the job is checked",
        }


@dataclass(frozen=True)
class VerificationTask:
    job_id: str
    tile_index: int
    node_id: str
    kernel: Kernel
    params: Mapping[str, Any]
    tile_input: bytes
    start: int
    stop: int
    claimed_sha256: str
    reason: str


@dataclass(frozen=True)
class VerificationOutcome:
    task: VerificationTask
    reference_output: bytes | None
    reference_sha256: str | None
    match: bool
    error: str | None = None


def reference_tile(kernel: Kernel, params: Mapping[str, Any], tile: bytes, start: int, stop: int) -> bytes:
    """The reference route's output for one tile."""
    return kernel.run_reference(None, params, tile, start, stop)


class ReferenceVerifier:
    """Background threads that recompute tiles on the reference route."""

    def __init__(self, on_outcome: Callable[[VerificationOutcome], None], threads: int = 2) -> None:
        self._queue: queue.Queue[VerificationTask | None] = queue.Queue()
        self._on_outcome = on_outcome
        self._threads = [
            threading.Thread(target=self._run, name=f"fleet-verifier-{i}", daemon=True) for i in range(max(1, threads))
        ]
        for thread in self._threads:
            thread.start()

    def submit(self, task: VerificationTask) -> None:
        self._queue.put(task)

    def pending(self) -> int:
        return self._queue.qsize()

    def stop(self) -> None:
        for _ in self._threads:
            self._queue.put(None)
        for thread in self._threads:
            thread.join(timeout=5)

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            if task is None:
                return
            try:
                output = reference_tile(task.kernel, task.params, task.tile_input, task.start, task.stop)
                digest = sha256_hex(output)
                outcome = VerificationOutcome(task, output, digest, digest == task.claimed_sha256)
            except Exception as exc:  # reported, never treated as a match
                logger.exception("reference verification failed")
                outcome = VerificationOutcome(task, None, None, False, f"{type(exc).__name__}: {exc}")
            try:
                self._on_outcome(outcome)
            except Exception:
                logger.exception("verification outcome handler failed")
