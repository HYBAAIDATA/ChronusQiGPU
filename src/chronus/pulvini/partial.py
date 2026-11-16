"""Verified, selective PULVINI V3 numerical reconstruction.

A one-time full verification compiles an immutable fold index. Thereafter a
window read traverses only required Fibonacci branches, O(depth * window).
Full residual kernels remain retained; no storage compression or device claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import numpy as np

from chronus.pulvini import FoldState, PhiRecursiveOperator, unfold_verified
from chronus.tensor.folded_compute import VerifiedFoldedOperand


@dataclass(frozen=True)
class VerifiedFoldIndex:
    _state: FoldState
    source_sha256: str
    elements: int
    depth: int

    @classmethod
    def compile(cls, operand: VerifiedFoldedOperand, *, max_elements: int = 1_000_000):
        if not isinstance(operand, VerifiedFoldedOperand):
            raise ValueError("verified complete fold required")
        if operand.state.sizes[0] > max_elements:
            raise ValueError("fold exceeds compile element policy")
        # Validate all kernels, chronology and full original digest just once.
        unfolded = unfold_verified(operand.state, receipt=operand.evidence)
        if unfolded.size != operand.state.sizes[0]:
            raise ValueError("invalid fold length")
        # Freeze into private immutable bytes; caller mutations cannot affect a
        # compiled index, even through NumPy's setflags.
        def freeze(array):
            contiguous = np.ascontiguousarray(array)
            return np.frombuffer(contiguous.tobytes(), dtype=contiguous.dtype)
        src = operand.state
        state = FoldState(
            folded=freeze(src.folded), kernels=tuple(freeze(k) for k in src.kernels),
            sizes=tuple(src.sizes), original_shape=tuple(src.original_shape),
            original_dtype=src.original_dtype, normalization=src.normalization,
        )
        return cls(state, operand.evidence.input_sha256, src.sizes[0], src.depth)

    def read(self, start: int, stop: int) -> np.ndarray:
        if type(start) is not int or type(stop) is not int or not 0 <= start <= stop <= self.elements:
            raise ValueError("partial fold window outside original array")
        if stop == start:
            return np.empty(0, dtype=self._state.folded.dtype)
        operator = PhiRecursiveOperator(normalization=self._state.normalization)
        w1, w2, denominator = operator._weights()
        sizes = self._state.sizes
        depth = self.depth
        folded = self._state.folded
        kernels = self._state.kernels

        @lru_cache(maxsize=None)
        def value(level: int, index: int):
            if level == depth:
                return folded[index]
            left = sizes[level + 1]
            if index < left:
                return (w1 * value(level+1, index) + w2 * kernels[level][index]) / denominator
            pos = index - left
            return (w2 * value(level+1, pos) - w1 * kernels[level][pos]) / denominator

        return np.asarray([value(0, k) for k in range(start, stop)],
                          dtype=self._state.folded.dtype)

    def read_rows(self, start: int, stop: int) -> np.ndarray:
        shape = self._state.original_shape
        if not shape or type(start) is not int or type(stop) is not int or not 0 <= start <= stop <= shape[0]:
            raise ValueError("row read outside tensor")
        width = int(np.prod(shape[1:])) if len(shape)>1 else 1
        return self.read(start*width, stop*width).reshape((stop-start, *shape[1:]))

    def evidence(self) -> dict:
        return {
            "schema": "chronus.pulvini.verified-partial/1",
            "input_sha256": self.source_sha256,
            "depth": self.depth,
            "full_reconstruction_verified_once": True,
            "complete_kernel_retention": True,
            "read_method": "selected_inverse_branches_only",
            "per_read_full_unfold": False,
            "source_attestation": "NOT CRYPTOGRAPHICALLY SIGNED",
            "storage_savings": "UNVERIFIED",
            "device_execution": "UNVERIFIED",
        }
