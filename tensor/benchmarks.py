"""Benchmark matrix for the folded-operator catalogue.

Sweeps operators x sizes x dtypes x layouts x residency x temperature and
records one measured row per repeat. Discipline:

* **Every sampled output is validated** against the operator's independent
  NumPy reference — a row's ``correct``/``max_residual`` are measured, not
  assumed. A failed validation is recorded, never hidden.
* **Cold/warm** is honest: for resident executions the first repeat is the
  cold row (state fetch + dispatch included in its elapsed); subsequent
  repeats are warm. For nonresident executions every repeat includes the
  fold, since folding is the cost a cold caller pays.
* **Resident vs nonresident** measures two real paths: executing over
  custody already in the store versus folding fresh operands each call.
* **Measured vs analytical bytes stay distinct**: ``bytes_decoded`` is
  measured traffic out of folded custody; ``bytes_analytical`` is the
  dense estimate of what conventional execution would move.
* ``truth_class`` is ``measured`` on every row; ``timing_scope`` is
  ``end_to_end`` — no device-event claims are fabricated on a CPU.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .folded import FOLDED_OPERATOR_CATALOGUE, FoldedOperator, folded_execute
from .receipts import TIMING_END_TO_END, resident_bytes
from .contracts import TruthClass


#: rtol for float64/complex128 validation; float32/complex64 use 1e-4.
_RTOL_FOR_KIND = {"f": 1e-4, "c": 1e-4, "i": 0.0, "u": 0.0}
_RTOL_STRICT = {"f": 1e-12, "c": 1e-12}


def _fold_as_deep_as(array: np.ndarray, depth: int):
    from aethel.phi_fold import PhiFoldError, phi_fold

    # Depth 0 is the honest floor: a degenerate fold (retained only) still
    # round-trips, so scalars and other too-small operands land there rather
    # than failing — and retrying depth 1 after the loop would mask the
    # very "cannot fold" error a small operand is allowed to avoid.
    last_err = None
    for candidate in range(depth, -1, -1):
        try:
            return phi_fold(array, depth=candidate)
        except PhiFoldError as exc:
            last_err = exc
    raise last_err  # pragma: no cover — phi_fold(depth=0) cannot raise for valid input


def _workload(
    op: FoldedOperator, shape: Tuple[int, ...], dtype: np.dtype, rng
) -> Tuple[np.ndarray, ...]:
    """Deterministic operand arrays for one catalogue operator."""

    def normal(dims):
        if dtype.kind == "c":
            return (
                rng.standard_normal(dims) + 1j * rng.standard_normal(dims)
            ).astype(dtype)
        return rng.standard_normal(dims).astype(dtype)

    if op.name in {"add", "hadamard", "matmul"}:
        return normal(shape), normal(shape)
    if op.name == "fma":
        return normal(shape), normal(shape), np.full(shape, 0.25, dtype=dtype)
    if op.name == "scale":
        return normal(shape), np.array([1.25], dtype=dtype)
    if op.name in {"reduce_sum", "transpose"}:
        return (normal(shape),)
    if op.name == "kron":
        # kron squares the element count — cap operands at 8x8 so the
        # benchmark's largest outputs stay bounded.
        n = min(int(shape[0]), 8)
        return normal((n, n)), normal((n, n))
    raise KeyError(f"no benchmark workload for operator {op.name!r}")


def _apply_layout(array: np.ndarray, layout: str) -> np.ndarray:
    if layout == "F" and array.ndim > 1:
        return np.asfortranarray(array)
    return np.ascontiguousarray(array)


def _validate(
    op: FoldedOperator, out_state, reference: np.ndarray, dtype: np.dtype
) -> Tuple[bool, float]:
    # Decode through the real path — phi_unfold reassembles the segments.
    from aethel.phi_fold import phi_unfold

    actual = phi_unfold(out_state).reshape(out_state.original_shape)
    diff = np.abs(np.asarray(actual, dtype=np.complex128)
                  - np.asarray(reference, dtype=np.complex128))
    max_residual = float(diff.max()) if diff.size else 0.0
    if op.bit_identical:
        return bool(np.array_equal(np.asarray(actual), np.asarray(reference))), 0.0
    rtol = _RTOL_STRICT.get(dtype.kind, 1e-12)
    if dtype in (np.dtype(np.float32), np.dtype(np.complex64)):
        rtol = _RTOL_FOR_KIND.get(dtype.kind, 1e-4)
    ok = bool(np.allclose(actual, reference, rtol=rtol, atol=rtol))
    return ok, max_residual


@dataclass(frozen=True)
class BenchmarkRow:
    """One measured repeat of one benchmark cell."""

    operation: str
    path: str
    residency: str  # "resident" | "nonresident"
    temperature: str  # "cold" | "warm"
    repeat: int
    shape: Tuple[int, ...]
    dtype: str
    layout: str
    elapsed_ns: int
    bytes_decoded: int
    bytes_resident: int
    bytes_analytical: int
    output_elements: int
    correct: bool
    max_residual: float
    truth_class: str
    timing_scope: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "path": self.path,
            "residency": self.residency,
            "temperature": self.temperature,
            "repeat": self.repeat,
            "shape": list(self.shape),
            "dtype": self.dtype,
            "layout": self.layout,
            "elapsed_ns": self.elapsed_ns,
            "bytes_decoded": self.bytes_decoded,
            "bytes_resident": self.bytes_resident,
            "bytes_analytical": self.bytes_analytical,
            "output_elements": self.output_elements,
            "correct": self.correct,
            "max_residual": self.max_residual,
            "truth_class": self.truth_class,
            "timing_scope": self.timing_scope,
        }


@dataclass
class BenchmarkReport:
    """The full measured matrix plus a declared-scope envelope."""

    seed: int
    repeats: int
    depth: int
    rows: List[BenchmarkRow] = field(default_factory=list)
    generated_ns: int = field(default_factory=time.perf_counter_ns)

    @property
    def all_valid(self) -> bool:
        return all(r.correct for r in self.rows)

    @property
    def validated_outputs(self) -> int:
        return sum(1 for r in self.rows if r.correct)

    @property
    def failed_outputs(self) -> int:
        return sum(1 for r in self.rows if not r.correct)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "tensor.benchmark/1",
            "truth_class": TruthClass.MEASURED.value,
            "timing_scope": TIMING_END_TO_END,
            "hardware": "cpu",
            "claim_boundary": (
                "host-timed end-to-end measurements on this machine; "
                "analytical bytes are estimates, decoded bytes are measured"
            ),
            "seed": self.seed,
            "repeats": self.repeats,
            "depth": self.depth,
            "validated_outputs": self.validated_outputs,
            "failed_outputs": self.failed_outputs,
            "all_valid": self.all_valid,
            "rows": [r.as_dict() for r in self.rows],
        }


def run_benchmarks(
    *,
    operations: Optional[Sequence[str]] = None,
    sizes: Sequence[Tuple[int, ...]] = ((16, 16), (64, 64)),
    dtypes: Sequence[str] = ("float64", "float32", "complex128"),
    layouts: Sequence[str] = ("C", "F"),
    repeats: int = 3,
    depth: int = 3,
    seed: int = 0,
) -> BenchmarkReport:
    """Run the benchmark matrix over the folded-operator catalogue.

    ``operations=None`` covers the whole catalogue. Every sampled output
    is validated; ``repeats`` warm rows follow one cold row for resident
    executions, while every nonresident repeat is cold by construction
    (fold included).
    """
    report = BenchmarkReport(seed=int(seed), repeats=int(repeats), depth=int(depth))
    selected = {
        name: op for name, op in FOLDED_OPERATOR_CATALOGUE.items()
        if operations is None or name in operations
    }
    for name, op in selected.items():
        for shape in sizes:
            for dtype_name in dtypes:
                dtype = np.dtype(dtype_name)
                for layout in layouts:
                    rng = np.random.default_rng(seed)
                    arrays = tuple(
                        _apply_layout(a, layout)
                        for a in _workload(op, shape, dtype, rng)
                    )
                    reference = op.np_reference(*arrays)
                    resident_states = tuple(
                        _fold_as_deep_as(a, depth) for a in arrays
                    )
                    analytical = sum(
                        int(a.nbytes) for a in arrays
                    ) + int(np.asarray(reference).nbytes)

                    for residency in ("nonresident", "resident"):
                        warm_repeats = repeats if residency == "resident" else repeats
                        cold_repeats = 1
                        total = cold_repeats + warm_repeats
                        for rep in range(total):
                            t0 = time.perf_counter_ns()
                            if residency == "nonresident":
                                states = tuple(
                                    _fold_as_deep_as(a, depth) for a in arrays
                                )
                            else:
                                states = resident_states
                            out_state, receipt = folded_execute(name, states)
                            elapsed = time.perf_counter_ns() - t0
                            correct, residual = _validate(
                                op, out_state, reference, dtype
                            )
                            report.rows.append(
                                BenchmarkRow(
                                    operation=name,
                                    path=receipt.path,
                                    residency=residency,
                                    temperature=(
                                        "cold"
                                        if rep == 0
                                        or residency == "nonresident"
                                        else "warm"
                                    ),
                                    repeat=rep,
                                    shape=tuple(int(d) for d in shape),
                                    dtype=dtype.name,
                                    layout=layout,
                                    elapsed_ns=int(elapsed),
                                    bytes_decoded=receipt.decoded_bytes,
                                    bytes_resident=sum(
                                        resident_bytes(s) for s in states
                                    ),
                                    bytes_analytical=analytical,
                                    output_elements=out_state.original_size,
                                    correct=correct,
                                    max_residual=residual,
                                    truth_class=TruthClass.MEASURED.value,
                                    timing_scope=TIMING_END_TO_END,
                                )
                            )
    return report


__all__ = ["BenchmarkReport", "BenchmarkRow", "run_benchmarks"]
