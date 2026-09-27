"""Native kernel runtime helpers for the iGPU substrate.

Memory honesty
--------------
This module distinguishes two things that are easy to conflate:

``allocate_host_mapped``
    Returns ordinary host RAM in a numpy array. It is *not* device memory,
    and no caller is told otherwise. The function is named for what it
    actually returns; a previous ``allocate_zero_copy`` name implied a
    device mapping that never existed.

``allocate_device``
    Returns genuinely device-backed memory and reports which mechanism
    succeeded in :attr:`DeviceAllocation.kind` -- ``"buffer"`` for a
    ``cl.Buffer``, ``"svm"`` for ``cl.SVMAllocation``, ``"unavailable"``
    when neither could be created. When the device is unreachable the
    allocation degrades to host memory *and says so* rather than returning
    host memory under a device-sounding name.

Measurement honesty
-------------------
:func:`profile` executes the callable it is given. It captures a monotonic
timestamp before the call and one after, and reports the elapsed wall time
together with the callable's own return value. When the clock resolution is
too coarse to resolve a single call it reports ``None`` for the derived
rate instead of a fabricated one.

Canonical home: ``igpu.runtime`` (the consolidated iGPU package). The
pre-consolidation path ``legacy/hyba/native_kernels/igpu_runtime.py``
re-exports this module.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

LOG = logging.getLogger(__name__)

#: Allocation kinds reported by :func:`allocate_device`.
KIND_BUFFER = "buffer"
KIND_SVM = "svm"
KIND_HOST_FALLBACK = "host_fallback"
KIND_UNAVAILABLE = "unavailable"
KIND_EMPTY = "empty"


@dataclass(frozen=True)
class DeviceAllocation:
    """One allocation plus an honest statement of where the bytes live."""

    kind: str
    nbytes: int
    host: Optional[np.ndarray] = None
    buffer: Any = None
    svm: Any = None
    reason: str = ""

    @property
    def is_device_backed(self) -> bool:
        """True only when the bytes are addressable by the device."""
        return self.kind in (KIND_BUFFER, KIND_SVM)

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "nbytes": self.nbytes,
            "is_device_backed": self.is_device_backed,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ProfileResult:
    """Wall time of a real call plus whatever metrics are actually derivable."""

    wall_seconds: float
    result: Any
    iterations: int
    per_iteration_seconds: float
    throughput_per_second: Optional[float]
    work_units: int = 0
    units_per_second: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "wall_seconds": self.wall_seconds,
            "iterations": self.iterations,
            "per_iteration_seconds": self.per_iteration_seconds,
            "throughput_per_second": self.throughput_per_second,
            "work_units": self.work_units,
            "units_per_second": self.units_per_second,
        }


def allocate_host_mapped(
    nbytes: int,
    *,
    dtype: Any = np.uint8,
    zero: bool = True,
) -> np.ndarray:
    """Allocate ``nbytes`` of **host** memory as a flat numpy array.

    Named for the memory it actually returns. The array is pageable host
    RAM: passing it to a kernel requires an explicit copy (or
    ``cl.Buffer(..., hostif=...)``), and no device access to the returned
    address is implied by this function.
    """
    nbytes = _validate_nbytes(nbytes)
    itemsize = np.dtype(dtype).itemsize
    if itemsize > 1 and nbytes % itemsize:
        raise ValueError(f"nbytes={nbytes} is not a multiple of itemsize={itemsize} for dtype {np.dtype(dtype)}")
    flat = np.empty(nbytes, dtype=np.uint8)
    if zero:
        flat.fill(0)
    return flat.view(dtype) if itemsize > 1 else flat


def _validate_nbytes(nbytes: int) -> int:
    if isinstance(nbytes, bool) or not isinstance(nbytes, (int, np.integer)):
        raise TypeError(f"nbytes must be an integer, got {type(nbytes).__name__}")
    nbytes = int(nbytes)
    if nbytes < 0:
        raise ValueError(f"nbytes must be >= 0, got {nbytes}")
    return nbytes


def allocate_device(
    nbytes: int,
    *,
    cl_module: Any = None,
    context: Any = None,
    mode: str = KIND_BUFFER,
) -> DeviceAllocation:
    """Allocate device-backed memory, reporting the mechanism that succeeded.

    ``mode="buffer"`` allocates a real ``cl.Buffer``; ``mode="svm"`` tries
    ``cl.SVMAllocation`` first and falls back to a buffer. If neither is
    possible the result is host memory with ``kind="host_fallback"`` and a
    populated ``reason``, so a caller can never mistake host RAM for VRAM.
    """
    nbytes = _validate_nbytes(nbytes)
    if mode not in (KIND_BUFFER, KIND_SVM):
        raise ValueError(f"mode must be {KIND_BUFFER!r} or {KIND_SVM!r}, got {mode!r}")
    if nbytes == 0:
        return DeviceAllocation(KIND_EMPTY, 0, reason="zero-byte request")

    cl = cl_module
    if cl is None:
        try:
            import pyopencl as cl  # type: ignore[no-redef]
        except Exception as exc:
            reason = f"pyopencl unavailable: {type(exc).__name__}: {exc}"
            LOG.debug("device allocation degraded to host: %s", reason)
            return DeviceAllocation(
                KIND_UNAVAILABLE, nbytes, allocate_host_mapped(nbytes), reason=reason
            )
    if context is None:
        reason = "no OpenCL context bound; refusing to pretend host RAM is device memory"
        LOG.debug("device allocation degraded to host: %s", reason)
        return DeviceAllocation(KIND_HOST_FALLBACK, nbytes, allocate_host_mapped(nbytes), reason=reason)

    if mode == KIND_SVM and hasattr(cl, "SVMAllocation"):
        try:
            svm = cl.SVMAllocation(context, nbytes, cl.SVM_MEM_READ_WRITE)
            return DeviceAllocation(KIND_SVM, nbytes, buffer=None, svm=svm)
        except Exception as exc:
            LOG.debug("SVM allocation failed, falling back to cl.Buffer: %s: %s", type(exc).__name__, exc)

    try:
        buffer = cl.Buffer(context, cl.mem_flags.READ_WRITE, nbytes)
    except Exception as exc:
        reason = f"cl.Buffer allocation failed: {type(exc).__name__}: {exc}"
        LOG.debug("device allocation degraded to host: %s", reason)
        return DeviceAllocation(
            KIND_HOST_FALLBACK, nbytes, allocate_host_mapped(nbytes), reason=reason
        )
    return DeviceAllocation(KIND_BUFFER, nbytes, buffer=buffer)


def profile(
    fn: Callable[..., Any],
    *args: Any,
    iterations: int = 1,
    work_units: int = 0,
    **kwargs: Any,
) -> ProfileResult:
    """Call ``fn`` and time the call for real.

    The callable is invoked ``iterations`` times between two
    :func:`time.perf_counter` reads, and the last return value is preserved.
    Derived rates are ``None`` rather than ``0`` or ``inf`` when the measured
    wall time is non-positive, because a rate cannot be honestly reported
    from a zero-length interval.

    Exceptions from ``fn`` propagate unchanged: a failing call is not
    converted into a successful-looking profile with a large duration.
    """
    if not callable(fn):
        raise TypeError(f"fn must be callable, got {type(fn).__name__}")
    if isinstance(iterations, bool) or not isinstance(iterations, int):
        raise TypeError(f"iterations must be an int, got {type(iterations).__name__}")
    if iterations < 1:
        raise ValueError(f"iterations must be >= 1, got {iterations}")
    if work_units < 0:
        raise ValueError(f"work_units must be >= 0, got {work_units}")

    started = time.perf_counter()
    result = None
    for _ in range(iterations):
        result = fn(*args, **kwargs)
    finished = time.perf_counter()

    wall = finished - started
    per_iteration = wall / iterations
    throughput = (iterations / wall) if wall > 0.0 else None
    units_per_second = (work_units / wall) if (wall > 0.0 and work_units > 0) else None
    return ProfileResult(
        wall_seconds=wall,
        result=result,
        iterations=iterations,
        per_iteration_seconds=per_iteration,
        throughput_per_second=throughput,
        work_units=work_units,
        units_per_second=units_per_second,
    )


__all__ = [
    "KIND_BUFFER",
    "KIND_EMPTY",
    "KIND_HOST_FALLBACK",
    "KIND_SVM",
    "KIND_UNAVAILABLE",
    "DeviceAllocation",
    "ProfileResult",
    "allocate_device",
    "allocate_host_mapped",
    "profile",
]
