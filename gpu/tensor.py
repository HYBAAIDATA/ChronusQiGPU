"""Tensor execution accounting and access to the exact tensor substrate.

Tensor work is measured independently from SHA-256d work.  No value produced
by this module can be interpreted as hashes per second.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Any

_HYBRID_EXPORTS = {
    "IdentityWindowRanker": ("hyba.hybrid.tensor_advisor", "IdentityWindowRanker"),
    "LayerSample": ("hyba.hybrid.performance", "LayerSample"),
    "PerformanceReport": ("hyba.hybrid.performance", "PerformanceReport"),
    "TensorAdviceEvidence": (
        "hyba.hybrid.tensor_advisor",
        "TensorAdviceEvidence",
    ),
    "TensorAdviceViolation": (
        "hyba.hybrid.tensor_advisor",
        "TensorAdviceViolation",
    ),
    "WindowRanker": ("hyba.hybrid.tensor_advisor", "WindowRanker"),
    "apply_tensor_advice": (
        "hyba.hybrid.tensor_advisor",
        "apply_tensor_advice",
    ),
}


@dataclass(frozen=True)
class TensorMeasurement:
    """Measured tensor operations over a wall-clock interval."""

    operations: int
    elapsed_ns: int
    backend: str
    model_id: str = ""

    def __post_init__(self) -> None:
        if self.operations < 0:
            raise ValueError("operations must be >= 0")
        if self.elapsed_ns <= 0:
            raise ValueError("elapsed_ns must be > 0")
        if not self.backend.strip():
            raise ValueError("backend must be non-empty")

    @property
    def tflops(self) -> float:
        return self.operations * 1_000_000_000.0 / self.elapsed_ns / 1e12

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "measured_tensor_tflops": self.tflops,
            "truth_class": "measured",
            "hashrate_hps": None,
        }


def load_exact_tensor_module() -> Any:
    """Load the canonical VQC exact-tensor implementation."""
    return import_module("turing_universal_quantum_computer.exact_tensor")


def load_quantum_tensor_module() -> Any:
    """Load the canonical VQC quantum-tensor implementation."""
    return import_module("turing_universal_quantum_computer.quantum_tensor")


def __getattr__(name: str) -> Any:
    """Resolve hybrid tensor policy and reporting symbols lazily."""
    try:
        module_name, attribute = _HYBRID_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attribute)


__all__ = [
    *_HYBRID_EXPORTS,
    "TensorMeasurement",
    "load_exact_tensor_module",
    "load_quantum_tensor_module",
]