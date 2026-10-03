"""HybridCoordinator — one job, two substrates, a deterministic partition.

The coordinator is the only place GPU and ASIC work meet. For each job it
partitions the nonce span (Lucas-weighted or even), dispatches every
window, polls all devices at chunk granularity, takes the first
consensus-valid share, and cancels the losers with an attested
``peer_won`` reason. The host re-verifies every returned share against
double-SHA256 and the job target — a device cannot win by lying.

Hard rules enforced here:

- never dispatch to an unsupported device,
- never fall back to CPU hashing silently (the GPU solver's own backend
  provenance rides in every attestation),
- never mutate nonces or targets after dispatch,
- never accept a share the host cannot re-verify,
- every dispatched window appears in the attestation record, including
  cancelled and exhausted ones.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from hyba.hybrid.lucas_partition import (
    CoverageCertificate,
    TraversalHistory,
    partition,
)
from hyba.hybrid.performance import LayerSample, job_performance_report
from hyba.hybrid.nonce_scheduler import (
    ASICNotPresent,
    AttestationRegistry,
    AttestationViolation,
    DispatchHandle,
    NONCE_SPACE,
    NonceScheduler,
    NonceWindow,
    Share,
    verify_share,
)
from hyba.hybrid.tensor_advisor import WindowRanker, apply_tensor_advice


@dataclass(frozen=True)
class StratumJob:
    """The minimal job contract the coordinator needs.

    ``nonce_space`` is partitioned as relative offsets ``[0, nonce_space)``;
    ``base_nonce`` shifts the whole job into the uint32 field so callers can
    run the partition over an arbitrary window.
    """

    job_id: str
    header80: bytes  # full 80-byte block header (nonce bytes ignored; solver patches)
    target: bytes  # 32-byte big-endian consensus target
    session_epoch: int = 0
    job_epoch: int = 0
    nonce_space: int = NONCE_SPACE
    base_nonce: int = 0

    def __post_init__(self) -> None:
        if len(self.header80) != 80:
            raise ValueError("header80 must be exactly 80 bytes")
        if len(self.target) != 32:
            raise ValueError("target must be exactly 32 bytes")
        if not (0 < self.nonce_space <= NONCE_SPACE):
            raise ValueError(f"nonce_space out of range: {self.nonce_space}")
        if not (0 <= self.base_nonce < NONCE_SPACE):
            raise ValueError(f"base_nonce out of uint32 range: {self.base_nonce}")
        if self.base_nonce + self.nonce_space > NONCE_SPACE:
            raise ValueError(
                "job wraps the uint32 nonce field: "
                f"base_nonce={self.base_nonce} + nonce_space={self.nonce_space} > 2^32"
            )


@dataclass(frozen=True)
class JobResult:
    """Everything an auditor needs to replay one job.

    ``hashes_executed`` is total physical device work; ``winner_probe_index``
    is the winner's depth in the winning device's traversal order — the
    ordering metric the benchmark compares, independent of launch granularity.
    """

    mode: str
    share: Optional[Share]
    certificate: CoverageCertificate
    handles: List[Dict[str, Any]]
    attestations: List[Dict[str, Any]]
    wall_ns: int
    total_nonces_tried: int
    winner_probe_index: Optional[int] = None
    tensor_advice: Optional[Dict[str, Any]] = None
    layer_samples: tuple[LayerSample, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        performance = job_performance_report(
            wall_ns=max(1, self.wall_ns),
            protocol_hashes=max(0, self.total_nonces_tried),
            accepted_shares=1 if self.share is not None else 0,
            samples=self.layer_samples or None,
        )
        return {
            "mode": self.mode,
            "share": (
                {
                    "device_id": self.share.device_id,
                    "job_id": self.share.job_id,
                    "nonce": self.share.nonce,
                    "digest": self.share.digest.hex(),
                    "nonces_tried": self.share.nonces_tried,
                    "probe_index": self.share.probe_index,
                    "face": self.share.face,
                }
                if self.share is not None
                else None
            ),
            "winner_probe_index": self.winner_probe_index,
            "certificate": self.certificate.as_dict(),
            "handles": list(self.handles),
            "attestations": list(self.attestations),
            "wall_ns": self.wall_ns,
            "total_nonces_tried": self.total_nonces_tried,
            "performance": performance.as_dict(),
            "tensor_advice": dict(self.tensor_advice) if self.tensor_advice else None,
        }


class HybridCoordinator:
    """Dispatch partitioned windows to GPU and (when present) ASIC."""

    def __init__(
        self,
        gpu: NonceScheduler,
        asic: Optional[NonceScheduler] = None,
        tensor_ranker: Optional[WindowRanker] = None,
        require_asic: bool = False,
        extra_devices: Sequence[NonceScheduler] = (),
    ) -> None:
        self.gpu = gpu
        self.asic = asic
        self.extra_devices = list(extra_devices)
        self.tensor_ranker = tensor_ranker
        self.require_asic = bool(require_asic)
        self.history = TraversalHistory()
        self._registry = AttestationRegistry.get()
        if asic is None:
            if self.require_asic:
                raise ASICNotPresent(
                    "ASIC-required policy is active but no ASIC solver was provided"
                )
            self._registry.record_gap("asic_absent", detail_note="no ASIC solver was provided")
        else:
            cap = asic.capability()
            if not cap.supported:
                if self.require_asic:
                    raise ASICNotPresent(
                        cap.reason_if_unsupported or "ASIC-required policy probe failed"
                    )
                self._registry.record_gap(
                    "asic_present_but_unsupported",
                    device_id=cap.device_id,
                    unsupported_reason=cap.reason_if_unsupported,
                )
        # hybrid means more than one supported substrate is actually joined.
        self.mode = "hybrid" if len(self._devices()) > 1 else "gpu_only"

    def _devices(self) -> List[NonceScheduler]:
        devices = [self.gpu]
        if self.asic is not None and self.asic.capability().supported:
            devices.append(self.asic)
        seen = {d.capability().device_id for d in devices}
        for scheduler in self.extra_devices:
            cap = scheduler.capability()
            # A member whose identity duplicates one already joined would
            # collapse under device_by_id — same substrate twice is no extra
            # hashrate, so it does not join.
            if cap.supported and cap.device_id not in seen:
                devices.append(scheduler)
                seen.add(cap.device_id)
        return devices

    def run_job(
        self,
        job: StratumJob,
        *,
        strategy: str = "lucas",
        history: Optional[TraversalHistory] = None,
    ) -> JobResult:
        """Partition, dispatch, poll, verify, cancel — the full auditable run."""
        t0 = time.monotonic_ns()
        history = history if history is not None else self.history
        devices = self._devices()

        for d in devices:
            prepare = getattr(d, "prepare", None)
            if callable(prepare):
                prepare(job.job_id, job.header80)

        spans, cert = partition(job.nonce_space, devices, history, strategy=strategy)
        tensor_advice: Optional[Dict[str, Any]] = None
        if self.tensor_ranker is not None:
            spans, evidence = apply_tensor_advice(self.tensor_ranker, job, spans)
            tensor_advice = evidence.as_dict()

        device_by_id: Dict[str, NonceScheduler] = {d.capability().device_id: d for d in devices}
        # Dispatch every window; per-device queues preserve emission order
        # so each device probes its assigned windows sequentially while
        # devices run concurrently.
        device_queues: Dict[str, List[tuple]] = {}
        all_handles: List[tuple] = []
        handle_records: List[Dict[str, Any]] = []
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
        device_cursor: Dict[str, int] = {d: 0 for d in device_queues}
        while winner is None:
            live = False
            for dev_id, queue in device_queues.items():
                idx = device_cursor[dev_id]
                while idx < len(queue) and _done(queue[idx][0], queue[idx][1]):
                    idx += 1
                device_cursor[dev_id] = idx
                if idx >= len(queue):
                    continue
                live = True
                scheduler, handle, window = queue[idx]
                share = scheduler.poll(handle)
                if share is None:
                    continue
                # Host consensus re-verification before accepting anything.
                if not verify_share(share, job.header80[:76], job.target):
                    raise AttestationViolation(
                        "device returned a share that fails host verification",
                    )
                winner = share
                winner_entry = (scheduler, handle, window)
                break
            if not live:
                break

        # Cancel everything still live; attest each with a reason.
        for dev_id, queue in device_queues.items():
            idx = device_cursor[dev_id]
            for scheduler, handle, window in queue[idx:]:
                if _done(scheduler, handle):
                    continue
                scheduler.cancel(handle, reason="peer_won" if winner else "job_aborted")
                self.history.append(window.face, handle.device_id, False, window.span)

        if winner is not None:
            self.history.append(winner.face, winner.device_id, True, winner.nonces_tried)

        # Serial-equivalent probe depth on the winning device: full spans of
        # that device's earlier windows + the winner's in-window position.
        winner_probe_index: Optional[int] = None
        if winner is not None and winner_entry is not None:
            _, winner_handle, _ = winner_entry
            queue = device_queues.get(winner.device_id, [])
            winner_pos = next(
                (i for i, (_, h, _) in enumerate(queue) if h.handle_id == winner_handle.handle_id),
                0,
            )
            prior = sum(w.span for _, _, w in queue[:winner_pos])
            winner_probe_index = prior + winner.probe_index

        # Total physical hashes remain attributed to the device that executed
        # them. All device samples share this job's concurrent wall window.
        per_device: Dict[str, int] = {device_id: 0 for device_id in device_by_id}
        for _, handle, _ in all_handles:
            scheduler = device_by_id.get(handle.device_id)
            counter = getattr(scheduler, "hashed_count", None) if scheduler else None
            if callable(counter):
                per_device[handle.device_id] += max(0, int(counter(handle)))
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

        attestations = self._registry.snapshot()
        return JobResult(
            mode=self.mode,
            share=winner,
            certificate=cert,
            handles=handle_records,
            attestations=attestations,
            wall_ns=wall_ns,
            total_nonces_tried=int(total_tried),
            winner_probe_index=winner_probe_index,
            tensor_advice=tensor_advice,
            layer_samples=tuple(layer_samples),
        )


__all__ = ["HybridCoordinator", "JobResult", "StratumJob"]
