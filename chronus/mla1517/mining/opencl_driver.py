"""Strict OpenCL execution boundary for PYTHIA.

This module never substitutes CPU work for a requested OpenCL execution. A
successful hardware receipt is created only after an OpenCL kernel dispatch
finishes on a discovered device. It reports execution facts, not estimates.

Multi-device behaviour: every enumerated device is ranked (HYBA alias first,
then GPU type, then compute units) and contexts, command queues and built
programs are cached per device so a composed substrate does not rebuild
state per dispatch. Timing reports ``device_ns`` from the OpenCL event
profile alongside ``wall_ns`` — both are real measurements; neither is a
projection.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

TRUTH_CLASSES = frozenset({"measured_hardware", "measured_cpu_reference", "unavailable", "rejected"})

# HYBA iGPU identity aliases (same convention as scripts/chronus_diag.py and
# Intelligence/backend_binding.py; overridable via HYBA_DEVICE_ALIAS).
_DEFAULT_HYBA_ALIASES = ("hyba-mla1517", "hyba_mla1517", "mla1517", "hyba")


def _hyba_aliases() -> tuple:
    raw = os.environ.get("HYBA_DEVICE_ALIAS", "").strip()
    if raw:
        return tuple(a.strip().lower() for a in raw.split(",") if a.strip())
    return _DEFAULT_HYBA_ALIASES


class OpenCLUnavailable(RuntimeError):
    """No usable OpenCL device or runtime is available."""


class OpenCLExecutionRejected(RuntimeError):
    """The requested hardware execution was rejected before dispatch."""


@dataclass(frozen=True)
class OpenCLDevice:
    platform: str
    name: str
    vendor: str
    version: str


@dataclass(frozen=True)
class OpenCLExecutionResult:
    requested_backend: str
    selected_backend: str | None
    actual_backend: str | None
    device_name: str | None
    device_available: bool
    hardware_execution: bool
    degraded: bool
    fallback_used: bool
    hashes_computed: int
    elapsed_seconds: float
    measured_hashrate: float
    truth_class: str
    # Device-side kernel time from the OpenCL event profile (nanoseconds).
    # 0 when the platform cannot profile the dispatch.
    device_ns: int = 0
    # Host-side wall time for the dispatch call (perf_counter_ns).
    wall_ns: int = 0
    # Which clock produced the primary elapsed_seconds figure:
    # "cl_event" when device profiling is live, else "perf_counter".
    clock_source: str = "perf_counter"

    def __post_init__(self) -> None:
        if self.truth_class not in TRUTH_CLASSES:
            raise ValueError(f"unsupported truth_class: {self.truth_class}")
        if self.hashes_computed < 0 or self.elapsed_seconds < 0 or self.measured_hashrate < 0:
            raise ValueError("execution counters cannot be negative")
        if self.hardware_execution != (self.truth_class == "measured_hardware"):
            raise ValueError("hardware_execution and truth_class disagree")
        if self.hardware_execution and not self.device_available:
            raise ValueError("hardware execution requires an available device")
        if self.fallback_used and self.truth_class == "measured_hardware":
            raise ValueError("hardware execution cannot use a fallback")

    @classmethod
    def unavailable(cls, requested_backend: str = "opencl") -> "OpenCLExecutionResult":
        return cls(
            requested_backend=requested_backend,
            selected_backend=None,
            actual_backend=None,
            device_name=None,
            device_available=False,
            hardware_execution=False,
            degraded=True,
            fallback_used=False,
            hashes_computed=0,
            elapsed_seconds=0.0,
            measured_hashrate=0.0,
            truth_class="unavailable",
        )


class OpenCLDriver:
    """Discover and dispatch actual OpenCL kernels without CPU fallback."""

    def __init__(self, *, platform_name: str | None = None, device_name: str | None = None) -> None:
        self._cl: Any | None = None
        self._devices: tuple[OpenCLDevice, ...] = ()
        self._selected_device: Any | None = None
        self._platform_name = platform_name
        self._device_name = device_name
        # Per-device runtime cache: context, profiling queue, and built
        # programs keyed by (device index, source hash, build options) so a
        # composed substrate pays compile cost once per (device, kernel).
        self._contexts: Dict[int, Any] = {}
        self._queues: Dict[int, Any] = {}
        self._programs: Dict[Tuple[int, str, Tuple[str, ...]], Any] = {}
        self._cl_devices: list[Any] = []
        try:
            import pyopencl as cl
        except ImportError:
            return
        self._cl = cl
        try:
            discovered: list[OpenCLDevice] = []
            cl_devices: list[Any] = []
            for platform in cl.get_platforms():
                for device in platform.get_devices():
                    info = OpenCLDevice(
                        platform=str(platform.name),
                        name=str(device.name),
                        vendor=str(device.vendor),
                        version=str(device.version),
                    )
                    if platform_name and info.platform != platform_name:
                        continue
                    if device_name and info.name != device_name:
                        continue
                    discovered.append(info)
                    cl_devices.append(device)
            # Rank beyond first-match: HYBA alias, GPU type, then compute
            # units — deterministic and honest (it describes preference, not
            # a capability claim).
            aliases = _hyba_aliases()

            def _rank(pair) -> tuple:
                info, dev = pair
                name_lower = info.name.lower()
                alias_hit = any(a and a in name_lower for a in aliases)
                try:
                    is_gpu = bool(dev.type & cl.device_type.GPU)
                except Exception:
                    is_gpu = False
                try:
                    cus = int(dev.max_compute_units)
                except Exception:
                    cus = 0
                return (
                    0 if alias_hit else 1,
                    0 if is_gpu else 1,
                    -cus,
                    name_lower,
                )

            ranked = sorted(
                zip(discovered, cl_devices),
                key=_rank,
            )
            self._devices = tuple(info for info, _dev in ranked)
            self._cl_devices = [dev for _info, dev in ranked]
            if self._cl_devices:
                self._selected_device = self._cl_devices[0]
        except Exception:
            self._devices = ()
            self._cl_devices = []

    def _context_for(self, index: int):
        """Cached profiling-ready Context for the ranked device ``index``."""
        assert self._cl is not None
        ctx = self._contexts.get(index)
        if ctx is None:
            ctx = self._cl.Context(devices=[self._cl_devices[index]])
            self._contexts[index] = ctx
        return ctx

    def _queue_for(self, index: int):
        """Cached PROFILING_ENABLE CommandQueue for the ranked device."""
        assert self._cl is not None
        queue = self._queues.get(index)
        if queue is None:
            props = 0
            try:
                props = int(self._cl.command_queue_properties.PROFILING_ENABLE)
            except Exception:
                props = 0
            queue = self._cl.CommandQueue(self._context_for(index), properties=props)
            self._queues[index] = queue
        return queue

    def _program_for(self, index: int, source: str, build_options: Sequence[str]):
        """Cached built program keyed by device + source hash + options."""
        assert self._cl is not None
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        key = (index, source_hash, tuple(build_options))
        program = self._programs.get(key)
        if program is None:
            program = self._cl.Program(self._context_for(index), source).build(
                options=list(build_options)
            )
            self._programs[key] = program
        return program

    @property
    def devices(self) -> tuple[OpenCLDevice, ...]:
        return self._devices

    @property
    def available(self) -> bool:
        return self._cl is not None and bool(self._devices)

    def unavailable_result(self) -> OpenCLExecutionResult:
        return OpenCLExecutionResult.unavailable("opencl")

    def execute_kernel(
        self,
        *,
        source: str,
        kernel_name: str,
        global_size: Sequence[int],
        args: Sequence[Any] = (),
        hashes_computed: int,
        build_options: Sequence[str] = (),
    ) -> OpenCLExecutionResult:
        """Build, dispatch, and finish one actual OpenCL kernel.

        ``hashes_computed`` must be supplied by the caller from the kernel's
        real work contract; this method never estimates it from work-group size.
        """
        if not self.available:
            raise OpenCLUnavailable("no OpenCL device discovered; refusing CPU fallback")
        if not isinstance(source, str) or not source.strip():
            raise OpenCLExecutionRejected("kernel source is required")
        if not isinstance(kernel_name, str) or not kernel_name:
            raise OpenCLExecutionRejected("kernel name is required")
        if hashes_computed < 0 or not global_size or any(int(size) <= 0 for size in global_size):
            raise OpenCLExecutionRejected("invalid kernel work contract")
        assert self._cl is not None
        device = self._selected_device
        if device is None:
            raise OpenCLUnavailable("selected OpenCL device disappeared before dispatch")
        index = self._cl_devices.index(device)
        queue = self._queue_for(index)
        program = self._program_for(index, source, build_options)
        kernel = getattr(program, kernel_name)
        wall_start = time.perf_counter_ns()
        event = kernel(queue, tuple(int(size) for size in global_size), None, *args)
        queue.finish()
        wall_ns = time.perf_counter_ns() - wall_start
        if wall_ns <= 0:
            raise OpenCLExecutionRejected("kernel completed without measurable elapsed time")
        device_ns = 0
        try:
            event.wait()
            device_ns = int(event.profile.end - event.profile.start)
        except Exception:
            device_ns = 0
        clock_source = "cl_event" if device_ns > 0 else "perf_counter"
        elapsed = device_ns / 1e9 if device_ns > 0 else wall_ns / 1e9
        device_info = OpenCLDevice(
            platform=str(device.platform.name),
            name=str(device.name),
            vendor=str(device.vendor),
            version=str(device.version),
        )
        return OpenCLExecutionResult(
            requested_backend="opencl",
            selected_backend="opencl",
            actual_backend="opencl",
            device_name=device_info.name,
            device_available=True,
            hardware_execution=True,
            degraded=False,
            fallback_used=False,
            hashes_computed=int(hashes_computed),
            elapsed_seconds=elapsed,
            measured_hashrate=int(hashes_computed) / elapsed,
            truth_class="measured_hardware",
            device_ns=device_ns,
            wall_ns=int(wall_ns),
            clock_source=clock_source,
        )
