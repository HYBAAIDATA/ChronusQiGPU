"""Threshold verification. Closes F4.

k-of-n independent devices re-run the kernel. Independence prefers
different device_id, then vendor, then host. A dissenting device is
quarantined and its attestation is retained for audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from igpu.seam import store
from igpu.seam.attest_compose import CompositeAttestation, attest_compose
from igpu.seam.kernel import dispatch, poll
from igpu.seam.probe import Capability
from igpu.seam.types import (
    Err,
    KernelName,
    Ok,
    Result,
    SeamError,
    ThresholdPolicy,
    digest_of,
)


@dataclass
class VerificationRequest:
    kernel: KernelName
    inputs: List[str]
    outputs: List[str]
    candidates: List[str]
    policy: ThresholdPolicy
    k: Optional[int] = None


def host_of(cap: Capability) -> str:
    return str(cap.vendor_extensions.get("host_id") or cap.vendor or cap.device_id)


def select_independent(candidates: Sequence[str], fleet: Sequence[Capability], k: Optional[int]) -> List[str]:
    by_id = {c.device_id: c for c in fleet}
    live = [by_id[cid] for cid in candidates if cid in by_id and not store.is_quarantined(cid)]
    selected: List[Capability] = []
    seen_vendor = set()
    seen_host = set()

    for cap in live:
        if cap.vendor not in seen_vendor:
            selected.append(cap)
            seen_vendor.add(cap.vendor)
            seen_host.add(host_of(cap))
        if k is not None and len(selected) >= k:
            return [c.device_id for c in selected]

    for cap in live:
        if cap in selected:
            continue
        if host_of(cap) not in seen_host:
            selected.append(cap)
            seen_host.add(host_of(cap))
        if k is not None and len(selected) >= k:
            return [c.device_id for c in selected]

    for cap in live:
        if cap not in selected:
            selected.append(cap)
        if k is not None and len(selected) >= k:
            break
    return [c.device_id for c in selected]


def min_required(policy: ThresholdPolicy, k: Optional[int], n: int) -> int:
    if policy is ThresholdPolicy.unanimous:
        return max(n, 1)
    if policy is ThresholdPolicy.at_least_k:
        return max(int(k or 1), 1)
    if k is not None:
        return max(k, 1)
    return max((n // 2) + 1, 1)


def verify_threshold(req: VerificationRequest, fleet: Sequence[Capability]) -> Result[CompositeAttestation]:
    k = req.k
    need = min_required(req.policy, k, len(req.candidates))
    verifiers = select_independent(req.candidates, fleet, k or need)
    if len(verifiers) < need:
        return Err(SeamError.verification_failed, f"independent verifiers {len(verifiers)} < {need}")

    links = []
    expected = list(req.outputs)
    idem = digest_of("|".join([req.kernel.value] + list(req.inputs)).encode("utf-8"))
    for device_id in verifiers:
        dispatched = dispatch("threshold", device_id, req.kernel, {"inputs": req.inputs}, f"tv:{idem}:{device_id}")
        if isinstance(dispatched, Err):
            store.audit("threshold_dispatch_fail", device_id=device_id, detail=dispatched.detail)
            continue
        polled = poll("threshold", dispatched.value)
        if isinstance(polled, Err) or polled.value is None:
            store.quarantine(device_id, "threshold_poll")
            store.audit("threshold_dissent", device_id=device_id, reason="poll")
            continue
        result = polled.value
        got = list(result.handle.outputs) if result.handle.outputs else [digest_of(o) for o in result.outputs]
        if expected and got != expected:
            store.quarantine(device_id, "threshold_mismatch")
            store.audit("threshold_dissent", device_id=device_id, reason="output_mismatch")
            continue
        links.append(result.attestation)

    if len(links) < need:
        return Err(SeamError.verification_failed, f"agreeing links {len(links)} < {need}")
    return attest_compose(links, req.policy, k)
