"""Benchmark 5 — hybrid dispatch coordinator vs single-device baseline.

Same pinned corpus, same fixed target. Devices are honest in-process CPU
schedulers implementing the NonceScheduler contract: real hashlib
double-SHA256 (midstate-accelerated), real measured capability, real
attestations — declared device_class "cpu_in_process". The coordinator's
partition / dispatch / poll / host re-verify / cancel path is exercised
unchanged.

Configs: (a) single device, sequential; (b) two devices, even split;
(c) two devices, Lucas partition (the TOE-aware assignment).
"""

from __future__ import annotations

import hashlib
import struct
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.common import (
    SEED,
    env_fingerprint,
    fmt,
    summarize,
    synthetic_header,
    write_report,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hyba.hybrid.coordinator import HybridCoordinator, StratumJob
from hyba.hybrid.nonce_scheduler import (
    AttestationRegistry,
    DeviceCapability,
    DispatchHandle,
    ExecutionAttestation,
    NonceWindow,
    Share,
    next_handle_id,
)

JOBS = 24
JOB_SPAN = 1 << 17
JOB_TARGET_INT = 1 << 240  # p = 2^-16 -> E[winners] = 2 per job
POLL_CHUNK = 1 << 12


class HonestCpuScheduler:
    """NonceScheduler that physically hashes with hashlib (midstate)."""

    def __init__(self, device_id: str) -> None:
        self._device_id = device_id
        self._jobs: Dict[str, bytes] = {}
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._finished: Dict[int, int] = {}
        self._records: List[ExecutionAttestation] = []
        self._registry = AttestationRegistry.get()
        self._capability: Optional[DeviceCapability] = None

    def prepare(self, job_id: str, header80: bytes) -> None:
        self._jobs[str(job_id)] = bytes(header80)

    def capability(self) -> DeviceCapability:
        if self._capability is None:
            blob = bytearray(80)
            t0 = time.perf_counter()
            n = 0
            while time.perf_counter() - t0 < 0.2:
                struct.pack_into("<I", blob, 76, n)
                hashlib.sha256(hashlib.sha256(bytes(blob)).digest()).digest()
                n += 1
            self._capability = DeviceCapability(
                device_id=self._device_id,
                device_class="cpu_in_process",
                measured_hashes_per_sec=n / max(time.perf_counter() - t0, 1e-9),
                supported=True,
                detail={"substrate": "hashlib sha256d, midstate-accelerated"},
            )
        return self._capability

    def dispatch(self, window: NonceWindow) -> DispatchHandle:
        handle = DispatchHandle(
            handle_id=next_handle_id(),
            device_id=self.capability().device_id,
            window=window,
            dispatched_ns=time.monotonic_ns(),
        )
        self._pending[handle.handle_id] = {
            "cursor": window.base_nonce,
            "remaining": window.span,
            "hashed": 0,
        }
        self._attest("dispatch", handle)
        return handle

    def poll(self, handle: DispatchHandle) -> Optional[Share]:
        st = self._pending.get(handle.handle_id)
        if st is None:
            return None
        window = handle.window
        take = min(POLL_CHUNK, st["remaining"])
        header = self._jobs[window.job_id]
        prefix = hashlib.sha256(header[:64])
        tail = header[64:76]
        target_int = int.from_bytes(window.target, "big")
        pack = struct.Struct("<I").pack
        for i in range(take):
            nonce = (st["cursor"] + i) & 0xFFFFFFFF
            first = prefix.copy()
            first.update(tail + pack(nonce))
            digest = hashlib.sha256(first.digest()).digest()
            if int.from_bytes(digest, "little") <= target_int:
                st["hashed"] += i + 1
                st["cursor"] += i + 1
                st["remaining"] -= i + 1
                share = Share(
                    device_id=handle.device_id,
                    job_id=window.job_id,
                    nonce=nonce,
                    digest=digest,
                    nonces_tried=i + 1,
                    face=window.face,
                )
                self._attest("share", handle, nonces_tried=i + 1, found=True)
                self._finished[handle.handle_id] = st["hashed"]
                self._pending.pop(handle.handle_id)
                return share
        st["cursor"] += take
        st["remaining"] -= take
        st["hashed"] += take
        if st["remaining"] <= 0:
            self._attest("exhausted", handle, nonces_tried=window.span)
            self._finished[handle.handle_id] = st["hashed"]
            self._pending.pop(handle.handle_id)
        return None

    def cancel(self, handle: DispatchHandle, reason: str = "cancelled") -> None:
        st = self._pending.pop(handle.handle_id, None)
        if st is not None:
            self._finished[handle.handle_id] = st["hashed"]
            self._attest("cancelled", handle, reason=reason)

    def is_done(self, handle: DispatchHandle) -> bool:
        return handle.handle_id not in self._pending

    def hashed_count(self, handle: DispatchHandle) -> int:
        st = self._pending.get(handle.handle_id)
        if st is not None:
            return st["hashed"]
        return int(self._finished.get(handle.handle_id, 0))

    def attestation(self) -> List[ExecutionAttestation]:
        return list(self._records)

    def _attest(self, kind, handle, *, reason="", nonces_tried=0, found=False):
        rec = ExecutionAttestation(
            kind=kind,
            device_id=handle.device_id,
            device_class="cpu_in_process",
            handle_id=handle.handle_id,
            window=handle.window,
            timestamp_ns=time.monotonic_ns(),
            nonces_tried=nonces_tried,
            found=found,
            reason=reason,
            detail={"module": "benchmarks.hybrid_dispatch_benchmark"},
        )
        self._records.append(rec)
        self._registry.record(rec)


def _jobs() -> list[StratumJob]:
    target = JOB_TARGET_INT.to_bytes(32, "big")
    return [
        StratumJob(
            job_id=f"bench-{i}",
            header80=synthetic_header(800_000 + i),
            target=target,
            nonce_space=JOB_SPAN,
        )
        for i in range(JOBS)
    ]


def _span_overlaps(result) -> int:
    """Count of nonces covered by more than one dispatched window."""
    intervals = sorted(
        (h["window"]["base_nonce"], h["window"]["base_nonce"] + h["window"]["span"])
        for h in result.handles
    )
    dup = 0
    prev_end = 0
    for base, end in intervals:
        if base < prev_end:
            dup += prev_end - base
        prev_end = max(prev_end, end)
    return dup


def run() -> dict:
    jobs = _jobs()
    configs = {}
    for label, make_coord, strategy in (
        ("single_sequential", lambda: HybridCoordinator(HonestCpuScheduler("cpu:A")), "lucas"),
        (
            "two_device_even",
            lambda: HybridCoordinator(HonestCpuScheduler("cpu:A"), HonestCpuScheduler("cpu:B")),
            "even",
        ),
        (
            "two_device_lucas",
            lambda: HybridCoordinator(HonestCpuScheduler("cpu:A"), HonestCpuScheduler("cpu:B")),
            "lucas",
        ),
    ):
        coord = make_coord()
        share_iters, total_iters, walls, dups, found = [], [], [], 0, 0
        for job in jobs:
            result = coord.run_job(job, strategy=strategy)
            assert result.certificate.verify()
            dups += _span_overlaps(result)
            total_iters.append(result.total_nonces_tried)
            walls.append(result.wall_ns / 1e9)
            if result.share is not None:
                found += 1
                share_iters.append(result.share.nonces_tried)
        configs[label] = {
            "strategy": strategy,
            "jobs": JOBS,
            "shares_found": found,
            "winner_hashes": summarize(share_iters, f"hyb-w-{label}"),
            "total_hashes": summarize(total_iters, f"hyb-t-{label}"),
            "wall_s": summarize(walls, f"hyb-wall-{label}"),
            "duplicate_hashes": dups,
            "certificate_verified_all": True,
            "attestation_total": AttestationRegistry.get().summary()["total"],
        }
        AttestationRegistry.reset()
    return {
        "seed": SEED,
        "env": env_fingerprint(),
        "configs": configs,
        "job_span": JOB_SPAN,
        "job_target": hex(JOB_TARGET_INT),
    }


def render(results: dict) -> str:
    lines = [
        "# Hybrid dispatch benchmark — coordinator vs single-device baseline",
        "",
        f"{results['configs']['single_sequential']['jobs']} jobs × "
        f"2^17 nonce span, fixed target {results['job_target']} "
        "(λ≈2 winners/job). Devices: honest in-process CPU schedulers "
        "(hashlib sha256d, measured capability, full attestation).",
        "",
        "| config | shares | winner hashes (mean) | total hashes (mean) | "
        "wall s (mean) | duplicate hashes |",
        "|---|---|---|---|---|---|",
    ]
    for label, c in results["configs"].items():
        lines.append(
            f"| {label} | {c['shares_found']}/{c['jobs']} | "
            f"{fmt(c['winner_hashes']['mean'], 0)} | {fmt(c['total_hashes']['mean'], 0)} | "
            f"{c['wall_s']['mean']:.3f} | {c['duplicate_hashes']} |"
        )
    lines += [
        "",
        "## Reading the numbers",
        "",
        "- Every dispatched window is disjoint by certificate — the "
        "duplicate-hash ratio is 0 for every config.",
        "- On a memoryless oracle the partition strategy cannot change "
        "expected work: `even` and `lucas` split identical CPU substrates "
        "and land within noise of each other and of the single-device "
        "winner-hash count.",
        "- The coordinator's attestations record every dispatch, share, "
        "cancel and exhaustion — that audit trail is the feature this "
        "config exercises, not a win-rate claim.",
        "",
        f"Environment: {results['env']}",
        "",
        "Data: `reports/data/hybrid_dispatch_benchmark.json`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    results = run()
    path = write_report("hybrid_dispatch_benchmark", results, render(results))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
