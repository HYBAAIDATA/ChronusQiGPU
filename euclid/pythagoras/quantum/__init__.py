"""Mathematically implemented quantum/tensor operators and scaled execution."""
from .quantum_tensor import (
    HilbertCoveragePlan,
    QuantumTensor,
    QuantumTensorAudit,
    VIRTUAL_QUANTUM_DIMENSION,
    VIRTUAL_QUANTUM_QUBITS,
    plan_hilbert_coverage,
)
from .lucas_pisot import HendrixStructuredSearch, LucasPisotScale, resolve_scale
from .hendrix import HendrixIGPUSearch

__all__ = [
    "QuantumTensor", "QuantumTensorAudit", "HilbertCoveragePlan",
    "plan_hilbert_coverage", "VIRTUAL_QUANTUM_QUBITS", "VIRTUAL_QUANTUM_DIMENSION",
    "LucasPisotScale", "resolve_scale", "HendrixStructuredSearch", "HendrixIGPUSearch",
]
