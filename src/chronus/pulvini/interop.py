"""Fail-closed, non-mining integration boundary for PULVINI V3 folds.

This is a *working-set representation* and does not assert net compression.
It does not mutate Chronus tensor, TURING, OVID, or mining authority.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import math
import numpy as np
from .formal import FoldState, PhiRecursiveOperator, ValidationError

@dataclass(frozen=True)
class FoldEvidence:
    schema: str
    normalization: str
    depth: int
    input_sha256: str
    reconstruction_sha256: str
    original_bytes: int
    folded_bytes: int
    kernel_bytes: int
    retained_bytes: int
    working_set_ratio: float
    retained_state_ratio: float
    relative_reconstruction_error: float
    reconstructed_within_tolerance: bool
    claim_scope: str = "reversible working-set representation, not net storage compression"


def _digest(array: np.ndarray) -> str:
    continuous = np.ascontiguousarray(array)
    return hashlib.sha256(continuous.tobytes(order="C")).hexdigest()


def _relative_error(reference: np.ndarray, reconstructed: np.ndarray) -> float:
    denom = max(float(np.linalg.norm(reference.reshape(-1))), np.finfo(float).eps)
    return float(np.linalg.norm((reference - reconstructed).reshape(-1)) / denom)


def fold_verified(data: np.ndarray, *, depth: int = 2,
                  normalization: str = "orthonormal", tolerance: float = 1e-12,
                  max_elements: int = 1_000_000) -> tuple[FoldState, FoldEvidence]:
    """Fold and immediately verify independent reconstruction before returning state.

    The signed receipt is not implied: hashes here provide integrity anchors only.
    Values are promoted to float64/complex128 by the V3 operator; the receipt
    compares against the promoted source, not float32 input storage.
    """
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0 or depth > 32:
        raise ValidationError("depth must be an integer from 0 to 32")
    if not math.isfinite(tolerance) or not 0.0 < tolerance <= 1e-6:
        raise ValidationError("tolerance must be finite, positive and <= 1e-6")
    source = np.asarray(data)
    if source.size == 0 or source.size > max_elements or not np.issubdtype(source.dtype, np.number):
        raise ValidationError("input size or dtype outside policy")
    if not np.all(np.isfinite(source)):
        raise ValidationError("non-finite input")
    operator = PhiRecursiveOperator(normalization=normalization, max_depth=32,
                                    max_elements=max_elements, require_finite=True)
    state = operator.fold_recursive(source, depth=depth)
    restored = operator.unfold_recursive(state)
    canonical = np.asarray(source, dtype=np.complex128 if np.iscomplexobj(source) else np.float64)
    if not np.all(np.isfinite(restored)) or restored.shape != canonical.shape:
        raise ValidationError("invalid reconstruction")
    error = _relative_error(canonical, restored)
    if not math.isfinite(error) or error > tolerance:
        raise ValidationError("reconstruction exceeds tolerance")
    retained = int(state.folded.nbytes + sum(k.nbytes for k in state.kernels))
    original = int(canonical.nbytes)
    folded = int(state.folded.nbytes)
    receipt = FoldEvidence(
        schema="chronus.pulvini.fold-evidence/1", normalization=normalization,
        depth=state.depth, input_sha256=_digest(canonical),
        reconstruction_sha256=_digest(restored), original_bytes=original,
        folded_bytes=folded, kernel_bytes=retained-folded,
        retained_bytes=retained, working_set_ratio=original/max(1, folded),
        retained_state_ratio=original/max(1, retained),
        relative_reconstruction_error=error, reconstructed_within_tolerance=True,
    )
    return state, receipt


def unfold_verified(state: FoldState, *, tolerance: float = 1e-12) -> np.ndarray:
    """Recover from a supplied state; validates chronology and finite output.

    This does not authenticate the source. Use independent signed custody when
    accepting untrusted artifacts; no mutable state should be trusted on its own.
    """
    if not math.isfinite(tolerance) or not 0 < tolerance <= 1e-6:
        raise ValidationError("invalid tolerance")
    operator = PhiRecursiveOperator(normalization=state.normalization)
    restored = operator.unfold_recursive(state)
    if not np.all(np.isfinite(restored)):
        raise ValidationError("non-finite reconstruction")
    return restored
