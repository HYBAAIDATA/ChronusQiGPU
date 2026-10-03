"""RemoteScheduler — NonceScheduler over the remote OpenCL agent/fleet.

Adapts :func:`mining.remote_hasher.hasher_for_env` — one configured agent or
the whole fleet — to the hybrid substrate's dispatch/poll lifecycle so the
Lucas partitioner can slice a job across remote devices exactly like local
silicon. This is what brings the super-GPU surface into the hybrid
coordinator: each remote agent grinds its assigned window over the real
``remote_opencl_v2`` wire, and every returned share is host re-verified by
the coordinator's consensus boundary — a remote agent cannot win by lying.

Fail-closed contract: no configured endpoint, an unreachable agent, an
agent that does not advertise ``sha256d``, or a probe grind that errors
or yields no device timing leaves ``capability().supported`` False with
the concrete reason; ``dispatch`` raises
:class:`DeviceUnsupportedError`. Nothing simulates a remote device.

Dispatch is asynchronous by construction: ``dispatch`` starts a worker
thread that runs the (blocking) remote call; ``poll`` reads the result
queue without blocking. ``cancel`` is honest about the wire: an in-flight
remote call cannot be aborted, so cancellation is attested with
``reason="cancel_requested_remote_inflight"`` and the late result is
discarded.
"""

from __future__ import annotations

import queue
import threading
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

#: Timed capability probe — a small contiguous window against an impossible
#: target (all zeros), so the remote device grinds the whole window and
#: returns a measured_ns for real work. The probe rate is recorded honestly;
#: it is a measurement on the live substrate, never a projection.
_PROBE_NONCES = 1 << 12
_PROBE_JOB_ID = "__capability_probe__"


class RemoteScheduler:
    """NonceScheduler over a remote agent or fleet of agents."""

    def __init__(self, *, timeout: float = 5.0) -> None:
        import sys
        from pathlib import Path

        repo_root = str(Path(__file__).resolve().parents[2])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from mining.remote_hasher import hasher_for_env

        self._hasher = hasher_for_env(timeout=timeout)
        self._jobs: Dict[str, bytes] = {}
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._finished: Dict[int, int] = {}
        self._records: List[ExecutionAttestation] = []
        self._registry = AttestationRegistry.get()
        self._capability: Optional[DeviceCapability] = None

    @classmethod
    def from_env(cls, timeout: float = 5.0) -> "RemoteScheduler":
        return cls(timeout=timeout)

    def prepare(self, job_id: str, header80: bytes) -> None:
        if len(header80) != 80:
            raise ValueError(f"header must be 80 bytes, got {len(header80)}")
        self._jobs[str(job_id)] = bytes(header80)

    # -- NonceScheduler ----------------------------------------------------

    def capability(self) -> DeviceCapability:
        """Probe the bound agent/fleet once; cache the honest result."""
        if self._capability is not None:
            return self._capability
        advertised = getattr(self._hasher, "k_range", None) is not None
        if not advertised:
            self._capability = DeviceCapability(
                device_id=f"remote:{self._hasher.device}",
                device_class="remote",
                measured_hashes_per_sec=0.0,
                supported=False,
                reason_if_unsupported="remote agent does not advertise the sha256d route",
            )
            return self._capability
        hps, measure_error = self._measure()
        if hps is None or hps <= 0:
            self._capability = DeviceCapability(
                device_id=str(self._hasher.device),
                device_class="remote",
                measured_hashes_per_sec=0.0,
                supported=False,
                reason_if_unsupported=f"remote probe grind failed: {measure_error}",
                detail={
                    "backend": getattr(self._hasher, "backend", "remote_opencl"),
                    "fleet_size": getattr(self._hasher, "fleet_size", 1),
                },
            )
            return self._capability
        self._capability = DeviceCapability(
            device_id=str(self._hasher.device),
            device_class="remote",
            measured_hashes_per_sec=hps,
            supported=True,
            detail={
                "backend": getattr(self._hasher, "backend", "remote_opencl"),
                "fleet_size": getattr(self._hasher, "fleet_size", 1),
                "execution_backend": self._hasher.last_execution_backend,
            },
        )
        return self._capability

    def _measure(self) -> tuple[Optional[float], Optional[str]]:
        """One timed probe window; the measured rate the partitioner weighs.

        Returns ``(hps, None)`` on a measured grind, or ``(None, reason)``
        when the dispatch errored or produced no device timing — a remote
        that cannot prove measured work is not supported, not slow.
        """
        header = bytes(80)
        target = b"\x00" * 32  # unreachable: forces a full-window grind
        self.prepare(_PROBE_JOB_ID, header)
        try:
            _, _, done = self._hasher.grind_target_range(header, target, 0, _PROBE_NONCES)
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
        measured_ns = getattr(self._hasher, "last_measured_ns", None)
        if measured_ns and measured_ns > 0:
            return int(done) / (measured_ns / 1e9), None
        return None, (
            "grind answered but reported no device timing "
            "(last_measured_ns absent or non-positive)"
        )

    def dispatch(self, window: NonceWindow) -> DispatchHandle:
        cap = self.capability()
        if not cap.supported:
            raise DeviceUnsupportedError(
                cap.reason_if_unsupported or "remote substrate not supported"
            )
        header = self._jobs.get(window.job_id)
        if header is None:
            raise DeviceUnsupportedError(
                f"job {window.job_id!r} has no bound header; call prepare() first"
            )
        handle = DispatchHandle(
            handle_id=next_handle_id(),
            device_id=cap.device_id,
            window=window,
            dispatched_ns=time.monotonic_ns(),
        )
        results: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)
        state = {
            "handle": handle,
            "results": results,
            "hashed_total": 0,
            "cancelled": False,
            "thread": None,
        }
        self._pending[handle.handle_id] = state

        def _run() -> None:
            try:
                nonce, digest, done = self._hasher.grind_target_range(
                    header, window.target, window.base_nonce, window.span
                )
                results.put({"nonce": nonce, "digest": digest, "done": int(done)})
            except Exception as exc:
                results.put({"error": f"{type(exc).__name__}: {exc}"})

        thread = threading.Thread(target=_run, daemon=True, name="remote-scheduler")
        state["thread"] = thread
        thread.start()
        self._attest("dispatch", handle, reason="dispatched")
        return handle

    def poll(self, handle: DispatchHandle) -> Optional[Share]:
        state = self._pending.get(handle.handle_id)
        if state is None:
            return None
        try:
            result = state["results"].get_nowait()
        except queue.Empty:
            return None
        device_ns = getattr(self._hasher, "last_measured_ns", None)
        if "error" in result:
            self._attest("exhausted", handle, reason=f"remote_dispatch_failed: {result['error']}")
            self._finished[handle.handle_id] = int(state["hashed_total"])
            self._pending.pop(handle.handle_id, None)
            return None
        done = int(result.get("done") or 0)
        state["hashed_total"] = done
        nonce = result.get("nonce")
        digest = result.get("digest")
        if nonce is not None:
            share = Share(
                device_id=handle.device_id,
                job_id=handle.window.job_id,
                nonce=int(nonce),
                digest=bytes(digest),
                nonces_tried=done,
                face=handle.window.face,
                probe_index=int(nonce) - handle.window.base_nonce + 1,
            )
            self._attest(
                "share",
                handle,
                nonces_tried=done,
                found=True,
                device_time_ns=device_ns,
            )
            self._finished[handle.handle_id] = done
            self._pending.pop(handle.handle_id, None)
            return share
        self._attest(
            "exhausted",
            handle,
            nonces_tried=handle.window.span,
            device_time_ns=device_ns,
            reason="window_exhausted",
        )
        self._finished[handle.handle_id] = done
        self._pending.pop(handle.handle_id, None)
        return None

    def cancel(self, handle: DispatchHandle, reason: str = "cancelled") -> None:
        state = self._pending.pop(handle.handle_id, None)
        if state is None or state["cancelled"]:
            return
        state["cancelled"] = True
        self._finished[handle.handle_id] = int(state["hashed_total"])
        # The remote wire is request/response: an in-flight call cannot be
        # aborted, so the attestation records the truth — cancellation was
        # requested while the remote window was still executing; whatever
        # the agent returns for it is discarded.
        self._attest(
            "cancelled",
            handle,
            reason=f"{reason}; remote call in flight (result discarded)",
        )

    def is_done(self, handle: DispatchHandle) -> bool:
        return handle.handle_id not in self._pending

    def hashed_count(self, handle: DispatchHandle) -> int:
        state = self._pending.get(handle.handle_id)
        if state is not None:
            return int(state["hashed_total"])
        return int(self._finished.get(handle.handle_id, 0))

    def attestation(self) -> List[ExecutionAttestation]:
        return list(self._records)

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
            device_class="remote",
            handle_id=handle.handle_id,
            window=handle.window,
            timestamp_ns=time.monotonic_ns(),
            device_time_ns=device_time_ns,
            nonces_tried=nonces_tried,
            found=found,
            reason=reason,
            detail={"module": "hyba.hybrid.remote_solver"},
        )
        self._records.append(record)
        self._registry.record(record)
        return record


__all__ = ["RemoteScheduler"]
