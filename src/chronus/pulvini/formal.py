"""Formal, validated implementation of the reversible phi-recursive operator."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Sequence
import math
import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0

class ValidationError(ValueError):
    """Raised when an operator contract is violated."""

@dataclass(frozen=True)
class FoldState:
    folded: np.ndarray
    kernels: tuple[np.ndarray, ...]
    sizes: tuple[int, ...]
    original_shape: tuple[int, ...]
    original_dtype: str
    normalization: str

    @property
    def depth(self) -> int: return len(self.kernels)
    @property
    def retained_values(self) -> int:
        return int(self.folded.size + sum(k.size for k in self.kernels))

class PhiRecursiveOperator:
    """Deterministic linear fold with explicit inverse and contract checks.

    ``legacy`` normalization uses weights 1/phi and 1/phi^2. ``orthonormal``
    scales both channels so the concatenated (folded, kernel) pair is an
    isometry. The folded channel alone is not norm preserving.
    """
    def __init__(self, *, normalization: str = "legacy", max_depth: int = 32,
                 max_elements: int = 50_000_000, require_finite: bool = True):
        if normalization not in {"legacy", "orthonormal"}:
            raise ValidationError("normalization must be legacy or orthonormal")
        self.normalization = normalization
        self.max_depth = int(max_depth); self.max_elements = int(max_elements)
        self.require_finite = bool(require_finite)
        if self.max_depth < 0 or self.max_elements < 1: raise ValidationError("invalid limits")

    @staticmethod
    def fibonacci_split(dim: int) -> tuple[int, int]:
        if dim < 1: raise ValidationError("dimension must be positive")
        n2 = max(1, int(np.round(dim / (PHI + 1.0)))) if dim > 1 else 0
        return dim - n2, n2

    def _weights(self) -> tuple[float, float, float]:
        w1, w2 = 1.0 / PHI, 1.0 / (PHI ** 2)
        norm_sq = w1*w1 + w2*w2
        if self.normalization == "orthonormal":
            scale = math.sqrt(norm_sq); w1 /= scale; w2 /= scale; norm_sq = 1.0
        return w1, w2, norm_sq

    def _vector(self, x: Any) -> np.ndarray:
        a = np.asarray(x)
        if a.ndim != 1: raise ValidationError("operator input must be one-dimensional")
        if a.size < 1 or a.size > self.max_elements: raise ValidationError("input size outside policy")
        dtype = np.complex128 if np.iscomplexobj(a) else np.float64
        a = np.asarray(a, dtype=dtype)
        if self.require_finite and not np.all(np.isfinite(a)): raise ValidationError("non-finite input")
        return a

    def fold(self, x: Any) -> tuple[np.ndarray, np.ndarray]:
        a = self._vector(x)
        if a.size == 1: return a.copy(), np.zeros(0, dtype=a.dtype)
        n1, n2 = self.fibonacci_split(a.size); x1, x2 = a[:n1], a[n1:]
        x2p = np.zeros(n1, dtype=a.dtype); x2p[:n2] = x2
        w1, w2, _ = self._weights()
        return w1*x1 + w2*x2p, w2*x1 - w1*x2p

    def unfold(self, folded: Any, kernel: Any, original_dim: int) -> np.ndarray:
        f, k = self._vector(folded), np.asarray(kernel, dtype=np.asarray(folded).dtype)
        if original_dim == 1:
            if f.size != 1 or k.size != 0: raise ValidationError("invalid singleton state")
            return f.copy()
        n1, n2 = self.fibonacci_split(int(original_dim))
        if f.size != n1 or k.ndim != 1 or k.size != n1: raise ValidationError("state dimensions inconsistent")
        if self.require_finite and not np.all(np.isfinite(k)): raise ValidationError("non-finite kernel")
        w1, w2, norm_sq = self._weights()
        x1 = (w1*f + w2*k) / norm_sq
        x2p = (w2*f - w1*k) / norm_sq
        return np.concatenate((x1, x2p[:n2]))

    def fold_recursive(self, x: Any, depth: int = 1) -> FoldState:
        a0 = np.asarray(x); shape = tuple(a0.shape); flat = self._vector(a0.reshape(-1))
        if depth < 0 or depth > self.max_depth: raise ValidationError("depth outside policy")
        current = flat.copy(); kernels=[]; sizes=[int(current.size)]
        for _ in range(int(depth)):
            if current.size <= 1: break
            current, kernel = self.fold(current); kernels.append(kernel); sizes.append(int(current.size))
        return FoldState(current, tuple(kernels), tuple(sizes), shape, str(a0.dtype), self.normalization)

    def unfold_recursive(self, state: FoldState) -> np.ndarray:
        if state.normalization != self.normalization: raise ValidationError("normalization mismatch")
        if len(state.sizes) != len(state.kernels)+1: raise ValidationError("invalid chronology")
        current = state.folded.copy()
        for kernel, original_dim in zip(reversed(state.kernels), reversed(state.sizes[:-1])):
            current = self.unfold(current, kernel, original_dim)
        if int(np.prod(state.original_shape)) != current.size: raise ValidationError("shape metadata mismatch")
        return current.reshape(state.original_shape)

    def adjoint_recursive(self, grad_folded: Any, sizes: Sequence[int]) -> np.ndarray:
        """Apply the adjoint Jacobian for neural backpropagation.

        Kernels are values, not derivatives, and are intentionally not used.
        """
        g = self._vector(grad_folded); w1, w2, _ = self._weights()
        for original_dim in reversed(tuple(sizes)[:-1]):
            n1, n2 = self.fibonacci_split(int(original_dim))
            if g.size != n1: raise ValidationError("gradient chronology mismatch")
            g = np.concatenate((w1*g, w2*g[:n2]))
        return g

    def characterize(self, x: Any, depth: int = 1) -> dict[str, Any]:
        original = self._vector(np.asarray(x).reshape(-1)); state = self.fold_recursive(original, depth)
        recovered = self.unfold_recursive(state).reshape(-1)
        eps=np.finfo(float).eps; rel=float(np.linalg.norm(original-recovered)/max(float(np.linalg.norm(original)),eps))
        kernel_bytes=sum(k.nbytes for k in state.kernels); retained=state.folded.nbytes+kernel_bytes
        pair_norm_sq=float(np.linalg.norm(state.folded)**2 + sum(np.linalg.norm(k)**2 for k in state.kernels))
        return {"schema":"PULVINI_FORMAL_CHARACTERIZATION_V1","depth":state.depth,
                "original_values":int(original.size),"folded_values":int(state.folded.size),
                "kernel_values":int(sum(k.size for k in state.kernels)),"original_bytes":int(original.nbytes),
                "folded_bytes":int(state.folded.nbytes),"kernel_bytes":int(kernel_bytes),"retained_bytes":int(retained),
                "working_set_ratio":original.nbytes/max(1,state.folded.nbytes),
                "retained_state_ratio":original.nbytes/max(1,retained),"relative_reconstruction_error":rel,
                "input_norm":float(np.linalg.norm(original)),"retained_pair_norm":math.sqrt(pair_norm_sq),
                "normalization":self.normalization,"complexity_contract":"O(depth*N) time; O(N) cumulative arithmetic per bounded geometric series",
                "claim_boundary":"Folded channel alone is not an isometry; full reversible state includes every kernel."}
