"""
EUCLID V2 Accelerators Module (DEPRECATED)
==========================================

Hardware acceleration support for EUCLID V2.

DEPRECATED: This module is deprecated. Please use macquantum instead:
    from macquantum import get_accelerator, MetalAccelerator, MacQuantumCuda

This module now re-exports from macquantum for backward compatibility.
"""

import warnings

warnings.warn(
    "euclid_v2.accelerators is deprecated. Use macquantum instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from macquantum for backward compatibility
from hermes.backends.macquantum import (
    AcceleratorBase,
    AcceleratorType,
    AppleSiliconGen,
    CPUFallbackAccelerator,
    DeviceCapabilities,
    KernelProfile,
    MacQuantumCuda,
    MetalAccelerator,
    NVIDIAGPUArch,
    get_accelerator,
)

# Backward compatibility alias
CUDAAccelerator = MacQuantumCuda

__all__ = [
    "AcceleratorType",
    "AppleSiliconGen",
    "NVIDIAGPUArch",
    "DeviceCapabilities",
    "KernelProfile",
    "AcceleratorBase",
    "MetalAccelerator",
    "CUDAAccelerator",
    "CPUFallbackAccelerator",
    "get_accelerator",
]
