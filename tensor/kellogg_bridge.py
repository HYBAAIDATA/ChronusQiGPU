"""Lazy bridges to existing tensor mathematics substrates.

This module does not re-implement any mathematics. It loads — on demand —
the project's existing exact/quantum tensor implementations so that
``tensor`` is the single place production code imports from, while the
underlying substrates (``kellogg.*`` and the in-tree VQC package) stay the
canonical owners of their algorithms.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


def load_exact_tensor_module() -> Any:
    """The canonical VQC exact-tensor implementation (Clifford+T, Q(sqrt2))."""
    return import_module("turing_universal_quantum_computer.exact_tensor")


def load_quantum_tensor_module() -> Any:
    """The canonical VQC quantum-tensor implementation."""
    return import_module("turing_universal_quantum_computer.quantum_tensor")


def load_kellogg_exact_tensor() -> Any:
    """Kellogg's Q(sqrt2)+iQ(sqrt2) exact state-vector substrate."""
    return import_module("kellogg.exact_tensor")


def load_kellogg_quantum_tensor() -> Any:
    """Kellogg's zero-dependency first-principles quantum tensor (C^N)."""
    return import_module("kellogg.quantum_tensor")


def load_kellogg_tensor_ml() -> Any:
    """Kellogg's TOE Tensor Elevation (exact linear model surface)."""
    return import_module("kellogg.tensor_ml")


__all__ = [
    "load_exact_tensor_module",
    "load_quantum_tensor_module",
    "load_kellogg_exact_tensor",
    "load_kellogg_quantum_tensor",
    "load_kellogg_tensor_ml",
]
