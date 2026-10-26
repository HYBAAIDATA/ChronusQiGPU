"""
Accelerator Factory
==================

Factory function to obtain the best available accelerator.

Selection priority (AS INTENDED):
    1. Metal MPS (Apple Silicon) - Apple BECOMES quantum computer
    2. MacQuantumCuda (FALLBACK) - transforms ANY substrate to quantum
    3. CPU Fallback - ONLY when nothing else available

Philosophy:
    - Apple Silicon: Metal → quantum computer
    - Other platforms: MacQuantumCuda → quantum computation
    - CPU: Emergency fallback only

Version: 1.0.0
Date: 2026-04-21
"""

from __future__ import annotations

import logging
from typing import List

from .accelerator_base import AcceleratorBase
from .cpu_fallback import CPUFallbackAccelerator
from .cuda_accelerator import MacQuantumCuda
from .metal_accelerator import MetalAccelerator

logger = logging.getLogger(__name__)


def get_accelerator(
    prefer_metal: bool = True,
    device_id: int = 0,
    memory_headroom: float = 0.15,
) -> AcceleratorBase:
    """
    Factory function to obtain the best available accelerator.

    INTENDED BEHAVIOR:
        - Apple Silicon (M1/M2/M3): Metal BECOMES quantum computer
        - Other platforms: MacQuantumCuda FALLBACK provides quantum
        - CPU: Emergency fallback ONLY when nothing else available

    Selection priority:
        1. Metal MPS (Apple Silicon) - PRIMARY on Apple
        2. MacQuantumCuda - FALLBACK (transforms substrate to quantum)
        3. CPU Fallback - emergency ONLY

    Args:
        prefer_metal: Prefer Metal (default True)
        device_id: Device ID (for future CUDA)
        memory_headroom: Fraction of GPU memory to reserve

    Returns:
        Initialized accelerator providing quantum computation

    Example:
        >>> accel = get_accelerator()
        >>> print(f"Using: {accel.accelerator_type}")
    """
    candidates: List[AcceleratorBase] = []

    # PRIORITY 1: Apple Silicon - Metal BECOMES quantum computer
    if prefer_metal:
        metal = MetalAccelerator(memory_headroom=memory_headroom)
        if metal.available:
            metal.initialize()
            candidates.append(metal)
            logger.info(f"Apple Silicon: Metal BECOMES quantum computer")

    # PRIORITY 2: MacQuantumCuda - FALLBACK transforms ANY substrate to quantum
    # This is the FALLBACK for non-Apple platforms
    quantum = MacQuantumCuda(memory_headroom=memory_headroom)
    if quantum.available:
        quantum.initialize()
        candidates.append(quantum)
        logger.info(f"MacQuantumCuda: Substrate transformed to quantum computation")

    # PRIORITY 3: CPU Fallback - ONLY when nothing else available
    if not candidates:
        fallback = CPUFallbackAccelerator()
        fallback.initialize()
        logger.warning("EMERGENCY: Only CPU available")
        return fallback

    # Return best available
    best = candidates[0]
    logger.info(f"Selected: {best.accelerator_type} " f"({best.get_capabilities().device_name})")
    return best


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ["get_accelerator"]
