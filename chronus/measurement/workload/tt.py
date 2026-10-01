"""TT-SVD throughput — real tensor-train decomposition on the substrate.

Invariants:
    TT1: every TT measurement includes the shape and max rank.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from .._common import distribution_of, timed_calls, unavailable


def measure_tt_svd(
    tensor_shape: Tuple[int, ...] = (8, 8, 8),
    max_rank: int = 8,
    repeats: int = 8,
) -> Dict[str, Any]:
    """Time full TT-SVD constructions of a random tensor."""
    try:
        from quantum_compute_substrate.pulvini import TensorTrain
    except Exception as exc:
        return unavailable(f"quantum_compute_substrate import failed: {exc}")

    rng = np.random.default_rng(0)
    tensor = rng.standard_normal(tensor_shape)
    durations_ns = timed_calls(lambda: TensorTrain(tensor, max_rank=max_rank), repeats)
    svd_ns = distribution_of(durations_ns)
    throughput = distribution_of([tensor.size / (d / 1e9) for d in durations_ns if d > 0])
    tt = TensorTrain(tensor, max_rank=max_rank)
    return {
        "available": True,
        "shape": list(tensor_shape),
        "max_rank": max_rank,
        "svd_time_ns": svd_ns.as_dict(),
        "elements_per_second": throughput.as_dict(),
        "compression_ratio": tt.get_compression_ratio(),
        "method": "quantum_compute_substrate.pulvini.TensorTrain(tensor, max_rank)",
    }
