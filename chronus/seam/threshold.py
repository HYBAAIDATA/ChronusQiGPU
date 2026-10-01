"""Threshold verification. Closes F4.

k-of-n independent devices re-run the kernel. Independence prefers
different device_id, then vendor, then host. A dissenting device is
quarantined and its attestation is retained for audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from . import store
from .attest_compose import CompositeAttestation, attest_compose
from .kernel import dispatch, poll
from .probe import Capability
from .types import (
    Err,
    KernelName,
    Ok,
    PrivacyMode,
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


def select_independent(
    candidates: Sequence[str],
    fleet: Sequence[Capability],
    k: Optional[int],
) -> List[str]:
    by_id = {cap.device_id: cap for cap in fleet}
    live = [
        by_id[cid]
        for cid in candidates
        if cid in by_id and not store.is_quarantined(cid)
    ]
    selected: List[Capability] = []
    seen_vendor = set()
    seen_host = set()

    for cap in live:
        if cap.vendor not in seen_vendor:
            selected.append(cap)
            seen_vendor.add(cap.vendor)
            seen_host.add(host_of(cap))
        if k is not None and len(selected) >= k:
            return [cap.device_id for cap in selected]

    for cap in live:
        if cap in selected:
            continue
        if host_of(cap) not in seen_host:
            selected.append(cap)
            seen_host.add(host_of(cap))
        if k is not None and len(selected) >= k:
            return [cap.device_id for cap in selected]

    for cap in live:
        if cap not in selected:
            selected.append(cap)
        if k is not None and len(selected) >= k:
            break
    return [cap.device_id for cap in selected]


def min_required(policy: ThresholdPolicy, k: Optional[int], n: int) -> int:
    if policy is ThresholdPolicy.unanimous:
        return max(n, 1)
    if policy is ThresholdPolicy.at_least_k:
        return max(int(k) if k is not None else n, 1)
    floor = max((n // 2) + 1, 1) if policy is ThresholdPolicy.majority else 1
    if k is not None:
        return max(k, floor)
    return floor


def verify_threshold(
    req: VerificationRequest,
    fleet: Sequence[Capability],
) -> Result[CompositeAttestation]:
    k = req.k
    need = min_required(req.policy, k, len(req.candidates))
    verifiers = select_independent(req.candidates, fleet, max(need, k or 0))
    if len(verifiers) < need:
        return Err(
            SeamError.verification_failed,
            f"independent verifiers {len(verifiers)} < {need}",
        )

    caps_by_id = {cap.device_id: cap for cap in fleet}
    allowed_issuers: set[str] = set()
    for device_id in verifiers:
        allowed_issuers.add(f"result:{device_id}")
        cap = caps_by_id.get(device_id)
        if cap is not None and cap.privacy_mode is PrivacyMode.zero_knowledge:
            allowed_issuers.add("zk")

    links = []
    expected = list(req.outputs)
    idem = digest_of(
        "|".join([req.kernel.value] + list(req.inputs)).encode("utf-8")
    )
    if req.kernel is KernelName.attest_compose:
        kernel_args = {"subjects": list(req.inputs)}
    elif req.kernel is KernelName.attest_result:
        kernel_args = {"subject": req.inputs[0] if req.inputs else ""}
    else:
        kernel_args = {"inputs": req.inputs}
    for device_id in verifiers:
        dispatched = dispatch(
            "threshold",
            device_id,
            req.kernel,
            kernel_args,
            f"tv:{idem}:{device_id}",
        )
        if isinstance(dispatched, Err):
            store.audit(
                "threshold_dispatch_fail",
                device_id=device_id,
                detail=dispatched.detail,
            )
            continue
        pre_state = dispatched.value.state
        polled = poll("threshold", dispatched.value)
        if isinstance(polled, Ok) and polled.value is None:
            store.audit("threshold_repoll", device_id=device_id)
            continue
        if isinstance(polled, Err):
            if pre_state == "pending" and polled.error is SeamError.verification_failed:
                store.quarantine(device_id, "threshold_poll")
                store.audit("threshold_dissent", device_id=device_id, reason="poll")
            else:
                store.audit(
                    "threshold_skip",
                    device_id=device_id,
                    reason=polled.error.value,
                )
            continue
        result = polled.value
        got = (
            list(result.handle.outputs)
            if result.handle.outputs
            else [digest_of(output) for output in result.outputs]
        )
        if expected and got != expected:
            store.quarantine(device_id, "threshold_mismatch")
            store.audit(
                "threshold_dissent",
                device_id=device_id,
                reason="output_mismatch",
            )
            continue
        if result.attestation.issuer not in allowed_issuers:
            store.quarantine(device_id, "threshold_issuer")
            store.audit(
                "threshold_dissent",
                device_id=device_id,
                reason="issuer_forgery",
                issuer=result.attestation.issuer,
            )
            continue
        links.append(result.attestation)

    if len(links) < need:
        return Err(
            SeamError.verification_failed,
            f"agreeing links {len(links)} < {need}",
        )
    return attest_compose(links, req.policy, k, issuers=allowed_issuers)
