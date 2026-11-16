"""Folded-state inference pilot with selective row materialisation."""

from __future__ import annotations

import time

import numpy as np

from chronus.tensor.folded_state import ExactFoldState
from chronus.tensor.geodesic import PhiTensorCore


class FoldedInferencePilot:
    def __init__(self, weights: np.ndarray) -> None:
        array = np.asarray(weights)
        if array.ndim != 2 or array.dtype not in (np.float32, np.float64):
            raise ValueError("weights must be rank-2 float32 or float64")
        self.state = ExactFoldState.from_array(array)
        self._shape = array.shape
        self._dtype = array.dtype

    def execute_rows(self, start: int, stop: int, vector: np.ndarray) -> dict:
        selected = self.state.unfold_rows(start, stop)
        x = np.asarray(vector, dtype=self._dtype)
        if x.ndim != 1 or x.shape[0] != self._shape[1]:
            raise ValueError("vector length must match weight columns")
        core = PhiTensorCore()
        t0 = time.perf_counter_ns()
        result = core.execute("matmul", selected, x.reshape(-1, 1))["output"].reshape(-1)
        elapsed_ns = time.perf_counter_ns() - t0
        return {
            "output": result,
            "rows_materialised": stop - start,
            "bytes_materialised": selected.nbytes,
            "total_weight_bytes": self.state.original_length,
            "elapsed_ns": elapsed_ns,
            "backend": "numpy-reference",
            "physical_compression_ratio": None,
        }
