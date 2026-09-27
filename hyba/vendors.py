"""Vendor runtime shims — Metal / CUDA / ROCm / Vulkan / OpenCL detectors.

Apple/NVIDIA/HPE posture: each vendor module reports observed facts only
(importable libraries, enumerated devices, driver strings). Detection
never claims execution capability the kernels do not implement: the
SHA-256d consensus path executes on OpenCL (or explicit CPU); Metal/CUDA/
ROCm/Vulkan presence is reported for dispatch planning and container
selection, and forcing an unimplemented dispatch fails explicitly.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class VendorProbe:
    """One vendor probe result: present flag + observed detail."""

    vendor: str
    backend: str
    present: bool
    detail: str
    devices: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        """JSON-safe probe record."""
        return {
            "vendor": self.vendor,
            "backend": self.backend,
            "present": self.present,
            "detail": self.detail,
            "devices": list(self.devices),
        }


def _run(exe: str, args: List[str], timeout: int = 10) -> str:
    try:
        proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"probe failed: {exc}"
    return (proc.stdout or "") + (proc.stderr or "")


def probe_apple() -> VendorProbe:
    """Apple Metal/MLX: Darwin + Metal device + mlx import state."""
    if platform.system() != "Darwin":
        return VendorProbe("Apple", "metal", False, "Metal requires Darwin")
    detail = platform.machine()
    devices: List[str] = []
    exe = shutil.which("system_profiler")
    if exe:
        out = _run(exe, ["SPDisplaysDataType"])
        if "Metal" in out or "Apple" in out:
            devices = [ln.strip() for ln in out.splitlines() if "Chipset Model" in ln][:4]
            detail = "Metal device enumerated"
    try:
        __import__("mlx")
        detail += "; mlx importable"
    except Exception:
        detail += "; mlx not installed"
    return VendorProbe("Apple", "metal", True, detail, devices)


def probe_nvidia() -> VendorProbe:
    """NVIDIA CUDA: nvidia-smi enumeration; HPE OEM SKUs share PCI IDs."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return VendorProbe("NVIDIA", "cuda", False, "no nvidia-smi")
    out = _run(exe, ["--query-gpu=name,pci.device_id,driver_version", "--format=csv,noheader"])
    devices = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not devices:
        return VendorProbe("NVIDIA", "cuda", False, f"{exe}: no GPUs")
    return VendorProbe("NVIDIA", "cuda", True, exe, devices)


def probe_amd_hpe() -> VendorProbe:
    """AMD ROCm / HPE Cray: rocm-smi, then OpenCL vendor fallback."""
    exe = shutil.which("rocm-smi")
    if exe is not None:
        out = _run(exe, ["--showproductname"])
        devices = [ln.strip() for ln in out.splitlines() if ln.strip()][:8]
        return VendorProbe("AMD", "rocm", True, exe, devices)
    try:
        import pyopencl as cl

        names = [
            d.name.strip()
            for p in cl.get_platforms()
            for d in p.get_devices()
            if "amd" in str(getattr(d, "vendor", "")).lower()
            or "amd" in str(getattr(d, "name", "")).lower()
            or "radeon" in str(getattr(d, "name", "")).lower()
        ]
    except Exception as exc:
        return VendorProbe("AMD", "rocm", False, f"no rocm-smi ({exc})")
    if names:
        return VendorProbe("AMD", "rocm", True, "OpenCL AMD device", names)
    return VendorProbe("AMD", "rocm", False, "no rocm-smi, no AMD OpenCL")


def probe_vulkan() -> VendorProbe:
    """Vulkan: vulkaninfo must enumerate a physical GPU device."""
    exe = shutil.which("vulkaninfo")
    if exe is None:
        return VendorProbe("Vulkan", "vulkan", False, "no vulkaninfo")
    out = _run(exe, ["--summary"], timeout=15)
    if "GPU0" in out and "deviceName" in out:
        names = [ln.strip() for ln in out.splitlines() if "deviceName" in ln][:4]
        return VendorProbe("Vulkan", "vulkan", True, exe, names)
    return VendorProbe("Vulkan", "vulkan", False, f"no devices ({exe})")


def probe_opencl() -> VendorProbe:
    """OpenCL: pyopencl imports AND at least one device enumerates."""
    try:
        import pyopencl as cl
    except Exception as exc:
        return VendorProbe("OpenCL", "opencl", False, f"pyopencl: {exc}")
    try:
        devs = [(p, d) for p in cl.get_platforms() for d in p.get_devices()]
    except Exception as exc:
        return VendorProbe("OpenCL", "opencl", False, f"enumerate: {exc}")
    if not devs:
        return VendorProbe("OpenCL", "opencl", False, "no OpenCL devices")
    names = [f"{p.name.strip()} :: {d.name.strip()}" for p, d in devs]
    return VendorProbe("OpenCL", "opencl", True, f"{len(devs)} device(s)", names)


def probe_all() -> List[VendorProbe]:
    """All vendor probes in dispatch-preference order."""
    return [probe_apple(), probe_nvidia(), probe_amd_hpe(), probe_vulkan(), probe_opencl()]


def probe_summary() -> Dict[str, Any]:
    """Environment capability map for container dispatch decisions."""
    probes = probe_all()
    backends = [p.backend for p in probes if p.present] + ["cpu"]
    return {
        "probes": [p.as_dict() for p in probes],
        "executing_backends": ["opencl", "cpu"],
        "planning_backends": backends,
        "container_hint": _container_hint(probes),
    }


def _container_hint(probes: List[VendorProbe]) -> str:
    by = {p.backend: p for p in probes}
    if by["metal"].present:
        return "apple-metal (native Darwin)"
    if by["cuda"].present:
        return "docker-compose.cuda.yml (NVIDIA toolkit)"
    if by["rocm"].present:
        return "docker-compose.rocm.yml (ROCm devices)"
    if by["opencl"].present:
        return "docker-compose.igpu-linux.yml or igpu-wsl2.yml"
    return "cpu-only (pocl-opencl-icd for OpenCL CPU fallback)"


__all__ = [
    "VendorProbe",
    "probe_all",
    "probe_amd_hpe",
    "probe_apple",
    "probe_nvidia",
    "probe_opencl",
    "probe_summary",
    "probe_vulkan",
]
