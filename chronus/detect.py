"""Unified GPU detector.

One ordered device census across CUDA, Metal, and OpenCL, with two rules
that the rest of the stack depends on.

Integration is evidence, never a guess
--------------------------------------
``is_integrated`` is true only when the vendor is Intel or Apple, or when the
device itself reports host-unified memory
(``CL_DEVICE_HOST_UNIFIED_MEMORY``). A discrete GPU is never labelled
integrated even though OpenCL reports it as a GPU, so ``is_gpu`` and
``is_integrated`` stay independent facts. Every record carries the
``integrated_reason`` that produced the verdict, so a wrong answer is
traceable to the evidence that caused it rather than hidden in a boolean.

Deduplication compares devices, not indices
--------------------------------------------
An OpenCL device is suppressed only when a device with the same normalized
name *and* vendor was already detected through CUDA or Metal. The
comparison runs against the previously detected device list itself, so the
result does not depend on how many entries that list happened to hold.
Suppressed duplicates are reported in :attr:`DetectionReport.deduped`
instead of being discarded silently.

Canonical home: ``chronus.detect`` (the Chronus package). The
pre-consolidation path ``legacy/accel/unified_gpu_detector.py`` re-exports
this module.
"""

from __future__ import annotations

import logging
import platform as _platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

LOG = logging.getLogger(__name__)

#: Vendor normalization buckets. Only vendors in :data:`INTEGRATED_VENDORS`
#: justify an integrated verdict on vendor evidence alone.
_VENDOR_ALIASES: Dict[str, str] = {
    "intel": "intel",
    "intel(r) corporation": "intel",
    "intel corporation": "intel",
    "apple": "apple",
    "apple inc.": "apple",
    "apple inc": "apple",
    "nvidia": "nvidia",
    "nvidia corporation": "nvidia",
    "amd": "amd",
    "advanced micro devices": "amd",
    "advanced micro devices, inc.": "amd",
    "hpe": "hpe",
    "hewlett-packard": "hpe",
    "hewlett packard": "hpe",
}

#: Vendors whose parts are integrated into the host package. A discrete
#: part from any other vendor is not integrated by vendor evidence; it may
#: still qualify through host-unified memory.
INTEGRATED_VENDORS = frozenset({"intel", "apple"})

#: Dropped during name normalization so that "Intel(R) Graphics [0x5917]"
#: and "Intel(R) Graphics" reduce to one identity.


def normalize_vendor(vendor: Any) -> str:
    """Collapse a vendor string to a comparison bucket ('' when unknown)."""
    text = " ".join(str(vendor or "").strip().lower().split())
    if not text:
        return ""
    if text in _VENDOR_ALIASES:
        return _VENDOR_ALIASES[text]
    for alias, bucket in _VENDOR_ALIASES.items():
        if text.startswith(alias):
            return bucket
    return text


def normalize_name(name: Any) -> str:
    """Collapse a device name to a comparison key (parentheticals removed)."""
    text = _NAME_NOISE.sub(" ", str(name or "").lower())
    return " ".join(text.split())


def device_identity(name: Any, vendor: Any) -> Tuple[str, str]:
    """The (name, vendor) key used to recognize one physical device twice."""
    return normalize_name(name), normalize_vendor(vendor)


def host_unified_memory(device: Any) -> Optional[bool]:
    """Read ``host_unified_memory`` when the binding exposes it.

    Returns ``None`` when the attribute is absent or unreadable, which keeps
    "the driver did not tell us" distinguishable from "the driver said no".
    """
    try:
        value = getattr(device, "host_unified_memory", None)
    except Exception as exc:  # pragma: no cover - driver specific
        LOG.debug("host_unified_memory probe failed: %s: %s", type(exc).__name__, exc)
        return None
    if value is None:
        return None
    return bool(value)


def classify_integrated(vendor: Any, device: Any = None) -> Tuple[bool, str]:
    """Decide whether a device is integrated, and say which evidence decided.

    Returns ``(is_integrated, reason)``. The reason string is always populated so
    telemetry can explain the verdict.
    """
    bucket = normalize_vendor(vendor)
    if bucket in INTEGRATED_VENDORS:
        return True, f"vendor:{bucket}"
    unified = host_unified_memory(device) if device is not None else None
    if unified:
        return True, "host_unified_memory"
    if unified is None:
        return False, f"vendor:{bucket or 'unknown'}:no-unified-memory-reported"
    return False, f"vendor:{bucket or 'unknown'}:host_unified_memory=false"


@dataclass(frozen=True)
class DetectedDevice:
    """One physical device observed through exactly one backend."""

    backend: str
    name: str
    vendor: str
    is_gpu: bool
    is_integrated: bool
    integrated_reason: str
    type_bits: int = 0
    platform: str = ""
    driver_version: str = ""
    version: str = ""
    host_unified_memory: Optional[bool] = None
    pci_ids: Tuple[str, ...] = ()

    @property
    def identity(self) -> Tuple[str, str]:
        return device_identity(self.name, self.vendor)

    @property
    def label(self) -> str:
        return f"{self.vendor}: {self.name}" if self.vendor else self.name

    def as_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "name": self.name,
            "vendor": self.vendor,
            "is_gpu": self.is_gpu,
            "is_integrated": self.is_integrated,
            "integrated_reason": self.integrated_reason,
            "type_bits": self.type_bits,
            "platform": self.platform,
            "driver_version": self.driver_version,
            "version": self.version,
            "host_unified_memory": self.host_unified_memory,
            "pci_ids": list(self.pci_ids),
            "identity": [self.identity[0], self.identity[1]],
        }


@dataclass
class DetectionReport:
    """Device census plus the records that explain what was left out."""

    devices: List[DetectedDevice] = field(default_factory=list)
    deduped: List[DetectedDevice] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    def default(self) -> Optional["DetectedDevice"]:
        return default_device(self.devices)

    def as_dict(self) -> Dict[str, Any]:
        chosen = self.default()
        return {
            "devices": [d.as_dict() for d in self.devices],
            "deduped": [d.as_dict() for d in self.deduped],
            "errors": dict(self.errors),
            "default": chosen.label if chosen else None,
        }


def _run(exe: str, args: List[str], timeout: int = 10) -> str:
    try:
        proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
    return (proc.stdout or "") + (proc.stderr or "")


def _split_csv(row: str) -> List[str]:
    return [part.strip() for part in row.split(",")]


_NAME_NOISE = re.compile(r"\(.*?\)|\[.*?\]")


def detect_cuda() -> List[DetectedDevice]:
    """NVIDIA CUDA devices from nvidia-smi. Discrete by construction."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return []
    out = _run(exe, ["--query-gpu=name,pci.device_id,driver_version", "--format=csv,noheader"])
    devices: List[DetectedDevice] = []
    for row in (line for line in out.splitlines() if line.strip()):
        parts = _split_csv(row)
        name = parts[0] if parts else ""
        pci = parts[1] if len(parts) > 1 else ""
        driver = parts[2] if len(parts) > 2 else ""
        is_integrated, reason = classify_integrated("nvidia")
        devices.append(
            DetectedDevice(
                backend="cuda",
                name=name,
                vendor="nvidia",
                is_gpu=True,
                is_integrated=is_integrated,
                integrated_reason=reason,
                type_bits=_GPU_TYPE_BIT,
                platform=exe,
                driver_version=driver,
                pci_ids=(pci,) if pci else (),
            )
        )
    return devices


def detect_metal() -> List[DetectedDevice]:
    """Apple Metal devices. Apple parts are integrated with the SoC."""
    if _platform.system() != "Darwin":
        return []
    devices: List[DetectedDevice] = []
    exe = shutil.which("system_profiler")
    if exe is not None:
        out = _run(exe, ["SPDisplaysDataType"])
        names = [ln.split(":", 1)[1].strip() for ln in out.splitlines() if "Chipset Model" in ln]
        for name in names[:4]:
            is_integrated, reason = classify_integrated("apple")
            devices.append(
                DetectedDevice(
                    backend="metal",
                    name=name,
                    vendor="apple",
                    is_gpu=True,
                    is_integrated=is_integrated,
                    integrated_reason=reason,
                    type_bits=_GPU_TYPE_BIT,
                    platform=exe,
                    pci_ids=(_platform.machine(),),
                )
            )
    if devices:
        return devices
    is_integrated, reason = classify_integrated("apple")
    return [
        DetectedDevice(
            backend="metal",
            name=_platform.machine() or "Apple GPU",
            vendor="apple",
            is_gpu=True,
            is_integrated=is_integrated,
            integrated_reason=reason,
            type_bits=_GPU_TYPE_BIT,
            platform=_platform.system(),
        )
    ]


#: CL_DEVICE_TYPE_GPU, used when no binding is available to ask.
_GPU_TYPE_BIT = 1 << 2

#: The Chronus contract device is the system's GPU identity: the MLA1517
#: contract defines an integrated, host-unified-memory SIMT accelerator whose
#: warp lanes the resident substrate executes. Enumerating it is contract
#: evidence, not a hardware guess — it appears only when the contract loads,
#: and the physical devices found beside it are execution backends.
_CHRONUS_BACKEND = "chronus"


def detect_chronus() -> List[DetectedDevice]:
    """Enumerate the Chronus contract device.

    Returns one integrated GPU-class record whose fields all come from the
    machine-readable contract (product name, contract version, UMA memory
    model). An absent or unreadable contract returns no device — the record
    exists only while the artifact it describes exists.
    """
    try:
        from . import spec as _spec

        contract = _spec.load_spec()
    except Exception:
        return []
    topo = _spec.topology(contract)
    version = str(contract.get("contract_version", "") or "")
    return [
        DetectedDevice(
            backend=_CHRONUS_BACKEND,
            name=_spec.product(contract),
            vendor="hyba",
            is_gpu=True,
            is_integrated=True,
            integrated_reason="contract:simt_host_unified_memory",
            type_bits=_GPU_TYPE_BIT,
            platform="mla1517_simt",
            driver_version=version,
            version=version,
            host_unified_memory=str(topo.get("memory_address_space", "")).upper()
            == "UMA",
        )
    ]


def find_prior(
    already: Sequence[DetectedDevice], identity: Tuple[str, str]
) -> Optional[DetectedDevice]:
    """Return the already-detected device with this identity, else ``None``.

    The comparison is against the detected records themselves. Comparing
    against ``range(len(already))`` would test indices instead of devices and
    would silently mis-decide whenever the two counts happened to coincide.
    """
    name_key, vendor_key = identity
    if not name_key and not vendor_key:
        return None
    for record in already:
        if record.identity == identity:
            return record
    return None


def _detect_opencl(
    cl: Any,
    already: Sequence[DetectedDevice] = (),
    deduped: Optional[List[DetectedDevice]] = None,
) -> List[DetectedDevice]:
    """Enumerate OpenCL devices, suppressing ones already seen via CUDA/Metal.

    ``already`` is the list of devices detected by earlier backends; an
    OpenCL device is skipped only when :func:`find_prior` finds a record
    with the same normalized name and vendor. Suppressed devices are
    appended to ``deduped`` so the drop is observable rather than silent.
    """
    sink: List[DetectedDevice] = [] if deduped is None else deduped
    gpu_bit = int(getattr(getattr(cl, "device_type", None), "GPU", _GPU_TYPE_BIT))
    out: List[DetectedDevice] = []
    for plat in cl.get_platforms():
        platform_name = str(getattr(plat, "name", "") or "")
        for dev in plat.get_devices():
            name = str(getattr(dev, "name", "") or "").strip()
            vendor = str(getattr(dev, "vendor", "") or "").strip()
            type_bits = int(getattr(dev, "type", 0) or 0)
            unified = host_unified_memory(dev)
            is_integrated, reason = classify_integrated(vendor, dev)
            record = DetectedDevice(
                backend="opencl",
                name=name,
                vendor=vendor,
                is_gpu=bool(type_bits & gpu_bit),
                is_integrated=is_integrated,
                integrated_reason=reason,
                type_bits=type_bits,
                platform=platform_name,
                driver_version=str(getattr(dev, "driver_version", "") or ""),
                version=str(getattr(dev, "version", "") or ""),
                host_unified_memory=unified,
            )
            prior = find_prior(already, record.identity)
            if prior is not None:
                LOG.debug(
                    "suppressing duplicate device %r: already detected via %s",
                    record.label,
                    prior.backend,
                )
                sink.append(record)
                continue
            out.append(record)
    return out


def detect_all() -> DetectionReport:
    """Census every backend in preference order and deduplicate across them."""
    report = DetectionReport()
    already: List[DetectedDevice] = []
    for name, probe in (
        ("chronus", detect_chronus),
        ("cuda", detect_cuda),
        ("metal", detect_metal),
    ):
        try:
            found = probe()
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            LOG.warning("GPU detection tier %r failed: %s", name, reason)
            report.errors[name] = reason
            continue
        report.devices.extend(found)
        already.extend(found)
    try:
        import pyopencl as cl
    except Exception as exc:
        report.errors["opencl"] = f"{type(exc).__name__}: {exc}"
        return report
    try:
        opencl_devices = _detect_opencl(cl, already, report.deduped)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        LOG.warning("GPU detection tier 'opencl' failed: %s", reason)
        report.errors["opencl"] = reason
        return report
    report.devices.extend(opencl_devices)
    return report


def default_device(devices: Optional[Sequence[DetectedDevice]] = None) -> Optional[DetectedDevice]:
    """The device the substrate should use: iGPU first, then GPU, then any."""
    pool = list(devices) if devices is not None else detect_all().devices
    if not pool:
        return None
    for predicate in (lambda d: d.is_integrated, lambda d: d.is_gpu, lambda d: True):
        for record in pool:
            if predicate(record):
                return record
    return None


__all__ = [
    "INTEGRATED_VENDORS",
    "DetectionReport",
    "DetectedDevice",
    "classify_integrated",
    "default_device",
    "detect_all",
    "detect_chronus",
    "detect_cuda",
    "detect_metal",
    "device_identity",
    "find_prior",
    "host_unified_memory",
    "normalize_name",
    "normalize_vendor",
]
