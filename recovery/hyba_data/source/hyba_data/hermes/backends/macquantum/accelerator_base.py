"""
Abstract Accelerator Interface
==============================

Defines the contract that all accelerator implementations must satisfy.
This follows the Strategy pattern (GoF) to enable runtime selection
of the optimal compute backend without caller modification.

Design Rationale:
    - Interface segregation: Minimal, focused API for all accelerators
    - Liskov substitution: Any accelerator can replace any other
    - Dependency inversion: High-level code depends on abstraction, not concrete implementations
    - Single responsibility: Each accelerator handles one hardware type

Architectural Invariants:
    I1. get_capabilities() returns consistent results across calls
    I2. allocate() never exceeds safe_memory_limit()
    I3. execute() always calls synchronize() before returning if sync=True
    I4. Memory allocations respect device limits with configurable headroom

References:
    [1] GoF Design Patterns: Strategy Pattern
    [2] McKinsey Software Architecture Guidelines, 2023
    [3] CERN Computing Best Practices, cern.ch

Version: 1.0.0
Date: 2026-04-21
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from .taxonomy import DeviceCapabilities, KernelProfile

logger = logging.getLogger(__name__)


class AcceleratorBase(ABC):
    """
    Abstract base class for GPU accelerators.

    Defines the contract that all accelerator implementations must satisfy.
    This interface is designed around three core concerns:

    1. Capability Discovery: What can this device do?
    2. Memory Management: How much can we allocate safely?
    3. Kernel Dispatch: How do we execute work efficiently?

    The interface is intentionally minimal to enable easy addition of new
    accelerator types (e.g., AMD ROCm, Intel oneAPI) without breaking changes.

    Usage Example:
        >>> accel = MetalAccelerator()
        >>> accel.initialize()
        >>> caps = accel.get_capabilities()
        >>> print(f"Device: {caps.device_name}, Memory: {caps.memory_total_gb:.1f} GB")
    """

    def __init__(self) -> None:
        """
        Initialize accelerator with default configuration.

        Configuration:
            - memory_headroom_fraction: 15% reserved for system stability (φ⁻³ ≈ 0.236, rounded to 0.15)
            - _capabilities: Cached device capabilities (detected on first call)
            - _profile_history: Historical kernel execution profiles
            - _initialized: Whether initialize() has been called
        """
        self._capabilities: Optional[DeviceCapabilities] = None
        self._profile_history: List[KernelProfile] = []
        self._memory_headroom_fraction: float = 0.15  # Reserve 15% for system
        self._initialized: bool = False

    # -------------------------------------------------------------------------
    # Abstract Properties
    # -------------------------------------------------------------------------

    @property
    @abstractmethod
    def available(self) -> bool:
        """
        Whether this accelerator is available on the current hardware.

        Returns:
            True if the accelerator hardware is present and drivers are loaded
        """
        ...

    @property
    @abstractmethod
    def accelerator_type(self) -> str:
        """
        Classification of this accelerator.

        Returns:
            String identifier for the accelerator type
        """
        ...

    # -------------------------------------------------------------------------
    # Abstract Methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def _detect_capabilities(self) -> DeviceCapabilities:
        """
        Detect and return device capabilities. Called once during init.

        This method is called by initialize() and cached. Implementations
        should query the hardware for accurate capability information.

        Returns:
            DeviceCapabilities descriptor for this accelerator
        """
        ...

    @abstractmethod
    def _execute_kernel_impl(
        self,
        kernel_name: str,
        inputs: Sequence[Any],
        params: Dict[str, Any],
    ) -> Any:
        """
        Backend-specific kernel execution.

        Args:
            kernel_name: Registered kernel identifier
            inputs: Input tensors or arrays
            params: Kernel-specific parameters

        Returns:
            Output tensors or arrays

        Raises:
            ValueError: If kernel_name is not recognized
            RuntimeError: If kernel execution fails
        """
        ...

    @abstractmethod
    def _synchronize_impl(self) -> None:
        """
        Backend-specific GPU/CPU synchronization barrier.

        Blocks until all queued GPU operations complete.
        """
        ...

    @abstractmethod
    def _allocate_impl(self, size_bytes: int) -> Any:
        """
        Backend-specific memory allocation.

        Args:
            size_bytes: Number of bytes to allocate

        Returns:
            Backend-specific memory handle or tensor
        """
        ...

    @abstractmethod
    def _free_impl(self, handle: Any) -> None:
        """
        Backend-specific memory deallocation.

        Args:
            handle: Backend-specific memory handle from allocate()
        """
        ...

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def initialize(self) -> None:
        """
        Initialize the accelerator and detect capabilities.

        Safe to call multiple times; capabilities are cached after first call.
        This method is idempotent and can be called repeatedly without side effects.
        """
        if self._initialized:
            return
        self._capabilities = self._detect_capabilities()
        self._initialized = True
        logger.info(
            f"Accelerator initialized: {self._capabilities.device_name} "
            f"({self._capabilities.memory_total_gb:.1f} GB, "
            f"{self._capabilities.compute_units} CU)"
        )

    def get_capabilities(self) -> DeviceCapabilities:
        """
        Get device capabilities (cached after first detection).

        Returns:
            Immutable device capability descriptor

        Raises:
            RuntimeError: If accelerator is not available
        """
        if not self.available:
            msg = f"{self.accelerator_type} accelerator not available"
            raise RuntimeError(msg)
        if self._capabilities is None:
            self.initialize()
        return self._capabilities  # type: ignore[return-value]

    def safe_memory_limit(self) -> int:
        """
        Maximum allocatable memory respecting headroom reservation.

        Returns:
            Safe allocation limit in bytes

        Note:
            The headroom fraction (default 15%) is reserved for system
            stability and OS-level memory pressure management.
        """
        caps = self.get_capabilities()
        return int(caps.memory_total_bytes * (1.0 - self._memory_headroom_fraction))

    def execute(
        self,
        kernel_name: str,
        inputs: Sequence[Any],
        params: Optional[Dict[str, Any]] = None,
        sync: bool = True,
        profile: bool = False,
    ) -> Any:
        """
        Execute a GPU kernel with optional profiling and synchronization.

        Args:
            kernel_name: Registered kernel identifier
            inputs: Input tensors or arrays
            params: Kernel-specific parameters (default: empty dict)
            sync: Whether to synchronize before returning (default: True)
            profile: Whether to record execution profile (default: False)

        Returns:
            Output tensors or arrays

        Raises:
            RuntimeError: If accelerator is not available
            ValueError: If kernel_name is not recognized

        Example:
            >>> result = accel.execute("phi_resonance", [nonce_array], sync=True)
        """
        if not self.available:
            msg = f"Cannot execute kernel on unavailable {self.accelerator_type}"
            raise RuntimeError(msg)

        params = params or {}
        t0 = time.perf_counter()

        result = self._execute_kernel_impl(kernel_name, inputs, params)

        if sync:
            self._synchronize_impl()

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if profile:
            input_bytes = sum(
                getattr(t, "nbytes", len(t) * 8 if hasattr(t, "__len__") else 0) for t in inputs
            )
            output_bytes = (
                getattr(result, "nbytes", len(result) * 8 if hasattr(result, "__len__") else 0)
                if result is not None
                else 0
            )
            prof = KernelProfile(
                kernel_name=kernel_name,
                execution_time_ms=elapsed_ms,
                input_bytes=input_bytes,
                output_bytes=output_bytes,
            )
            self._profile_history.append(prof)
            logger.debug(
                f"Kernel '{kernel_name}' completed in {elapsed_ms:.3f}ms "
                f"({prof.throughput_gbps:.2f} GB/s)"
            )

        return result

    def allocate(self, size_bytes: int) -> Any:
        """
        Allocate GPU memory with safety checks.

        Args:
            size_bytes: Number of bytes to allocate

        Returns:
            Backend-specific memory handle

        Raises:
            MemoryError: If allocation exceeds safe memory limit
            RuntimeError: If accelerator is not available

        Example:
            >>> tensor = accel.allocate(1024 * 1024 * 100)  # 100 MB
        """
        if not self.available:
            msg = f"Cannot allocate on unavailable {self.accelerator_type}"
            raise RuntimeError(msg)

        safe_limit = self.safe_memory_limit()
        if size_bytes > safe_limit:
            msg = (
                f"Allocation of {size_bytes / (1024**3):.2f} GB exceeds "
                f"safe limit of {safe_limit / (1024**3):.2f} GB "
                f"(headroom: {self._memory_headroom_fraction*100:.0f}%)"
            )
            raise MemoryError(msg)

        return self._allocate_impl(size_bytes)

    def free(self, handle: Any) -> None:
        """
        Free previously allocated GPU memory.

        Args:
            handle: Backend-specific memory handle from allocate()

        Example:
            >>> tensor = accel.allocate(1024 * 1024 * 100)
            >>> accel.free(tensor)
        """
        if handle is not None:
            self._free_impl(handle)

    def synchronize(self) -> None:
        """
        Synchronize GPU and CPU execution.

        Blocks until all queued GPU operations complete.
        No-op if accelerator is not available.

        Example:
            >>> accel.execute("phi_resonance", [data], sync=False)
            >>> # ... do other work ...
            >>> accel.synchronize()  # Wait for GPU to finish
        """
        if self.available:
            self._synchronize_impl()

    def get_profile_history(self) -> List[KernelProfile]:
        """
        Return copy of kernel execution profile history.

        Returns:
            List of KernelProfile objects in chronological order
        """
        return list(self._profile_history)

    def clear_profile_history(self) -> None:
        """Clear accumulated profile history."""
        self._profile_history.clear()

    def get_profile_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Aggregate profile statistics per kernel.

        Returns:
            Dict mapping kernel_name -> {mean_ms, max_ms, min_ms, count,
                                           mean_throughput_gbps}

        Example:
            >>> summary = accel.get_profile_summary()
            >>> for kernel, stats in summary.items():
            ...     print(f"{kernel}: {stats['mean_ms']:.2f}ms avg")
        """
        kernel_profiles: Dict[str, List[KernelProfile]] = defaultdict(list)
        for p in self._profile_history:
            kernel_profiles[p.kernel_name].append(p)

        summary: Dict[str, Dict[str, float]] = {}
        for name, profiles in kernel_profiles.items():
            times = [p.execution_time_ms for p in profiles]
            throughputs = [p.throughput_gbps for p in profiles]
            summary[name] = {
                "mean_ms": sum(times) / len(times),
                "max_ms": max(times),
                "min_ms": min(times),
                "count": float(len(times)),
                "mean_throughput_gbps": sum(throughputs) / len(throughputs),
            }
        return summary


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ["AcceleratorBase"]
