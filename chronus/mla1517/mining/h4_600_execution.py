"""Canonical H4/600-cell execution coordinator for PYTHIA mining.

This module promotes the repository's existing 600-cell geometry into the real
composite mining dispatch path without creating a second Stratum client or a
second proof boundary.

The mathematical topology is fixed at 600 logical search vertices (the 600
cell-normal frames lifted to R^11).  Physical capacity is elastic underneath:
a fleet with fewer than 600 workers queues multiple logical vertices per
worker; a fleet with 600 or more independently capable workers can execute the
600 shards concurrently.  Hashrate is always measured physical work, never
``600 * single-worker-rate`` unless 600 workers actually execute that work.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from hyba.hybrid.coordinator import HybridCoordinator, JobResult, StratumJob
from hyba.hybrid.lucas_partition import H4_FACE_COUNT, partition
from hyba.hybrid.nonce_scheduler import (
    AttestationViolation,
    DispatchHandle,
    NonceScheduler,
    NonceWindow,
    Share,
    verify_share,
)
from hyba.hybrid.performance import LayerSample
from hyba.hybrid.tensor_advisor import apply_tensor_advice


class H4600HybridCoordinator(HybridCoordinator):
    """HybridCoordinator whose production partition is the H4/600-cell fabric."""

    topology_id = "chronus_h4_600_11d"
    logical_vertices = H4_FACE_COUNT

    @classmethod
    def promote(cls, coordinator: HybridCoordinator) -> "H4600HybridCoordinator":
        """Promote an already-bound coordinator without probing devices twice."""
        if isinstance(coordinator, cls):
            return coordinator
        promoted = cls.__new__(cls)
        promoted.__dict__ = dict(coordinator.__dict__)
        return promoted

    def run_job(
        self,
        job: StratumJob,
        *,
        strategy: str = "h4_600",
        history: Optional[Any] = None,
    ) -> JobResult:
        """Dispatch the full lease as 600 certified logical search shards.

        ``strategy`` is accepted for API compatibility but cannot demote the
        production coordinator back to the historical 32-face partition.
        """
        del strategy
        t0 = time.monotonic_ns()
        history = history if history is not None else self.history
        devices = self._devices()

        for device in devices:
            prepare = getattr(device, "prepare", None)
            if callable(prepare):
                prepare(job.job_id, job.header80)

        spans, cert = partition(job.nonce_space, devices, history, strategy="h4_600")
        if cert.topology != self.topology_id:
            raise RuntimeError(f"unexpected mining topology: {cert.topology}")
        if job.nonce_space >= H4_FACE_COUNT and len(spans) != H4_FACE_COUNT:
            raise RuntimeError(
                f"H4 production lease expected {H4_FACE_COUNT} active shards, got {len(spans)}"
            )
        if not cert.verify():
            raise RuntimeError("H4/600 coverage certificate failed verification")

        tensor_advice: Optional[Dict[str, Any]] = None
        if self.tensor_ranker is not None:
            spans, evidence = apply_tensor_advice(self.tensor_ranker, job, spans)
            tensor_advice = evidence.as_dict()

        device_by_id: Dict[str, NonceScheduler] = {
            device.capability().device_id: device for device in devices
        }
        device_queues: Dict[str, List[tuple]] = {}
        all_handles: List[tuple] = []
        handle_records: List[Dict[str, Any]] = []

        # Every logical vertex is dispatched before polling begins. Separate
        # physical schedulers therefore run concurrently; a scheduler owning
        # multiple vertices serialises its own queue, which is truthful when
        # the fleet has fewer than 600 workers.
        for span in spans:
            scheduler = device_by_id[span.device_id]
            window = NonceWindow(
                job_id=job.job_id,
                session_epoch=job.session_epoch,
                job_epoch=job.job_epoch,
                base_nonce=job.base_nonce + span.base_nonce,
                span=span.span,
                target=job.target,
                face=span.face,
            )
            handle = scheduler.dispatch(window)
            device_queues.setdefault(span.device_id, []).append((scheduler, handle, window))
            all_handles.append((scheduler, handle, window))
            handle_records.append(handle.as_dict())

        def _done(scheduler: NonceScheduler, handle: DispatchHandle) -> bool:
            is_done = getattr(scheduler, "is_done", None)
            return bool(is_done(handle)) if callable(is_done) else False

        winner: Optional[Share] = None
        winner_entry: Optional[tuple] = None
        device_cursor: Dict[str, int] = {device_id: 0 for device_id in device_queues}

        while winner is None:
            live = False
            for device_id, queue in device_queues.items():
                idx = device_cursor[device_id]
                while idx < len(queue) and _done(queue[idx][0], queue[idx][1]):
                    idx += 1
                device_cursor[device_id] = idx
                if idx >= len(queue):
                    continue
                live = True
                scheduler, handle, window = queue[idx]
                share = scheduler.poll(handle)
                if share is None:
                    continue
                if not verify_share(share, job.header80[:76], job.target):
                    raise AttestationViolation(
                        "device returned a share that fails host verification"
                    )
                winner = share
                winner_entry = (scheduler, handle, window)
                break
            if not live:
                break

        for device_id, queue in device_queues.items():
            idx = device_cursor[device_id]
            for scheduler, handle, window in queue[idx:]:
                if _done(scheduler, handle):
                    continue
                scheduler.cancel(handle, reason="peer_won" if winner else "job_aborted")
                self.history.append(window.face, handle.device_id, False, window.span)

        if winner is not None:
            self.history.append(winner.face, winner.device_id, True, winner.nonces_tried)

        winner_probe_index: Optional[int] = None
        if winner is not None and winner_entry is not None:
            _, winner_handle, _ = winner_entry
            queue = device_queues.get(winner.device_id, [])
            winner_pos = next(
                (i for i, (_, handle, _) in enumerate(queue) if handle.handle_id == winner_handle.handle_id),
                0,
            )
            prior = sum(window.span for _, _, window in queue[:winner_pos])
            winner_probe_index = prior + winner.probe_index

        per_device: Dict[str, int] = {device_id: 0 for device_id in device_by_id}
        for record, (scheduler, handle, window) in zip(handle_records, all_handles):
            counter = getattr(scheduler, "hashed_count", None)
            completed = max(0, int(counter(handle))) if callable(counter) else 0
            terminal = _done(scheduler, handle)
            record["assigned_nonces"] = int(window.span)
            record["completed_nonces"] = completed
            record["terminal_observed"] = terminal
            record["fully_completed"] = terminal and completed == int(window.span)
            per_device[handle.device_id] += completed
        total_tried = sum(per_device.values())
        if total_tried == 0 and winner is not None:
            per_device[winner.device_id] = max(0, int(winner.nonces_tried))
            total_tried = per_device[winner.device_id]

        wall_ns = max(1, time.monotonic_ns() - t0)
        layer_samples: List[LayerSample] = []
        for device_id, scheduler in device_by_id.items():
            cap = scheduler.capability()
            raw_class = str(cap.device_class).lower()
            if "asic" in raw_class:
                layer = "asic"
            elif "remote" in raw_class:
                layer = "remote"
            elif "integrated" in raw_class or "igpu" in raw_class or "chronus" in raw_class:
                layer = "chronus"
            elif "gpu" in raw_class:
                layer = "gpu"
            else:
                layer = "cpu"
            layer_samples.append(
                LayerSample(
                    layer=layer,
                    device_id=device_id,
                    elapsed_ns=wall_ns,
                    protocol_hashes=per_device.get(device_id, 0),
                    accepted_shares=int(winner is not None and winner.device_id == device_id),
                )
            )

        return JobResult(
            mode=self.mode,
            share=winner,
            certificate=cert,
            handles=handle_records,
            attestations=self._registry.snapshot(),
            wall_ns=wall_ns,
            total_nonces_tried=int(total_tried),
            winner_probe_index=winner_probe_index,
            tensor_advice=tensor_advice,
            layer_samples=tuple(layer_samples),
        )


def promote_execution_hasher(hasher: Any) -> Any:
    """Promote a bound composite hasher to H4/600 without fabricating a fleet.

    Only the real ``super_asic`` joined-substrate hasher has the scheduler set
    required for 600-way fleet dispatch. Other hashers are returned unchanged;
    their lack of 600-way physical fan-out remains visible in evidence.
    """
    backend = str(getattr(hasher, "backend", "") or "")
    coordinator = getattr(hasher, "_coord", None)
    if backend.startswith("super_asic:") and isinstance(coordinator, HybridCoordinator):
        hasher._coord = H4600HybridCoordinator.promote(coordinator)
        hasher.topology_id = H4600HybridCoordinator.topology_id
        hasher.logical_vertices = H4600HybridCoordinator.logical_vertices
    return hasher


__all__ = ["H4600HybridCoordinator", "promote_execution_hasher"]
