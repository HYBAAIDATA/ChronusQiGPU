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
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

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


# HYBA iGPU identity. Duplicated from scripts/igpu_diag.py on purpose — this
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
    """One probe result. ``present`` is honest: absent stays absent."""

    backend: BackendType
    present: bool
    detail: str
    device_info: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend.value,
            "present": self.present,
            "detail": self.detail,
            "device_info": self.device_info,
        }


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
        return {"present": False, "detail": f"pyopencl unavailable ({exc})", "device_info": ""}
    try:
        devices = [d for p in cl.get_platforms() for d in p.get_devices()]
    except Exception as exc:
        return {"present": False, "detail": f"OpenCL enumeration failed: {exc}", "device_info": ""}
    if not devices:
        return {"present": False, "detail": "no OpenCL devices", "device_info": ""}
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
    }


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


_binder: Optional[BackendBinder] = None
_bound: Optional[BoundBackend] = None


def get_compute_backend(binder: Optional[BackendBinder] = None) -> BoundBackend:
    """Bind (once) and return the compute backend."""
    global _binder, _bound
    if _bound is None:
        _binder = binder or _binder or BackendBinder()
        _bound = _binder.bind()
    return _bound


def reset_compute_backend() -> None:
    """Clear the cached binding (next call re-detects and re-binds)."""
    global _binder, _bound
    _binder = None
    _bound = None


__all__ = [
    "BackendBinder",
    "BackendDetector",
    "BackendType",
    "BoundBackend",
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

    from .lucas.pool import get as _lucas_get

    result = _lucas_get("gap_kernel")(np.array([[1.0, 0.0], [0.0, -1.0]]), n)
    result["module"] = __name__
    return result
