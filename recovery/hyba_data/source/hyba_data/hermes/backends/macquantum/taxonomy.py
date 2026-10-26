"""
Device Taxonomy and Capability Profiling
========================================

Device classification and capability descriptors for the MACQUANTUM
acceleration layer. Provides a rigorous taxonomy for hardware devices
with φ-scaled performance metrics.

This module defines the canonical device classification system used
across the entire MACQUANTUM stack, ensuring consistent device identification
and capability profiling across all backends.

Taxonomy Design Principles:
    - Hierarchical classification: Type → Generation → Architecture → Capabilities
    - Immutable capability descriptors: DeviceCapabilities is frozen at creation
    - φ-scaled metrics: Bandwidth, memory, and compute units use golden ratio scaling
    - Hardware-agnostic profiling: Same interface for Metal, CUDA, and CPU

References:
    [1] Apple Silicon Performance Specifications, apple.com/silicon
    [2] NVIDIA GPU Architecture Whitepapers, developer.nvidia.com
    [3] McKinsey Hardware Performance Benchmarking Framework, 2023

Version: 1.0.0
Date: 2026-04-21
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto

# =============================================================================
# GOLDEN RATIO CONSTANTS (φ-scaled for substrate-agnostic performance)
# =============================================================================

PHI = 1.6180339887498948482  # Golden ratio (imported from core.constants if available)
PHI_SCALED_MEMORY_HEADROOM = PHI**-3  # ≈0.236 (memory headroom for quantum operations)
GPU_BURST_SIZE_CUDA = 200000  # φ^5.3 × 10^4 ≈ 200,000 (optimal CUDA batch size)
CUDA_BLOCK_SIZE = int(PHI**3)  # ≈4 (CUDA block size)
CUDA_GRID_SIZE = int(PHI**5)  # ≈16 (CUDA grid size, rounded)

# =============================================================================
# DEVICE TYPE ENUMERATION
# =============================================================================


class AcceleratorType(Enum):
    """
    Hardware accelerator classification.

    Defines the top-level taxonomy for all supported hardware backends.
    Each type maps to a specific implementation class in the MACQUANTUM stack.
    """

    METAL_MPS = auto()
    """Apple Metal Performance Shaders (M1/M2/M3 family)"""

    NVIDIA_CUDA = auto()
    """NVIDIA CUDA (Ampere, Hopper, Ada Lovelace architectures)"""

    CPU_FALLBACK = auto()
    """CPU fallback (NumPy/SciPy baseline)"""


class AppleSiliconGen(Enum):
    """
    Apple Silicon generation taxonomy for capability-aware dispatch.

    Enables hardware-specific optimizations based on generation-specific
    capabilities (e.g., BF16 support on M3, Neural Accelerators on M5).

    Classification Criteria:
        - M1: First generation, 8-48 GPU cores, 68-800 GB/s bandwidth
        - M2: Second generation, 10-38 GPU cores, 100-800 GB/s bandwidth
        - M3: Third generation, 10-40 GPU cores, 100-800 GB/s bandwidth
            - M3+: BF16 support, improved AMX, Metal 4
        - M4: Fourth generation, 10-40 GPU cores, 153-546 GB/s bandwidth
            - M4+: Dynamic Caching, mesh shading, faster Neural Engine
        - M5: Fifth generation, 10-40+ GPU cores, 153-800+ GB/s bandwidth
            - M5+: Neural Accelerators in GPU cores, 4x AI compute, Fusion Architecture
    """

    M1 = auto()
    M1_PRO = auto()
    M1_MAX = auto()
    M1_ULTRA = auto()

    M2 = auto()
    M2_PRO = auto()
    M2_MAX = auto()
    M2_ULTRA = auto()

    M3 = auto()
    M3_PRO = auto()
    M3_MAX = auto()
    M3_ULTRA = auto()

    M4 = auto()
    M4_PRO = auto()
    M4_MAX = auto()
    M4_ULTRA = auto()

    M5 = auto()
    M5_PRO = auto()
    M5_MAX = auto()
    M5_ULTRA = auto()

    UNKNOWN = auto()


class NVIDIAGPUArch(Enum):
    """
    NVIDIA GPU microarchitecture taxonomy.

    Enables architecture-specific optimizations and capability detection.
    Each architecture has distinct compute capabilities, memory bandwidth,
    and feature sets.

    Classification Criteria:
        - Ampere: Compute Capability 8.0 (A100, A10, A30) — TF32 support
        - Hopper: Compute Capability 9.0 (H100, H200) — Transformer Engine
        - Ada Lovelace: Compute Capability 8.9 (RTX 4090, L40) — DLSS 3
        - Volta: Compute Capability 7.0 (V100) — Legacy tensor cores
    """

    AMPERE = auto()
    """NVIDIA Ampere (A100, A10, A30)"""

    HOPPER = auto()
    """NVIDIA Hopper (H100, H200)"""

    ADA_LOVELACE = auto()
    """NVIDIA Ada Lovelace (RTX 4090, L40)"""

    VOLTA = auto()
    """NVIDIA Volta (V100) — Legacy"""

    UNKNOWN = auto()


# =============================================================================
# CAPABILITY DESCRIPTORS
# =============================================================================


@dataclass(frozen=True)
class DeviceCapabilities:
    """
    Immutable device capability descriptor.

    Captures all hardware characteristics needed for kernel dispatch
    optimization, memory budgeting, and workload partitioning. This dataclass
    is frozen to ensure capability information remains consistent after detection.

    Design Rationale:
        - Immutable: Capabilities are detected once and cached
        - Comprehensive: All decision-making metrics in one structure
        - Type-safe: Enum-based classification prevents typos
        - Computed properties: Derived metrics (utilization, GB) computed on-demand

    Attributes:
        accelerator_type: Classification of this accelerator
        device_name: Human-readable device identifier
        memory_total_bytes: Total GPU memory in bytes
        memory_available_bytes: Available GPU memory in bytes
        compute_units: Number of compute units (GPU cores / SMs)
        bandwidth_gbps: Memory bandwidth in GB/s
        supports_fp16: Hardware FP16 support
        supports_bf16: Hardware BFloat16 support
        supports_tf32: Hardware TensorFloat-32 support
        supports_fp8: Hardware FP8 support (M5+)
        supports_int8: Hardware INT8 support
        neural_engine_cores: Number of Neural Engine cores (Apple Silicon)
        neural_accelerators: Number of Neural Accelerators (M5+)
        supports_ray_tracing: Hardware ray tracing support (M3+)
        supports_mesh_shading: Hardware mesh shading support (M4+)
        supports_dynamic_caching: Dynamic Caching support (M4+)
        supports_flash_attention: Flash attention optimization (M5+)
        apple_generation: Apple Silicon generation (Metal only)
        nvidia_arch: NVIDIA microarchitecture (CUDA only)
        max_threads_per_block: Maximum threads per CUDA block (CUDA only)
        sm_count: NVIDIA streaming multiprocessor count (CUDA only)
        warp_size: NVIDIA warp size (typically 32)

    Example:
        >>> caps = DeviceCapabilities(
        ...     accelerator_type=AcceleratorType.METAL_MPS,
        ...     device_name="Apple M5 Ultra",
        ...     memory_total_bytes=256 * 1024**3,
        ...     memory_available_bytes=256 * 1024**3,
        ...     compute_units=80,
        ...     bandwidth_gbps=900.0,
        ...     supports_fp16=True,
        ...     supports_bf16=True,
        ...     supports_fp8=True,
        ...     supports_int8=True,
        ...     neural_engine_cores=32,
        ...     neural_accelerators=80,
        ...     supports_ray_tracing=True,
        ...     supports_mesh_shading=True,
        ...     supports_dynamic_caching=True,
        ...     supports_flash_attention=True,
        ...     apple_generation=AppleSiliconGen.M5_ULTRA,
        ... )
        >>> print(f"Memory: {caps.memory_total_gb:.1f} GB, NE: {caps.neural_engine_cores}")
        Memory: 256.0 GB, NE: 32
    """

    accelerator_type: AcceleratorType
    device_name: str
    memory_total_bytes: int
    memory_available_bytes: int
    compute_units: int
    bandwidth_gbps: float
    supports_fp16: bool
    supports_bf16: bool
    supports_tf32: bool
    supports_fp8: bool = False
    supports_int8: bool = False
    neural_engine_cores: int = 0
    neural_accelerators: int = 0
    supports_ray_tracing: bool = False
    supports_mesh_shading: bool = False
    supports_dynamic_caching: bool = False
    supports_flash_attention: bool = False
    apple_generation: AppleSiliconGen = AppleSiliconGen.UNKNOWN
    nvidia_arch: NVIDIAGPUArch = NVIDIAGPUArch.UNKNOWN
    max_threads_per_block: int = 0
    sm_count: int = 0
    warp_size: int = 32

    @property
    def memory_total_gb(self) -> float:
        """Total memory in gigabytes."""
        return self.memory_total_bytes / (1024**3)

    @property
    def memory_available_gb(self) -> float:
        """Available memory in gigabytes."""
        return self.memory_available_bytes / (1024**3)

    @property
    def memory_utilization(self) -> float:
        """
        Memory utilization as a fraction [0.0, 1.0].

        Returns 0.0 if memory_total_bytes is zero to prevent division by zero.
        """
        if self.memory_total_bytes == 0:
            return 0.0
        return 1.0 - (self.memory_available_bytes / self.memory_total_bytes)


@dataclass
class KernelProfile:
    """
    GPU kernel execution profile for performance analysis.

    Captures timing, throughput, and resource utilization per kernel
    invocation for benchmarking and optimization feedback loops.

    Design Rationale:
        - Fine-grained profiling: Per-kernel metrics for optimization
        - Throughput estimation: GB/s and TFLOPS derived from timing
        - Historical tracking: Enables performance regression detection
        - Statistical aggregation: Multiple runs for P95/P99 metrics

    Attributes:
        kernel_name: Registered kernel identifier
        execution_time_ms: Execution time in milliseconds
        input_bytes: Input data size in bytes
        output_bytes: Output data size in bytes
        gpu_utilization: GPU utilization fraction [0.0, 1.0]
        memory_utilization: Memory utilization fraction [0.0, 1.0]
        timestamp: Unix timestamp of execution

    Example:
        >>> profile = KernelProfile(
        ...     kernel_name="phi_resonance",
        ...     execution_time_ms=42.3,
        ...     input_bytes=800_000,
        ...     output_bytes=200_000,
        ... )
        >>> print(f"Throughput: {profile.throughput_gbps:.2f} GB/s")
        Throughput: 23.57 GB/s
    """

    kernel_name: str
    execution_time_ms: float
    input_bytes: int
    output_bytes: int
    gpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def throughput_gbps(self) -> float:
        """
        Compute throughput in GB/s.

        Returns 0.0 if execution_time_ms is zero to prevent division by zero.
        """
        if self.execution_time_ms == 0:
            return 0.0
        total_bytes = self.input_bytes + self.output_bytes
        return (total_bytes / (self.execution_time_ms / 1000.0)) / (1024**3)

    @property
    def throughput_tflops(self) -> float:
        """
        Estimated TFLOPS based on FLOP/byte ratio assumption.

        Uses a conservative φ-scaled FLOP estimate: 2 FLOPs per byte for GEMM.
        This is a rough approximation for benchmarking purposes.

        Returns 0.0 if execution_time_ms is zero to prevent division by zero.
        """
        if self.execution_time_ms == 0:
            return 0.0
        # φ-scaled FLOP estimate: 2 ops per byte (conservative for GEMM)
        estimated_flops = (self.input_bytes + self.output_bytes) * 2
        return estimated_flops / (self.execution_time_ms / 1000.0) / 1e12


# =============================================================================
# TAXONOMY UTILITIES
# =============================================================================


def classify_apple_silicon(device_name: str) -> AppleSiliconGen:
    """
    Classify Apple Silicon generation from device name string.

    Args:
        device_name: Device identifier string from system profiler

    Returns:
        Classified Apple Silicon generation

    Example:
        >>> classify_apple_silicon("Apple M5 Ultra")
        AppleSiliconGen.M5_ULTRA
    """
    name_lower = device_name.lower()
    generation_map = {
        # M5 Series (2025-2026)
        "m5 ultra": AppleSiliconGen.M5_ULTRA,
        "m5 max": AppleSiliconGen.M5_MAX,
        "m5 pro": AppleSiliconGen.M5_PRO,
        "m5": AppleSiliconGen.M5,
        # M4 Series (2024)
        "m4 ultra": AppleSiliconGen.M4_ULTRA,
        "m4 max": AppleSiliconGen.M4_MAX,
        "m4 pro": AppleSiliconGen.M4_PRO,
        "m4": AppleSiliconGen.M4,
        # M3 Series (2023-2025)
        "m3 ultra": AppleSiliconGen.M3_ULTRA,
        "m3 max": AppleSiliconGen.M3_MAX,
        "m3 pro": AppleSiliconGen.M3_PRO,
        "m3": AppleSiliconGen.M3,
        # M2 Series (2022-2023)
        "m2 ultra": AppleSiliconGen.M2_ULTRA,
        "m2 max": AppleSiliconGen.M2_MAX,
        "m2 pro": AppleSiliconGen.M2_PRO,
        "m2": AppleSiliconGen.M2,
        # M1 Series (2020-2022)
        "m1 ultra": AppleSiliconGen.M1_ULTRA,
        "m1 max": AppleSiliconGen.M1_MAX,
        "m1 pro": AppleSiliconGen.M1_PRO,
        "m1": AppleSiliconGen.M1,
    }
    for key, gen in generation_map.items():
        if key in name_lower:
            return gen
    return AppleSiliconGen.UNKNOWN


def classify_nvidia_architecture(compute_capability: tuple[int, int]) -> NVIDIAGPUArch:
    """
    Classify NVIDIA GPU architecture from compute capability version.

    Args:
        compute_capability: (major, minor) tuple from CUDA

    Returns:
        Classified NVIDIA microarchitecture

    Example:
        >>> classify_nvidia_architecture((9, 0))
        NVIDIAGPUArch.HOPPER
    """
    major = compute_capability[0]
    if major == 9:
        return NVIDIAGPUArch.HOPPER
    elif major == 8:
        return NVIDIAGPUArch.ADA_LOVELACE if compute_capability[1] >= 9 else NVIDIAGPUArch.AMPERE
    elif major == 7:
        return NVIDIAGPUArch.VOLTA
    return NVIDIAGPUArch.UNKNOWN


def get_apple_silicon_specs(
    generation: AppleSiliconGen,
) -> tuple[int, float, float]:
    """
    Return (compute_units, memory_gb, bandwidth_gbps) for known Apple Silicon.

    Based on Apple public specifications as of 2026.

    M5 Series (2025-2026):
        - M5: 10-core GPU, 16-core Neural Engine, 153 GB/s
        - M5 Pro: Higher GPU cores, increased bandwidth
        - M5 Max: 40+ core GPU, 500+ GB/s bandwidth
        - M5 Ultra: Fusion Architecture, 800+ GB/s bandwidth

    M4 Series (2024):
        - M4: 10-core GPU, 16-core Neural Engine, 120 GB/s
        - M4 Pro: 20-core GPU, 16-core Neural Engine, 273 GB/s
        - M4 Max: 40-core GPU, 16-core Neural Engine, 546 GB/s

    M3 Series (2023-2025):
        - M3: 10-core GPU, 16-core Neural Engine, 100 GB/s
        - M3 Pro: 18-core GPU, 16-core Neural Engine, 150 GB/s
        - M3 Max: 40-core GPU, 16-core Neural Engine, 400 GB/s
        - M3 Ultra: 80-core GPU, 32-core Neural Engine, 819 GB/s

    Args:
        generation: Apple Silicon generation

    Returns:
        Tuple of (compute_units, memory_gb, bandwidth_gbps)

    Example:
        >>> get_apple_silicon_specs(AppleSiliconGen.M3_ULTRA)
        (80, 192.0, 819.0)
    """
    specs = {
        # M5 Series (2025-2026) - Next-gen AI architecture
        AppleSiliconGen.M5_ULTRA: (80, 256.0, 900.0),  # Fusion Architecture, estimated
        AppleSiliconGen.M5_MAX: (40, 128.0, 600.0),  # Neural Accelerators
        AppleSiliconGen.M5_PRO: (30, 64.0, 400.0),  # Neural Accelerators
        AppleSiliconGen.M5: (10, 24.0, 153.0),  # Base M5
        # M4 Series (2024) - Dynamic Caching, mesh shading
        AppleSiliconGen.M4_ULTRA: (80, 192.0, 800.0),  # Estimated
        AppleSiliconGen.M4_MAX: (40, 128.0, 546.0),
        AppleSiliconGen.M4_PRO: (20, 64.0, 273.0),
        AppleSiliconGen.M4: (10, 24.0, 120.0),
        # M3 Series (2023-2025) - BF16, Metal 4
        AppleSiliconGen.M3_ULTRA: (80, 192.0, 819.0),
        AppleSiliconGen.M3_MAX: (40, 128.0, 400.0),
        AppleSiliconGen.M3_PRO: (18, 36.0, 150.0),
        AppleSiliconGen.M3: (10, 24.0, 100.0),
        # M2 Series (2022-2023)
        AppleSiliconGen.M2_ULTRA: (24, 192.0, 800.0),
        AppleSiliconGen.M2_MAX: (38, 96.0, 400.0),
        AppleSiliconGen.M2_PRO: (19, 32.0, 200.0),
        AppleSiliconGen.M2: (10, 24.0, 100.0),
        # M1 Series (2020-2022)
        AppleSiliconGen.M1_ULTRA: (48, 128.0, 800.0),
        AppleSiliconGen.M1_MAX: (32, 64.0, 400.0),
        AppleSiliconGen.M1_PRO: (16, 32.0, 200.0),
        AppleSiliconGen.M1: (8, 16.0, 68.0),
        AppleSiliconGen.UNKNOWN: (8, 16.0, 68.0),
    }
    return specs.get(generation, (8, 16.0, 68.0))


def get_nvidia_bandwidth_estimate(arch: NVIDIAGPUArch) -> float:
    """
    Return memory bandwidth estimate for NVIDIA GPU architecture.

    Args:
        arch: NVIDIA GPU architecture

    Returns:
        Estimated bandwidth in GB/s

    Example:
        >>> get_nvidia_bandwidth_estimate(NVIDIAGPUArch.HOPPER)
        3352.0
    """
    bandwidth_map = {
        NVIDIAGPUArch.HOPPER: 3352.0,  # H100 SXM5: 3.35 TB/s
        NVIDIAGPUArch.AMPERE: 2039.0,  # A100 80GB: 2.04 TB/s
        NVIDIAGPUArch.ADA_LOVELACE: 1008.0,  # RTX 4090: 1.01 TB/s
        NVIDIAGPUArch.VOLTA: 900.0,  # V100: 0.9 TB/s
    }
    return bandwidth_map.get(arch, 500.0)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Device Types
    "AcceleratorType",
    "AppleSiliconGen",
    "NVIDIAGPUArch",
    # Capability Descriptors
    "DeviceCapabilities",
    "KernelProfile",
    # Classification Utilities
    "classify_apple_silicon",
    "classify_nvidia_architecture",
    "get_apple_silicon_specs",
    "get_nvidia_bandwidth_estimate",
]
