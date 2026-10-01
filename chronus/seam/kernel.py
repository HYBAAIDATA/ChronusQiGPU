"""Layer 3 — named, signed kernels dispatched through the iGPU device."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from gpu.reference import (
    cassini_step,
    grover_hendrix_iterate,
    grover_iterate,
    korobov_point,
    lucas_wind,
    matmul_f4,
    matvec_f4,
    morton_step,
    pisot_wind,
    qfi_pure,
    sha256_midstate,
    sha256d_merkle,
    sha256d_verify,
)
from . import store
from .probe import lifecycle
from .types import (
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
    canonical_json,
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


def dispatch(
    caller: str,
    device_id: str,
    kernel: KernelName,
    args: Any,
    idempotency_key: str,
) -> Result[KernelHandle]:
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
    att = attest(
        f"{device_id}:{kernel.value}:{','.join(inputs)}:{idempotency_key}",
        issuer=f"dispatch:{device_id}",
    )
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
        return bool(outputs) and all(o in (b"\x00", b"\x01") for o in outputs)
    return True


def _encoded(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def _argument_error(handle: KernelHandle, detail: str) -> Err:
    handle.state = "failed"
    store.put_handle(handle)
    return Err(SeamError.capability_mismatch, detail)


def _execute(handle: KernelHandle) -> Result[KernelResult]:
    t0 = time.perf_counter_ns()
    outputs: List[bytes] = []
    kernel = handle.kernel
    try:
        if kernel is KernelName.sha256d_scan:
            from chronus.device import Chronus

            header = handle.args.get("header80") if isinstance(handle.args, dict) else None
            target = handle.args.get("target") if isinstance(handle.args, dict) else None
            if isinstance(header, (bytes, bytearray)) and isinstance(target, (bytes, bytearray)):
                nonce, digest, hashed = Chronus().grind(
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
                return _argument_error(
                    handle,
                    "sha256d_scan requires header80 and target byte strings",
                )
        elif kernel is KernelName.sha256d_verify:
            a = handle.args if isinstance(handle.args, dict) else {}
            payload = a.get("payload")
            claimed = a.get("claimed")
            if (
                not isinstance(payload, (bytes, bytearray))
                or not isinstance(claimed, (bytes, bytearray))
                or len(claimed) != 32
            ):
                return _argument_error(
                    handle,
                    "sha256d_verify requires args: payload (bytes) and claimed (32-byte digest)",
                )
            outputs = [b"\x01" if sha256d_verify(bytes(payload), bytes(claimed)) else b"\x00"]
        elif kernel is KernelName.sha256d_midstate:
            block = handle.args.get("block64")
            if not isinstance(block, (bytes, bytearray)) or len(block) != 64:
                return _argument_error(
                    handle,
                    "sha256d_midstate requires block64 (exactly 64 bytes)",
                )
            outputs = [sha256_midstate(bytes(block))]
        elif kernel is KernelName.sha256d_merkle:
            left = handle.args.get("left")
            right = handle.args.get("right")
            if not isinstance(left, (bytes, bytearray)) or not isinstance(
                right, (bytes, bytearray)
            ):
                return _argument_error(
                    handle,
                    "sha256d_merkle requires left and right byte strings",
                )
            outputs = [sha256d_merkle(bytes(left), bytes(right))]
        elif kernel is KernelName.matmul_f4:
            outputs = [_encoded(matmul_f4(handle.args["a"], handle.args["b"]))]
        elif kernel is KernelName.matvec_f4:
            outputs = [_encoded(matvec_f4(handle.args["a"], handle.args["x"]))]
        elif kernel is KernelName.qfi_pure:
            outputs = [
                _encoded(
                    qfi_pure(
                        handle.args["state"],
                        handle.args["derivative"],
                    )
                )
            ]
        elif kernel is KernelName.grover_iterate:
            outputs = [
                _encoded(
                    grover_iterate(
                        handle.args["state"],
                        handle.args["marked"],
                    )
                )
            ]
        elif kernel is KernelName.grover_hendrix_iterate:
            outputs = [
                _encoded(
                    grover_hendrix_iterate(
                        handle.args["state"],
                        handle.args["marked"],
                        handle.args["order"],
                    )
                )
            ]
        elif kernel is KernelName.lucas_wind:
            outputs = [_encoded(lucas_wind(handle.args["index"]))]
        elif kernel is KernelName.pisot_wind:
            outputs = [
                _encoded(
                    pisot_wind(
                        handle.args["size"],
                        handle.args.get("seed", 0),
                    )
                )
            ]
        elif kernel is KernelName.cassini_step:
            outputs = [
                _encoded(
                    cassini_step(
                        handle.args["index"],
                        handle.args["modulus"],
                        handle.args["stride"],
                        handle.args.get("origin", 0),
                    )
                )
            ]
        elif kernel is KernelName.morton_step:
            outputs = [
                _encoded(
                    morton_step(
                        handle.args["x"],
                        handle.args["y"],
                        handle.args.get("bits", 16),
                    )
                )
            ]
        elif kernel is KernelName.korobov_point:
            outputs = [
                _encoded(
                    korobov_point(
                        handle.args["index"],
                        handle.args["modulus"],
                        handle.args["multipliers"],
                    )
                )
            ]
        elif kernel is KernelName.attest_result:
            subject = str(handle.args["subject"])
            issuer = str(handle.args.get("issuer", "pythia.seam"))
            outputs = [_encoded(attest(subject, issuer=issuer).as_dict())]
        elif kernel is KernelName.attest_compose:
            subjects = handle.args.get("subjects")
            if not isinstance(subjects, list) or not subjects:
                return _argument_error(
                    handle,
                    "attest_compose requires a non-empty subjects list",
                )
            subject = digest_of(canonical_json(subjects).encode("utf-8"))
            outputs = [_encoded(attest(subject, issuer="pythia.seam.compose").as_dict())]
        else:
            handle.state = "failed"
            store.put_handle(handle)
            return Err(
                SeamError.kernel_unavailable,
                f"no executable implementation for {kernel.value}",
            )
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
    result_att = attest(
        f"result:{handle.id}:{','.join(out_digests)}",
        issuer=f"result:{handle.device_id}",
    )
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
