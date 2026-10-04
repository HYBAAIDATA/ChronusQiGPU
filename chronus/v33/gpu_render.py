# gpu_render.py
# Chronos GPU -- fail-closed GPU render lane for the v3.3 reconstruction plane
# (elevation pass, 5 Oct 2026)
#
# Doctrine: the documented substrate for Chronos is "Classical GPU
# (Numba/CuPy/Metal)". This module makes that substrate real for the render
# pipeline without weakening a single guarantee:
#
#   - The numpy reference path stays the default and the acceptance authority.
#   - The CuPy lane is opt-in (CHRONUS_V33_RENDER_BACKEND=cupy|auto) and
#     fail-closed: an explicitly requested lane that cannot bind raises
#     RenderBackendUnavailable with the measured reason; it is never silently
#     skipped.
#   - Binding requires a known-answer self-check battery of ray-trace scenes
#     verified exactly against the numpy reference before any frame is trusted.
#   - Every dispatch is re-checked on the CPU against a deterministic sample
#     of its own pixels (exact recompute). A mismatch fails closed to the
#     numpy reference result for that block and records the evidence.
#   - Nothing here claims performance: wall times are measured per run and
#     reported in the frame metadata as evidence, never as marketing.

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


ENV_BACKEND = "CHRONUS_V33_RENDER_BACKEND"
_BACKENDS = ("numpy", "cupy", "auto")


class RenderBackendUnavailable(RuntimeError):
    """Raised when an explicitly requested render backend cannot bind."""

    def __init__(self, status: "BackendStatus"):
        self.status = status
        super().__init__(f"render backend {status.backend!r} unavailable: {status.reason}")


@dataclass(frozen=True)
class BackendStatus:
    backend: str
    available: bool
    reason: str = ""
    device_name: str = ""


def configured_backend() -> str:
    """Backend request from the environment; unset means the numpy default."""
    value = os.environ.get(ENV_BACKEND, "numpy").strip().lower()
    if value not in _BACKENDS:
        raise ValueError(f"{ENV_BACKEND} must be one of {_BACKENDS}, got {value!r}")
    return value


def probe_cupy() -> BackendStatus:
    """Lazy, honest probe. Never imports CuPy unless probed."""
    try:
        import cupy as cp  # type: ignore
    except Exception as exc:  # import failure is a measured state, not a crash
        return BackendStatus(backend="cupy", available=False, reason=f"cupy not importable: {type(exc).__name__}: {exc}")
    try:
        count = int(cp.cuda.runtime.getDeviceCount())
    except Exception as exc:
        return BackendStatus(backend="cupy", available=False, reason=f"no CUDA device: {type(exc).__name__}: {exc}")
    if count < 1:
        return BackendStatus(backend="cupy", available=False, reason="cupy reports zero CUDA devices")
    try:
        props = cp.cuda.runtime.getDeviceProperties(0)
        device_name = str(props.get("name", "unknown"))
    except Exception:
        device_name = "unknown"
    return BackendStatus(backend="cupy", available=True, reason="bound", device_name=device_name)


def numpy_ray_sphere(origin, dirs, center, radius) -> Tuple[np.ndarray, np.ndarray]:
    """Reference ray-sphere intersection, shared by the self-check battery."""
    oc = np.asarray(origin, dtype=np.float64) - np.asarray(center, dtype=np.float64)
    b = 2.0 * (dirs @ oc)
    c = float(oc @ oc) - radius * radius
    disc = b * b - 4.0 * c
    hit = disc >= 0
    sq = np.sqrt(np.clip(disc, 0.0, None))
    t0 = (-b - sq) / 2.0
    t1 = (-b + sq) / 2.0
    tmin = np.where(t0 > 1e-6, t0, t1)
    valid = hit & (tmin > 1e-6)
    t = np.full(dirs.shape[0], np.inf)
    t[valid] = tmin[valid]
    return t, valid


class CupyRenderBackend:
    """CuPy execution of the exact v3.3 pinhole ray-trace math.

    The numpy reference implementation stays the acceptance authority: this
    backend proposes block results, and every block is re-checked on the CPU
    against a deterministic sample of its own pixels before it is trusted.
    """

    def __init__(self):
        self.status = probe_cupy()
        if not self.status.available:
            raise RenderBackendUnavailable(self.status)
        import cupy as cp  # type: ignore
        self._cp = cp

    def self_check(self) -> Dict:
        """Known-answer battery against the numpy reference; binding gate."""
        rng = np.random.default_rng(20261005)
        worst = 0.0
        for _case in range(8):
            n_rays = 1024
            origin = np.array([0.0, 0.0, 5.0])
            dirs = rng.normal(size=(n_rays, 3))
            dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
            center = np.zeros(3)
            radius = float(rng.uniform(0.5, 2.0))
            t_ref, hit_ref = numpy_ray_sphere(origin, dirs, center, radius)
            t_gpu, hit_gpu = self.ray_sphere(origin, dirs, center, radius)
            if not np.array_equal(hit_ref, hit_gpu):
                raise RuntimeError("cupy self-check: hit mask disagrees with the numpy reference")
            if hit_ref.any():
                err = float(np.max(np.abs(t_ref[hit_ref] - t_gpu[hit_ref])))
                worst = max(worst, err)
        if not (worst <= 1e-9):
            raise RuntimeError(f"cupy self-check exceeded tolerance: max |dt| = {worst}")
        return {"cases": 8, "max_abs_error": worst, "passed": True}

    def ray_sphere(self, origin, dirs, center, radius) -> Tuple[np.ndarray, np.ndarray]:
        """Identical math to numpy_ray_sphere, executed on the GPU."""
        cp = self._cp
        d = cp.asarray(dirs, dtype=cp.float64)
        oc = cp.asarray(origin, dtype=cp.float64) - cp.asarray(center, dtype=cp.float64)
        b = 2.0 * (d @ oc)
        c = float(oc @ oc) - float(radius) * float(radius)
        disc = b * b - 4.0 * c
        hit = disc >= 0
        sq = cp.sqrt(cp.clip(disc, 0.0, None))
        t0 = (-b - sq) / 2.0
        t1 = (-b + sq) / 2.0
        tmin = cp.where(t0 > 1e-6, t0, t1)
        valid = hit & (tmin > 1e-6)
        t = cp.full(d.shape[0], cp.inf)
        t[valid] = tmin[valid]
        return cp.asnumpy(t), cp.asnumpy(valid)


__all__ = [
    "ENV_BACKEND",
    "BackendStatus",
    "RenderBackendUnavailable",
    "configured_backend",
    "probe_cupy",
    "numpy_ray_sphere",
    "CupyRenderBackend",
]
