"""SuperAsicHasher — the registry's ``super_asic`` lane.

One hasher over EVERY bound mining substrate: the local OpenCL/CPU solver,
any physically attached ASIC channel, and every configured remote GPU agent
(or fleet). The lucas partitioner divides each requested window across the
joined substrates by measured throughput, the coordinator dispatches them
concurrently, and every returned share is host re-verified — the composite
is strictly faster than its slowest member only when it actually is, and
the ``backend`` label always names the substrates that really joined.

This is the wiring for combining ASIC-class channels with the super-GPU
remote fleet over one window. Composition can increase aggregate throughput
when multiple real substrates actually join; any such increase is evidence only
after comparative measurement, never an assumption. A degenerate single-
substrate composition (``super_asic:cpu``) is a truthful orchestration lane,
not evidence that ASIC + super-GPU composition increased hashrate.

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
from hyba.hybrid.hybrid_asic_profile import DEFAULT_HYBRID_ASIC_PROFILE
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
        # The channel must hash THIS header — bind it before dispatch so
        # the wire payload carries the requested header prefix.
        self._solver.prepare(job_id, bytes(header80))
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
        # The window ended without a share. Only an explicit exhaustion
        # outcome means the span was ground; every other terminal state —
        # channel error, EOF, cancellation — is a device failure, not
        # coverage. Fabricating `count` here would claim unsearched nonces.
        outcome = self._solver.outcome(handle)
        if outcome in ("exhausted", "exhausted_partial"):
            # Report the channel's TRUE executed count, never the assigned
            # count. `exhausted_partial` means the channel declared exhaustion
            # having covered less than the span, so this surfaces its real
            # coverage instead of promoting it to the full window.
            self.launches += 1
            return None, None, self._solver.hashed_count(handle)
        raise RuntimeError(
            f"ASIC channel ended the window without exhaustion "
            f"(outcome={outcome!r}) — refusing to report uncovered "
            "nonces as hashed"
        )

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
    """Decompose an explicit nonce sequence into (base, span) contiguous runs,
    preserving the caller's traversal order — a ranked or topological nonce
    list is searched in the order supplied, so the first winner and the probe
    count correspond to that order, not a sorted one."""
    seq = [int(n) & 0xFFFFFFFF for n in nonces]
    if not seq:
        return []
    runs: List[tuple[int, int]] = []
    start = prev = seq[0]
    for n in seq[1:]:
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

    def __init__(
        self,
        coordinator: HybridCoordinator,
        members: List[NonceScheduler],
        bind_report: Optional[List[Dict[str, object]]] = None,
    ) -> None:
        if not members:
            raise DeviceUnsupportedError("super_asic lane bound zero substrates")
        self._coord = coordinator
        self.design_profile = DEFAULT_HYBRID_ASIC_PROFILE
        self._members = list(members)
        # Per-substrate join evidence: which classes were probed, which
        # joined, and the measured reason for every exclusion — a
        # configured-but-broken member is visible here, never dropped
        # silently.
        self.bind_report: List[Dict[str, object]] = list(bind_report or [])
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
        self.last_batch_evidence: Optional[Dict[str, object]] = None
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
        bind_report: List[Dict[str, object]] = []
        registry = AttestationRegistry.get()
        asic = ASICSolver()
        asic_cap = asic.capability()
        bind_report.append(
            {
                "substrate": "asic",
                "joined": bool(asic_cap.supported),
                "device_id": asic_cap.device_id,
                "reason": asic_cap.reason_if_unsupported,
            }
        )
        gpu = GPUSolver(backend="auto", allow_cpu=allow_cpu)
        gpu_cap = gpu.capability()
        bind_report.append(
            {
                "substrate": "local",
                "joined": bool(gpu_cap.supported),
                "device_id": gpu_cap.device_id,
                "reason": gpu_cap.reason_if_unsupported,
            }
        )
        # Remote fleet (the super-GPU surface). A configured-but-broken
        # remote is a visible exclusion — it lands in bind_report AND in
        # the attestation registry, so composite evidence carries the
        # reason instead of silently degrading to fewer substrates.
        remote_endpoints = cls._remote_endpoints()
        if remote_endpoints:
            try:
                from hyba.hybrid.remote_solver import RemoteScheduler

                remote = RemoteScheduler.from_env(timeout=remote_timeout)
                rcap = remote.capability()
                bind_report.append(
                    {
                        "substrate": "remote",
                        "joined": bool(rcap.supported),
                        "device_id": rcap.device_id,
                        "reason": rcap.reason_if_unsupported,
                    }
                )
                if rcap.supported:
                    members.append(remote)
                else:
                    registry.record_gap(
                        "super_asic_remote_excluded: "
                        + (rcap.reason_if_unsupported or "unsupported"),
                        device_id=rcap.device_id,
                        endpoints=list(remote_endpoints),
                    )
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}"
                bind_report.append(
                    {
                        "substrate": "remote",
                        "joined": False,
                        "device_id": "remote:unbound",
                        "reason": reason,
                    }
                )
                registry.record_gap(
                    f"super_asic_remote_excluded: {reason}",
                    endpoints=list(remote_endpoints),
                )
        else:
            bind_report.append(
                {
                    "substrate": "remote",
                    "joined": False,
                    "device_id": "remote:none",
                    "reason": "no remote endpoints configured",
                }
            )
        unified_enabled = os.environ.get(
            "PYTHIA_UNIFIED_THEORY_HYBRID", "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        if unified_enabled:
            from hyba.hybrid.unified_theory_ranker import GoldenUnifiedWindowRanker

            ranker = GoldenUnifiedWindowRanker()
        else:
            ranker = None
        bind_report.append(
            {
                "substrate": "unified_theory_ranker",
                "joined": bool(ranker),
                "device_id": ranker.model_id if ranker else "ranker:disabled",
                "reason": None if ranker else "PYTHIA_UNIFIED_THEORY_HYBRID is disabled",
                "effect": "dispatch_order_only",
            }
        )
        coord = HybridCoordinator(
            gpu,
            asic,
            tensor_ranker=ranker,
            extra_devices=members,
        )
        joined = coord._devices()
        return cls(coord, joined, bind_report=bind_report)

    def design_report(self) -> Dict[str, object]:
        """Return evidence-scoped design metadata, not fabricated silicon data."""
        return {
            "profile": self.design_profile.report(),
            "backend": self.backend,
            "members": [cap.as_dict() for cap in self._caps.values()],
            "bind_report": list(self.bind_report),
            "tensor_ranker": (
                self._coord.tensor_ranker.model_id
                if self._coord.tensor_ranker is not None
                else None
            ),
        }

    @staticmethod
    def _remote_endpoints() -> List[str]:
        """The fleet's configured endpoints — empty when none are set."""
        try:
            import sys
            from pathlib import Path

            repo_root = str(Path(__file__).resolve().parents[2])
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            from chronus.mla1517.remote_gpu import remote_endpoints

            return [str(e) for e in remote_endpoints()]
        except Exception:
            return []

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
        # ``weighted`` apportions the span across every joined substrate in
        # proportion to measured hps — the composite only combines hashrate
        # when each member actually receives work (lucas argmax would award
        # every face to the single fastest device).
        result = self._coord.run_job(job, strategy="weighted")
        self.last_result = result
        device_ns = 0
        device_windows = 0
        failed: List[str] = []
        for rec in self._registry.snapshot()[before:]:
            if rec.get("kind") == "failed" and (rec.get("window") or {}).get("job_id") == job_id:
                failed.append(f"{rec.get('device_id')}: {rec.get('reason')}")
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
        if failed:
            # A member died mid-job: its assigned spans were not covered.
            # Fail-closed — never return a result that skipped nonces.
            raise RuntimeError("super_asic substrate failed during the job: " + "; ".join(failed))
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
        requested = [int(nonce) & 0xFFFFFFFF for nonce in nonces]
        runs = _contiguous_runs(requested)
        evidence: Dict[str, object] = {
            "schema": "chronus.h4_600_ordered_batch/1",
            "topology": getattr(self, "topology_id", None) or "Unavailable",
            "ordered_nonce_count": len(requested),
            "contiguous_run_count": len(runs),
            "h4_job_count": 0,
            "h4_active_shards": 0,
            "h4_full_600_shard_jobs": 0,
            "h4_completed_600_shard_jobs": 0,
            "h4_topology_observed": False,
            "full_600_shard_dispatch_observed": False,
            "physical_fanout_observed": False,
            "completed_work_items": 0,
            "candidate_found": False,
            "completion_state": "NOT_RUN" if not requested else "RUNNING",
            "claim_boundary": (
                "H4/600 capability is distinct from observed 600-shard fan-out; "
                "only completed scheduler handles count as physical execution evidence"
            ),
        }
        self.last_batch_evidence = evidence
        if not requested:
            evidence["completion_state"] = "COMPLETE"
            return None, None, 0

        total = 0
        for run_base, run_len in runs:
            try:
                nonce, digest, done = self._run(header80, target_be, run_base, run_len)
            except Exception as exc:
                evidence["completion_state"] = "DEVICE_ERROR"
                evidence["error"] = f"{type(exc).__name__}: {exc}"
                evidence["completed_work_items"] = total
                evidence["physical_fanout_observed"] = False
                self.last_batch_evidence = dict(evidence)
                raise
            total += int(done)
            result = self.last_result
            certificate = getattr(result, "certificate", None)
            topology = getattr(certificate, "topology", None)
            handles = list(getattr(result, "handles", ()) or ())
            if topology == "chronus_h4_600_11d":
                evidence["h4_topology_observed"] = True
                evidence["h4_job_count"] = int(evidence["h4_job_count"]) + 1
                evidence["h4_active_shards"] = int(evidence["h4_active_shards"]) + len(handles)
                if len(handles) == 600:
                    evidence["h4_full_600_shard_jobs"] = (
                        int(evidence["h4_full_600_shard_jobs"]) + 1
                    )
                    evidence["full_600_shard_dispatch_observed"] = True
                    fully_completed = all(
                        bool(handle.get("terminal_observed"))
                        and bool(handle.get("fully_completed"))
                        and int(handle.get("completed_nonces", -1))
                        == int((handle.get("window") or {}).get("span", -2))
                        for handle in handles
                    )
                    if fully_completed:
                        evidence["h4_completed_600_shard_jobs"] = (
                            int(evidence["h4_completed_600_shard_jobs"]) + 1
                        )
                        evidence["physical_fanout_observed"] = True
            evidence["completed_work_items"] = total
            if nonce is not None:
                evidence["candidate_found"] = True
                evidence["completion_state"] = "CANDIDATE_FOUND"
                self.last_batch_evidence = dict(evidence)
                return nonce, digest, total

        evidence["completion_state"] = (
            "COMPLETE" if total == len(requested) else "PARTIAL"
        )
        self.last_batch_evidence = dict(evidence)
        return None, None, total


__all__ = ["AsicHasherAdapter", "SuperAsicHasher"]
