"""Layer 5 — market-based routing with honest degradation.

Wraps hyba.hybrid.coordinator when a live job is supplied; otherwise
routes kernels by capability bids without leaking silicon identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from igpu.seam import store
from igpu.seam.hybrid import Window, fallback_candidates, partition, supports_class
from igpu.seam.kernel import KernelResult, dispatch, poll
from igpu.seam.probe import Capability
from igpu.seam.types import (
    AttestationLink,
    Distribution,
    Err,
    KernelName,
    Ok,
    PhysicalMeasurement,
    Result,
    SeamError,
    attest,
    canonical_json,
)


@dataclass
class Bid:
    device_id: str
    kernel: KernelName
    cost: Distribution
    confidence: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "kernel": self.kernel.value,
            "cost": self.cost.as_dict(),
            "confidence": self.confidence,
        }


@dataclass
class DeviceAssignment:
    device_id: str
    kernel: KernelName
    window: Window
    priority: int
    deadline: Optional[str]
    cost_estimate: Distribution
    fallback: bool
    job_id: str = ""
    idempotency_key: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "kernel": self.kernel.value,
            "window": self.window.as_dict(),
            "priority": self.priority,
            "deadline": self.deadline,
            "cost_estimate": self.cost_estimate.as_dict(),
            "fallback": self.fallback,
            "job_id": self.job_id,
        }


@dataclass
class JobResult:
    job_id: str
    assignments: List[DeviceAssignment]
    results: List[KernelResult]
    dispatch_tree: str
    attestation: AttestationLink
    measurement: PhysicalMeasurement
    degraded: bool
    gap: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "assignments": [a.as_dict() for a in self.assignments],
            "results": [r.as_dict() for r in self.results],
            "dispatch_tree": self.dispatch_tree,
            "attestation": self.attestation.as_dict(),
            "measurement": self.measurement.as_dict(),
            "degraded": self.degraded,
            "gap": self.gap,
        }


def bid(device: Capability, kernel: KernelName) -> Result[Bid]:
    if kernel not in device.supported_kernels:
        return Err(SeamError.kernel_unavailable, kernel.value)
    cost = device.kernel_costs.get(kernel.value, Distribution(1.0, 0.0, 1))
    hps = max(device.measured_hps.mean, 1.0)
    confidence = min(1.0, device.measured_hps.samples / 8.0)
    return Ok(Bid(device.device_id, kernel, Distribution(cost.mean / hps, cost.stddev, cost.samples), confidence))


def _select_bid(bids: List[Bid]) -> Optional[Bid]:
    if not bids:
        return None
    return sorted(bids, key=lambda b: (b.cost.mean, -b.confidence))[0]


def route(job: Dict[str, Any], fleet: Sequence[Capability]) -> Result[List[DeviceAssignment]]:
    kernels = [KernelName(k) if not isinstance(k, KernelName) else k for k in job.get("kernels", [])]
    if not kernels:
        return Err(SeamError.unknown, "job has no kernels")
    span = int(job.get("span", 1 << 20))
    parts = partition(kernels, span)
    assignments: List[DeviceAssignment] = []
    gap: Optional[str] = None
    degraded = False
    for klass, windows in parts.items():
        candidates = [d for d in fleet if supports_class(d, klass) and d.state.value == "present"]
        used_fallback = False
        if not candidates:
            candidates = fallback_candidates(fleet, klass)
            used_fallback = bool(candidates)
            if not candidates:
                gap = f"no capable device for {klass.value}"
                store.audit("route_gap", klass=klass.value)
                continue
        for window in windows:
            kernel = window.kernel
            collected: List[Bid] = []
            for dev in candidates:
                result = bid(dev, kernel)
                if isinstance(result, Ok):
                    collected.append(result.value)
            winner = _select_bid(collected)
            if winner is None:
                gap = f"no bid for {kernel.value}"
                continue
            assignments.append(
                DeviceAssignment(
                    device_id=winner.device_id,
                    kernel=kernel,
                    window=window,
                    priority=int(job.get("priority", 0)),
                    deadline=job.get("deadline"),
                    cost_estimate=winner.cost,
                    fallback=used_fallback,
                    job_id=str(job.get("job_id", "")),
                    idempotency_key=f"{job.get('job_id', '')}:{kernel.value}:{window.start}",
                )
            )
            if used_fallback:
                degraded = True
    store.audit("route", assignments=len(assignments), degraded=degraded, gap=gap)
    if not assignments:
        return Err(SeamError.kernel_unavailable, gap or "no assignments")
    return Ok(assignments)


def execute(caller: str, assignments: Sequence[DeviceAssignment], fleet: Sequence[Capability]) -> Result[JobResult]:
    results: List[KernelResult] = []
    for a in assignments:
        dispatched = dispatch(caller, a.device_id, a.kernel, {"window": a.window.as_dict()}, a.idempotency_key)
        if isinstance(dispatched, Err):
            if dispatched.error is SeamError.device_quarantined:
                store.audit("reroute_needed", device_id=a.device_id)
            continue
        polled = poll(caller, dispatched.value)
        if isinstance(polled, Ok) and polled.value is not None:
            if not polled.value.host_verified:
                store.quarantine(a.device_id, "host_verify")
                continue
            results.append(polled.value)
    degraded = any(a.fallback for a in assignments)
    failed = len(assignments) - len(results)
    if failed == len(assignments):
        gap = "all assignments failed" if assignments else None
    elif failed:
        gap = f"{failed} of {len(assignments)} assignments failed or were skipped"
    else:
        gap = None
    tree = canonical_json([a.as_dict() for a in assignments])
    att = attest(tree, issuer="fleet")
    wall = sum(r.measurement.time_ns for r in results)
    job_id = assignments[0].job_id if assignments else ""
    return Ok(
        JobResult(
            job_id=job_id,
            assignments=list(assignments),
            results=results,
            dispatch_tree=tree,
            attestation=att,
            measurement=PhysicalMeasurement(time_ns=wall),
            degraded=degraded,
            gap=gap,
        )
    )


def coordinate(caller: str, job: Dict[str, Any], fleet: Sequence[Capability]) -> Result[JobResult]:
    routed = route(job, fleet)
    if isinstance(routed, Err):
        return routed
    return execute(caller, routed.value, fleet)


def run_hybrid_stratum(job: Any, gpu: Any, asic: Any = None) -> Result[Dict[str, Any]]:
    """Delegate a live Stratum job to hyba.hybrid.HybridCoordinator."""
    try:
        from hyba.hybrid.coordinator import HybridCoordinator
    except Exception as exc:
        return Err(SeamError.kernel_unavailable, f"hybrid coordinator missing: {exc}")
    try:
        coordinator = HybridCoordinator(gpu, asic)
        result = coordinator.run_job(job)
    except Exception as exc:
        return Err(SeamError.verification_failed, f"{type(exc).__name__}: {exc}")
    payload = result.as_dict() if hasattr(result, "as_dict") else {"result": str(result)}
    store.audit("hybrid_stratum", mode=payload.get("mode"), degraded=asic is None)
    return Ok(payload)
