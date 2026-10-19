"""Chronus resident OpenCL execution engine.

One process-wide context, queue, and program cache
-------------------------------------------------
:class:`ChronusOpenCLEngine` owns exactly one OpenCL context per process. The
mathematical kernels in this module and the SHA-256d scanner both bind to this
engine, so device selection, program build, and residency are decided once.

Chronus is the iGPU offering; TURING remains an independent VQC authority. Device
selection prefers a HYBA alias device, then evidence-based integrated GPUs,
then the best measured GPU/device. The selected backend and reason are retained
and surfaced rather than inferred later.

Resident buffers are per instance. Shape is never used as a pool key, so two
resident objects of identical dimensions never alias a device buffer.
"""

from __future__ import annotations

import itertools
import logging
import threading
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

LOG = logging.getLogger(__name__)

DEFAULT_LOCAL_SIZE = 64
MAX_LOCAL_SIZE = 1024

_RESIDENT_IDS = itertools.count(1)


class ChronusOpenCLUnavailable(RuntimeError):
    """No usable OpenCL device or runtime is available to Chronus."""


class LocalSizeError(ValueError):
    """The requested local work size is invalid for the kernel."""


def is_power_of_two(value: Any) -> bool:
    """True when ``value`` is a positive power of two."""
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        return False
    number = int(value)
    return number > 0 and (number & (number - 1)) == 0


def validate_local_size(
    local_size: Any,
    *,
    kernel: str,
    max_size: Optional[int] = None,
) -> int:
    """Return ``local_size`` as int, rejecting anything not a power of two."""
    if isinstance(local_size, bool) or not isinstance(local_size, (int, np.integer)):
        raise LocalSizeError(
            f"{kernel}: local_size must be an integer, got {type(local_size).__name__}"
        )
    number = int(local_size)
    if number <= 0:
        raise LocalSizeError(f"{kernel}: local_size must be > 0, got {number}")
    if not is_power_of_two(number):
        raise LocalSizeError(f"{kernel}: local_size must be a power of two, got {number}")
    if max_size is not None and number > max_size:
        raise LocalSizeError(
            f"{kernel}: local_size {number} exceeds the device maximum {max_size}"
        )
    return number


def _round_to_local(global_size: int, local_size: int) -> int:
    """Pad ``global_size`` up to a multiple of ``local_size``."""
    return -(-int(global_size) // int(local_size)) * int(local_size)


_CL_SOURCE = """
#ifdef USE_FP64
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
typedef double acc_t;
#else
typedef float acc_t;
#endif

__kernel void cgemv_lr(__global const acc_t *A,
                       __global const acc_t *B,
                       __global const acc_t *x,
                       __global acc_t *y,
                       const uint m,
                       const uint k,
                       const uint n) {
    const uint row = get_global_id(0);
    if (row >= m) return;
    acc_t acc = (acc_t)0;
    for (uint p = 0; p < k; ++p) {
        acc_t inner = (acc_t)0;
        __global const acc_t *b_row = B + (size_t)p * (size_t)n;
        for (uint j = 0; j < n; ++j) inner += b_row[j] * x[j];
        acc += A[(size_t)row * (size_t)k + p] * inner;
    }
    y[row] = acc;
}

__kernel void cgemv_batch(__global const acc_t *A,
                          __global const acc_t *B,
                          __global const acc_t *X,
                          __global acc_t *Y,
                          const uint m,
                          const uint k,
                          const uint n,
                          const uint batch) {
    const size_t gid = get_global_id(0);
    const size_t total = (size_t)m * (size_t)batch;
    if (gid >= total) return;
    const uint row = (uint)(gid / (size_t)batch);
    const uint col = (uint)(gid % (size_t)batch);
    acc_t acc = (acc_t)0;
    for (uint p = 0; p < k; ++p) {
        acc_t inner = (acc_t)0;
        __global const acc_t *b_row = B + (size_t)p * (size_t)n;
        for (uint j = 0; j < n; ++j) {
            inner += b_row[j] * X[(size_t)j * (size_t)batch + col];
        }
        acc += A[(size_t)row * (size_t)k + p] * inner;
    }
    Y[gid] = acc;
}
"""


class ChronusOpenCLEngine:
    """Process-wide Chronus OpenCL context, queue and program cache."""

    _singleton_lock = threading.Lock()
    _instance: Optional["ChronusOpenCLEngine"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "ChronusOpenCLEngine":
        instance = cls._instance
        if instance is not None:
            return instance
        with cls._singleton_lock:
            instance = cls._instance
            if instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
        return instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._lock = threading.RLock()
        self._cl: Any = None
        self._context: Any = None
        self._queue: Any = None
        self._device: Any = None
        self._device_name: str = ""
        self._selection_reason: str = ""
        self._programs: Dict[str, Any] = {}
        self._use_fp64: bool = False
        self._unavailable: str = ""
        self._transfer_style: Optional[str] = None
        self._initialized = True

    @classmethod
    def get(cls) -> "ChronusOpenCLEngine":
        """Return the process-wide engine, creating it under the lock."""
        return cls()

    @classmethod
    def reset(cls) -> None:
        """Drop the singleton and release its context. Test/teardown only."""
        with cls._singleton_lock:
            instance = cls._instance
            cls._instance = None
        if instance is not None:
            instance.close()

    def _select_device(self, cl: Any) -> Tuple[Any, str]:
        """HYBA alias, then evidence-based integrated GPU, then GPU/device."""
        from .detect import classify_integrated
        from hyba.device import is_hyba_name

        devices = [device for platform in cl.get_platforms() for device in platform.get_devices()]
        if not devices:
            raise ChronusOpenCLUnavailable("no OpenCL device enumerated")
        gpu_bit = int(getattr(cl.device_type, "GPU", 1 << 2))
        gpus = [
            device
            for device in devices
            if int(getattr(device, "type", 0) or 0) & gpu_bit
        ]

        for device in devices:
            alias = is_hyba_name(device)
            if alias:
                return device, f"hyba alias {alias!r}"
        for device in gpus or devices:
            is_integrated, reason = classify_integrated(
                getattr(device, "vendor", ""), device
            )
            if is_integrated:
                return device, f"integrated device ({reason})"
        if gpus:
            best = max(
                gpus,
                key=lambda device: int(
                    getattr(device, "max_compute_units", 0) or 0
                ),
            )
            return best, "highest-compute-unit GPU (no integrated device present)"
        best = max(
            devices,
            key=lambda device: int(getattr(device, "max_compute_units", 0) or 0),
        )
        return best, "highest-compute-unit device (no GPU present)"

    def ensure(self) -> bool:
        """Build the context on first use. Returns True when available."""
        with self._lock:
            if self._context is not None:
                return True
            if self._unavailable:
                return False
            try:
                import pyopencl as cl
            except Exception as exc:
                self._unavailable = f"pyopencl unavailable: {type(exc).__name__}: {exc}"
                LOG.debug("Chronus engine unavailable: %s", self._unavailable)
                return False
            try:
                device, reason = self._select_device(cl)
            except Exception as exc:
                self._unavailable = f"device selection failed: {type(exc).__name__}: {exc}"
                LOG.debug("Chronus engine unavailable: %s", self._unavailable)
                return False
            try:
                context = cl.Context([device])
                queue = cl.CommandQueue(
                    context,
                    properties=cl.command_queue_properties.PROFILING_ENABLE,
                )
            except Exception as exc:
                self._unavailable = f"context creation failed: {type(exc).__name__}: {exc}"
                LOG.warning("Chronus could not create a context: %s", self._unavailable)
                return False
            self._cl = cl
            self._context = context
            self._queue = queue
            self._device = device
            self._device_name = str(getattr(device, "name", "") or "")
            self._selection_reason = reason
            self._use_fp64 = "cl_khr_fp64" in str(
                getattr(device, "extensions", "") or ""
            )
            LOG.info(
                "Chronus bound to %r via %s (fp64=%s)",
                self._device_name,
                reason,
                self._use_fp64,
            )
            return True

    def _require(self) -> None:
        if not self.ensure():
            raise ChronusOpenCLUnavailable(
                self._unavailable or "Chronus OpenCL engine unavailable"
            )

    @property
    def available(self) -> bool:
        return self.ensure()

    @property
    def cl(self) -> Any:
        self._require()
        return self._cl

    @property
    def context(self) -> Any:
        self._require()
        return self._context

    @property
    def queue(self) -> Any:
        self._require()
        return self._queue

    @property
    def device(self) -> Any:
        self._require()
        return self._device

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def selection_reason(self) -> str:
        return self._selection_reason

    @property
    def unavailable_reason(self) -> str:
        return self._unavailable

    @property
    def uses_fp64(self) -> bool:
        return self._use_fp64

    def as_dict(self) -> Dict[str, Any]:
        device = self._device
        return {
            "product": "Chronus",
            "compute_substrate": "chronus_execution_plane",
            "available": self._context is not None,
            "reason": self._unavailable,
            "device_name": self._device_name,
            "selection_reason": self._selection_reason,
            "vendor": str(getattr(device, "vendor", "") or "")
            if device is not None
            else "",
            "fp64": self._use_fp64,
            "max_work_group_size": int(
                getattr(device, "max_work_group_size", 0) or 0
            )
            if device is not None
            else 0,
        }

    def program(self, source: str, options: Sequence[str] = ()) -> Any:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("kernel source is required")
        opts = list(options)
        cache_key = f"{hash(source)}|{','.join(opts)}"
        with self._lock:
            cached = self._programs.get(cache_key)
            if cached is not None:
                return cached
            self._require()
            program = self._cl.Program(self._context, source).build(options=opts)
            self._programs[cache_key] = program
            return program

    def default_local_size(self, kernel: str, requested: Any = None) -> int:
        max_size = (
            int(getattr(self._device, "max_work_group_size", 0) or 0)
            or MAX_LOCAL_SIZE
        )
        if requested is not None:
            return validate_local_size(requested, kernel=kernel, max_size=max_size)
        size = DEFAULT_LOCAL_SIZE
        while size > 1 and size > max_size:
            size //= 2
        return validate_local_size(size, kernel=kernel, max_size=max_size)

    def close(self) -> None:
        with self._lock:
            self._programs.clear()
            self._cl = None
            self._context = None
            self._queue = None
            self._device = None
            self._initialized = False

    @staticmethod
    def _resolve_enqueue(cl: Any, name: str) -> Any:
        fn = getattr(cl, name, None) or getattr(cl, f"_{name}", None)
        if fn is None:
            raise ChronusOpenCLUnavailable(
                f"pyopencl exposes neither {name} nor _{name}"
            )
        return fn

    def _transfer_layout(self) -> str:
        if self._transfer_style is not None:
            return self._transfer_style
        self._require()
        cl = self._cl
        fn = self._resolve_enqueue(cl, "enqueue_write_buffer")
        scratch = cl.Buffer(self._context, cl.mem_flags.READ_WRITE, 16)
        probe = np.zeros(16, dtype=np.uint8)
        try:
            fn(self._queue, scratch, probe, 0)
            self._transfer_style = "modern"
        except Exception:
            try:
                fn(self._queue, scratch, cl.mem_flags.READ_ONLY, 0, probe)
                self._transfer_style = "legacy"
            except Exception as exc:
                raise ChronusOpenCLUnavailable(
                    f"unrecognized pyopencl buffer transfer signature: {exc}"
                ) from exc
        LOG.debug("pyopencl buffer transfer layout: %s", self._transfer_style)
        return self._transfer_style

    def _transfer(self, direction: str, buffer: Any, host: Any, offset: int) -> None:
        self._require()
        cl = self._cl
        write = direction == "write"
        fn = self._resolve_enqueue(
            cl,
            "enqueue_write_buffer" if write else "enqueue_read_buffer",
        )
        offset = int(offset)
        if self._transfer_layout() == "modern":
            fn(self._queue, buffer, host, offset)
        else:
            flags = cl.mem_flags.READ_ONLY if write else cl.mem_flags.READ_WRITE
            fn(self._queue, buffer, flags, offset, host)

    def write_buffer(self, buffer: Any, host: Any, offset: int = 0) -> None:
        self._transfer("write", buffer, host, offset)

    def read_buffer(self, buffer: Any, host: Any, offset: int = 0) -> Any:
        self._transfer("read", buffer, host, offset)
        return host


class ResidentBufferSet:
    """Device buffers owned by exactly one Chronus resident instance."""

    def __init__(self, engine: Any, owner: str) -> None:
        self._engine = engine
        self._owner = owner
        self._instance_id = next(_RESIDENT_IDS)
        self._buffers: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._closed = False

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def instance_id(self) -> int:
        return self._instance_id

    def key(self, name: str) -> str:
        return f"{self._owner}/{self._instance_id}/{name}"

    def buffer(self, name: str, nbytes: int, *, read_only: bool = False) -> Any:
        if self._closed:
            raise RuntimeError(
                f"buffer set for {self._owner}#{self._instance_id} is closed"
            )
        if nbytes < 0:
            raise ValueError(f"nbytes must be >= 0, got {nbytes}")
        with self._lock:
            existing = self._buffers.get(name)
            if existing is not None:
                return existing
            cl = self._engine.cl
            flags = cl.mem_flags.READ_ONLY if read_only else cl.mem_flags.READ_WRITE
            buffer = cl.Buffer(self._engine.context, flags, int(nbytes))
            self._buffers[name] = buffer
            return buffer

    @property
    def keys(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(self.key(name) for name in sorted(self._buffers))

    def get(self, name: str) -> Any:
        with self._lock:
            return self._buffers[name]

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffers)

    def close(self) -> None:
        with self._lock:
            self._buffers.clear()
            self._closed = True


def _engine_or_default(engine: Any) -> Any:
    return engine if engine is not None else ChronusOpenCLEngine.get()


def _as_square(
    matrix: np.ndarray,
    dim: int,
    name: str,
    dtype: Any = np.float64,
) -> np.ndarray:
    array = np.ascontiguousarray(matrix, dtype=dtype)
    if array.shape != (dim, dim):
        raise ValueError(f"{name} must have shape ({dim}, {dim}), got {array.shape}")
    return array


def _as_vector(
    vector: np.ndarray,
    dim: int,
    name: str,
    dtype: Any = np.float64,
) -> np.ndarray:
    array = np.ascontiguousarray(vector, dtype=dtype)
    if array.shape != (dim,):
        raise ValueError(f"{name} must have shape ({dim},), got {array.shape}")
    return array


class _ResidentBase:
    _owner = "resident"

    def __init__(self, engine: Any = None, label: str = "") -> None:
        self._engine = _engine_or_default(engine)
        self.label = label or self._owner
        self._buffers = ResidentBufferSet(self._engine, self._owner)

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def buffer_keys(self) -> Tuple[str, ...]:
        return self._buffers.keys

    @property
    def instance_id(self) -> int:
        return self._buffers.instance_id

    def _build_options(self) -> list:
        return ["-DUSE_FP64"] if getattr(self._engine, "uses_fp64", False) else []

    @property
    def _acc_dtype(self) -> Any:
        return (
            np.float64
            if getattr(self._engine, "uses_fp64", False)
            else np.float32
        )

    @property
    def _acc_bytes(self) -> int:
        return int(np.dtype(self._acc_dtype).itemsize)

    def _upload(self, name: str, array: np.ndarray) -> None:
        self._engine.write_buffer(self._buffers.get(name), array, 0)

    def _download(self, name: str, array: np.ndarray) -> np.ndarray:
        return self._engine.read_buffer(self._buffers.get(name), array, 0)

    def close(self) -> None:
        self._buffers.close()

    def __enter__(self) -> "_ResidentBase":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


class ResidentChronusState(_ResidentBase):
    """One Chronus resident state with private A/x/y device buffers."""

    _owner = "res_m"

    def __init__(self, dim: int, *, engine: Any = None, label: str = "") -> None:
        if isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0:
            raise ValueError(f"dim must be a positive int, got {dim!r}")
        self.dim = int(dim)
        super().__init__(engine=engine, label=label or f"state{self.dim}")
        self._buffers.buffer("A", self.dim * self.dim * self._acc_bytes)
        self._buffers.buffer("x", self.dim * self._acc_bytes)
        self._buffers.buffer("y", self.dim * self._acc_bytes)

    def set_A(self, matrix: np.ndarray) -> None:
        self._upload("A", _as_square(matrix, self.dim, "A", self._acc_dtype))

    def set_x(self, vector: np.ndarray) -> None:
        self._upload("x", _as_vector(vector, self.dim, "x", self._acc_dtype))

    def apply(self, B: np.ndarray, *, local_size: Any = None) -> np.ndarray:
        factor = _as_square(B, self.dim, "B", self._acc_dtype)
        self._buffers.buffer("B", factor.nbytes, read_only=True)
        self._upload("B", factor)
        program = self._engine.program(_CL_SOURCE, self._build_options())
        local = self._engine.default_local_size("cgemv_lr", local_size)
        out = np.empty(self.dim, dtype=self._acc_dtype)
        program.cgemv_lr(
            self._engine.queue,
            (_round_to_local(self.dim, local),),
            (local,),
            self._buffers.get("A"),
            self._buffers.get("B"),
            self._buffers.get("x"),
            self._buffers.get("y"),
            np.uint32(self.dim),
            np.uint32(self.dim),
            np.uint32(self.dim),
        )
        self._engine.queue.finish()
        return self._download("y", out)


class ResidentChronusEnsemble(_ResidentBase):
    """A batch of independent Chronus resident states."""

    _owner = "ensa"

    def __init__(
        self,
        members: int,
        dim: int,
        *,
        engine: Any = None,
        label: str = "",
    ) -> None:
        for field_name, value in (("members", members), ("dim", dim)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"{field_name} must be a positive int, got {value!r}"
                )
        self.members = int(members)
        self.dim = int(dim)
        super().__init__(
            engine=engine,
            label=label or f"ensemble{self.members}x{self.dim}",
        )
        self._buffers.buffer("A", self.members * self.dim * self._acc_bytes)
        self._buffers.buffer(
            "B",
            self.dim * self.dim * self._acc_bytes,
            read_only=True,
        )
        self._buffers.buffer(
            "X",
            self.dim * self.members * self._acc_bytes,
            read_only=True,
        )
        self._buffers.buffer(
            "Y",
            self.members * self.members * self._acc_bytes,
        )

    def _as_A(self, matrix: np.ndarray) -> np.ndarray:
        array = np.ascontiguousarray(matrix, dtype=self._acc_dtype)
        if array.shape != (self.members, self.dim):
            raise ValueError(
                f"A must have shape ({self.members}, {self.dim}), got {array.shape}"
            )
        return array

    def _as_X(self, matrix: np.ndarray) -> np.ndarray:
        array = np.ascontiguousarray(matrix, dtype=self._acc_dtype)
        if array.shape != (self.dim, self.members):
            raise ValueError(
                f"X must have shape ({self.dim}, {self.members}), got {array.shape}"
            )
        return array

    def set_A(self, matrix: np.ndarray) -> None:
        self._upload("A", self._as_A(matrix))

    def set_B(self, matrix: np.ndarray) -> None:
        self._upload("B", _as_square(matrix, self.dim, "B", self._acc_dtype))

    def set_X(self, matrix: np.ndarray) -> None:
        self._upload("X", self._as_X(matrix))

    def apply(self, *, local_size: Any = None) -> np.ndarray:
        program = self._engine.program(_CL_SOURCE, self._build_options())
        local = self._engine.default_local_size("cgemv_batch", local_size)
        out = np.empty((self.members, self.members), dtype=self._acc_dtype)
        program.cgemv_batch(
            self._engine.queue,
            (_round_to_local(self.members * self.members, local),),
            (local,),
            self._buffers.get("A"),
            self._buffers.get("B"),
            self._buffers.get("X"),
            self._buffers.get("Y"),
            np.uint32(self.members),
            np.uint32(self.dim),
            np.uint32(self.dim),
            np.uint32(self.members),
        )
        self._engine.queue.finish()
        return self._download("Y", out)


class ResidentFoldedBytes(_ResidentBase):
    """A private device-side byte buffer for folded state payloads."""

    _owner = "fold"

    def __init__(self, nbytes: int, *, engine: Any = None, label: str = "") -> None:
        if isinstance(nbytes, bool) or not isinstance(nbytes, int) or nbytes < 0:
            raise ValueError(f"nbytes must be a non-negative int, got {nbytes!r}")
        self.nbytes = int(nbytes)
        super().__init__(engine=engine, label=label or f"fold{self.nbytes}")
        if self.nbytes:
            self._buffers.buffer("bytes", self.nbytes)

    def write(self, offset: int, data: bytes) -> None:
        if offset < 0 or offset + len(data) > self.nbytes:
            raise ValueError(
                f"write [{offset}, {offset + len(data)}) exceeds buffer size {self.nbytes}"
            )
        if not data:
            return
        payload = np.frombuffer(bytes(data), dtype=np.uint8)
        self._engine.write_buffer(self._buffers.get("bytes"), payload, int(offset))

    def read(self, offset: int, length: int) -> bytes:
        if length < 0 or offset < 0 or offset + length > self.nbytes:
            raise ValueError(
                f"read [{offset}, {offset + length}) exceeds buffer size {self.nbytes}"
            )
        if length == 0:
            return b""
        out = np.empty(length, dtype=np.uint8)
        self._engine.read_buffer(self._buffers.get("bytes"), out, int(offset))
        return out.tobytes()

    def zero(self) -> None:
        if not self.nbytes:
            return
        zeros = np.zeros(self.nbytes, dtype=np.uint8)
        self._engine.write_buffer(self._buffers.get("bytes"), zeros, 0)


from .v33.engine import ChronosEngine

__all__ = [
    "ChronosEngine",
    "DEFAULT_LOCAL_SIZE",
    "ChronusOpenCLEngine",
    "ChronusOpenCLUnavailable",
    "LocalSizeError",
    "ResidentBufferSet",
    "ResidentFoldedBytes",
    "ResidentChronusEnsemble",
    "ResidentChronusState",
    "is_power_of_two",
    "validate_local_size",
]

