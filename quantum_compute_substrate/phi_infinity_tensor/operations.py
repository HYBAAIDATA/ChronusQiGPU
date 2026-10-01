"""Symbolic tensor operations that preserve algebraic structure."""
from __future__ import annotations
import math
from typing import Any, Dict
from .tensor import HYBAQuantumTensorXInfinity
from .phi_identities import lucas


def tensor_product(A: HYBAQuantumTensorXInfinity,
                   B: HYBAQuantumTensorXInfinity) -> Dict[str, Any]:
    """A tensor B: shape becomes shape(A) + shape(B), rank sums."""
    new_shape = A.shape + B.shape
    new_rank = A.rank + B.rank
    new_elements = A.total_elements() * B.total_elements()
    return {
        "result_rank": new_rank,
        "result_shape": new_shape,
        "result_total_elements": new_elements,
        "log10_elements": math.log10(new_elements),
    }


def contract(T: HYBAQuantumTensorXInfinity, axis_i: int, axis_j: int) -> Dict[str, Any]:
    """Contract two axes of T. Requires axes to have equal size.
    Reduces rank by 2.
    """
    if not 0 <= axis_i < T.rank or not 0 <= axis_j < T.rank:
        raise IndexError("axis out of range")
    if axis_i == axis_j:
        raise ValueError("cannot contract an axis with itself")
    if T.shape[axis_i] != T.shape[axis_j]:
        raise ValueError("contracted axes must have equal size")
    remaining = tuple(s for k, s in enumerate(T.shape) if k not in (axis_i, axis_j))
    return {
        "contracted_axes": (axis_i, axis_j),
        "result_rank": T.rank - 2,
        "result_shape": remaining,
        "result_total_elements": int(math.prod(remaining)) if remaining else 1,
    }


def phi_scaling_transform(T: HYBAQuantumTensorXInfinity,
                          new_scaling_exp: int) -> Dict[str, Any]:
    """Rescale every axis to phi^{new_scaling_exp}. Returns metadata."""
    if new_scaling_exp < 2:
        raise ValueError("new_scaling_exp must be >= 2")
    new_axis_size = lucas(new_scaling_exp)
    new_total = new_axis_size ** T.rank
    return {
        "old_scaling_exp": T.scaling_exp,
        "new_scaling_exp": new_scaling_exp,
        "new_axis_size": new_axis_size,
        "new_total_elements": new_total,
        "log10_new_elements": T.rank * math.log10(new_axis_size),
    }


def quantum_fourier_transform_all_axes(T: HYBAQuantumTensorXInfinity) -> Dict[str, Any]:
    """Apply QFT along all rank axes.
    Preserves shape and total_elements. Each axis has QFT circuit depth
    ~ log2(N) * log2(N) with the substrate's Coppersmith banded QFT.
    """
    N = T.shape[0]
    log2N = math.log2(N)
    per_axis_depth = log2N * (log2N + 1) / 2
    return {
        "result_shape": T.shape,
        "result_rank": T.rank,
        "unitary": True,
        "per_axis_depth": per_axis_depth,
        "total_depth": T.rank * per_axis_depth,
        "backend": "quantum_2026.classics.qft.exact_qft_matrix",
    }


def topological_decomposition(T: HYBAQuantumTensorXInfinity) -> Dict[str, Any]:
    """Two topologies on the index domain:
      * open boundary   -> contractible 6-cube, chi = 1, Betti = [1,0,0,0,0,0,0]
      * periodic (torus)-> product of 6 circles, chi = 0, Betti = [C(6,k) for k=0..6]
    Kunneth: H_k(T^6) has rank C(6, k). Sum with sign = 0 = chi(T^6).
    """
    from math import comb
    betti_torus = [comb(T.rank, k) for k in range(T.rank + 1)]
    euler_torus = sum(((-1) ** k) * betti_torus[k] for k in range(T.rank + 1))
    betti_cube = [1] + [0] * T.rank
    return {
        "open_boundary": {
            "topology": "6-cube (contractible)",
            "betti_numbers": betti_cube,
            "euler_characteristic": 1,
        },
        "periodic": {
            "topology": "6-torus",
            "betti_numbers": betti_torus,
            "euler_characteristic": euler_torus,
        },
    }
