"""Folded-resident operator catalogue for the ``tensor`` package.

The aethel numeric fold (:func:`aethel.phi_fold.phi_fold`) is a pure
contiguous partition: every resident segment holds logical tensor values
verbatim in C-order. That makes coordinate-local operators free to lift —
``D(op(E(x), E(y))) = op(x, y)`` holds because ``D`` is the identity on
segment contents — so a lifted coordinate op runs directly on folded
segments with **zero** decoded bytes and no re-fold.

Each :class:`FoldedOperator` declares a domain guard (dtypes/shapes it may
operate on), either a ``lifted`` implementation over
:class:`NumericFoldState` or an honest ``materializing`` declaration, and a
``precision`` flag distinguishing bit-identical lifts from approximate
ones. :func:`folded_execute` is the runtime entry point;
:func:`evaluate_operator` is the promotion harness — it measures both the
lifted and the materializing paths end-to-end against an independent
NumPy reference and returns a :class:`PromotionEvidence` record. Nothing
is promoted on faith: correctness is verified against the reference and
improvement is measured.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy as np

from aethel.phi_fold import (
    KernelBoundary,
    NumericFoldState,
    PhiFoldError,
    phi_fold,
    phi_unfold,
    splice_region,
    unfold_region,
)
from .contracts import TensorOpKind


class FoldedOpError(PhiFoldError):
    """A folded-resident operation violated its domain or custody rules."""


def _require_folded(condition: bool, message: str) -> None:
    if not condition:
        raise FoldedOpError(message)


def _segments(state: NumericFoldState) -> Tuple[np.ndarray, ...]:
    return (state.retained,) + tuple(reversed(state.complements))


def _same_domain(states: Tuple[NumericFoldState, ...]) -> None:
    base = states[0]
    for state in states[1:]:
        _require_folded(
            state.dtype == base.dtype,
            f"dtype mismatch: {state.dtype} vs {base.dtype}",
        )
        _require_folded(
            state.depth == base.depth,
            "fold depth mismatch — operands must share one fold geometry",
        )
        _require_folded(
            state.original_shape == base.original_shape,
            "shape mismatch between folded operands",
        )
        _require_folded(
            len(state.complements) == len(base.complements),
            "segment count mismatch — operands were folded differently",
        )
        for got, want in zip(_segments(state), _segments(base)):
            _require_folded(
                got.shape == want.shape,
                "segment layout mismatch between folded operands",
            )


def _coordinate_binary(
    states: Tuple[NumericFoldState, ...], np_op: Callable, op_name: str
) -> NumericFoldState:
    _require_folded(len(states) == 2, f"{op_name} is binary")
    _same_domain(states)
    left, right = states
    depth = left.depth
    segs_a, segs_b = _segments(left), _segments(right)
    retained = np_op(segs_a[0], segs_b[0])
    complements = tuple(
        np_op(a, b) for a, b in zip(reversed(segs_a[1:]), reversed(segs_b[1:]))
    )
    out = NumericFoldState(
        retained=np.asarray(retained, dtype=left.dtype),
        complements=tuple(
            np.asarray(s, dtype=left.dtype) for s in complements
        ),
        original_shape=left.original_shape,
        original_size=left.original_size,
        depth=depth,
        dtype=left.dtype,
        layout=left.layout,
    )
    object.__setattr__(out, "content_hash", out.compute_content_hash())
    return out


def _lifted_add(states):
    return _coordinate_binary(states, np.add, "add")


def _lifted_hadamard(states):
    return _coordinate_binary(states, np.multiply, "hadamard")


def _lifted_scale(states):
    tensor_state, scalar_state = states
    _require_folded(
        scalar_state.original_size == 1,
        "scale's second operand must be a single-element folded scalar",
    )
    scalar = scalar_state.retained.ravel()[0]
    segs = _segments(tensor_state)
    out = NumericFoldState(
        retained=np.asarray(segs[0] * scalar, dtype=tensor_state.dtype),
        complements=tuple(
            np.asarray(s * scalar, dtype=tensor_state.dtype)
            for s in reversed(segs[1:])
        ),
        original_shape=tensor_state.original_shape,
        original_size=tensor_state.original_size,
        depth=tensor_state.depth,
        dtype=tensor_state.dtype,
        layout=tensor_state.layout,
    )
    object.__setattr__(out, "content_hash", out.compute_content_hash())
    return out


def _lifted_fma(states):
    _require_folded(len(states) == 3, "fma is ternary")
    a_state, x_state, b_state = states
    _same_domain(states)
    segs = [_segments(s) for s in states]
    depth = a_state.depth
    retained = np.multiply(segs[0][0], segs[1][0]) + segs[2][0]
    complements = tuple(
        np.multiply(a, x) + b
        for a, x, b in zip(
            reversed(segs[0][1:]), reversed(segs[1][1:]), reversed(segs[2][1:])
        )
    )
    out = NumericFoldState(
        retained=np.asarray(retained, dtype=a_state.dtype),
        complements=tuple(
            np.asarray(s, dtype=a_state.dtype) for s in complements
        ),
        original_shape=a_state.original_shape,
        original_size=a_state.original_size,
        depth=depth,
        dtype=a_state.dtype,
        layout=a_state.layout,
    )
    object.__setattr__(out, "content_hash", out.compute_content_hash())
    return out


def _fold_operand(array: np.ndarray, depth: int) -> NumericFoldState:
    """Fold as deep as possible: small operands (e.g. scalars) cannot reach
    every depth — fold them at the deepest level their size permits."""
    for candidate in range(int(depth), -1, -1):
        try:
            return phi_fold(np.atleast_1d(np.asarray(array)), depth=candidate)
        except PhiFoldError:
            continue
    raise FoldedOpError(f"operand of size {np.asarray(array).size} cannot fold")  # pragma: no cover


def _materialize(
    states: Tuple[NumericFoldState, ...], np_op: Callable
) -> NumericFoldState:
    """Declared-materializing fallback: decode, compute, re-fold."""
    base = states[0]
    arrays = [phi_unfold(s) for s in states]
    out = np_op(*arrays)
    return _fold_operand(np.asarray(out), base.depth)


def _np_add(a, b):
    return a + b


def _np_hadamard(a, b):
    return a * b


def _np_scale(a, b):
    return a * np.asarray(b).reshape(-1)[0] if np.asarray(b).size == 1 else a * b


def _np_fma(a, x, b):
    return a * x + b


def _np_matmul(a, b):
    return np.matmul(a, b)


def _np_kron(a, b):
    return np.kron(a, b)


def _np_transpose(a):
    return np.transpose(a)


def _committed_rows(
    states: Tuple[NumericFoldState, ...],
    *,
    out_cols: int,
    rows_per_a_row: int,
    block_for: Callable[[np.ndarray, np.ndarray], np.ndarray],
) -> Tuple[NumericFoldState, Dict[str, int]]:
    """Row-block-committed contraction — the closed-loop folded write path.

    A contiguous row-block of the output depends on a contiguous row-range
    of the first operand plus ALL of the second: ``b`` is decoded once
    (global dependency, declared on the receipt) and each ``a`` row-range
    is fetched by region decode — no full-``a`` materialisation ahead of
    need. Every computed block is spliced into the allocated output fold
    at its declared flat coordinates, so the output exists *only* as
    committed folded lineage — never a whole-state replica assembled then
    re-folded.

    ``rows_per_a_row`` is how many output rows one ``a`` row spans (1 for
    matmul, ``b.shape[0]`` for kron); ``block_for(a_rows, b)`` computes
    the ``(a1 - a0) * rows_per_a_row`` output rows for an ``a`` row-block.
    """
    a_state, b_state = states
    a_rows, a_cols = a_state.original_shape
    b = np.asarray(phi_unfold(b_state))
    itemsize = np.dtype(a_state.dtype).itemsize
    decoded = b_state.original_size * itemsize
    out_rows = a_rows * rows_per_a_row
    out = phi_fold(
        np.zeros((out_rows, out_cols), dtype=a_state.dtype),
        depth=a_state.depth,
    )
    a_block_rows = max(1, a_rows // 8)
    peak = b.nbytes
    commit_regions = 0
    a0 = 0
    while a0 < a_rows:
        a1 = min(a_rows, a0 + a_block_rows)
        block, stats = unfold_region(a_state, (slice(a0, a1), slice(0, a_cols)))
        decoded += stats.decoded_bytes
        a_block = np.asarray(block).reshape(a1 - a0, a_cols)
        c_block = block_for(a_block, b)
        expected = (a1 - a0) * rows_per_a_row
        if c_block.shape != (expected, out_cols):
            raise FoldedOpError(  # pragma: no cover — invariant
                f"committed block shape {c_block.shape}, expected "
                f"({expected}, {out_cols})"
            )
        out, _ = splice_region(
            out,
            KernelBoundary(a0 * rows_per_a_row * out_cols, expected * out_cols),
            c_block,
        )
        peak = max(peak, b.nbytes + stats.decoded_bytes + c_block.nbytes)
        commit_regions += 1
        a0 = a1
    return out, {
        "decoded_bytes": int(decoded),
        "peak_materialized_bytes": int(peak),
        "commit_regions": commit_regions,
        "commit_bytes": out_rows * out_cols * itemsize,
    }


def _committed_matmul(
    states: Tuple[NumericFoldState, ...]
) -> Optional[Tuple[NumericFoldState, Dict[str, int]]]:
    """matmul with committed folded output: A row-blocks + global B.

    Dependency is honest: B is a global cone (decoded once, full); each
    output row-block decodes only its A rows. ``None`` when the operands
    are not rank-2 conformable — the caller falls back to the declared
    materializing path.
    """
    a_state, b_state = states
    if len(a_state.original_shape) != 2 or len(b_state.original_shape) != 2:
        return None
    if a_state.original_shape[1] != b_state.original_shape[0]:
        return None
    n = b_state.original_shape[1]
    return _committed_rows(
        states,
        out_cols=n,
        rows_per_a_row=1,
        block_for=lambda a_rows, b: np.matmul(a_rows, b),
    )


def _committed_kron(
    states: Tuple[NumericFoldState, ...]
) -> Optional[Tuple[NumericFoldState, Dict[str, int]]]:
    """kron with committed folded output: A row-blocks + global B.

    Output rows ``i*b_rows .. i*b_rows+b_rows-1`` belong to A row ``i`` —
    the same contiguous A-block cone as matmul. ``None`` for non-rank-2
    operands (mixed-radix kron stays declared-materializing).
    """
    a_state, b_state = states
    if len(a_state.original_shape) != 2 or len(b_state.original_shape) != 2:
        return None
    b_rows, b_cols = b_state.original_shape
    out_cols = a_state.original_shape[1] * b_cols
    return _committed_rows(
        states,
        out_cols=out_cols,
        rows_per_a_row=b_rows,
        block_for=lambda a_rows, b: np.kron(a_rows, b),
    )


def _np_reduce_sum(a):
    return np.asarray(np.sum(a))


@dataclass(frozen=True)
class FoldedOperator:
    """One registered folded-domain operator.

    ``lifted=None`` marks a declared-materializing operator: folded
    execution decodes to the reference path (its measured cost is what
    promotion must beat). ``bit_identical`` means the lifted path produces
    byte-identical results to the decode→compute→re-fold reference;
    ``False`` means the op is correct only up to declared float
    reassociation (residual is measured).
    """

    name: str
    kind: TensorOpKind
    arity: int
    np_reference: Callable
    lifted: Optional[Callable] = None
    #: Optional closed-loop implementation: still decodes its full
    #: dependency cone honestly, but the output is committed into folded
    #: custody by declared coordinates (no whole-state replica). Returns
    #: ``(state, info)`` or ``None`` when the operands are out of domain.
    committed: Optional[Callable] = None
    bit_identical: bool = True
    domain: str = "iufc dtypes, shared fold geometry"


FOLDED_OPERATOR_CATALOGUE: Dict[str, FoldedOperator] = {
    "add": FoldedOperator(
        "add", TensorOpKind.ELEMENTWISE, 2, _np_add, _lifted_add
    ),
    "hadamard": FoldedOperator(
        "hadamard", TensorOpKind.ELEMENTWISE, 2, _np_hadamard, _lifted_hadamard
    ),
    "scale": FoldedOperator(
        "scale",
        TensorOpKind.SCALE,
        2,
        _np_scale,
        _lifted_scale,
        domain="iufc dtypes; second operand is a 1-element folded scalar",
    ),
    "fma": FoldedOperator(
        "fma", TensorOpKind.FMA, 3, _np_fma, _lifted_fma
    ),
    "reduce_sum": FoldedOperator(
        "reduce_sum",
        TensorOpKind.REDUCE,
        1,
        _np_reduce_sum,
        None,  # partial sums over segments reorder reductions — declared materializing
        bit_identical=False,
        domain="iufc dtypes; reduces over the whole flat tensor",
    ),
    "transpose": FoldedOperator(
        "transpose",
        TensorOpKind.TRANSPOSE,
        1,
        _np_transpose,
        None,  # transposed flat order is a gather across segments — declared materializing
        domain="iufc dtypes; any rank",
    ),
    "matmul": FoldedOperator(
        "matmul",
        TensorOpKind.MATMUL,
        2,
        _np_matmul,
        None,  # global B dependency — committed output path below
        committed=_committed_matmul,
        # Row-block contraction reassociates vs one BLAS call — measured
        # ~1e-16 residual, so this is exact only up to declared tolerance.
        bit_identical=False,
        domain="iufc dtypes; rank-2 operands with conformable inner dims",
    ),
    "kron": FoldedOperator(
        "kron",
        TensorOpKind.KRON,
        2,
        _np_kron,
        None,  # global B dependency — committed output path below
        committed=_committed_kron,
        domain="iufc dtypes",
    ),
}


@dataclass(frozen=True)
class FoldedReceipt:
    """Measurement + provenance for one folded-domain execution."""

    operation: str
    path: str  # "lifted" | "committed" | "materialized"
    decoded_bytes: int
    output_elements: int
    output_hash: str
    elapsed_ns: int
    bit_identical: bool
    #: Committed-path measurements (0 on lifted/materialized paths):
    #: peak bytes held decoded at once, number of coordinate commits, and
    #: bytes written through commits.
    peak_materialized_bytes: int = 0
    commit_regions: int = 0
    commit_bytes: int = 0


def folded_execute(
    operation: str, states: Sequence[NumericFoldState]
) -> Tuple[NumericFoldState, FoldedReceipt]:
    """Execute a catalogue operator on folded state.

    Prefers the operator's lifted path; falls back to the declared
    materializing path and says so on the receipt. ``decoded_bytes`` is
    the measured residency read — zero for lifted coordinate ops.
    """
    op = FOLDED_OPERATOR_CATALOGUE.get(operation)
    _require_folded(op is not None, f"no folded operator registered for {operation!r}")
    states = tuple(states)
    _require_folded(
        len(states) == op.arity,
        f"{operation} expects {op.arity} operands, got {len(states)}",
    )
    for state in states:
        _require_folded(
            state.dtype.kind in "iufc",
            f"{operation} requires a numeric foldable dtype, got {state.dtype}",
        )
    start = time.perf_counter_ns()
    info: Dict[str, int] = {}
    if op.lifted is not None:
        out = op.lifted(states)
        decoded = 0
        path = "lifted"
    elif op.committed is not None and (
        committed := op.committed(states)
    ) is not None:
        out, info = committed
        decoded = info["decoded_bytes"]
        path = "committed"
    else:
        decoded = sum(
            s.original_size * np.dtype(s.dtype).itemsize for s in states
        )
        out = _materialize(states, op.np_reference)
        path = "materialized"
    elapsed = time.perf_counter_ns() - start
    receipt = FoldedReceipt(
        operation=operation,
        path=path,
        decoded_bytes=decoded,
        output_elements=out.original_size,
        output_hash=out.content_hash,
        elapsed_ns=elapsed,
        bit_identical=op.bit_identical,
        peak_materialized_bytes=info.get("peak_materialized_bytes", 0),
        commit_regions=info.get("commit_regions", 0),
        commit_bytes=info.get("commit_bytes", 0),
    )
    return out, receipt


@dataclass(frozen=True)
class PromotionEvidence:
    """Verified correctness + measured improvement for one operator."""

    operation: str
    promoted: bool
    path: str
    correct: bool
    max_residual: float
    lifted_ns: int
    materialized_ns: int
    decoded_bytes: int
    materialized_decoded_bytes: int
    rationale: str


def _time_call(fn: Callable[[], object], repeats: int) -> Tuple[int, ...]:
    """Best-of-N timing per call — returns each repeat's elapsed ns."""
    samples = []
    for _ in range(max(1, repeats)):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    return tuple(samples)


def evaluate_operator(
    operation: str,
    arrays: Sequence[np.ndarray],
    *,
    depth: int = 3,
    repeats: int = 5,
    rtol: float = 1e-12,
) -> PromotionEvidence:
    """Promotion harness: independent reference + measured cost, both paths.

    Runs the lifted path (if any) and the materializing path on the same
    folded operands, checks the result against the NumPy reference on
    unfolded data, and times both end-to-end. ``promoted`` requires a
    lifted path that is (a) correct vs the reference within ``rtol``
    (bit-identical for exact lifts) and (b) better on a named axis:
    strictly fewer decoded bytes, or strictly faster wall-time. Wall
    time is reported in the rationale but never gates promotion — a
    timing gate makes the verdict hostage to host jitter. Rejections
    carry their measured rationale — no operator hides a negative result.
    """
    op = FOLDED_OPERATOR_CATALOGUE.get(operation)
    _require_folded(op is not None, f"no folded operator registered for {operation!r}")
    _require_folded(
        len(arrays) == op.arity,
        f"{operation} expects {op.arity} operands, got {len(arrays)}",
    )
    states = tuple(_fold_operand(np.asarray(a), depth) for a in arrays)
    reference = op.np_reference(*[np.asarray(a) for a in arrays])

    # Materializing baseline — the honest comparison point. Timing uses the
    # per-path minimum over repeats: the mean stays hostage to scheduler
    # jitter on a loaded host, while the minimum is each path's real floor.
    mat_ns = min(
        _time_call(lambda: _materialize(states, op.np_reference), repeats)
    )
    mat_decoded = sum(
        s.original_size * np.dtype(s.dtype).itemsize for s in states
    )

    if op.lifted is None:
        if op.committed is not None:
            out = None

            def _commit_once() -> None:
                nonlocal out
                out = op.committed(states)

            commit_ns = min(_time_call(_commit_once, repeats))
            if out is not None:
                out_state, info = out
                unfolded = np.asarray(phi_unfold(out_state))
                residual = float(
                    np.max(np.abs(unfolded - np.asarray(reference)))
                    if np.asarray(reference).size
                    else 0.0
                )
                if op.bit_identical:
                    correct = bool(
                        unfolded.dtype == np.asarray(reference).dtype
                        and np.array_equal(unfolded, np.asarray(reference))
                    )
                else:
                    correct = residual <= rtol
                rationale = (
                    f"verified vs reference; committed row-block path: decoded "
                    f"{info['decoded_bytes']}B (full dependency cone), peak "
                    f"{info['peak_materialized_bytes']}B materialized, "
                    f"{info['commit_regions']} coordinate commits "
                    f"(committed {commit_ns}ns vs materialized {mat_ns}ns)"
                    if correct
                    else f"rejected: committed residual {residual} exceeds {rtol}"
                )
                return PromotionEvidence(
                    operation=operation,
                    promoted=correct,
                    path="committed" if correct else "materialized",
                    correct=correct,
                    max_residual=residual,
                    lifted_ns=commit_ns,
                    materialized_ns=mat_ns,
                    decoded_bytes=info["decoded_bytes"],
                    materialized_decoded_bytes=mat_decoded,
                    rationale=rationale,
                )
        out = _materialize(states, op.np_reference)
        residual = float(
            np.max(np.abs(np.asarray(phi_unfold(out)) - np.asarray(reference)))
            if np.asarray(reference).size
            else 0.0
        )
        return PromotionEvidence(
            operation=operation,
            promoted=False,
            path="materialized",
            correct=residual <= rtol,
            max_residual=residual,
            lifted_ns=mat_ns,
            materialized_ns=mat_ns,
            decoded_bytes=mat_decoded,
            materialized_decoded_bytes=mat_decoded,
            rationale="no lifted implementation — declared materializing",
        )

    out = None

    def _lift_once() -> None:
        nonlocal out
        out = op.lifted(states)

    lift_ns = min(_time_call(_lift_once, repeats))
    assert out is not None
    unfolded = np.asarray(phi_unfold(out))
    residual = float(
        np.max(np.abs(unfolded - np.asarray(reference)))
        if np.asarray(reference).size
        else 0.0
    )
    if op.bit_identical:
        correct = bool(
            unfolded.dtype == np.asarray(reference).dtype
            and np.array_equal(unfolded, np.asarray(reference))
        )
    else:
        correct = residual <= rtol
    # Promotion = verified correctness AND improvement on a named axis:
    # strictly fewer decoded bytes (structural — folded execution exists
    # to avoid the decode), or strictly faster wall-time. Wall time is
    # reported as evidence in the rationale but never gates promotion:
    # gate-on-timing makes the verdict hostage to host jitter.
    faster = lift_ns < mat_ns
    residency_win = 0 < mat_decoded
    promoted = correct and (faster or residency_win)
    if promoted and faster:
        rationale = (
            f"verified vs reference; lifted {lift_ns}ns < materialized {mat_ns}ns; "
            f"0 of {mat_decoded}B decoded"
        )
    elif promoted:
        rationale = (
            f"verified vs reference; residency promotion: 0 of {mat_decoded}B "
            f"decoded (lifted {lift_ns}ns vs materialized {mat_ns}ns)"
        )
    else:
        rationale = f"rejected: residual {residual} exceeds {rtol}"
    return PromotionEvidence(
        operation=operation,
        promoted=promoted,
        path="lifted" if promoted else "materialized",
        correct=correct,
        max_residual=residual,
        lifted_ns=lift_ns,
        materialized_ns=mat_ns,
        decoded_bytes=0,
        materialized_decoded_bytes=mat_decoded,
        rationale=rationale,
    )


def catalogue_report(
    depth: int = 3, repeats: int = 5
) -> Dict[str, PromotionEvidence]:
    """Run the promotion harness over every catalogue entry on one workload."""
    a = np.linspace(-1.0, 1.0, 256).reshape(16, 16)
    b = np.linspace(0.5, 1.5, 256).reshape(16, 16)
    scalar = np.array([1.25])
    workloads = {
        "add": (a, b),
        "hadamard": (a, b),
        "scale": (a, scalar),
        "fma": (a, b, np.full((16, 16), 0.25)),
        "reduce_sum": (a,),
        "transpose": (a,),
        "matmul": (a, b),
        "kron": (a[:4], b[:8, :8]),
    }
    return {
        name: evaluate_operator(name, workloads[name], depth=depth, repeats=repeats)
        for name in workloads
    }


__all__ = [
    "FOLDED_OPERATOR_CATALOGUE",
    "FoldedOpError",
    "FoldedOperator",
    "FoldedReceipt",
    "PromotionEvidence",
    "catalogue_report",
    "evaluate_operator",
    "folded_execute",
]
