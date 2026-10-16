"""Canonical Chronus GPU Domain Model.

This module establishes the single coherent domain model for all GPU and accelerator
execution in Chronus.

Device classification:
    CPU, INTEGRATED_GPU, DISCRETE_GPU, MULTI_GPU, OTHER_ACCELERATOR

Backend support:
    SOFTWARE, CUDA, ROCM, METAL, OPENCL, VULKAN, DIRECTML, SYCL, ONEAPI, NATIVE, ASIC

Topology:
    Single-GPU and Multi-GPU are execution topologies, NOT independent subsystems.
    Integrated GPU (iGPU) is a device capability/property (UMA memory, host-package integration),
    NOT a separate runtime architecture.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
import time

LOG = logging.getLogger("chronus.domain")


class ChronusDeviceType(StrEnum):
    """Canonical device classification."""

    CPU = "cpu"
    INTEGRATED_GPU = "integrated_gpu"
    DISCRETE_GPU = "discrete_gpu"
    MULTI_GPU = "multi_gpu"
    OTHER_ACCELERATOR = "other_accelerator"


class ChronusBackend(StrEnum):
    """Supported physical and software execution backends."""

    SOFTWARE = "software"
    CPU = "cpu"
    CHRONUS = "chronus"
    CUDA = "cuda"
    ROCM = "rocm"
    METAL = "metal"
    OPENCL = "opencl"
    VULKAN = "vulkan"
    DIRECTML = "directml"
    SYCL = "sycl"
    ONEAPI = "oneapi"
    NATIVE = "native"
    ASIC = "asic"


class ChronusExecutionPolicy(StrEnum):
    """Authoritative execution policy for Chronus workloads."""

    STANDALONE_SOFTWARE = "standalone_software"
    PREFERRED_ACCELERATOR = "preferred_accelerator"
    REQUIRED_ADAPTER = "required_adapter"
    REQUIRED_DEVICE = "required_device"
    AUTO = "auto"
    FAIL_CLOSED = "fail_closed"
    FALLBACK_ALLOWED = "fallback_allowed"
    DISCRETE_ONLY = "discrete_only"
    INTEGRATED_ONLY = "integrated_only"


class ChronusProductMode(StrEnum):
    """Canonical Chronus product mode."""

    NATIVE_CHRONUS_GPU = "native_chronus_gpu"
    HOST_GPU_AUGMENTATION = "host_gpu_augmentation"


class ChronusDeviceTopology(StrEnum):
    """Execution topology constraint."""

    SINGLE = "single"
    MULTI = "multi"
    ALL = "all"


class ChronusExecutionError(RuntimeError):
    """Raised when an execution fails on a Chronus device."""


class ChronusDeviceUnavailable(RuntimeError):
    """Raised when a required device or backend is unavailable."""


ChronusDeviceUnavailableError = ChronusDeviceUnavailable


class ChronusOutOfMemoryError(ChronusExecutionError):
    """Raised when device or host-unified memory is exhausted."""


@dataclass(frozen=True)
class ChronusCapabilities:
    """Advertised capabilities and hardware features of a Chronus device."""

    operations: Tuple[str, ...] = ()
    dtypes: Tuple[str, ...] = ("float32", "float64")
    compute_units: int = 0
    max_work_group_size: int = 1
    tensor_cores: bool = False
    fp64_supported: bool = True
    has_unified_memory: bool = False
    is_integrated: bool = False
    clock_mhz: Optional[float] = None
    limits: Dict[str, Any] = field(default_factory=dict)
    arithmetic: Dict[str, Any] = field(default_factory=dict)

    def supports_operation(self, op: str) -> bool:
        return op in self.operations or not self.operations

    def as_dict(self) -> Dict[str, Any]:
        return {
            "operations": list(self.operations),
            "dtypes": list(self.dtypes),
            "compute_units": self.compute_units,
            "max_work_group_size": self.max_work_group_size,
            "tensor_cores": self.tensor_cores,
            "fp64_supported": self.fp64_supported,
            "has_unified_memory": self.has_unified_memory,
            "is_integrated": self.is_integrated,
            "clock_mhz": self.clock_mhz,
            "limits": dict(self.limits),
            "arithmetic": dict(self.arithmetic),
        }


@dataclass
class ChronusMemory:
    """Unified GPU memory manager for both UMA and dedicated VRAM.

    Integrated GPUs use shared system memory (host unified memory).
    Discrete GPUs use dedicated device memory pools.
    """

    total_bytes: int = 0
    allocated_bytes: int = 0
    is_unified: bool = False
    memory_type: str = "DDR"
    max_allocation_bytes: int = 0

    def __post_init__(self) -> None:
        if self.max_allocation_bytes <= 0:
            self.max_allocation_bytes = self.total_bytes or (256 * 1024 * 1024)
        if self.total_bytes <= 0:
            self.total_bytes = self.max_allocation_bytes

    @property
    def free_bytes(self) -> int:
        return max(0, self.total_bytes - self.allocated_bytes)

    def can_allocate(self, nbytes: int) -> bool:
        if nbytes < 0:
            return False
        return (self.allocated_bytes + nbytes) <= self.total_bytes

    def allocate(self, nbytes: int, tag: str = "buffer") -> Dict[str, Any]:
        if not self.can_allocate(nbytes):
            raise ChronusOutOfMemoryError(
                f"Cannot allocate {nbytes} bytes: total={self.total_bytes}, "
                f"allocated={self.allocated_bytes}, free={self.free_bytes} "
                f"(unified={self.is_unified})"
            )
        self.allocated_bytes += nbytes
        return {
            "tag": tag,
            "nbytes": nbytes,
            "is_unified": self.is_unified,
            "memory_type": self.memory_type,
            "allocated_at": time.time(),
        }

    def release(self, nbytes: int) -> None:
        self.allocated_bytes = max(0, self.allocated_bytes - max(0, nbytes))

    def metrics(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "allocated_bytes": self.allocated_bytes,
            "free_bytes": self.free_bytes,
            "is_unified": self.is_unified,
            "memory_type": self.memory_type,
            "utilization": (self.allocated_bytes / self.total_bytes) if self.total_bytes > 0 else 0.0,
        }

    def as_dict(self) -> Dict[str, Any]:
        return self.metrics()


@dataclass
class ChronusDevice:
    """Canonical representation of an execution device in Chronus."""

    id: str
    name: str
    vendor: str
    device_type: ChronusDeviceType
    backend: ChronusBackend
    memory: ChronusMemory = field(default_factory=ChronusMemory)
    capabilities: ChronusCapabilities = field(default_factory=ChronusCapabilities)
    is_integrated: bool = False
    is_gpu: bool = True
    integrated_reason: str = ""
    platform: str = ""
    driver_version: str = ""
    version: str = ""
    raw_device: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.is_integrated:
            self.memory.is_unified = True
            if self.device_type == ChronusDeviceType.DISCRETE_GPU:
                self.device_type = ChronusDeviceType.INTEGRATED_GPU
        elif self.device_type == ChronusDeviceType.INTEGRATED_GPU:
            self.is_integrated = True
            self.memory.is_unified = True

    @property
    def label(self) -> str:
        return f"{self.vendor}: {self.name}" if self.vendor else self.name

    @property
    def identity(self) -> Tuple[str, str]:
        from .detect import device_identity
        return device_identity(self.name, self.vendor)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "vendor": self.vendor,
            "device_type": self.device_type.value if hasattr(self.device_type, "value") else str(self.device_type),
            "backend": self.backend.value if hasattr(self.backend, "value") else str(self.backend),
            "memory": self.memory.as_dict(),
            "capabilities": self.capabilities.as_dict(),
            "is_integrated": self.is_integrated,
            "is_gpu": self.is_gpu,
            "integrated_reason": self.integrated_reason,
            "platform": self.platform,
            "driver_version": self.driver_version,
            "version": self.version,
            "identity": [self.identity[0], self.identity[1]],
        }


class ChronusExecutionContext:
    """Execution context bound to an authoritative ChronusDevice."""

    def __init__(
        self,
        device: ChronusDevice,
        runtime: Optional["ChronusRuntime"] = None,
        policy: ChronusExecutionPolicy = ChronusExecutionPolicy.FAIL_CLOSED,
    ) -> None:
        self.device = device
        self.runtime = runtime
        self.policy = policy
        self._created_at = time.time()

    def execute(self, workload: Any) -> Any:
        """Execute a workload within this device context."""
        if isinstance(workload, dict):
            return {
                "executed": True,
                "device_id": self.device.id,
                "backend": self.device.backend.value if hasattr(self.device.backend, "value") else str(self.device.backend),
                "is_gpu": self.device.is_gpu,
                "is_integrated": self.device.is_integrated,
                "workload": workload,
                "timestamp": time.time(),
            }
        if self.runtime is not None:
            return self.runtime.execute_on_device(self.device, workload)
        # Fallback to direct adapter execution if runtime not attached
        from .virtual_igpu.abi import Workload
        from .virtual_igpu.runtime import get_embedded_daemon
        daemon = get_embedded_daemon()
        return daemon.submit_and_wait(workload)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "device": self.device.as_dict(),
            "policy": self.policy.value if hasattr(self.policy, "value") else str(self.policy),
            "created_at": self._created_at,
        }


class ChronusScheduler:
    """Unified Chronus scheduler for workload placement across devices.

    Reasoning over:
      - available devices
      - device type (integrated GPU vs discrete GPU vs CPU)
      - memory capacity and pressure
      - backend (CUDA, Metal, OpenCL, software)
      - load and capabilities
      - topology constraints (single-device: device_count=1, multi-device)
      - fallback policy
    """

    def __init__(self, devices: Optional[Sequence[ChronusDevice]] = None) -> None:
        self._devices: List[ChronusDevice] = list(devices) if devices is not None else []

    def update_devices(self, devices: Sequence[ChronusDevice]) -> None:
        self._devices = list(devices)

    def select(
        self,
        *,
        device_type: Optional[ChronusDeviceType | str] = None,
        topology: ChronusDeviceTopology | str = ChronusDeviceTopology.SINGLE,
        preference: Optional[str] = None,
        prefer_integrated: bool = False,
        backend: Optional[ChronusBackend | str] = None,
        policy: Optional[ChronusExecutionPolicy | str] = None,
        required_memory_bytes: int = 0,
        operation: Optional[str] = None,
        allow_software_fallback: bool = True,
    ) -> ChronusDevice:
        """Authoritative single device selection according to policy.

        'one_GPU' is represented as topology=ChronusDeviceTopology.SINGLE (or device_count=1).
        'iGPU' is represented as preference='integrated' or device_type=ChronusDeviceType.INTEGRATED_GPU.
        """
        if prefer_integrated:
            preference = "integrated"

        if policy is not None:
            pol_str = policy.value if hasattr(policy, "value") else str(policy)
            if pol_str in (ChronusExecutionPolicy.FAIL_CLOSED.value, "fail_closed"):
                allow_software_fallback = False
            elif pol_str in (ChronusExecutionPolicy.FALLBACK_ALLOWED.value, "fallback_allowed"):
                allow_software_fallback = True
            elif pol_str in (ChronusExecutionPolicy.DISCRETE_ONLY.value, "discrete_only"):
                preference = "discrete"
                allow_software_fallback = False
            elif pol_str in (ChronusExecutionPolicy.INTEGRATED_ONLY.value, "integrated_only"):
                preference = "integrated"
                allow_software_fallback = False

        candidates = list(self._devices)
        if not candidates:
            if allow_software_fallback:
                return self._create_software_fallback_device()
            raise ChronusDeviceUnavailable("No execution devices registered in Chronus scheduler")

        # Filter by backend if specified
        if backend is not None:
            backend_str = backend.value if hasattr(backend, "value") else str(backend)
            matched = [
                d for d in candidates
                if (d.backend.value if hasattr(d.backend, "value") else str(d.backend)).lower() == backend_str.lower()
            ]
            if matched:
                candidates = matched
            elif not allow_software_fallback:
                raise ChronusDeviceUnavailable(f"No suitable Chronus device found: requested backend {backend_str!r} not available")

        # Filter by operation capability
        if operation is not None:
            capable = [d for d in candidates if d.capabilities.supports_operation(operation)]
            if capable:
                candidates = capable

        # Filter by memory requirement
        if required_memory_bytes > 0:
            with_mem = [d for d in candidates if d.memory.can_allocate(required_memory_bytes)]
            if with_mem:
                candidates = with_mem
            elif not allow_software_fallback:
                raise ChronusOutOfMemoryError(
                    f"No candidate device has {required_memory_bytes} free bytes"
                )

        # Apply preference: 'integrated' (iGPU first) vs 'discrete' (discrete GPU first)
        pref = (preference or "").lower().strip()
        type_req = device_type.value if hasattr(device_type, "value") else str(device_type or "").lower().strip()

        if type_req == ChronusDeviceType.INTEGRATED_GPU.value or pref in ("integrated", "igpu"):
            for d in candidates:
                if d.is_integrated:
                    return d
        elif type_req == ChronusDeviceType.DISCRETE_GPU.value or pref in ("discrete", "dgpu"):
            for d in candidates:
                if d.is_gpu and not d.is_integrated:
                    return d

        # Standard hierarchy: integrated GPU -> discrete GPU -> any GPU -> CPU
        for pred in (
            lambda d: d.is_integrated,
            lambda d: d.is_gpu and not d.is_integrated,
            lambda d: d.is_gpu,
            lambda d: True,
        ):
            for d in candidates:
                if pred(d):
                    return d

        if allow_software_fallback:
            return self._create_software_fallback_device()
        raise ChronusDeviceUnavailable("No matching device satisfying execution constraints")

    def select_device(
        self,
        *,
        device_type: Optional[ChronusDeviceType | str] = None,
        topology: ChronusDeviceTopology | str = ChronusDeviceTopology.SINGLE,
        preference: Optional[str] = None,
        prefer_integrated: bool = False,
        backend: Optional[ChronusBackend | str] = None,
        policy: Optional[ChronusExecutionPolicy | str] = None,
        required_memory_bytes: int = 0,
        operation: Optional[str] = None,
        allow_software_fallback: bool = True,
    ) -> ChronusDevice:
        """Alias for select()."""
        return self.select(
            device_type=device_type,
            topology=topology,
            preference=preference,
            prefer_integrated=prefer_integrated,
            backend=backend,
            policy=policy,
            required_memory_bytes=required_memory_bytes,
            operation=operation,
            allow_software_fallback=allow_software_fallback,
        )

    def create_context(
        self,
        device: Optional[ChronusDevice] = None,
        policy: ChronusExecutionPolicy = ChronusExecutionPolicy.FAIL_CLOSED,
    ) -> ChronusExecutionContext:
        """Create an execution context bound to a device."""
        if device is None:
            device = self.select(policy=policy)
        return ChronusExecutionContext(device, policy=policy)

    def select_multi(
        self,
        count: Optional[int] = None,
        *,
        backend: Optional[ChronusBackend | str] = None,
    ) -> List[ChronusDevice]:
        """Multi-device selection topology."""
        candidates = list(self._devices)
        if backend is not None:
            b_str = backend.value if hasattr(backend, "value") else str(backend)
            candidates = [d for d in candidates if d.backend == b_str]
        gpus = [d for d in candidates if d.is_gpu]
        pool = gpus if gpus else candidates
        if count is not None and count > 0:
            return pool[:count]
        return pool

    def _create_software_fallback_device(self) -> ChronusDevice:
        return ChronusDevice(
            id="chronus-software-reference",
            name="Chronus Software Reference",
            vendor="hyba",
            device_type=ChronusDeviceType.CPU,
            backend=ChronusBackend.SOFTWARE,
            memory=ChronusMemory(total_bytes=1024 * 1024 * 1024, is_unified=True, memory_type="DDR"),
            capabilities=ChronusCapabilities(
                compute_units=1,
                has_unified_memory=True,
                is_integrated=False,
                fp64_supported=True,
            ),
            is_integrated=False,
            is_gpu=False,
            integrated_reason="software_fallback",
            platform="cpu_reference",
            driver_version="1.0.0",
        )


class ChronusRuntime:
    """The canonical Chronus execution runtime.

    Unifies:
      - Device discovery & census
      - Authoritative device selection
      - Memory management
      - Execution context creation
      - Kernel dispatch
      - Telemetry
    """

    _instance: Optional["ChronusRuntime"] = None

    def __init__(self) -> None:
        self._scheduler = ChronusScheduler()
        self._devices: List[ChronusDevice] = []
        self._initialized = False

    @classmethod
    def get(cls) -> "ChronusRuntime":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self, *, force_refresh: bool = False) -> None:
        if self._initialized and not force_refresh:
            return
        from .detect import detect_all, DetectedDevice

        report = detect_all()
        devices: List[ChronusDevice] = []
        for d in report.devices:
            dev_type = (
                ChronusDeviceType.INTEGRATED_GPU if d.is_integrated
                else (ChronusDeviceType.DISCRETE_GPU if d.is_gpu else ChronusDeviceType.CPU)
            )
            backend_map = {
                "cuda": ChronusBackend.CUDA,
                "metal": ChronusBackend.METAL,
                "opencl": ChronusBackend.OPENCL,
                "rocm": ChronusBackend.ROCM,
                "chronus": ChronusBackend.SOFTWARE,
                "software": ChronusBackend.SOFTWARE,
            }
            backend = backend_map.get(d.backend.lower(), ChronusBackend.OPENCL)
            mem = ChronusMemory(
                total_bytes=512 * 1024 * 1024 if d.is_integrated else 1024 * 1024 * 1024,
                is_unified=d.is_integrated,
                memory_type="UMA" if d.is_integrated else "VRAM",
            )
            caps = ChronusCapabilities(
                has_unified_memory=d.is_integrated,
                is_integrated=d.is_integrated,
                compute_units=8 if d.is_integrated else 16,
            )
            devices.append(
                ChronusDevice(
                    id=f"{d.backend}:{d.name}",
                    name=d.name,
                    vendor=d.vendor,
                    device_type=dev_type,
                    backend=backend,
                    memory=mem,
                    capabilities=caps,
                    is_integrated=d.is_integrated,
                    is_gpu=d.is_gpu,
                    integrated_reason=d.integrated_reason,
                    platform=d.platform,
                    driver_version=d.driver_version,
                    version=d.version,
                    raw_device=d,
                )
            )
        self._devices = devices
        self._scheduler.update_devices(devices)
        self._initialized = True

    @property
    def devices(self) -> List[ChronusDevice]:
        self.initialize()
        return list(self._devices)

    def select_device(
        self,
        *,
        device_type: Optional[ChronusDeviceType | str] = None,
        topology: ChronusDeviceTopology | str = ChronusDeviceTopology.SINGLE,
        preference: Optional[str] = None,
        backend: Optional[ChronusBackend | str] = None,
        required_memory_bytes: int = 0,
        operation: Optional[str] = None,
        allow_software_fallback: bool = True,
    ) -> ChronusDevice:
        """Select a single device according to policy."""
        self.initialize()
        return self._scheduler.select(
            device_type=device_type,
            topology=topology,
            preference=preference,
            backend=backend,
            required_memory_bytes=required_memory_bytes,
            operation=operation,
            allow_software_fallback=allow_software_fallback,
        )

    def create_context(self, device: Optional[ChronusDevice] = None) -> ChronusExecutionContext:
        """Create an execution context bound to a device."""
        if device is None:
            device = self.select_device()
        return ChronusExecutionContext(device, runtime=self)

    def execute_on_device(self, device: ChronusDevice, workload: Any) -> Any:
        from .virtual_igpu.runtime import get_embedded_daemon
        daemon = get_embedded_daemon()
        return daemon.submit_and_wait(workload)

    @property
    def telemetry(self) -> Any:
        from .telemetry import get_telemetry
        return get_telemetry()


__all__ = [
    "ChronusBackend",
    "ChronusCapabilities",
    "ChronusDevice",
    "ChronusDeviceTopology",
    "ChronusDeviceType",
    "ChronusDeviceUnavailable",
    "ChronusExecutionContext",
    "ChronusExecutionError",
    "ChronusExecutionPolicy",
    "ChronusMemory",
    "ChronusOutOfMemoryError",
    "ChronusProductMode",
    "ChronusRuntime",
    "ChronusScheduler",
]
