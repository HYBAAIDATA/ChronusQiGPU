"""Chronus native runtime helpers.

This module owns the memory-allocation and measurement boundary for Chronus.
Chronus reports where state lives and
what execution actually measured.

``allocate_host_mapped`` returns ordinary host RAM and never labels it as
device memory. ``allocate_device`` returns a real OpenCL buffer/SVM allocation
when possible and an explicitly labelled fallback/unavailable result otherwise.
``profile`` measures real calls with a monotonic clock and emits no fabricated
rate when the interval cannot be resolved.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

LOG = logging.getLogger(__name__)

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
    """Wall time of a real call plus derivable metrics only."""

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
    """Allocate ``nbytes`` of host memory as a flat NumPy array."""
    nbytes = _validate_nbytes(nbytes)
    itemsize = np.dtype(dtype).itemsize
    if itemsize > 1 and nbytes % itemsize:
        raise ValueError(
            f"nbytes={nbytes} is not a multiple of itemsize={itemsize} "
            f"for dtype {np.dtype(dtype)}"
        )
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
    """Allocate device-backed memory and report the mechanism that succeeded."""
    nbytes = _validate_nbytes(nbytes)
    if mode not in (KIND_BUFFER, KIND_SVM):
        raise ValueError(
            f"mode must be {KIND_BUFFER!r} or {KIND_SVM!r}, got {mode!r}"
        )
    if nbytes == 0:
        return DeviceAllocation(KIND_EMPTY, 0, reason="zero-byte request")

    cl = cl_module
    if cl is None:
        try:
            import pyopencl as cl  # type: ignore[no-redef]
        except Exception as exc:
            reason = f"pyopencl unavailable: {type(exc).__name__}: {exc}"
            LOG.debug("device allocation unavailable: %s", reason)
            return DeviceAllocation(
                KIND_UNAVAILABLE,
                nbytes,
                allocate_host_mapped(nbytes),
                reason=reason,
            )
    if context is None:
        reason = "no OpenCL context bound; host memory is not device memory"
        return DeviceAllocation(
            KIND_HOST_FALLBACK,
            nbytes,
            allocate_host_mapped(nbytes),
            reason=reason,
        )

    if mode == KIND_SVM and hasattr(cl, "SVMAllocation"):
        try:
            svm = cl.SVMAllocation(context, nbytes, cl.SVM_MEM_READ_WRITE)
            return DeviceAllocation(KIND_SVM, nbytes, svm=svm)
        except Exception as exc:
            LOG.debug(
                "SVM allocation failed, falling back to cl.Buffer: %s: %s",
                type(exc).__name__,
                exc,
            )

    try:
        buffer = cl.Buffer(context, cl.mem_flags.READ_WRITE, nbytes)
    except Exception as exc:
        reason = f"cl.Buffer allocation failed: {type(exc).__name__}: {exc}"
        return DeviceAllocation(
            KIND_HOST_FALLBACK,
            nbytes,
            allocate_host_mapped(nbytes),
            reason=reason,
        )
    return DeviceAllocation(KIND_BUFFER, nbytes, buffer=buffer)


def profile(
    fn: Callable[..., Any],
    *args: Any,
    iterations: int = 1,
    work_units: int = 0,
    **kwargs: Any,
) -> ProfileResult:
    """Execute ``fn`` and measure it for real."""
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
    wall = time.perf_counter() - started
    per_iteration = wall / iterations
    throughput = iterations / wall if wall > 0.0 else None
    units_per_second = work_units / wall if wall > 0.0 and work_units > 0 else None
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
