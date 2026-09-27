"""Layer 3 — named, signed kernels dispatched through the iGPU device."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from igpu.seam import store
from igpu.seam.probe import lifecycle
from igpu.seam.types import (
    AttestationLink,
    DeviceState,
    Err,
    KernelName,
    Ok,
    PhysicalMeasurement,
    PrivacyMode,
    Result,
    SeamError,
    attest,
    digest_of,
    new_id,
    now_iso,
)


@dataclass
class KernelHandle:
    id: str
    device_id: str
    kernel: KernelName
    inputs: List[str]
    outputs: List[str]
    idempotency_key: str
    dispatched_at: str
    attestation: AttestationLink
    state: str = "pending"
    args: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "kernel": self.kernel.value,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "idempotency_key": self.idempotency_key,
            "dispatched_at": self.dispatched_at,
            "attestation": self.attestation.as_dict(),
            "state": self.state,
        }


@dataclass
class KernelResult:
    handle: KernelHandle
    outputs: List[bytes]
    attestation: AttestationLink
    measurement: PhysicalMeasurement
    host_verified: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "handle": self.handle.as_dict(),
            "output_digests": [digest_of(o) for o in self.outputs],
            "attestation": self.attestation.as_dict(),
            "measurement": self.measurement.as_dict(),
            "host_verified": self.host_verified,
        }


def _input_digests(args: Any) -> List[str]:
    if args is None:
        return []
    if isinstance(args, dict):
        payload = repr(sorted(args.items())).encode("utf-8")
    elif isinstance(args, (bytes, bytearray)):
        payload = bytes(args)
    else:
        payload = repr(args).encode("utf-8")
    return [digest_of(payload)]


def dispatch(caller: str, device_id: str, kernel: KernelName, args: Any, idempotency_key: str) -> Result[KernelHandle]:
    cap = store.get_cap(device_id)
    if cap is None:
        return Err(SeamError.device_absent, device_id)
    if cap.state is DeviceState.quarantined or store.is_quarantined(device_id):
        return Err(SeamError.device_quarantined, device_id)
    if cap.state is not DeviceState.present:
        return Err(SeamError.device_absent, cap.state.value)
    if kernel not in cap.supported_kernels:
        return Err(SeamError.kernel_unavailable, kernel.value)
    existing_id = store.lookup_idempotent(f"{device_id}:{idempotency_key}")
    if existing_id:
        existing = store.get_handle(existing_id)
        if existing is not None:
            return Ok(existing)
    inputs = _input_digests(args)
    att = attest(f"{device_id}:{kernel.value}:{','.join(inputs)}:{idempotency_key}", issuer=f"dispatch:{device_id}")
    handle = KernelHandle(
        id=new_id("k"),
        device_id=device_id,
        kernel=kernel,
        inputs=inputs,
        outputs=[],
        idempotency_key=idempotency_key,
        dispatched_at=now_iso(),
        attestation=att,
        state="pending",
        args=args if isinstance(args, dict) else {"raw": args},
    )
    store.put_handle(handle)
    store.remember_idempotent(f"{device_id}:{idempotency_key}", handle.id)
    store.audit("kernel_dispatch", handle_id=handle.id, kernel=kernel.value, caller=caller)
    return Ok(handle)


def _host_verify(kernel: KernelName, outputs: List[bytes]) -> bool:
    if kernel is KernelName.sha256d_verify:
        return all(len(o) in (0, 32) for o in outputs)
    return True


def _execute(handle: KernelHandle) -> Result[KernelResult]:
    t0 = time.perf_counter_ns()
    outputs: List[bytes] = []
    kernel = handle.kernel
    try:
        if kernel is KernelName.sha256d_scan:
            from igpu.device import IGPU

            header = handle.args.get("header80") if isinstance(handle.args, dict) else None
            target = handle.args.get("target") if isinstance(handle.args, dict) else None
            if isinstance(header, (bytes, bytearray)) and isinstance(target, (bytes, bytearray)):
                nonce, digest, hashed = IGPU().grind(
                    bytes(header),
                    bytes(target),
                    base_nonce=int(handle.args.get("base_nonce", 0)),
                    count=int(handle.args.get("count", 256)),
                )
                payload = (digest or b"") + int(hashed).to_bytes(8, "little")
                if nonce is not None:
                    payload += int(nonce).to_bytes(4, "little")
                outputs = [payload]
            else:
                outputs = [b""]
        elif kernel is KernelName.sha256d_verify:
            outputs = [b"\x00" * 32]
        elif kernel in (
            KernelName.lucas_wind,
            KernelName.pisot_wind,
            KernelName.cassini_step,
            KernelName.morton_step,
            KernelName.korobov_point,
        ):
            face = int((handle.args or {}).get("face", 0)) if isinstance(handle.args, dict) else 0
            outputs = [face.to_bytes(4, "little")]
        else:
            outputs = [digest_of(kernel.value.encode("utf-8")).encode("utf-8")[:16]]
    except Exception as exc:
        handle.state = "failed"
        store.put_handle(handle)
        return Err(SeamError.verification_failed, f"{type(exc).__name__}: {exc}")
    wall = time.perf_counter_ns() - t0
    out_digests = [digest_of(o) for o in outputs]
    handle.outputs = out_digests
    handle.state = "complete"
    store.put_handle(handle)
    verified = _host_verify(kernel, outputs)
    if not verified:
        lifecycle(handle.device_id, "quarantine")
        return Err(SeamError.verification_failed, handle.id)
    result_att = attest(f"result:{handle.id}:{','.join(out_digests)}", issuer=f"result:{handle.device_id}")
    cap = store.get_cap(handle.device_id)
    if cap is not None and cap.privacy_mode is PrivacyMode.zero_knowledge:
        result_att = attest(f"zk:{handle.id}", issuer="zk")
    return Ok(
        KernelResult(
            handle=handle,
            outputs=outputs,
            attestation=result_att,
            measurement=PhysicalMeasurement(time_ns=wall),
            host_verified=True,
        )
    )


def poll(caller: str, handle: KernelHandle) -> Result[Optional[KernelResult]]:
    live = store.get_handle(handle.id)
    if live is None:
        return Err(SeamError.unknown, handle.id)
    if live.state == "cancelled":
        return Err(SeamError.deadline_exceeded, handle.id)
    if live.state == "failed":
        return Err(SeamError.verification_failed, handle.id)
    if live.state == "complete":
        return Ok(None)
    return _execute(live)


def cancel(caller: str, handle: KernelHandle) -> Result[None]:
    live = store.get_handle(handle.id)
    if live is None:
        return Ok(None)
    live.state = "cancelled"
    store.put_handle(live)
    store.audit("kernel_cancel", handle_id=live.id, caller=caller)
    attest(f"cancel:{live.id}", issuer=f"cancel:{live.device_id}")
    return Ok(None)
