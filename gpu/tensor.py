"""Deprecated compatibility shim -- import from the ``tensor`` package instead.

``tensor`` is now the canonical logical Tensor layer (contracts, backend
registry/router, runtime, and bridges to the exact/quantum substrates). This
module stays only as a temporary, zero-duplication re-export so existing
imports such as ``from gpu.tensor import TensorMeasurement`` keep working.

Migration guidance:

* ``gpu.tensor.TensorMeasurement`` -> ``tensor.TensorMeasurement``
* ``gpu.tensor.load_exact_tensor_module`` -> ``tensor.kellogg_bridge.load_exact_tensor_module``
* ``gpu.tensor.load_quantum_tensor_module`` -> ``tensor.kellogg_bridge.load_quantum_tensor_module``
* ``gpu.tensor.apply_tensor_advice`` / ``WindowRanker`` / etc. -> ``tensor.advisor``

This module intentionally contains no tensor mathematics or execution
logic of its own; see ``docs/TENSOR_ARCHITECTURE.md`` for the layer
boundaries this re-export preserves.
"""

from __future__ import annotations

import warnings
from importlib import import_module
from typing import Any

_EXPORTS = {
    "TensorMeasurement": ("tensor.contracts", "TensorMeasurement"),
    "load_exact_tensor_module": ("tensor.kellogg_bridge", "load_exact_tensor_module"),
    "load_quantum_tensor_module": ("tensor.kellogg_bridge", "load_quantum_tensor_module"),
    "IdentityWindowRanker": ("tensor.advisor", "IdentityWindowRanker"),
    "TensorAdviceEvidence": ("tensor.advisor", "TensorAdviceEvidence"),
    "TensorAdviceViolation": ("tensor.advisor", "TensorAdviceViolation"),
    "WindowRanker": ("tensor.advisor", "WindowRanker"),
    "apply_tensor_advice": ("tensor.advisor", "apply_tensor_advice"),
    "LayerSample": ("hyba.hybrid.performance", "LayerSample"),
    "PerformanceReport": ("hyba.hybrid.performance", "PerformanceReport"),
}

warnings.warn(
    "gpu.tensor is a temporary compatibility shim; import from the 'tensor' "
    "package instead (e.g. 'from tensor import TensorMeasurement'). See "
    "docs/TENSOR_ARCHITECTURE.md for the migration map.",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    """Resolve re-exported tensor symbols lazily, without duplicating them."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attribute)


__all__ = sorted(_EXPORTS)
