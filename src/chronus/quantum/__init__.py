"""Chronus Quantum iGPU Quantum Integration Layer.

Production-ready quantum-classical hybrid execution with hardware abstraction,
Holonomic Berry Connection, NVQLink QLDPC, and CUDA-Q compiler integration.
"""

__version__ = "36.0.0"
__all__ = [
    "QuantumHardwareAbstraction",
    "HolonomicPulseProcessor",
    "NVQLinkController",
    "CUDAQCompiler",
    "HybridWorkloadRunner",
    "QuantumError",
    "HardwareUnavailable",
    "QECError",
]