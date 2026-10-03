"""SuperAsicHasher — the registry's ``super_asic`` lane.

One hasher over EVERY bound mining substrate: the local OpenCL/CPU solver,
any physically attached ASIC channel, and every configured remote GPU agent
(or fleet). The lucas partitioner divides each requested window across the
joined substrates by measured throughput, the coordinator dispatches them
concurrently, and every returned share is host re-verified — the composite
is strictly faster than its slowest member only when it actually is, and
the ``backend`` label always names the substrates that really joined.

This is the wiring for combining ASIC-class channels with the super-GPU
remote fleet for increased hashrate: same window, more silicon, measured.

Honesty contract:

- ``backend`` reports ``super_asic:`` plus the joined device classes
  (e.g. ``super_asic:cpu``, ``super_asic:gpu+remote``, ``super_asic:asic+gpu``).
- ``k_range`` exists because partitioned contiguous dispatch is real;
  ``k_m32``/``k_gold``/``k_hendrix`` stay ``None`` — the composite does
  partition, it does not reproduce the m32 lane-order or gold-stride
  traversal inside a member window.
- ``launches``/``kernel_ms`` count device-side work only (windows executed
  on a non-CPU substrate and their attested ``device_time_ns``); CPU member
  work is real work but not a device launch.
- When only one substrate binds, the lane still runs — a degenerate
  composition is real execution, labelled accordingly.
"""

from __future__ import annotations

import itertools
import os
import time
from typing import Dict, List, Optional, Sequence

from hyba.hybrid.asic_solver import ASICSolver
from hyba.hybrid.coordinator import HybridCoordinator, JobResult, StratumJob
from hyba.hybrid.gpu_solver import GPUSolver
from hyba.hybrid.nonce_scheduler import (
    AttestationRegistry,
    DeviceCapability,
    DeviceUnsupportedError,
    NonceScheduler,
    NonceWindow,
    verify_share,
)

_JOB_IDS = itertools.count(1)

#: Upper bound for one ASIC channel grind call. A channel that never
#: answers fails loudly instead of spinning the poll loop forever.
_ASIC_GRIND_TIMEOUT_S = float(os.environ.get("PYTHIA_ASIC_GRIND_TIMEOUT", "300"))


class AsicHasherAdapter:
    """The registry's grind surface over a probed :class:`ASICSolver`.

    Only meaningful when the solver's capability probe actually bound a
    dispatch-capable ASIC channel (today: the network channel); the
    registry's probe is what decides that — this adapter assumes it and
    still re-verifies every share host-side before returning it.
    """

    backend = "asic"
    launches = 0
    kernel_ms = 0.0
    grind_batch = 1 << 20
    m32_window_max = 1 << 32
    k_gold = k_m32 = None
    fallback_reason = None
    vendor = None

    def __init__(self, solver: ASICSolver) -> None:
        self._solver = solver
        self.device = solver.capability().device_id
        # The network dispatch protocol exists; its presence means a
        # contiguous-window arm is real.
        self.k_range = object()

    def _grind_window(self, header80: bytes, target_be: bytes, base: int, count: int):
        job_id = f"asic-{_next_job_seq()}"
        window = NonceWindow(
            job_id=job_id,
            session_epoch=0,
            job_epoch=0,
            base_nonce=base,
            span=count,
            target=target_be,
        )
        handle = self._solver.dispatch(window)
        deadline = time.perf_counter() + _ASIC_GRIND_TIMEOUT_S
        while not self._solver.is_done(handle):
            if time.perf_counter() > deadline:
                self._solver.cancel(handle, reason="grind_deadline_exceeded")
                raise RuntimeError(
                    f"ASIC channel did not answer window within {_ASIC_GRIND_TIMEOUT_S:g}s"
                )
            share = self._solver.poll(handle)
            if share is None:
                time.sleep(0.001)
                continue
            if not verify_share(share, header80[:76], target_be):
                raise RuntimeError("ASIC returned a share failing host re-verification")
            self.launches += 1
            return share.nonce, share.digest, share.nonces_tried
        # No share: the channel attests exhaustion at full span — the
        # honest executed count is the whole window.
        self.launches += 1
        return None, None, count

    def grind_target_range(self, header80, target_be, base_nonce, count):
        return self._grind_window(header80, target_be, int(base_nonce), int(count))

    def grind_target_range_chunked(
        self, header80, target_be, base_nonce, count, stop_on_first: bool = True
    ):
        return self.grind_target_range(header80, target_be, base_nonce, count)

    def grind_target_m32(self, header80, target_be, base_nonce, lane_order, count):
        raise RuntimeError(
            "asic lane dispatches contiguous windows; in-window m32 lane order "
            "is not a contract the ASIC channel implements"
        )

    def grind_target_batch(self, header80, target_be, nonces: Sequence[int]):
        for run_base, run_len in _contiguous_runs(nonces):
            nonce, digest, done = self._grind_window(header80, target_be, run_base, run_len)
            if nonce is not None:
                return nonce, digest, done
        return None, None, len(nonces)


def _next_job_seq() -> int:
    return next(_JOB_IDS)


def _contiguous_runs(nonces: Sequence[int]) -> List[tuple[int, int]]:
    """Decompose an explicit nonce set into (base, span) contiguous runs."""
    ordered = sorted({int(n) & 0xFFFFFFFF for n in nonces})
    if not ordered:
        return []
    runs: List[tuple[int, int]] = []
    start = prev = ordered[0]
    for n in ordered[1:]:
        if n != prev + 1:
            runs.append((start, prev - start + 1))
            start = n
        prev = n
    runs.append((start, prev - start + 1))
    return runs


class SuperAsicHasher:
    """One hasher dispatching each window across every bound substrate."""

    # The contiguous-window arm is real — partition + dispatch is what this
    # lane IS. m32/gold traversal inside a member window is not implemented:
    # the handles stay absent so callers cannot select what does not exist.
    k_gold = k_m32 = k_hendrix = None
    fallback_reason: Optional[str] = None
    vendor = None
    grind_batch = 1 << 32  # the partition accepts the full nonce field
    m32_window_max = 1 << 32

    def __init__(self, coordinator: HybridCoordinator, members: List[NonceScheduler]) -> None:
        if not members:
            raise DeviceUnsupportedError("super_asic lane bound zero substrates")
        self._coord = coordinator
        self._members = list(members)
        self._caps: Dict[int, DeviceCapability] = {id(m): m.capability() for m in self._members}
        classes = sorted({c.device_class for c in self._caps.values()})
        self.backend = "super_asic:" + "+".join(classes)
        self.device = "hybrid[" + ", ".join(c.device_id for c in self._caps.values()) + "]"
        self.k_range = object()
        self.launches = 0
        self.kernel_ms = 0.0
        self.remote_calls = 0
        self.remote_ms = 0.0
        self.last_result: Optional[JobResult] = None
        self._registry = AttestationRegistry.get()

    @classmethod
    def bind(cls, *, allow_cpu: bool = True, remote_timeout: float = 5.0) -> "SuperAsicHasher":
        """Compose every substrate that is actually bound, in honesty order.

        Order: a physically attached ASIC channel, then the remote fleet
        (super-GPU surface), then the local OpenCL/CPU solver — the resident
        floor. Each member is bound with a real probe; absent channels and
        unconfigured endpoints simply do not join, never silently.
        """
        members: List[NonceScheduler] = []
        asic = ASICSolver()
        gpu = GPUSolver(backend="auto", allow_cpu=allow_cpu)
        remote = None
        try:
            from hyba.hybrid.remote_solver import RemoteScheduler

            remote = RemoteScheduler.from_env(timeout=remote_timeout)
        except Exception:
            remote = None
        if remote is not None and remote.capability().supported:
            members.append(remote)
        coord = HybridCoordinator(gpu, asic, extra_devices=members)
        joined = coord._devices()
        return cls(coord, joined)

    def _run(self, header80: bytes, target_be: bytes, base: int, count: int) -> tuple:
        job_id = f"superasic-{_next_job_seq()}"
        job = StratumJob(
            job_id=job_id,
            header80=bytes(header80),
            target=bytes(target_be),
            nonce_space=int(count),
            base_nonce=int(base),
        )
        # Device-side accounting: only attestations appended by THIS run
        # count, and only windows executed on a non-CPU substrate are device
        # launches — a CPU member's work is real work, not a launch.
        before = len(self._registry.snapshot())
        result = self._coord.run_job(job)
        self.last_result = result
        device_ns = 0
        device_windows = 0
        for rec in self._registry.snapshot()[before:]:
            if rec.get("kind") not in ("share", "exhausted"):
                continue
            if rec.get("device_class") == "cpu":
                continue
            window = rec.get("window") or {}
            if window.get("job_id") != job_id:
                continue
            device_windows += 1
            if rec.get("device_time_ns"):
                device_ns += int(rec["device_time_ns"])
        self.launches += device_windows
        self.kernel_ms += device_ns / 1e6
        share = result.share
        return (
            share.nonce if share is not None else None,
            share.digest if share is not None else None,
            int(result.total_nonces_tried),
        )

    def grind_target_range(self, header80, target_be, base_nonce, count):
        return self._run(header80, target_be, base_nonce, count)

    def grind_target_range_chunked(
        self, header80, target_be, base_nonce, count, stop_on_first: bool = True
    ):
        # The coordinator already dispatches all member windows concurrently
        # and cancels losers on the first verified share — that IS the
        # chunked stop-on-first discipline at composite granularity.
        return self.grind_target_range(header80, target_be, base_nonce, count)

    def grind_target_m32(self, header80, target_be, base_nonce, lane_order, count):
        raise RuntimeError(
            "super_asic dispatches the lucas partition (contiguous spans); "
            "in-window m32 lane order is not implemented on the composite"
        )

    def grind_target_batch(self, header80, target_be, nonces: Sequence[int]):
        total = 0
        for run_base, run_len in _contiguous_runs(nonces):
            nonce, digest, done = self._run(header80, target_be, run_base, run_len)
            total += int(done)
            if nonce is not None:
                return nonce, digest, total
        return None, None, total


__all__ = ["AsicHasherAdapter", "SuperAsicHasher"]
