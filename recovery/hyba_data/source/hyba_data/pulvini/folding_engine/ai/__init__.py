"""Reversible AI layers — Torch / JAX / training loops."""

from .phi_layer_jax import available as jax_available
from .phi_layer_jax import make_layer as make_jax_layer
from .phi_layer_torch import available as torch_available
from .phi_layer_torch import make_module as make_torch_module
from .phi_layer_torch import numpy_roundtrip
from .training_loop_phi_layer import TrainResult, train_phi_layer_classifier

__all__ = [
    "torch_available",
    "make_torch_module",
    "numpy_roundtrip",
    "jax_available",
    "make_jax_layer",
    "train_phi_layer_classifier",
    "TrainResult",
]
