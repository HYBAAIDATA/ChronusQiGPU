"""HYBA capability inventory — the measured census the substrate composes.

``ClusterInventory.collect()`` walks every reachable backend and emits one
:class:`DeviceInfo` per physical device with only *measured* capability
keys: a capability that was not probed is simply absent from the mapping —
never reported as False and never guessed. Tiers that cannot enumerate
record their concrete reason in ``errors`` instead of raising, so the
composed substrate degrades explicitly rather than silently.
"""

from __future__ import annotations

import os
import platform as _platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Kernel entry names whose presence in a .cl file makes a capability claim.
_M32_KERNEL = "bitcoin_sha256d_m32"
_LADDER_KERNEL = "mla1517_lucas_pisot_scale"


def _kernel_source_has(entry: str) -> bool:
    """True when a canonical .cl source actually defines ``entry``."""
    for base in (_REPO_ROOT / "kernels", _REPO_ROOT / "chronus" / "kernels"):
        if not base.is_dir():
            continue
        for path in base.glob("*.cl"):
            try:
                if f"__kernel void {entry}" in path.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                continue
    # Platform kernel dir (mla1517) is canonical for the ladder executor.
    plat = _REPO_ROOT / "chronus/mla1517_platform" / "kernels"
    if plat.is_dir():
        for path in plat.glob("*.cl"):
            try:
                if f"__kernel void {entry}" in path.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                continue
    return False


@dataclass(frozen=True)
class DeviceInfo:
    """One physical device observed through exactly one backend.

    ``capabilities`` maps capability name -> measured value. Absent keys
    are unmeasured; present keys were probed on this device.
    """

    name: str
    vendor: str
    backend: str  # opencl | cuda | metal | rocm | mlx | asic | rtl | cpu
    type: str  # gpu | chronus | cpu | asic | rtl
    compute_units: Optional[int]
    global_mem_mb: Optional[int]
    capabilities: Tuple[Tuple[str, Any], ...] = ()

    def capability(self, key: str, default: Any = None) -> Any:
        return dict(self.capabilities).get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "name": self.name,
            "vendor": self.vendor,
            "backend": self.backend,
            "type": self.type,
        }
        if self.compute_units is not None:
            out["compute_units"] = self.compute_units
        if self.global_mem_mb is not None:
            out["global_mem_mb"] = self.global_mem_mb
        if self.capabilities:
            out["capabilities"] = dict(self.capabilities)
        return out


@dataclass
class ClusterInventory:
    """The measured device census plus per-tier probe errors."""

    devices: List[DeviceInfo] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
    detected_at: float = 0.0

    @classmethod
    def collect(cls) -> "ClusterInventory":
        """Walk every backend; nothing raises — failures land in errors."""
        inv = cls(detected_at=time.time())
        for tier, fn in (
            ("opencl", _probe_opencl),
            ("opencl_remote", _probe_remote_opencl),
            ("cuda", _probe_cuda),
            ("metal", _probe_metal),
            ("rocm", _probe_rocm),
            ("mlx", _probe_mlx),
            ("asic", _probe_asic),
            ("rtl", _probe_rtl),
            ("cpu", _probe_cpu),
        ):
            try:
                inv.devices.extend(fn())
            except Exception as exc:  # inventory must never crash callers
                inv.errors[tier] = f"{type(exc).__name__}: {exc}"
        return inv

    def by_backend(self, backend: str) -> List[DeviceInfo]:
        return [d for d in self.devices if d.backend == backend]

    def by_capability(self, key: str) -> List[DeviceInfo]:
        return [d for d in self.devices if d.capability(key) not in (None, False, 0)]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "devices": [d.as_dict() for d in self.devices],
            "errors": dict(self.errors),
            "detected_at": self.detected_at,
        }


# ---------------------------------------------------------------------------
# Probes — one per backend, each returning measured facts only.
# ---------------------------------------------------------------------------


def _opencl_type(cl: Any, device: Any) -> str:
    dtype = int(getattr(device, "type", 0) or 0)
    gpu_bit = int(getattr(cl.device_type, "GPU", 0) or 0)
    cpu_bit = int(getattr(cl.device_type, "CPU", 0) or 0)
    accel_bit = int(getattr(cl.device_type, "ACCELERATOR", 0) or 0)
    if dtype & gpu_bit:
        unified = False
        try:
            unified = bool(
                device.get_info(getattr(cl.device_info, "HOST_UNIFIED_MEMORY"))
            )
        except Exception:
            unified = False
        vendor = str(getattr(device, "vendor", "") or "").lower()
        if unified or vendor.startswith(("intel", "apple")):
            return "chronus"
        return "gpu"
    if dtype & cpu_bit:
        return "cpu"
    if dtype & accel_bit:
        return "asic"
    return "other"


def _probe_opencl() -> List[DeviceInfo]:
    import pyopencl as cl

    out: List[DeviceInfo] = []
    m32 = _kernel_source_has(_M32_KERNEL)
    ladder = _kernel_source_has(_LADDER_KERNEL)
    for plat in cl.get_platforms():
        for dev in plat.get_devices():
            caps: Dict[str, Any] = {}
            try:
                caps["fp64"] = "cl_khr_fp64" in str(getattr(dev, "extensions", "") or "")
            except Exception:
                pass
            try:
                caps["local_mem_kb"] = int(dev.local_mem_size) // 1024
            except Exception:
                pass
            try:
                caps["max_workgroup"] = int(dev.max_work_group_size)
            except Exception:
                pass
            try:
                caps["opencl2_svm"] = bool(
                    int(dev.get_info(cl.device_info.SVM_CAPABILITIES) or 0) & 0x3
                )
            except Exception:
                pass
            try:
                caps["host_unified_memory"] = bool(
                    dev.get_info(cl.device_info.HOST_UNIFIED_MEMORY)
                )
            except Exception:
                pass
            if m32:
                caps["m32_lane_kernel"] = True
            if ladder:
                caps["lucas_ladder_kernel"] = True
            try:
                cu = int(dev.max_compute_units)
            except Exception:
                cu = None
            try:
                mem_mb = int(dev.global_mem_size) // (1024 * 1024)
            except Exception:
                mem_mb = None
            out.append(
                DeviceInfo(
                    name=str(getattr(dev, "name", "") or "").strip(),
                    vendor=str(getattr(dev, "vendor", "") or "").strip(),
                    backend="opencl",
                    type=_opencl_type(cl, dev),
                    compute_units=cu,
                    global_mem_mb=mem_mb,
                    capabilities=tuple(sorted(caps.items())),
                )
            )
    return out


def _probe_cuda() -> List[DeviceInfo]:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return []
    proc = subprocess.run(
        [
            exe,
            "--query-gpu=name,compute_cap,memory.total",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if proc.returncode != 0:
        return []
    out: List[DeviceInfo] = []
    for line in proc.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        name, cc_raw, mem_raw = parts[0], parts[1], parts[2]
        caps: Dict[str, Any] = {"cuda": True}
        try:
            cc = float(cc_raw)
            caps["compute_capability"] = cc_raw
            if cc >= 7.0:
                caps["tensor_cores"] = True
            if cc >= 8.0:
                caps["tf32"] = True
            if cc >= 8.9:
                caps["fp8"] = True
        except ValueError:
            pass
        try:
            mem_mb = int(float(mem_raw))
        except ValueError:
            mem_mb = None
        out.append(
            DeviceInfo(
                name=name,
                vendor="NVIDIA",
                backend="cuda",
                type="gpu",
                compute_units=None,  # SM count not in the default query — omitted.
                global_mem_mb=mem_mb,
                capabilities=tuple(sorted(caps.items())),
            )
        )
    if not out:
        return []
    # NVLink: a live `nvidia-smi nvlink --status` report with non-empty rows.
    try:
        nv = subprocess.run(
            [exe, "nvlink", "--status"], capture_output=True, text=True, timeout=10
        )
        if nv.returncode == 0 and "Link" in (nv.stdout or ""):
            for d in range(len(out)):
                caps = dict(out[d].capabilities)
                caps["nvlink"] = True
                out[d] = DeviceInfo(
                    name=out[d].name,
                    vendor=out[d].vendor,
                    backend=out[d].backend,
                    type=out[d].type,
                    compute_units=out[d].compute_units,
                    global_mem_mb=out[d].global_mem_mb,
                    capabilities=tuple(sorted(caps.items())),
                )
    except Exception:
        pass
    # MIG partitions when the driver reports them.
    try:
        mig = subprocess.run(
            [exe, "--query-gpu=mig.mode.current", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if mig.returncode == 0 and "Enabled" in (mig.stdout or ""):
            for i, flag in enumerate(mig.stdout.strip().splitlines()):
                if i < len(out) and "Enabled" in flag:
                    caps = dict(out[i].capabilities)
                    caps["mig_partitions"] = True
                    out[i] = DeviceInfo(
                        name=out[i].name,
                        vendor=out[i].vendor,
                        backend=out[i].backend,
                        type=out[i].type,
                        compute_units=out[i].compute_units,
                        global_mem_mb=out[i].global_mem_mb,
                        capabilities=tuple(sorted(caps.items())),
                    )
    except Exception:
        pass
    return out


def _probe_metal() -> List[DeviceInfo]:
    if _platform.system() != "Darwin":
        return []
    try:
        from Intelligence.apple_features import AppleSiliconRuntime
    except Exception:
        return []
    runtime = AppleSiliconRuntime()
    metal = getattr(runtime, "metal", None)
    if metal is None or not getattr(metal, "available", False):
        return []
    info = getattr(metal, "info", None)
    name = str(getattr(info, "chip_name", "") or "Apple Silicon")
    caps: Dict[str, Any] = {"metal": True, "unified_memory": True}
    if getattr(runtime, "unified_memory", None) is not None:
        caps["shared_memory"] = True
    return [
        DeviceInfo(
            name=name,
            vendor="Apple",
            backend="metal",
            type="chronus",
            compute_units=int(getattr(info, "gpu_cores", 0)) or None,
            global_mem_mb=None,
            capabilities=tuple(sorted(caps.items())),
        )
    ]


def _probe_rocm() -> List[DeviceInfo]:
    exe = shutil.which("rocm-smi")
    if exe is None:
        return []
    proc = subprocess.run(
        [exe, "--showproductname", "--csv"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    out: List[DeviceInfo] = []
    for line in proc.stdout.strip().splitlines():
        if "Card series" in line or "GPU[" in line:
            name = line.split(",")[-1].strip() or "AMD GPU"
            out.append(
                DeviceInfo(
                    name=name,
                    vendor="AMD",
                    backend="rocm",
                    type="gpu",
                    compute_units=None,
                    global_mem_mb=None,
                    capabilities=(("rocm", True),),
                )
            )
    return out


def _probe_mlx() -> List[DeviceInfo]:
    try:
        import mlx.core as mx  # noqa: F401
    except Exception:
        return []
    if _platform.system() != "Darwin":
        return []
    caps: Dict[str, Any] = {"mlx": True, "unified_memory": True}
    return [
        DeviceInfo(
            name="Apple MLX device",
            vendor="Apple",
            backend="mlx",
            type="chronus",
            compute_units=None,
            global_mem_mb=None,
            capabilities=tuple(sorted(caps.items())),
        )
    ]


def _probe_asic() -> List[DeviceInfo]:
    """ASIC presence via MLA1517_MMIO_LIBRARY — loaded driver or nothing."""
    lib = os.environ.get("MLA1517_MMIO_LIBRARY", "").strip()
    if not lib:
        return []
    try:
        from chronus.mla1517.hardware import _load_library  # noqa: PLC0415
    except Exception:
        try:
            import sys

            plat = _REPO_ROOT / "chronus/mla1517_platform" / "python"
            if str(plat) not in sys.path:
                sys.path.append(str(plat))
            from chronus.mla1517.hardware import _load_library  # noqa: PLC0415
        except Exception as exc:
            raise RuntimeError(f"chronus.mla1517.hardware import failed: {exc}") from exc
    library = _load_library(lib)
    if not hasattr(library, "mla1517_open"):
        raise RuntimeError(f"{lib} loaded but exposes no mla1517_open")
    return [
        DeviceInfo(
            name=Path(lib).name,
            vendor="MLA1517",
            backend="asic",
            type="asic",
            compute_units=None,
            global_mem_mb=None,
            capabilities=(("mmio", True), ("sha256d_fixed", True)),
        )
    ]


def _probe_rtl() -> List[DeviceInfo]:
    """RTL design artifacts — truth_class 'design', never hardware."""
    out: List[DeviceInfo] = []
    for label, rel in (
        ("mla1517_rtl", "chronus/mla1517_platform/rtl"),
        ("legacy_rtl", "legacy/hardware/rtl"),
    ):
        d = _REPO_ROOT / rel
        if not d.is_dir():
            continue
        files = sorted(p.name for p in d.glob("*.sv*"))
        if not files:
            continue
        out.append(
            DeviceInfo(
                name=label,
                vendor="",
                backend="rtl",
                type="rtl",
                compute_units=None,
                global_mem_mb=None,
                capabilities=(
                    ("truth_class", "design"),
                    ("rtl_files", len(files)),
                ),
            )
        )
    return out


def _remote_opencl_endpoints() -> List[str]:
    raw = os.environ.get("HYBA_REMOTE_OPENCL_ENDPOINTS", "")
    out = [part.strip() for part in raw.split(",") if part.strip()]
    single = os.environ.get("MLA1517_REMOTE_GPU_ENDPOINT", "").strip()
    if single and single not in out:
        out.append(single)
    return out


def _probe_remote_opencl() -> List[DeviceInfo]:
    """Devices measured by remote GPU agents — a GPU anywhere counts.

    Endpoints come from ``HYBA_REMOTE_OPENCL_ENDPOINTS`` (comma list) or
    ``MLA1517_REMOTE_GPU_ENDPOINT``. Each agent is a real OpenCL host —
    a local box, another PC, or a cloud VM. Unreachable or deviceless
    endpoints degrade explicitly in ``errors``; they are never faked.
    """
    endpoints = _remote_opencl_endpoints()
    if not endpoints:
        return []
    try:
        from chronus.mla1517.remote_gpu import RemoteGPUClient
    except Exception:
        import sys

        plat = _REPO_ROOT / "chronus/mla1517_platform" / "python"
        if str(plat) not in sys.path:
            sys.path.append(str(plat))
        from chronus.mla1517.remote_gpu import RemoteGPUClient
    out: List[DeviceInfo] = []
    errors: List[str] = []
    for endpoint in endpoints:
        try:
            devices = RemoteGPUClient(endpoint).devices()
        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")
            continue
        for d in devices:
            caps = dict(d.capabilities)
            caps["remote_endpoint"] = endpoint
            out.append(
                DeviceInfo(
                    name=d.name,
                    vendor=d.vendor,
                    backend="opencl_remote",
                    type=d.device_type,
                    compute_units=d.compute_units,
                    global_mem_mb=d.global_mem_mb,
                    capabilities=tuple(sorted(caps.items())),
                )
            )
    if errors and not out:
        raise RuntimeError("; ".join(errors))
    return out


def _probe_cpu() -> List[DeviceInfo]:
    """The universal host CPU — always present, always honest."""
    caps: Dict[str, Any] = {
        "hashlib_sha256d": True,
        "exact_math": True,
        "numpy": False,
    }
    try:
        import numpy  # noqa: F401

        caps["numpy"] = True
    except Exception:
        pass
    return [
        DeviceInfo(
            name="CPU (hashlib)",
            vendor=_platform.processor() or "generic",
            backend="cpu",
            type="cpu",
            compute_units=os.cpu_count() or 1,
            global_mem_mb=None,
            capabilities=tuple(sorted(caps.items())),
        )
    ]


__all__ = ["ClusterInventory", "DeviceInfo"]
