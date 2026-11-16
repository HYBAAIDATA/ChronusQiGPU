"""Genuine PULVINI complete-fold linear arithmetic with verified recovery.

Because the protected V3 map is linear, F(a*x+b*y) can be computed from
(a*folded_x+b*folded_y, a*kernels_x+b*kernels_y) without re-folding.
We nevertheless materialise each original ONCE for fail-closed integrity and
an independent NumPy reference comparator. No physical or net-compression claim.
"""
from __future__ import annotations

import hashlib
import time

import numpy as np

from chronus.pulvini import FoldEvidence, FoldState, PhiRecursiveOperator, unfold_verified
from chronus.tensor.folded_compute import FoldedExecutionResult, VerifiedFoldedOperand


def combine_verified_folded(
    left: VerifiedFoldedOperand,
    right: VerifiedFoldedOperand,
    *,
    alpha: float | complex = 1.0,
    beta: float | complex = 1.0,
    tolerance: float = 1e-12,
    max_elements: int = 1_000_000,
) -> FoldedExecutionResult:
    """Linear combination on full folded channels, then independently check it."""
    if not isinstance(left, VerifiedFoldedOperand) or not isinstance(right, VerifiedFoldedOperand):
        raise ValueError("complete verified PULVINI operands required")
    a,b=left.state,right.state
    if (a.normalization != b.normalization or a.sizes != b.sizes or
            a.original_shape != b.original_shape or len(a.kernels) != len(b.kernels)):
        raise ValueError("folded operands have incompatible chronology or geometry")
    if (not a.sizes or a.sizes[0] > max_elements or type(max_elements) is not int or
            not 1 <= max_elements <= 1_000_000):
        raise ValueError("folded arithmetic outside bounded element policy")
    if not np.isfinite(tolerance) or not 0 < tolerance <= 1e-6:
        raise ValueError("invalid arithmetic error budget")
    # Neither an apparently matching receipt nor unfold_recursive checks the
    # final sizes entry by itself. Validate the full chronology before acting.
    operator_geometry = PhiRecursiveOperator(normalization=a.normalization)
    for state in (a,b):
        if (len(state.sizes) != len(state.kernels)+1 or
                state.sizes[-1] != state.folded.size or
                state.folded.dtype not in (np.dtype("float64"),np.dtype("complex128")) or
                any(kernel.dtype != state.folded.dtype for kernel in state.kernels)):
            raise ValueError("complete-fold chronology or canonical dtype invalid")
        for depth, kernel in enumerate(state.kernels):
            original_dim = state.sizes[depth]
            if type(original_dim) is not int or original_dim < 2:
                raise ValueError("complete-fold chronology invalid")
            folded_dim,_ = operator_geometry.fibonacci_split(original_dim)
            if state.sizes[depth+1] != folded_dim or kernel.size != folded_dim:
                raise ValueError("complete-fold split geometry invalid")
    for scalar in (alpha,beta):
        if (not np.isscalar(scalar) or isinstance(scalar,(str,bytes,bool)) or
                not np.issubdtype(np.asarray(scalar).dtype,np.number) or
                not np.isfinite(scalar)):
            raise ValueError("finite numeric scalar required")
        scalar_source = np.asarray(scalar)
        canonical = np.dtype("complex128") if (
            np.iscomplexobj(a.folded) or np.iscomplexobj(b.folded) or
            np.iscomplexobj(scalar_source)) else np.dtype("float64")
        with np.errstate(over="ignore", invalid="ignore"):
            promoted = scalar_source.astype(canonical)
            roundtripped = promoted.astype(scalar_source.dtype)
        if not np.array_equal(roundtripped, scalar_source):
            raise ValueError("folded coefficient not exactly representable")
    result_dtype=np.result_type(a.folded.dtype,b.folded.dtype,
                                np.asarray(alpha).dtype,np.asarray(beta).dtype)
    if result_dtype not in (np.dtype("float64"),np.dtype("complex128")):
        raise ValueError("only canonical float64/complex128 folded arithmetic is supported")
    t0=time.perf_counter_ns()
    # Full input recovery validates each retained state/receipt before reuse.
    xa=unfold_verified(a,receipt=left.evidence)
    xb=unfold_verified(b,receipt=right.evidence)
    reference=np.asarray(alpha*xa+beta*xb,dtype=result_dtype)
    # The operation itself is in the FULL folded representation.
    folded=np.asarray(alpha*a.folded+beta*b.folded,dtype=result_dtype)
    kernels=tuple(np.asarray(alpha*ka+beta*kb,dtype=result_dtype)
                  for ka,kb in zip(a.kernels,b.kernels))
    state=FoldState(folded=folded,kernels=kernels,sizes=a.sizes,
                    original_shape=a.original_shape,
                    original_dtype=str(reference.dtype),normalization=a.normalization)
    operator=PhiRecursiveOperator(normalization=a.normalization,max_elements=max_elements)
    recovered=operator.unfold_recursive(state)
    if (not np.all(np.isfinite(reference)) or not np.all(np.isfinite(recovered))
            or not np.allclose(recovered,reference,rtol=tolerance,atol=tolerance)):
        raise ValueError("folded-domain arithmetic failed independent numerical comparator")
    reference_bytes=np.ascontiguousarray(reference).tobytes()
    recovered_bytes=np.ascontiguousarray(recovered).tobytes()
    original_bytes=reference.nbytes
    active_bytes=folded.nbytes
    kernel_bytes=sum(k.nbytes for k in kernels)
    error=float(np.linalg.norm((reference-recovered).reshape(-1))/
                max(float(np.linalg.norm(reference.reshape(-1))),np.finfo(float).eps))
    evidence=FoldEvidence(
        schema="chronus.pulvini.fold-evidence/1",
        normalization=a.normalization,depth=state.depth,
        input_sha256=hashlib.sha256(reference_bytes).hexdigest(),
        reconstruction_sha256=hashlib.sha256(recovered_bytes).hexdigest(),
        original_bytes=int(original_bytes),folded_bytes=int(active_bytes),
        kernel_bytes=int(kernel_bytes),retained_bytes=int(active_bytes+kernel_bytes),
        working_set_ratio=original_bytes/max(1,active_bytes),
        retained_state_ratio=original_bytes/max(1,active_bytes+kernel_bytes),
        relative_reconstruction_error=error,reconstructed_within_tolerance=True,
    )
    if not np.array_equal(unfold_verified(state,receipt=evidence),recovered):
        raise ValueError("constructed arithmetic receipt fails verification")
    return FoldedExecutionResult(
        operand=VerifiedFoldedOperand(
            state,evidence,"LOCAL_NUMERICAL_COMPARATOR_NOT_SIGNED"),
        operation="linear_combination_complete_fold",
        backend="numpy-reference-folded-channels",
        elapsed_ns=time.perf_counter_ns()-t0,numerical_output_verified=True,
        whole_state_materialised=True,physical_accelerator_measured=False,
        net_storage_savings_measured=False,fused_hardware_instruction=False,
    )
