"""Layer 1 — statistical, attested, lifecycle-aware device probe.

Wraps igpu.detect. Never labels CPU as iGPU.
A device with measured_hps.mean == 0 is not returned (P1).
"""

from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from igpu.seam import store
from igpu.seam.types import (
    DeviceClass,
    DeviceState,
    Distribution,
    Err,
    KernelName,
    Ok,
    PrivacyMode,
    Result,
    SeamError,
    attest,
    digest_of,
    now_iso,
)


@dataclass
class CapabilityFeatures:
    fp64: bool = False
    fp16: bool = False
    int8: bool = True
    unified_memory: bool = False
    async_queue: bool = False
    reversible: bool = False
    fault_tolerant: bool = False
    power_states: Set[str] = field(default_factory=set)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "fp64": self.fp64,
            "fp16": self.fp16,
            "int8": self.int8,
            "unified_memory": self.unified_memory,
            "async_queue": self.async_queue,
            "reversible": self.reversible,
            "fault_tolerant": self.fault_tolerant,
            "power_states": sorted(self.power_states),
        }


@dataclass
class Capability:
    device_id: str
    device_class: DeviceClass
    vendor: str
    model: str
    firmware_digest: str
    memory_bytes: int
    compute_units: int
    max_work_group: int
    measured_hps: Distribution
    supported_kernels: Set[KernelName]
    kernel_costs: Dict[str, Distribution]
    features: CapabilityFeatures
    attestation_chain: list
    privacy_mode: PrivacyMode
    state: DeviceState
    vendor_extensions: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_class": self.device_class.value,
            "vendor": self.vendor,
            "model": self.model,
            "firmware_digest": self.firmware_digest,
            "memory_bytes": self.memory_bytes,
            "compute_units": self.compute_units,
            "max_work_group": self.max_work_group,
            "measured_hps": self.measured_hps.as_dict(),
            "supported_kernels": sorted(k.value for k in self.supported_kernels),
            "kernel_costs": {k: v.as_dict() for k, v in self.kernel_costs.items()},
            "features": self.features.as_dict(),
            "attestation_chain": [a.as_dict() for a in self.attestation_chain],
            "privacy_mode": self.privacy_mode.value,
            "state": self.state.value,
            "vendor_extensions": dict(self.vendor_extensions),
        }


def _classify(detected: Any) -> DeviceClass:
    vendor = str(getattr(detected, "vendor", "") or "").lower()
    name = str(getattr(detected, "name", "") or "").lower()
    is_igpu = bool(getattr(detected, "is_igpu", False))
    is_gpu = bool(getattr(detected, "is_gpu", False))
    if any(tag in name for tag in ("h100", "a100", "mi300", "b200")):
        return DeviceClass.gpu_datacenter
    if is_igpu:
        return DeviceClass.gpu_integrated
    if is_gpu:
        return DeviceClass.gpu_discrete
    if "asic" in name or "bitmain" in vendor:
        return DeviceClass.asic
    return DeviceClass.cpu_reference


def _default_kernels(klass: DeviceClass) -> Set[KernelName]:
    traversal = {
        KernelName.lucas_wind,
        KernelName.pisot_wind,
        KernelName.cassini_step,
        KernelName.morton_step,
        KernelName.korobov_point,
    }
    attest_set = {KernelName.attest_result, KernelName.attest_compose, KernelName.sha256d_verify}
    if klass in {
        DeviceClass.gpu_integrated,
        DeviceClass.gpu_discrete,
        DeviceClass.gpu_datacenter,
        DeviceClass.gpu_cloud_instance,
    }:
        return traversal | attest_set | {KernelName.sha256d_scan, KernelName.matmul_f4, KernelName.matvec_f4}
    if klass == DeviceClass.asic:
        return {KernelName.sha256d_scan, KernelName.sha256d_verify} | attest_set
    return traversal | attest_set | {KernelName.sha256d_verify}


def _measure_host_hps(samples: int = 3, work: int = 1024) -> Distribution:
    rates: List[float] = []
    payload = b"\x00" * 80
    for _ in range(samples):
        t0 = time.perf_counter()
        digest = payload
        for _n in range(work):
            digest = hashlib.sha256(hashlib.sha256(digest).digest()).digest()
        wall = time.perf_counter() - t0
        if wall > 0:
            rates.append(work / wall)
    if not rates:
        return Distribution(0.0, 0.0, 0)
    mean = statistics.fmean(rates)
    std = statistics.pstdev(rates) if len(rates) > 1 else 0.0
    return Distribution(mean, std, len(rates))


def _firmware_digest(detected: Any) -> str:
    driver = str(getattr(detected, "driver_version", "") or "")
    version = str(getattr(detected, "version", "") or "")
    name = str(getattr(detected, "name", "") or "")
    vendor = str(getattr(detected, "vendor", "") or "")
    return digest_of(f"{vendor}|{name}|{driver}|{version}".encode("utf-8"))


def _measure_from_telemetry(detected: Any) -> Optional[Distribution]:
    try:
        from igpu.telemetry import get_telemetry

        snap = get_telemetry().snapshot()
    except Exception:
        return None
    if not isinstance(snap, dict):
        return None
    hps = snap.get("measured_hps") or snap.get("hashes_per_second")
    if isinstance(hps, (int, float)) and float(hps) > 0.0:
        return Distribution(float(hps), 0.0, 1)
    return None


def _from_detected(detected: Any) -> Optional[Capability]:
    klass = _classify(detected)
    measured = _measure_from_telemetry(detected)
    if measured is None:
        measured = _measure_host_hps()
    if measured.mean <= 0.0:
        return None
    firmware = _firmware_digest(detected)
    device_id = digest_of(f"{klass.value}|{detected.vendor}|{detected.name}".encode("utf-8"))[:16]
    unified = bool(getattr(detected, "host_unified_memory", False))
    chain = [attest(firmware, issuer=f"probe:{device_id}"), attest(device_id, issuer="pythia.seam", chain_root=firmware)]
    kernels = _default_kernels(klass)
    return Capability(
        device_id=device_id,
        device_class=klass,
        vendor=str(getattr(detected, "vendor", "") or "unknown"),
        model=str(getattr(detected, "name", "") or "unknown"),
        firmware_digest=firmware,
        memory_bytes=0,
        compute_units=0,
        max_work_group=0,
        measured_hps=measured,
        supported_kernels=kernels,
        kernel_costs={k.value: Distribution(1.0, 0.0, 1) for k in kernels},
        features=CapabilityFeatures(unified_memory=unified, power_states={"unknown"}),
        attestation_chain=chain,
        privacy_mode=PrivacyMode.none,
        state=DeviceState.present,
        vendor_extensions={
            "backend": str(getattr(detected, "backend", "") or ""),
            "integrated_reason": str(getattr(detected, "integrated_reason", "") or ""),
            "is_igpu": str(bool(getattr(detected, "is_igpu", False))),
            "is_gpu": str(bool(getattr(detected, "is_gpu", False))),
        },
    )


def _cpu_reference_capability() -> Capability:
    measured = _measure_host_hps()
    firmware = digest_of(b"cpu_reference")
    kernels = _default_kernels(DeviceClass.cpu_reference)
    return Capability(
        device_id="cpu_reference",
        device_class=DeviceClass.cpu_reference,
        vendor="host",
        model="cpu_reference",
        firmware_digest=firmware,
        memory_bytes=0,
        compute_units=1,
        max_work_group=1,
        measured_hps=measured,
        supported_kernels=kernels,
        kernel_costs={k.value: Distribution(1.0, 0.0, 1) for k in kernels},
        features=CapabilityFeatures(),
        attestation_chain=[attest(firmware, issuer="probe:cpu_reference")],
        privacy_mode=PrivacyMode.none,
        state=DeviceState.present,
        vendor_extensions={"backend": "cpu"},
    )


def probe_devices() -> Result[List[Capability]]:
    caps: List[Capability] = []
    try:
        from igpu.detect import detect_all

        report = detect_all()
        for detected in getattr(report, "devices", []) or []:
            cap = _from_detected(detected)
            if cap is None or cap.measured_hps.mean <= 0.0 or not cap.attestation_chain or not cap.firmware_digest:
                continue
            store.put_cap(cap)
            caps.append(cap)
    except Exception as exc:
        store.audit("probe_error", detail=f"{type(exc).__name__}: {exc}")
    if not any(c.device_class == DeviceClass.cpu_reference for c in caps):
        cpu = _cpu_reference_capability()
        if cpu.measured_hps.mean > 0.0 and cpu.attestation_chain:
            store.put_cap(cpu)
            caps.append(cpu)
    if not caps:
        return Err(SeamError.device_absent, "no measurable attested device")
    store.audit("probe_devices", count=len(caps), at=now_iso())
    return Ok(caps)


_TRANSITIONS = {
    ("present", "quarantine"): DeviceState.quarantined,
    ("present", "deprovision"): DeviceState.deprovisioned,
    ("quarantined", "rehabilitate"): DeviceState.rehabilitated,
    ("rehabilitated", "provision"): DeviceState.present,
    ("absent", "provision"): DeviceState.provisioning,
    ("provisioning", "provision"): DeviceState.present,
}


def lifecycle(device_id: str, transition: str) -> Result[Capability]:
    cap = store.get_cap(device_id)
    if cap is None:
        return Err(SeamError.device_absent, device_id)
    nxt = _TRANSITIONS.get((cap.state.value, transition))
    if nxt is None:
        return Err(SeamError.capability_mismatch, f"illegal {cap.state.value}->{transition}")
    cap.state = nxt
    if nxt is DeviceState.quarantined:
        store.quarantine(device_id, transition)
    cap.attestation_chain.append(attest(f"{device_id}:{transition}:{nxt.value}", issuer="lifecycle"))
    store.put_cap(cap)
    store.audit("lifecycle", device_id=device_id, transition=transition, state=nxt.value)
    return Ok(cap)
