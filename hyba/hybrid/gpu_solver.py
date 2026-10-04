"""GPUSolver — NonceScheduler over the in-process OpenCL SHA-256d hasher.

Wraps :class:`mining.bitcoin_hasher.BitcoinHasher`, which already provides
the corrected scanner contract: host-computed midstate, on-device nonce
derivation, atomic_min winner reduction, and a hashlib re-check of every
device-reported hit. The solver adds the hybrid lifecycle: capability()
measures throughput on the live device, dispatch() attests before the
first nonce is tried, and poll() grinds the window in bounded chunks so
the coordinator can interleave devices and cancel losers.

Fallback honesty: when the hasher falls back to its CPU path, this solver
reports ``device_class="cpu"`` and the hasher's ``fallback_reason`` — the
capability record always names the substrate that will actually execute.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from hyba.hybrid.nonce_scheduler import (
    AttestationRegistry,
    DeviceCapability,
    DeviceUnsupportedError,
    DispatchHandle,
    ExecutionAttestation,
    NonceWindow,
    Share,
    next_handle_id,
)

POLL_CHUNK_NONCES = 1 << 18  # per-poll grind bound: keeps hybrid polling fair


class GPUSolver:
    """NonceScheduler over the resident SHA-256d scanner.

    ``backend`` is any in-process lane ``hasher_for_backend`` resolves —
    ``auto``/``cpu``/``opencl``/``gpu`` (OpenCL or its declared CPU
    reference) and ``cuda``/``metal`` (the Chronus-owned native lanes).
    ``remote`` belongs to ``RemoteScheduler`` and is rejected here.
    """

    def __init__(self, backend: str = "auto", allow_cpu: bool = True) -> None:
        from mining.bitcoin_hasher import GRIND_BATCH, hasher_for_backend

        if (backend or "").strip().lower() == "remote":
            raise DeviceUnsupportedError(
                "GPUSolver binds in-process lanes only; use RemoteScheduler for 'remote'"
            )
        self._grind_batch = int(GRIND_BATCH)
        self._hasher = hasher_for_backend(backend)
        self._jobs: Dict[str, bytes] = {}
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._finished: Dict[int, int] = {}
        self._records: List[ExecutionAttestation] = []
        self._registry = AttestationRegistry.get()
        self._capability: Optional[DeviceCapability] = None
        if self._hasher.backend == "cpu" and not allow_cpu:
            raise DeviceUnsupportedError(
                f"GPU solver unavailable: {self._hasher.fallback_reason}"
            )

    # -- job binding -------------------------------------------------------

    def prepare(self, job_id: str, header80: bytes) -> None:
        """Bind the 80-byte block header a job's windows will grind."""
        if len(header80) != 80:
            raise ValueError(f"header must be 80 bytes, got {len(header80)}")
        self._jobs[str(job_id)] = bytes(header80)

    # -- NonceScheduler ----------------------------------------------------

    def capability(self) -> DeviceCapability:
        """Measured throughput from a timed warm run on the live substrate."""
        if self._capability is not None:
            return self._capability
        if self._hasher.backend == "cpu":
            self._capability = DeviceCapability(
                device_id=self._hasher.device,
                device_class="cpu",
                measured_hashes_per_sec=self._measure(),
                supported=True,
                reason_if_unsupported=None,
                detail={"fallback_reason": self._hasher.fallback_reason},
            )
            return self._capability
        self._capability = DeviceCapability(
            device_id=self._hasher.device,
            device_class="gpu",
            measured_hashes_per_sec=self._measure(),
            supported=True,
            detail={"backend": self._hasher.backend},
        )
        return self._capability

    def _measure(self) -> float:
        """~1s timed grind; device-side rate preferred, wall rate recorded."""
        header = bytes(80)
        target = b"\xff" * 32
        kernel_ms0 = self._hasher.kernel_ms
        wall0 = time.perf_counter()
        nonces = 0
        # The hasher's grind_batch is derived from the real device memory limit
        # and can sit below this solver's policy constant, so the request is
        # bounded by the hasher's own accepted cap. Using self._grind_batch here
        # raised ValueError on any device whose snapped cap is smaller.
        launch = max(1, min(int(self._grind_batch), int(self._hasher.grind_batch)))
        while time.perf_counter() - wall0 < 0.5:
            _, _, done = self._hasher.grind_target_range(header, target, 0, launch)
            nonces += done
            break  # a single max-range launch already saturates the queue
        wall_s = max(time.perf_counter() - wall0, 1e-9)
        kernel_s = (self._hasher.kernel_ms - kernel_ms0) / 1e3
        if kernel_s > 0:
            return nonces / kernel_s
        return nonces / wall_s

    def dispatch(self, window: NonceWindow) -> DispatchHandle:
        cap = self.capability()
        if not cap.supported:
            raise DeviceUnsupportedError(
                cap.reason_if_unsupported or "gpu solver not supported"
            )
        if window.job_id not in self._jobs:
            raise DeviceUnsupportedError(
                f"job {window.job_id!r} has no bound header; call prepare() first"
            )
        handle = DispatchHandle(
            handle_id=next_handle_id(),
            device_id=cap.device_id,
            window=window,
            dispatched_ns=time.monotonic_ns(),
        )
        self._pending[handle.handle_id] = {
            "handle": handle,
            "cursor": window.base_nonce,
            "remaining": window.span,
            "hashed_total": 0,
            "cancelled": False,
        }
        self._attest("dispatch", handle, reason="dispatched")
        return handle

    def poll(self, handle: DispatchHandle) -> Optional[Share]:
        state = self._pending.get(handle.handle_id)
        if state is None or state["cancelled"]:
            return None
        window = handle.window
        take = min(POLL_CHUNK_NONCES, self._grind_batch, state["remaining"])
        if take <= 0:
            return None
        header = self._jobs[window.job_id]
        kernel_ms0 = self._hasher.kernel_ms
        chunk_base = state["cursor"]
        winner, digest, hashed = self._hasher.grind_target_range(
            header, window.target, chunk_base, take
        )
        device_ns = int((self._hasher.kernel_ms - kernel_ms0) * 1e6) or None
        state["cursor"] += take
        state["remaining"] -= take
        state["hashed_total"] += int(hashed)
        if winner is not None:
            # Probe position in the emitted traversal order: hashes fully
            # burned by earlier chunks + offset of the winner in its chunk.
            probe_index = (
                state["hashed_total"] - take + (int(winner) - chunk_base + 1)
            )
            share = Share(
                device_id=handle.device_id,
                job_id=window.job_id,
                nonce=int(winner),
                digest=bytes(digest),
                nonces_tried=int(hashed),
                face=window.face,
                probe_index=probe_index,
            )
            self._attest(
                "share", handle, nonces_tried=int(hashed), found=True,
                device_time_ns=device_ns,
            )
            self._finished[handle.handle_id] = int(state["hashed_total"])
            self._pending.pop(handle.handle_id, None)
            return share
        if state["remaining"] <= 0:
            self._attest(
                "exhausted", handle, nonces_tried=window.span,
                device_time_ns=device_ns, reason="window_exhausted",
            )
            self._finished[handle.handle_id] = int(state["hashed_total"])
            self._pending.pop(handle.handle_id, None)
        return None

    def cancel(self, handle: DispatchHandle, reason: str = "cancelled") -> None:
        state = self._pending.pop(handle.handle_id, None)
        if state is None or state["cancelled"]:
            return
        state["cancelled"] = True
        self._finished[handle.handle_id] = int(state["hashed_total"])
        self._attest("cancelled", handle, reason=reason)

    def is_done(self, handle: DispatchHandle) -> bool:
        """True once the handle produced a share, exhausted, or was cancelled."""
        return handle.handle_id not in self._pending

    def hashed_count(self, handle: DispatchHandle) -> int:
        """Total physical hashes executed for this handle so far."""
        state = self._pending.get(handle.handle_id)
        if state is not None:
            return int(state["hashed_total"])
        return int(self._finished.get(handle.handle_id, 0))

    def attestation(self) -> List[ExecutionAttestation]:
        return list(self._records)

    # -- internals ---------------------------------------------------------

    def _attest(
        self,
        kind: str,
        handle: DispatchHandle,
        *,
        nonces_tried: int = 0,
        found: bool = False,
        device_time_ns: Optional[int] = None,
        reason: str = "",
    ) -> ExecutionAttestation:
        record = ExecutionAttestation(
            kind=kind,
            device_id=handle.device_id,
            device_class=self.capability().device_class,
            handle_id=handle.handle_id,
            window=handle.window,
            timestamp_ns=time.monotonic_ns(),
            device_time_ns=device_time_ns,
            nonces_tried=nonces_tried,
            found=found,
            reason=reason,
            detail={"module": "hyba.hybrid.gpu_solver"},
        )
        self._records.append(record)
        self._registry.record(record)
        return record


__all__ = ["GPUSolver", "POLL_CHUNK_NONCES"]
