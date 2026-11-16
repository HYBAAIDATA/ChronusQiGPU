"""PULVINI V3 -> HERMES folded-operands execution bridge.

Reinstates the July 2026 FoldState-facing FMA/tensor operation contract using
existing PULVINI and Chronus tensor engines. Numerical work currently executes
on NumPy CPU reference, not folded-domain arithmetic or an accelerator.
The entire fold state (including all kernels) is retained and validated.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Any

import numpy as np

from chronus.pulvini import FoldEvidence, FoldState, fold_verified, unfold_verified
from chronus.tensor.geodesic import PhiTensorCore


@dataclass(frozen=True)
class VerifiedFoldedOperand:
    state: FoldState
    evidence: FoldEvidence
    # Unkeyed receipt hashes establish local consistency, NOT independently
    # authenticated original-data provenance or an AL HARAS signature.
    source_digest_authentication: str = "UNVERIFIED_UNSIGNED_ORIGIN"


@dataclass(frozen=True)
class FoldedExecutionResult:
    operand: VerifiedFoldedOperand
    operation: str
    backend: str
    elapsed_ns: int
    numerical_output_verified: bool
    physical_accelerator_measured: bool = False
    net_storage_savings_measured: bool = False
    whole_state_materialised: bool = True
    fused_hardware_instruction: bool = False

    def public_metrics(self) -> dict[str, Any]:
        receipt = self.operand.evidence
        return {
            "schema": "chronus.pulvini.hermes-local-execution/1",
            "operation": self.operation,
            "backend": self.backend,
            "elapsed_ns": self.elapsed_ns,
            "numerical_output_verified": self.numerical_output_verified,
            "input_storage_claim": "complete fold includes all retained kernels",
            "original_bytes": receipt.original_bytes,
            "active_folded_bytes": receipt.folded_bytes,
            "kernel_bytes": receipt.kernel_bytes,
            "total_retained_bytes": receipt.retained_bytes,
            "relative_reconstruction_error": receipt.relative_reconstruction_error,
            "physical_accelerator_measured": self.physical_accelerator_measured,
            "net_storage_savings_measured": self.net_storage_savings_measured,
            "source_hash_status": "LOCAL_UNKEYED_DIGEST_NOT_INDEPENDENT_ATTESTATION",
            "whole_state_materialised": self.whole_state_materialised,
            "fused_hardware_instruction": self.fused_hardware_instruction,
        }


class FoldedTensorExecutor:
    """FoldState-facing operations over current Chronus without reimplementing cores.

    Input FoldStates must have trustworthy matching FoldEvidence. This does not
    claim O(1) partial access or folded-domain arithmetic: verification unfolds
    the complete state before dispatch to the existing NumPy reference backend.
    """

    def __init__(self, *, depth: int = 4, tolerance: float = 1e-12,
                 max_elements: int = 1_000_000):
        if type(depth) is not int or not 0 <= depth <= 32:
            raise ValueError("depth must be 0..32")
        if type(max_elements) is not int or not 1 <= max_elements <= 1_000_000:
            raise ValueError("max_elements outside bounded policy")
        if not np.isfinite(tolerance) or not 0 < tolerance <= 1e-6:
            raise ValueError("invalid numerical error budget")
        self.depth, self.tolerance, self.max_elements = depth, float(tolerance), max_elements
        self.tensor_core = PhiTensorCore()

    def fold(self, data: np.ndarray) -> VerifiedFoldedOperand:
        state, evidence = fold_verified(np.asarray(data), depth=self.depth,
                                        tolerance=self.tolerance,
                                        max_elements=self.max_elements)
        return VerifiedFoldedOperand(state, evidence,
                                     "LOCAL_SOURCE_HASH_COMPUTED_NOT_SIGNED")

    def materialise(self, operand: VerifiedFoldedOperand) -> np.ndarray:
        if not isinstance(operand, VerifiedFoldedOperand):
            raise ValueError("FoldState requires paired verification evidence")
        if (not operand.state.sizes or operand.state.sizes[0] > self.max_elements
                or operand.state.folded.size > self.max_elements):
            raise ValueError("folded state outside bounded policy")
        return unfold_verified(operand.state, receipt=operand.evidence)

    def execute(self, operation: str, *operands: VerifiedFoldedOperand,
                scalar: float | complex | None = None) -> FoldedExecutionResult:
        if operation not in {"fma", "add", "hadamard", "scale", "matmul", "reduce_sum"}:
            raise ValueError("unsupported folded operation")
        required = {"fma": 3, "add": 2, "hadamard": 2,
                    "scale": 1, "matmul": 2, "reduce_sum": 1}[operation]
        if len(operands) != required:
            raise ValueError("wrong folded operand count")
        t0 = perf_counter_ns()
        values = [self.materialise(v) for v in operands]
        if operation == "matmul" and all(v.ndim == 2 for v in values):
            if (values[0].shape[1] != values[1].shape[0] or
                    values[0].shape[0] * values[1].shape[1] > self.max_elements):
                raise ValueError("matrix multiplication output exceeds bounded policy")
        if operation == "fma":
            # Two ordinary CPU operations; NOT fused arithmetic or a GPU FMA.
            multiplied = self.tensor_core.execute("hadamard", values[0], values[1])
            core = self.tensor_core.execute("add", multiplied["output"], values[2])
            expected = np.add(np.multiply(values[0], values[1]), values[2])
        else:
            core = self.tensor_core.execute(operation, *values, scalar=scalar)
            if operation == "add": expected = values[0] + values[1]
            elif operation == "hadamard": expected = values[0] * values[1]
            elif operation == "scale": expected = values[0] * scalar
            elif operation == "matmul": expected = values[0] @ values[1]
            else: expected = np.asarray(values[0].sum())
        output = np.asarray(core["output"])
        if output.size < 1 or output.size > self.max_elements or not np.all(np.isfinite(output)):
            raise ValueError("execution output outside policy")
        # This checks the candidate output, not an independently different
        # numerical algorithm; performance cannot be inferred from this check.
        if not np.array_equal(output, expected):
            raise ValueError("NumPy reference output mismatch")
        folded = self.fold(output)
        materialised = self.materialise(folded)
        if not np.allclose(materialised, output, rtol=self.tolerance,
                           atol=self.tolerance, equal_nan=False):
            raise ValueError("folded output reconstruction failed")
        return FoldedExecutionResult(
            operand=folded, operation=operation, backend=core["backend"],
            elapsed_ns=perf_counter_ns()-t0, numerical_output_verified=True,
        )

    def execute_folded_linear(self, left: VerifiedFoldedOperand,
                              right: VerifiedFoldedOperand, *,
                              alpha: float | complex = 1.0,
                              beta: float | complex = 1.0) -> FoldedExecutionResult:
        """Execute linear combination IN complete fold coordinates.

        This uses the maintained PULVINI map and all residual kernels; it
        independently materialises inputs for evidence verification. Not an
        unmeasured GPU acceleration claim or a folded-only compression codec.
        """
        from chronus.pulvini.linear_arithmetic import combine_verified_folded

        return combine_verified_folded(
            left, right, alpha=alpha, beta=beta, tolerance=self.tolerance,
            max_elements=self.max_elements,
        )

    def update_window(self, base: VerifiedFoldedOperand,
                      replacement: np.ndarray, *, start: int,
                      stop: int) -> FoldedExecutionResult:
        """Restore bounded July slice updates, materialising the entire array.

        This path reconstructs, updates and re-folds the complete state. It is
        NOT true selective φ-unfold and does not claim bandwidth amplification.
        """
        if type(start) is not int or type(stop) is not int:
            raise ValueError("window bounds must be integers")
        t0 = perf_counter_ns()
        array = self.materialise(base)
        if not (0 <= start < stop <= array.size):
            raise ValueError("window outside original tensor")
        items = np.asarray(replacement)
        if items.ndim != 1 or items.size != stop-start or not np.all(np.isfinite(items)):
            raise ValueError("replacement shape or finite contract failed")
        if not np.can_cast(items.dtype, array.dtype, casting="safe"):
            raise ValueError("replacement would silently truncate numerical precision")
        # dtype-level "safe" casting is insufficient: NumPy permits int64 ->
        # float64 although values beyond 2**53 are not exactly representable.
        # Compare in the ORIGINAL dtype after round-tripping the candidate.
        with np.errstate(over="ignore", invalid="ignore"):
            candidate = np.asarray(items, dtype=array.dtype)
            roundtripped = candidate.astype(items.dtype)
        if not np.array_equal(roundtripped, items):
            raise ValueError("replacement would silently truncate numerical precision")
        changed = array.copy().reshape(-1)
        changed[start:stop] = items
        folded = self.fold(changed.reshape(array.shape))
        restored = self.materialise(folded)
        if not np.allclose(restored, changed.reshape(array.shape), rtol=self.tolerance,
                           atol=self.tolerance):
            raise ValueError("updated fold did not reconstruct")
        return FoldedExecutionResult(
            operand=folded, operation="bounded_full_refold_window_update",
            backend="numpy-reference", elapsed_ns=perf_counter_ns()-t0,
            numerical_output_verified=True,
        )
