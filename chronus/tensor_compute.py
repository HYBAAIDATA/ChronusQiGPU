"""Measured tensor execution on a physical Chronus OpenCL GPU.

The runtime is intentionally fail closed: CPU OpenCL devices are never accepted
and an explicitly requested platform/device/vendor must be present.  Selection
and launch policy favour integrated GPUs (shared host memory) without making
unmeasured performance claims.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
from threading import Lock
from time import perf_counter_ns
from typing import Any, Sequence

from .virtual_igpu.capabilities import DeviceLimits, KernelLimits, legal_local_size

import numpy as np


class ChronusTensorUnavailable(RuntimeError):
    pass


class ChronusTensorValidationError(ValueError):
    pass


# HYBA iGPU identity aliases — same HYBA_DEVICE_ALIAS contract as
# mining/bitcoin_hasher.py and unified_punch.py.
DEFAULT_HYBA_ALIASES = ("hyba-mla1517", "hyba_mla1517", "mla1517", "hyba")


def _require_hyba() -> bool:
    return os.getenv("HYBA_REQUIRE_HYBA", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@dataclass(frozen=True)
class _DeviceSelector:
    platform: str = ""
    device: str = ""
    vendor: str = ""
    aliases: tuple[str, ...] = ()
    require_aliases: bool = False

    @property
    def explicit(self) -> bool:
        return bool(
            self.platform or self.device or self.vendor or (self.require_aliases and self.aliases)
        )


@dataclass(frozen=True)
class TensorDeviceProbe:
    available: bool
    device_id: str
    device_name: str
    platform_name: str
    reason: str
    operations: tuple[str, ...] = ("matmul", "add", "scale", "kron", "hadamard")
    dtypes: tuple[str, ...] = ("float32",)
    vendor: str = ""
    compute_units: int | None = None
    global_memory_bytes: int | None = None
    local_memory_bytes: int | None = None
    max_work_group_size: int | None = None
    max_work_item_sizes: tuple[int, ...] | None = None
    host_unified_memory: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TensorExecutionEvidence:
    operation: str
    device_id: str
    kernel: str
    global_size: tuple[int, ...]
    local_size: tuple[int, ...]
    output_shape: tuple[int, ...]
    device_time_ns: int | None
    wall_time_ns: int
    profiling_available: bool
    hardware_executed: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int_attr(value: Any, name: str) -> int:
    try:
        return int(getattr(value, name, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _bool_attr(value: Any, name: str) -> bool:
    try:
        return bool(getattr(value, name, False))
    except Exception:
        return False


def _hyba_aliases() -> tuple[str, ...]:
    raw = os.getenv("HYBA_DEVICE_ALIAS", "").strip()
    if raw:
        return tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    return DEFAULT_HYBA_ALIASES


def _selector_from_env() -> _DeviceSelector:
    return _DeviceSelector(
        platform=os.getenv("CHRONUS_OPENCL_PLATFORM", "").strip().lower(),
        device=os.getenv("CHRONUS_OPENCL_DEVICE", "").strip().lower(),
        vendor=os.getenv("HYBA_DEVICE_VENDOR", "").strip().lower(),
        aliases=_hyba_aliases(),
        require_aliases=_require_hyba(),
    )


def _device_identity(platform: Any, device: Any) -> str:
    return " ".join(
        (
            _text(getattr(platform, "name", "")),
            _text(getattr(device, "vendor", "")),
            _text(getattr(device, "name", "")),
        )
    ).lower()


def _alias_match(platform: Any, device: Any, aliases: tuple[str, ...]) -> bool:
    identity = _device_identity(platform, device)
    return any(alias and alias in identity for alias in aliases)


def _matches(platform: Any, device: Any, selector: _DeviceSelector) -> bool:
    platform_name = _text(getattr(platform, "name", "")).lower()
    name = _text(getattr(device, "name", "")).lower()
    vendor = _text(getattr(device, "vendor", "")).lower()
    alias_gate = selector.require_aliases and selector.aliases
    return (
        (not selector.platform or selector.platform in platform_name)
        and (not selector.device or selector.device in name)
        and (not selector.vendor or selector.vendor in vendor)
        and (not alias_gate or _alias_match(platform, device, selector.aliases))
    )


def _device_score(platform: Any, device: Any) -> tuple[int, int, int, int]:
    """Rank actual device facts; shared-memory Intel GPUs are preferred.

    An Intel device only counts as integrated when it reports unified host
    memory — discrete GPUs (e.g. Arc) may carry a ``Graphics`` product name
    and must not outrank genuinely shared-memory devices.
    """
    identity = _device_identity(platform, device)
    unified = _bool_attr(device, "host_unified_memory")
    intel_igpu = (
        unified
        and "intel" in identity
        and any(token in identity for token in ("uhd", "iris", "graphics"))
    )
    return (
        3 if intel_igpu else 1 if unified else 0,
        _int_attr(device, "max_compute_units"),
        _int_attr(device, "global_mem_size"),
        _int_attr(device, "max_clock_frequency"),
    )


def _pick_gpu():
    try:
        import pyopencl as cl
    except Exception as exc:
        return None, None, f"pyopencl unavailable: {type(exc).__name__}: {exc}"
    try:
        candidates = []
        mask = int(cl.device_type.GPU) | int(cl.device_type.ACCELERATOR)
        for platform in cl.get_platforms():
            for device in platform.get_devices():
                if int(getattr(device, "type", 0)) & mask:
                    candidates.append((platform, device))
    except Exception as exc:
        return None, None, f"OpenCL enumeration failed: {type(exc).__name__}: {exc}"
    if not candidates:
        return None, None, "no OpenCL GPU/accelerator device found"
    selector = _selector_from_env()
    matching = [item for item in candidates if _matches(*item, selector)]
    if selector.explicit and not matching:
        requested = {
            "platform": selector.platform or None,
            "device": selector.device or None,
            "vendor": selector.vendor or None,
            "aliases": selector.aliases or None,
        }
        return None, None, f"requested OpenCL GPU identity not found: {requested}"
    pool = matching or candidates
    if selector.aliases and not selector.require_aliases:
        # Aliases are a preference hint unless HYBA_REQUIRE_HYBA makes them a
        # gate: prefer an alias-named device, never reject a valid one.
        aliased = [item for item in pool if _alias_match(*item, selector.aliases)]
        if aliased:
            pool = aliased
    selected = max(pool, key=lambda item: _device_score(*item))
    return cl, selected, ""


def _probe_for(platform: Any, device: Any) -> TensorDeviceProbe:
    name = _text(getattr(device, "name", "unknown"))
    platform_name = _text(getattr(platform, "name", "unknown"))
    return TensorDeviceProbe(
        True,
        f"opencl:{platform_name}:{name}",
        name,
        platform_name,
        "",
        vendor=_text(getattr(device, "vendor", "")),
        compute_units=_int_attr(device, "max_compute_units") or None,
        global_memory_bytes=_int_attr(device, "global_mem_size") or None,
        local_memory_bytes=_int_attr(device, "local_mem_size") or None,
        max_work_group_size=_int_attr(device, "max_work_group_size") or None,
        max_work_item_sizes=tuple(int(v) for v in (getattr(device, "max_work_item_sizes", ()) or ())) or None,
        host_unified_memory=_bool_attr(device, "host_unified_memory"),
    )


def probe() -> TensorDeviceProbe:
    cl, selected, reason = _pick_gpu()
    del cl
    if selected is None:
        return TensorDeviceProbe(False, "unavailable", "", "", reason)
    return _probe_for(*selected)


def _round_up(value: int, multiple: int) -> int:
    return ((int(value) + int(multiple) - 1) // int(multiple)) * int(multiple)


def _power_of_two_at_most(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (int(value).bit_length() - 1)


def _plan_1d(output_size: int, max_work_group_size: int, preferred_multiple: int = 1) -> tuple[tuple[int], tuple[int]]:
    cap = min(max(1, output_size), max(1, max_work_group_size), 256)
    local = _power_of_two_at_most(cap)
    preferred_multiple = max(1, int(preferred_multiple))
    if local >= preferred_multiple:
        local = max(preferred_multiple, (local // preferred_multiple) * preferred_multiple)
    return (_round_up(output_size, local),), (local,)


def _plan_matmul(
    m: int, n: int, max_work_group_size: int, local_memory_bytes: int
) -> tuple[tuple[int, int], tuple[int, int]]:
    tile = 16
    while tile > 1 and (
        tile * tile > max(1, max_work_group_size)
        or 2 * tile * tile * np.dtype(np.float32).itemsize > max(1, local_memory_bytes)
    ):
        tile //= 2
    return (_round_up(n, tile), _round_up(m, tile)), (tile, tile)


class ChronusTensorRuntime:
    def __init__(self) -> None:
        cl, selected, reason = _pick_gpu()
        if cl is None or selected is None:
            raise ChronusTensorUnavailable(reason)
        platform, device = selected
        source_path = Path(__file__).resolve().parent / "kernels" / "tensor_ops.cl"
        if not source_path.is_file():
            raise ChronusTensorUnavailable(f"tensor kernel source missing: {source_path}")
        try:
            context = cl.Context([device])
            profiling = int(getattr(cl.command_queue_properties, "PROFILING_ENABLE", 0))
            queue = cl.CommandQueue(context, properties=profiling)
            program = cl.Program(context, source_path.read_text(encoding="utf-8")).build()
        except Exception as exc:
            raise ChronusTensorUnavailable(
                f"OpenCL tensor kernel build failed: {type(exc).__name__}: {exc}"
            ) from exc
        self.cl = cl
        self.context = context
        self.queue = queue
        self.program = program
        self.device = device
        self.probe = _probe_for(platform, device)
        self.device_id = self.probe.device_id
        self.max_work_group_size = self.probe.max_work_group_size or 1
        self.local_memory_bytes = self.probe.local_memory_bytes or 1
        self.device_limits = DeviceLimits(
            self.max_work_group_size,
            self.probe.max_work_item_sizes or (self.max_work_group_size,) * 3,
            self.local_memory_bytes,
            self.probe.global_memory_bytes,
            _int_attr(device, "max_mem_alloc_size") or None,
            self.probe.host_unified_memory,
        )
        self.last_evidence: TensorExecutionEvidence | None = None

    def _launch_limits(self, kernel_name: str) -> tuple[int, int]:
        """Work-group size and dynamic local-memory budget for a built kernel.

        ``CL_KERNEL_WORK_GROUP_SIZE`` can be lower than the device maximum and
        the kernel's static local memory shrinks the dynamic budget, so the
        compiled kernel's own limits bound every launch plan.  A driver that
        cannot report them falls back to the device limits; an illegal launch
        then still fails loudly at enqueue rather than being concealed.
        """
        kernel = getattr(self.program, kernel_name)
        work_group = 0
        static_local = 0
        try:
            info = self.cl.kernel_work_group_info
            work_group = int(kernel.get_work_group_info(info.WORK_GROUP_SIZE, self.device) or 0)
            static_local = int(kernel.get_work_group_info(info.LOCAL_MEM_SIZE, self.device) or 0)
        except Exception:
            pass
        max_group = (
            min(self.max_work_group_size, work_group)
            if work_group > 0
            else self.max_work_group_size
        )
        local_budget = self.local_memory_bytes - max(0, static_local)
        return max(1, max_group), max(1, local_budget)

    @staticmethod
    def _float32_array(value: Any, shape: Sequence[int]) -> np.ndarray:
        array = np.asarray(value, dtype=np.float32, order="C")
        expected = tuple(int(v) for v in shape)
        if tuple(array.shape) != expected:
            raise ChronusTensorValidationError(
                f"input shape {array.shape} does not match declared shape {expected}"
            )
        return np.ascontiguousarray(array)

    def _buffers(self, arrays: Sequence[np.ndarray], output_size: int):
        flags = self.cl.mem_flags
        inputs = [
            self.cl.Buffer(self.context, flags.READ_ONLY | flags.COPY_HOST_PTR, hostbuf=array)
            for array in arrays
        ]
        output = np.empty(int(output_size), dtype=np.float32)
        output_buffer = self.cl.Buffer(self.context, flags.WRITE_ONLY, output.nbytes)
        return inputs, output, output_buffer

    @staticmethod
    def _device_time(event: Any) -> int | None:
        try:
            event.wait()
            start = int(event.profile.start)
            end = int(event.profile.end)
            return max(0, end - start)
        except Exception:
            return None

    def _finish(
        self,
        operation: str,
        kernel: str,
        event: Any,
        started_ns: int,
        output: np.ndarray,
        output_buffer: Any,
        shape: Sequence[int],
        global_size: tuple[int, ...],
        local_size: tuple[int, ...],
    ) -> tuple[np.ndarray, TensorExecutionEvidence]:
        self.cl.enqueue_copy(self.queue, output, output_buffer)
        self.queue.finish()
        device_time_ns = self._device_time(event)
        evidence = TensorExecutionEvidence(
            operation=operation,
            device_id=self.device_id,
            kernel=kernel,
            global_size=global_size,
            local_size=local_size,
            output_shape=tuple(int(v) for v in shape),
            device_time_ns=device_time_ns,
            wall_time_ns=max(0, perf_counter_ns() - started_ns),
            profiling_available=device_time_ns is not None,
        )
        self.last_evidence = evidence
        return output.reshape(evidence.output_shape), evidence

    def execute_with_evidence(
        self,
        operation: str,
        inputs: Sequence[Any],
        input_shapes: Sequence[Sequence[int]],
        output_shape: Sequence[int],
    ) -> tuple[np.ndarray, TensorExecutionEvidence]:
        if len(inputs) != len(input_shapes):
            raise ChronusTensorValidationError("input count does not match declared shapes")
        arrays = [self._float32_array(v, s) for v, s in zip(inputs, input_shapes)]
        out_size = int(np.prod(tuple(output_shape), dtype=np.int64))
        if out_size <= 0:
            raise ChronusTensorValidationError("output must contain at least one element")
        buffers, output, out_buffer = self._buffers(arrays, out_size)
        u32 = np.uint32
        started_ns = perf_counter_ns()
        if operation in {"add", "hadamard"}:
            if len(arrays) != 2 or arrays[0].shape != arrays[1].shape:
                raise ChronusTensorValidationError(f"{operation} requires two equal shapes")
            kernel = f"tensor_{operation}_f32"
            group_limit, _local_budget = self._launch_limits(kernel)
            global_size, local_size = _plan_1d(out_size, group_limit)
            event = getattr(self.program, kernel)(
                self.queue,
                global_size,
                local_size,
                buffers[0],
                buffers[1],
                out_buffer,
                u32(out_size),
            )
        elif operation == "scale":
            if len(arrays) != 2 or arrays[1].size != 1:
                raise ChronusTensorValidationError("scale requires a tensor and one scalar")
            kernel = "tensor_scale_f32"
            group_limit, _local_budget = self._launch_limits(kernel)
            global_size, local_size = _plan_1d(out_size, group_limit)
            event = self.program.tensor_scale_f32(
                self.queue,
                global_size,
                local_size,
                buffers[0],
                buffers[1],
                out_buffer,
                u32(out_size),
            )
        elif operation == "matmul":
            if len(arrays) != 2 or arrays[0].ndim != 2 or arrays[1].ndim != 2:
                raise ChronusTensorValidationError("matmul requires two rank-2 inputs")
            m, k = arrays[0].shape
            k2, n = arrays[1].shape
            if k != k2 or tuple(output_shape) != (m, n):
                raise ChronusTensorValidationError("matmul dimensions/output shape disagree")
            kernel = "tensor_matmul_tiled_f32"
            group_limit, local_budget = self._launch_limits(kernel)
            global_size, local_size = _plan_matmul(m, n, group_limit, local_budget)
            tile = local_size[0]
            event = self.program.tensor_matmul_tiled_f32(
                self.queue,
                global_size,
                local_size,
                buffers[0],
                buffers[1],
                out_buffer,
                u32(m),
                u32(k),
                u32(n),
                self.cl.LocalMemory(tile * tile * 4),
                self.cl.LocalMemory(tile * tile * 4),
            )
        elif operation == "kron":
            if len(arrays) != 2 or arrays[0].ndim != arrays[1].ndim:
                raise ChronusTensorValidationError("kron requires equal-rank inputs")
            if arrays[0].ndim == 1:
                an, bn = arrays[0].size, arrays[1].size
                if tuple(output_shape) != (an * bn,):
                    raise ChronusTensorValidationError("kron output shape disagrees")
                kernel = "tensor_kron_1d_f32"
                group_limit, _local_budget = self._launch_limits(kernel)
                global_size, local_size = _plan_1d(out_size, group_limit)
                event = self.program.tensor_kron_1d_f32(
                    self.queue,
                    global_size,
                    local_size,
                    buffers[0],
                    buffers[1],
                    out_buffer,
                    u32(an),
                    u32(bn),
                )
            elif arrays[0].ndim == 2:
                ar, ac = arrays[0].shape
                br, bc = arrays[1].shape
                if tuple(output_shape) != (ar * br, ac * bc):
                    raise ChronusTensorValidationError("kron output shape disagrees")
                kernel = "tensor_kron_2d_f32"
                group_limit, _local_budget = self._launch_limits(kernel)
                global_size, local_size = _plan_1d(out_size, group_limit)
                event = self.program.tensor_kron_2d_f32(
                    self.queue,
                    global_size,
                    local_size,
                    buffers[0],
                    buffers[1],
                    out_buffer,
                    u32(ar),
                    u32(ac),
                    u32(br),
                    u32(bc),
                )
            else:
                raise ChronusTensorValidationError("Chronus kron supports rank 1 or 2")
        else:
            raise ChronusTensorValidationError(f"unsupported operation {operation!r}")
        return self._finish(
            operation,
            kernel,
            event,
            started_ns,
            output,
            out_buffer,
            output_shape,
            global_size,
            local_size,
        )

    def execute(
        self,
        operation: str,
        inputs: Sequence[Any],
        input_shapes: Sequence[Sequence[int]],
        output_shape: Sequence[int],
    ) -> np.ndarray:
        result, _evidence = self.execute_with_evidence(
            operation, inputs, input_shapes, output_shape
        )
        return result


_RUNTIME: ChronusTensorRuntime | None = None
_RUNTIME_LOCK = Lock()


def get_runtime() -> ChronusTensorRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        with _RUNTIME_LOCK:
            if _RUNTIME is None:
                _RUNTIME = ChronusTensorRuntime()
    return _RUNTIME


get_tensor_runtime = get_runtime
probe_tensor = probe

__all__ = [
    "ChronusTensorRuntime",
    "ChronusTensorUnavailable",
    "ChronusTensorValidationError",
    "TensorDeviceProbe",
    "TensorExecutionEvidence",
    "get_runtime",
    "get_tensor_runtime",
    "probe",
    "probe_tensor",
]
