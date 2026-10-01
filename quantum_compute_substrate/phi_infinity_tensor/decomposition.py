"""Metadata for tensor decompositions (SVD, CP, Tucker, TT).

No materialization; we describe the decomposition structure and its cost.
"""
from __future__ import annotations
import math
from typing import Any, Dict, List
from .tensor import HYBAQuantumTensorXInfinity


def svd_metadata(T: HYBAQuantumTensorXInfinity, matricization_axis: int = 0) -> Dict[str, Any]:
    """Reshape rank-r tensor as N x N^(r-1) matrix and describe its SVD size."""
    N = T.shape[0]
    rows = N
    cols = N ** (T.rank - 1)
    max_rank = min(rows, cols)
    return {
        "type": "SVD-matricization",
        "axis": matricization_axis,
        "rows": rows,
        "log10_cols": (T.rank - 1) * math.log10(N),
        "max_svd_rank": max_rank,
        "singular_values": max_rank,
    }


def cp_decomposition_metadata(T: HYBAQuantumTensorXInfinity, cp_rank: int = 128) -> Dict[str, Any]:
    """CP: T = sum_{r=1..R} lambda_r * a_r^{(1)} circ ... circ a_r^{(rank)}.

    Storage: rank * cp_rank * N + cp_rank scalars.
    """
    N = T.shape[0]
    scalars = T.rank * cp_rank * N + cp_rank
    return {
        "type": "CP",
        "cp_rank": cp_rank,
        "scalars": scalars,
        "bytes": scalars * 16,
        "compression_log10": math.log10(scalars) - T.log10_elements(),
    }


def tucker_decomposition_metadata(T: HYBAQuantumTensorXInfinity,
                                  core_dims: List[int] | None = None) -> Dict[str, Any]:
    """Tucker: T = G x_1 U_1 x_2 U_2 ... x_r U_r  with core G of shape core_dims."""
    if core_dims is None:
        core_dims = [32] * T.rank
    if len(core_dims) != T.rank:
        raise ValueError("core_dims must have length rank")
    N = T.shape[0]
    core_scalars = 1
    for d in core_dims:
        core_scalars *= d
    factor_scalars = sum(d * N for d in core_dims)
    total = core_scalars + factor_scalars
    return {
        "type": "Tucker",
        "core_dims": core_dims,
        "core_scalars": core_scalars,
        "factor_scalars": factor_scalars,
        "total_scalars": total,
        "bytes": total * 16,
        "compression_log10": math.log10(total) - T.log10_elements(),
    }


def tensor_train_metadata(T: HYBAQuantumTensorXInfinity, tt_rank: int = 128) -> Dict[str, Any]:
    """Tensor-train: rank cores each of shape (tt_rank, N, tt_rank), ends smaller."""
    N = T.shape[0]
    # End cores: (1, N, tt_rank) and (tt_rank, N, 1)
    # Interior: (tt_rank, N, tt_rank), (rank - 2) of them
    scalars = 2 * (N * tt_rank) + max(0, T.rank - 2) * (tt_rank * N * tt_rank)
    return {
        "type": "TT",
        "tt_rank": tt_rank,
        "scalars": scalars,
        "bytes": scalars * 16,
        "compression_log10": math.log10(scalars) - T.log10_elements(),
    }
