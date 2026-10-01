"""Compute-backend binding for the Intelligence substrate (iGPU-first).

Implements the iGPU-first acceptance gates: detection across MLX, Metal,
CUDA, ROCm, Vulkan, OpenCL and CPU; an explicit binding step; and
**fail-explicit** semantics — when ``HYBA_REQUIRE_GPU`` (or
``KELLOGG_REQUIRE_GPU``) is set and no GPU backend is bound, operations
refuse with ``GPUUnavailableError`` instead of silently degrading to CPU.

Environment policy:

- ``HYBA_BACKEND`` / ``KELLOGG_BACKEND`` — force a backend by name
  (``auto`` selects the highest-preference present backend). Forcing a
  backend that detection cannot see fails explicitly; it never silently
  falls back.
- ``HYBA_REQUIRE_GPU`` / ``KELLOGG_REQUIRE_GPU`` — refuse a CPU binding.
- Unset everything: ``auto`` with an implicit CPU fallback, and the
  binding reports exactly which backend was chosen and why.

Per AGENTS.md, the substrate is an algebraic choice, not a physical one:
a CPU binding is an *explicit CPU binding*, always available, never an
excuse to fake a GPU claim.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: gap

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

THEOREM_PROVEN = False


class BackendType(Enum):
    """Compute backend families, in detection-probe order."""

    METAL = "metal"
    CUDA = "cuda"
    ROCM = "rocm"
    MLX = "mlx"
    VULKAN = "vulkan"
    OPENCL = "opencl"
    CPU = "cpu"


# HYBA iGPU identity. Duplicated from scripts/chronus_diag.py on purpose — this
# module implements its own substrate route (see LUCAS WIRING header).
# Overridable via HYBA_DEVICE_ALIAS (comma-separated).
DEFAULT_HYBA_ALIASES = ("hyba-mla1517", "hyba_mla1517", "mla1517", "hyba")


def _hyba_aliases() -> tuple:
    raw = os.environ.get("HYBA_DEVICE_ALIAS", "").strip()
    if raw:
        return tuple(a.strip().lower() for a in raw.split(",") if a.strip())
    return DEFAULT_HYBA_ALIASES


# Every backend that is not the host CPU.
GPU_BACKENDS = frozenset(
    {
        BackendType.METAL,
        BackendType.CUDA,
        BackendType.ROCM,
        BackendType.MLX,
        BackendType.VULKAN,
        BackendType.OPENCL,
    }
)

# auto-mode preference: exact-math iGPU stacks first; among cross-platform
# runtimes the binding must match the dispatch path the code actually
# implements (OpenCL kernels), so OpenCL outranks a merely-enumerable Vulkan
# device; CPU last.
PREFERENCE_ORDER: List[BackendType] = [
    BackendType.MLX,
    BackendType.METAL,
    BackendType.CUDA,
    BackendType.ROCM,
    BackendType.OPENCL,
    BackendType.VULKAN,
    BackendType.CPU,
]


class GPUUnavailableError(RuntimeError):
    """Fail-explicit refusal: the requested GPU backend is not available."""


@dataclass
class DetectedBackend:
    """One probe result. ``present`` is honest: absent stays absent.

    ``devices`` carries one record per enumerated device for backends that
    can see more than one (OpenCL); a single-device or absent backend leaves
    it empty rather than inventing topology.
    """

    backend: BackendType
    present: bool
    detail: str
    device_info: str = ""
    devices: Tuple[Dict[str, Any], ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        out = {
            "backend": self.backend.value,
            "present": self.present,
            "detail": self.detail,
            "device_info": self.device_info,
        }
        if self.devices:
            out["devices"] = [dict(d) for d in self.devices]
        return out


@dataclass
class BoundBackend:
    """The result of binding: one backend, bound explicitly."""

    backend: BackendType
    gpu_bound: bool
    detail: str
    device_info: str = ""
    dispatch_count: int = 0

    @property
    def healthy(self) -> bool:
        return True

    def record_dispatch(self, name: str = "") -> int:
        self.dispatch_count += 1
        return self.dispatch_count

    def as_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend.value,
            "gpu_bound": self.gpu_bound,
            "detail": self.detail,
            "device_info": self.device_info,
            "dispatch_count": self.dispatch_count,
            "healthy": self.healthy,
            "fail_explicit": True,
        }


@dataclass
class BoundBackends:
    """Composition record from :meth:`BackendBinder.bind_all`.

    ``primary`` is the backend :meth:`BackendBinder.bind` would select;
    ``members`` holds one :class:`BoundBackend` per present backend in
    ``PREFERENCE_ORDER`` — the composite substrate binds all of them at
    once. ``init_records`` logs each attempted bind as ``{tier, ok,
    reason}`` so a failed member is reported, never swallowed.
    """

    primary: BoundBackend
    members: Tuple[BoundBackend, ...]
    init_records: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "primary": self.primary.as_dict(),
            "members": [m.as_dict() for m in self.members],
            "init_records": [dict(r) for r in self.init_records],
        }


class BackendDetector:
    """Read-only probe of the machine's compute backends."""

    def detect(self) -> List[DetectedBackend]:
        results: List[DetectedBackend] = []
        darwin = platform.system() == "Darwin"
        results.append(
            DetectedBackend(
                BackendType.METAL,
                present=darwin,
                detail=platform.system() if darwin else "Metal requires Darwin",
                device_info=platform.machine() if darwin else "",
            )
        )
        if _module_importable("mlx"):
            results.append(DetectedBackend(BackendType.MLX, True, "mlx available"))
        else:
            results.append(DetectedBackend(BackendType.MLX, False, "mlx not installed"))
        nvidia_smi = shutil.which("nvidia-smi")
        results.append(
            DetectedBackend(
                BackendType.CUDA,
                present=nvidia_smi is not None,
                detail=nvidia_smi or "no nvidia-smi",
            )
        )
        rocm_smi = shutil.which("rocm-smi")
        results.append(
            DetectedBackend(
                BackendType.ROCM,
                present=rocm_smi is not None,
                detail=rocm_smi or "no rocm-smi",
            )
        )
        vulkan_probe = _probe_vulkan()
        results.append(
            DetectedBackend(
                BackendType.VULKAN,
                present=vulkan_probe["present"],
                detail=vulkan_probe["detail"],
            )
        )
        opencl_probe = _probe_opencl()
        results.append(
            DetectedBackend(
                BackendType.OPENCL,
                present=opencl_probe["present"],
                detail=opencl_probe["detail"],
                device_info=opencl_probe["device_info"],
                devices=tuple(opencl_probe.get("devices", ()) or ()),
            )
        )
        results.append(
            DetectedBackend(BackendType.CPU, True, "explicit CPU binding", platform.processor())
        )
        return results


def _module_importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _env_truthy(var: str) -> bool:
    return os.environ.get(var, "").strip().lower() in ("1", "true", "yes", "on")


def _probe_vulkan() -> Dict[str, Any]:
    """vulkaninfo must actually enumerate a physical device to count."""
    exe = shutil.which("vulkaninfo")
    if exe is None:
        return {"present": False, "detail": "no vulkaninfo"}
    try:
        proc = subprocess.run(
            [exe, "--summary"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"present": False, "detail": f"vulkaninfo failed: {exc}"}
    if proc.returncode != 0:
        return {"present": False, "detail": f"vulkaninfo exit {proc.returncode}"}
    output = proc.stdout or ""
    has_gpu = "GPU0" in output and "deviceName" in output
    return {
        "present": has_gpu,
        "detail": exe if has_gpu else f"no Vulkan devices enumerated ({exe})",
    }


def _probe_opencl() -> Dict[str, Any]:
    """OpenCL counts only when pyopencl imports AND a device enumerates."""
    try:
        import pyopencl as cl
    except Exception as exc:
        return {
            "present": False,
            "detail": f"pyopencl unavailable ({exc})",
            "device_info": "",
            "devices": [],
        }
    try:
        devices = [d for p in cl.get_platforms() for d in p.get_devices()]
    except Exception as exc:
        return {
            "present": False,
            "detail": f"OpenCL enumeration failed: {exc}",
            "device_info": "",
            "devices": [],
        }
    if not devices:
        return {
            "present": False,
            "detail": "no OpenCL devices",
            "device_info": "",
            "devices": [],
        }
    aliases = _hyba_aliases()
    gpu = next(
        (
            d
            for d in devices
            if any(a and a in str(getattr(d, "name", "")).lower() for a in aliases)
        ),
        next((d for d in devices if d.type & cl.device_type.GPU), devices[0]),
    )
    name_lower = str(getattr(gpu, "name", "")).lower()
    hyba_bound = any(a and a in name_lower for a in aliases)
    return {
        "present": True,
        "detail": f"{len(devices)} device(s)"
        + ("; HYBA iGPU bound" if hyba_bound else "; no HYBA-alias device"),
        "device_info": f"{gpu.name.strip()} ({int(gpu.max_compute_units)} CUs)",
        "hyba_alias_found": hyba_bound,
        "devices": [_opencl_device_record(cl, d, aliases) for d in devices],
    }


def _opencl_device_record(cl, device, aliases: tuple) -> Dict[str, Any]:
    """Measured facts for one enumerated OpenCL device.

    Every value is read off the device object; a probe failure on one
    attribute leaves the key out rather than guessing it.
    """

    def _attr(name: str, default=None):
        try:
            return getattr(device, name)
        except Exception:
            return default

    record: Dict[str, Any] = {}
    name = str(_attr("name", "")).strip()
    vendor = str(_attr("vendor", "")).strip()
    record["name"] = name
    record["vendor"] = vendor
    if name:
        name_lower = name.lower()
        record["hyba_alias"] = next((a for a in aliases if a and a in name_lower), None)
    dtype = _attr("type")
    try:
        if dtype & cl.device_type.GPU:
            record["type"] = "gpu"
        elif dtype & cl.device_type.CPU:
            record["type"] = "cpu"
        elif dtype & cl.device_type.ACCELERATOR:
            record["type"] = "accelerator"
        else:
            record["type"] = "other"
    except Exception:
        pass
    for key, attr in (
        ("compute_units", "max_compute_units"),
        ("max_work_group_size", "max_work_group_size"),
        ("local_mem_kb", "local_mem_size"),
        ("global_mem_mb", "global_mem_size"),
        ("max_mem_alloc_mb", "max_mem_alloc_size"),
        ("max_work_item_dims", "max_work_item_dimensions"),
        ("address_bits", "address_bits"),
    ):
        value = _attr(attr)
        if value is None:
            continue
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if key in ("local_mem_kb",):
            value //= 1024
        elif key in ("global_mem_mb", "max_mem_alloc_mb"):
            value //= 1024 * 1024
        record[key] = value
    try:
        record["platform"] = str(device.platform.name).strip()
    except Exception:
        pass
    extensions = _attr("extensions", "") or ""
    if extensions:
        record["fp64"] = "cl_khr_fp64" in extensions.split() or "cl_khr_fp64" in extensions
    svm = _attr("svm_capabilities")
    if svm is not None:
        try:
            record["opencl2_svm"] = bool(int(svm) & 0x3)  # coarse+fine grain
        except (TypeError, ValueError):
            pass
    uma = _attr("host_unified_memory")
    if uma is not None:
        try:
            record["host_unified_memory"] = bool(uma)
        except (TypeError, ValueError):
            pass
    return record


class BackendBinder:
    """Binds one backend under the environment policy. Never fakes a GPU."""

    def __init__(
        self,
        detector: Optional[BackendDetector] = None,
        requested: Optional[str] = None,
        require_gpu: Optional[bool] = None,
    ) -> None:
        self.detector = detector or BackendDetector()
        if requested is None:
            requested = (
                os.environ.get("HYBA_BACKEND") or os.environ.get("KELLOGG_BACKEND") or "auto"
            )
        self.requested = (requested or "auto").strip().lower()
        if require_gpu is None:
            require_gpu = _env_truthy("HYBA_REQUIRE_GPU") or _env_truthy("KELLOGG_REQUIRE_GPU")
        self.require_gpu = bool(require_gpu)

    def bind(self) -> BoundBackend:
        detected = {d.backend: d for d in self.detector.detect()}
        if self.requested in ("auto", "", "none"):
            for candidate in PREFERENCE_ORDER:
                if detected[candidate].present:
                    return self._bound(candidate, detected)
            return self._bound(BackendType.CPU, detected)
        matches = [b for b in BackendType if b.value == self.requested]
        if not matches:
            raise ValueError(f"backend_mismatch: unknown backend '{self.requested}'")
        target = matches[0]
        if not detected[target].present:
            raise GPUUnavailableError(
                f"fail_explicit: requested backend '{target.value}' is not "
                f"available ({detected[target].detail}) — no silent fallback"
            )
        return self._bound(target, detected)

    def _bound(
        self, backend: BackendType, detected: Dict[BackendType, DetectedBackend]
    ) -> BoundBackend:
        if self.require_gpu and backend is BackendType.CPU:
            raise GPUUnavailableError("no GPU bound — HYBA_REQUIRE_GPU is set")
        info = detected[backend]
        return BoundBackend(
            backend=backend,
            gpu_bound=backend in GPU_BACKENDS,
            detail=info.detail,
            device_info=info.device_info,
        )

    def bind_all(self) -> BoundBackends:
        """Bind every present backend at once — the ChronusFabric composite.

        Unlike :meth:`bind`, an explicit ``HYBA_BACKEND``/``KELLOGG_BACKEND``
        request does not hide the other detected backends: ``primary`` honors
        the same selection policy, but ``members`` still lists everything the
        probe could see. Each member records its own ``{tier, ok, reason}``
        init record so a partial composition is reported, never silent.
        """
        detected = {d.backend: d for d in self.detector.detect()}
        members: List[BoundBackend] = []
        init_records: List[Dict[str, Any]] = []
        for tier in PREFERENCE_ORDER:
            info = detected[tier]
            record: Dict[str, Any] = {"tier": tier.value}
            if info.present:
                if self.require_gpu and tier is BackendType.CPU:
                    record["ok"] = False
                    record["reason"] = "require_gpu refuses CPU"
                else:
                    members.append(
                        BoundBackend(
                            backend=tier,
                            gpu_bound=tier in GPU_BACKENDS,
                            detail=info.detail,
                            device_info=info.device_info,
                        )
                    )
                    record["ok"] = True
                    record["reason"] = "present"
            else:
                record["ok"] = False
                record["reason"] = info.detail
            init_records.append(record)
        if not members:
            raise GPUUnavailableError(
                "fail_explicit: no backend is present to compose — "
                "detection saw nothing (this should be impossible: CPU is "
                "always a member unless require_gpu refused it)"
            )
        if self.requested in ("auto", "", "none"):
            primary = members[0]
        else:
            matches = [b for b in BackendType if b.value == self.requested]
            if not matches:
                raise ValueError(f"backend_mismatch: unknown backend '{self.requested}'")
            target = matches[0]
            if not detected[target].present:
                raise GPUUnavailableError(
                    f"fail_explicit: requested backend '{target.value}' is not "
                    f"available ({detected[target].detail}) — no silent fallback"
                )
            if self.require_gpu and target is BackendType.CPU:
                raise GPUUnavailableError(
                    "no GPU bound — HYBA_REQUIRE_GPU is set"
                )
            primary = next(m for m in members if m.backend is target)
        return BoundBackends(
            primary=primary,
            members=tuple(members),
            init_records=tuple(init_records),
        )


_binder: Optional[BackendBinder] = None
_bound: Optional[BoundBackend] = None
_binding_lock = threading.Lock()


def get_compute_backend(binder: Optional[BackendBinder] = None) -> BoundBackend:
    """Bind (once) and return the compute backend."""
    global _binder, _bound
    with _binding_lock:
        if _bound is None:
            _binder = binder or _binder or BackendBinder()
            _bound = _binder.bind()
        return _bound


def reset_compute_backend() -> None:
    """Clear the cached binding (next call re-detects and re-binds)."""
    global _binder, _bound
    with _binding_lock:
        _binder = None
        _bound = None


__all__ = [
    "BackendBinder",
    "BackendDetector",
    "BackendType",
    "BoundBackend",
    "BoundBackends",
    "GPU_BACKENDS",
    "GPUUnavailableError",
    "PREFERENCE_ORDER",
    "THEOREM_PROVEN",
    "get_compute_backend",
    "reset_compute_backend",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("gap_kernel")(np.array([[1.0, 0.0], [0.0, -1.0]]), n)
    result["module"] = __name__
    return result
