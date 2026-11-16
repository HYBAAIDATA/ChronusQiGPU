"""Bounded full-state PULVINI operator calculus (July V3 API recovery).

Builds M by invoking the protected PhiRecursiveOperator on exact basis vectors,
not by replacing the operator. F(x) means the *complete* (folded, kernel)
representation; the contracted channel alone has no such isometry.

No universal quantum claim or physical speedup. Bounds prevent dense matrix
explosion; outputs report measured floating-point residuals.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from chronus.pulvini import PhiRecursiveOperator


@dataclass(frozen=True)
class CalculusCertificate:
    schema: str
    size: int
    normalization: str
    full_state_width: int
    injective: bool
    operator_condition_number: float
    induced_metric_scale: float
    induced_metric_relative_error: float
    numerical_tolerance: float
    verified: bool
    backend: str = "numpy-reference"
    physical_accelerator_measured: bool = False


class PulviniOperatorCalculus:
    """Finite-dimensional linear transport over a complete first-level fold."""

    def __init__(self, *, normalization: str = "orthonormal",
                 max_dimensions: int = 256, tolerance: float = 1e-10):
        if normalization not in {"orthonormal", "legacy"}:
            raise ValueError("normalization outside PULVINI contract")
        if type(max_dimensions) is not int or not 1 <= max_dimensions <= 256:
            raise ValueError("max_dimensions outside bounded dense-matrix policy")
        if not np.isfinite(tolerance) or not 0 < tolerance <= 1e-6:
            raise ValueError("invalid finite error budget")
        self.normalization = normalization
        self.max_dimensions = max_dimensions
        self.tolerance = tolerance
        self._operator = PhiRecursiveOperator(normalization=normalization)

    def fold_matrix(self, dimensions: int) -> np.ndarray:
        """F(x) = M x, where F holds BOTH working and residual channels."""
        if type(dimensions) is not int or not 1 <= dimensions <= self.max_dimensions:
            raise ValueError("dense operator dimensions outside bounded policy")
        unit = np.eye(dimensions, dtype=np.float64)
        columns = []
        for index in range(dimensions):
            folded, kernel = self._operator.fold(unit[:, index])
            columns.append(np.concatenate([folded, kernel]))
        return np.column_stack(columns)

    def certificate(self, dimensions: int) -> CalculusCertificate:
        M = self.fold_matrix(dimensions)
        metric = M.conj().T @ M
        # Full single-level state obeys M* M = c I; for a singleton
        # PhiRecursiveOperator.fold is explicitly identity.
        scale = float(np.vdot(M[:, 0], M[:, 0]).real)
        target = scale * np.eye(dimensions)
        residual = float(np.linalg.norm(metric-target) /
                         max(float(np.linalg.norm(target)), np.finfo(float).eps))
        singular = np.linalg.svd(M,compute_uv=False)
        condition = float(singular[0] / singular[-1])
        valid = (M.shape[1] == dimensions and
                 singular[-1] > self.tolerance and
                 residual <= self.tolerance and
                 abs(condition - 1.0) <= self.tolerance)
        return CalculusCertificate(
            schema="chronus.pulvini.full-state-calculus/1",
            size=dimensions, normalization=self.normalization,
            full_state_width=M.shape[0], injective=bool(valid),
            operator_condition_number=condition,
            induced_metric_scale=scale,
            induced_metric_relative_error=residual,
            numerical_tolerance=self.tolerance, verified=bool(valid),
        )

    def lift(self, operator: np.ndarray) -> np.ndarray:
        """B = M A M+ is an exact-space lift on range(M), not a QPU gate."""
        A = np.asarray(operator)
        if (A.ndim != 2 or A.shape[0] != A.shape[1] or
                not 1 <= A.shape[0] <= self.max_dimensions or
                not np.issubdtype(A.dtype, np.number) or
                not np.all(np.isfinite(A))):
            raise ValueError("operator must be a finite bounded square matrix")
        M = self.fold_matrix(A.shape[0])
        denom = float(np.vdot(M[:, 0],M[:, 0]).real)
        if denom <= 0:
            raise ValueError("non-injective fold geometry")
        # Pseudoinverse is M* / c when M* M = c I.
        with np.errstate(over="ignore", invalid="ignore"):
            lifted = M @ A @ (M.conj().T / denom)
        if not np.all(np.isfinite(lifted)):
            raise ValueError("lifted operator overflowed finite numerical contract")
        return lifted

    def verify_action(self, operator: np.ndarray, vector: np.ndarray) -> dict:
        A = np.asarray(operator)
        x = np.asarray(vector)
        if x.ndim != 1 or A.ndim != 2 or A.shape != (x.size,x.size):
            raise ValueError("operator and vector shape mismatch")
        if not np.issubdtype(x.dtype,np.number) or not np.all(np.isfinite(x)):
            raise ValueError("vector outside finite numerical contract")
        # Integer matrix products may wrap before the comparator runs.
        # Promote to the same reference scalar dtype as the lifted path;
        # reject integers/floats that cannot survive conversion exactly.
        dtype = np.dtype("complex128") if (
            np.iscomplexobj(A) or np.iscomplexobj(x)) else np.dtype("float64")
        with np.errstate(over="ignore", invalid="ignore"):
            cast_A = A.astype(dtype)
            cast_x = x.astype(dtype)
            back_A = cast_A.astype(A.dtype)
            back_x = cast_x.astype(x.dtype)
        if (not np.array_equal(A, back_A) or not np.array_equal(x, back_x)):
            raise ValueError("input values not exactly representable in numerical reference dtype")
        A, x = cast_A, cast_x
        M = self.fold_matrix(x.size)
        lifted = self.lift(A)
        with np.errstate(over="ignore", invalid="ignore"):
            expected = M @ (A @ x)
            actual = lifted @ (M @ x)
        if not np.all(np.isfinite(expected)) or not np.all(np.isfinite(actual)):
            raise ValueError("lifted action overflowed finite numerical contract")
        denom = max(float(np.linalg.norm(expected)),np.finfo(float).eps)
        error = float(np.linalg.norm(actual-expected)/denom)
        return {"schema":"chronus.pulvini.lifted-action/1",
                "size":int(x.size),"normalization":self.normalization,
                "relative_error":error,"tolerance":self.tolerance,
                "verified":bool(np.isfinite(error) and error <= self.tolerance),
                "backend":"numpy-reference","complete_state_required":True,
                "physical_accelerator_measured":False}
