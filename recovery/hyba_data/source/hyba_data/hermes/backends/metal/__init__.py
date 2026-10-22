"""
Metal Performance Shaders (MPS) module for phi-Grover.

This module provides GPU acceleration for Apple Silicon using Metal and MLX.
"""

from .phi_metal_kernel import PhiMetalKernel, create_metal_kernel
from .phi_metal_runner import MetalRunner, run_metal_computation

__all__ = [
    "PhiMetalKernel",
    "create_metal_kernel",
    "MetalRunner",
    "run_metal_computation",
]
