"""Independent re-verification of executed tensor results.

A receipt certifies the path taken; by itself it cannot prove the math is
right — a wrong-but-well-formed computation still produces a valid,
self-signed receipt. This module closes that transition on the production
route: before publication, every ``TensorRuntime`` execution re-derives
its output on an *alternate* path and compares.

* Folded results (lifted / committed / materialized) are re-checked
  against the unfolded NumPy reference — an independent computation over
  decoded operands that shares no code with the folded operator.
* Backend results are re-checked against the folded-resident catalogue —
  fold the operands, run ``folded_execute`` (lifted/committed/
  materializing as declared), unfold, and compare.

A divergence is a custody-violating defect: publication is refused
(:class:`TensorVerificationError`), the divergent output never reaches the
fold store, and no receipt is issued.

Honesty rules:

* ``bit_identical`` catalogue operators must match element-for-element —
  reassociation is only tolerated where the catalogue itself declares it
  (``bit_identical=False``), and then only to ``REASSOCIATION_RTOL``, the
  same bound the promotion harness declares.
* An operation with no alternate path is never faked: the verdict records
  ``recomputed=False`` and the receipt's correctness stays
  ``unvalidated``.
* Re-verification failure inside the checker itself (an unencodable
  operand, a fold refusal) degrades to an ``unverified`` verdict with the
  exception recorded — the checker must not crash the runtime nor claim
  coverage it did not perform.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from aethel.phi_fold import NumericFoldState, PhiFoldError, phi_fold, phi_unfold

from .errors import TensorVerificationError
from .folded import FOLDED_OPERATOR_CATALOGUE, folded_execute

VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_UNVERIFIED = "unverified"

#: Absolute residual bound for operators whose catalogue entry declares
#: float reassociation (``bit_identical=False``) — the same 1e-12 the
#: promotion harness (:func:`tensor.folded.evaluate_operator`) enforces.
REASSOCIATION_RTOL = 1e-12

#: Fold depth used when the backend path's operands are re-derived through
#: the folded-resident catalogue; mirrors ``TensorRuntime.default_depth``.
RECHECK_FOLD_DEPTH = 3


@dataclass(frozen=True)
class VerificationVerdict:
    """The independent re-check's evidence record for one execution.

    ``recomputed`` is the load-bearing honesty flag: ``False`` means no
    alternate-path recompute ran, and the verdict explains why. A
    ``verdict`` of ``"fail"`` is only ever produced by a completed,
    divergent recompute — never by an unavailable checker.
    """

    recomputed: bool
    method: str  # "unfolded_numpy_reference" | "folded_resident_recompute" | "none"
    verdict: str  # "pass" | "fail" | "unverified"
    max_residual: Optional[float]
    output_digest: str
    reference_digest: Optional[str]
    tolerance: Optional[float]
    elapsed_ns: int
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "recomputed": self.recomputed,
            "method": self.method,
            "verdict": self.verdict,
            "max_residual": self.max_residual,
            "output_digest": self.output_digest,
            "reference_digest": self.reference_digest,
            "tolerance": self.tolerance,
            "elapsed_ns": self.elapsed_ns,
            "detail": self.detail,
        }


def _unverified(method: str, detail: str, *, data=None) -> VerificationVerdict:
    return VerificationVerdict(
        recomputed=False,
        method=method,
        verdict=VERDICT_UNVERIFIED,
        max_residual=None,
        output_digest=_array_digest(data) if data is not None else "",
        reference_digest=None,
        tolerance=None,
        elapsed_ns=0,
        detail=detail,
    )


def _array_digest(array) -> str:
    """SHA-256 over dtype + C-order bytes — the compare surface itself."""
    arr = np.ascontiguousarray(np.asarray(array))
    digest = hashlib.sha256()
    digest.update(arr.dtype.str.encode("utf-8"))
    digest.update(repr(tuple(arr.shape)).encode("utf-8"))
    digest.update(arr.tobytes(order="C"))
    return digest.hexdigest()


def _compare(actual, reference, *, bit_identical: bool) -> tuple[bool, float]:
    """Element-space comparison under the operator's declared precision.

    Returns ``(matched, max_abs_residual)``. Bit-identical operators must
    match dtype and every element exactly; reassociation-tolerant
    operators compare within ``REASSOCIATION_RTOL``.
    """
    actual = np.asarray(actual)
    reference = np.atleast_1d(np.asarray(reference))
    if actual.shape != reference.shape or actual.size != reference.size:
        return False, float("inf")
    residual = (
        float(np.max(np.abs(actual - reference))) if actual.size else 0.0
    )
    if bit_identical:
        return bool(
            actual.dtype == reference.dtype
            and np.array_equal(actual, reference)
        ), residual
    return residual <= REASSOCIATION_RTOL, residual


def _verdict(
    *,
    method: str,
    matched: bool,
    residual: float,
    actual,
    reference,
    bit_identical: bool,
    elapsed_ns: int,
    detail: str,
) -> VerificationVerdict:
    return VerificationVerdict(
        recomputed=True,
        method=method,
        verdict=VERDICT_PASS if matched else VERDICT_FAIL,
        max_residual=residual,
        output_digest=_array_digest(actual),
        reference_digest=_array_digest(reference),
        tolerance=None if bit_identical else REASSOCIATION_RTOL,
        elapsed_ns=elapsed_ns,
        detail=detail,
    )


def _fold_operand(array: np.ndarray, depth: int) -> NumericFoldState:
    """Fold as deep as the operand allows — same policy as folded.py."""
    for candidate in range(int(depth), -1, -1):
        try:
            return phi_fold(np.atleast_1d(np.asarray(array)), depth=candidate)
        except PhiFoldError:
            continue
    raise PhiFoldError(  # pragma: no cover — any non-empty array folds at 0
        f"operand of size {np.asarray(array).size} cannot fold"
    )


def verify_folded_output(
    operation: str,
    states: Sequence[NumericFoldState],
    out_state: NumericFoldState,
) -> VerificationVerdict:
    """Re-check a folded-resident execution against the NumPy reference.

    The alternate path decodes every input operand, runs the catalogue
    operator's declared ``np_reference``, and compares the unfolded output
    element-for-element (exactly for ``bit_identical`` operators, within
    reassociation tolerance otherwise). This shares no compute path with
    the lifted/committed implementation under test.
    """
    op = FOLDED_OPERATOR_CATALOGUE.get(operation)
    if op is None:
        return _unverified(
            "none", f"no folded operator registered for {operation!r}"
        )
    started = time.perf_counter_ns()
    try:
        actual = phi_unfold(out_state)
        reference = np.atleast_1d(
            op.np_reference(*[phi_unfold(s) for s in states])
        )
    except Exception as exc:  # checker failed — honest unverified, no fake
        return _unverified(
            "unfolded_numpy_reference",
            f"re-check could not run: {type(exc).__name__}: {exc}",
            data=out_state.retained,
        )
    matched, residual = _compare(
        actual, reference, bit_identical=op.bit_identical
    )
    return _verdict(
        method="unfolded_numpy_reference",
        matched=matched,
        residual=residual,
        actual=actual,
        reference=reference,
        bit_identical=op.bit_identical,
        elapsed_ns=time.perf_counter_ns() - started,
        detail=(
            "folded output re-derived on the unfolded reference path"
            if matched
            else f"folded output diverges from the unfolded reference "
            f"(max abs residual {residual})"
        ),
    )


def verify_backend_output(
    operation: str,
    arrays: Sequence[np.ndarray],
    data,
) -> VerificationVerdict:
    """Re-check a backend execution against the folded-resident catalogue.

    The alternate path folds the same operands, runs ``folded_execute``
    (lifted/committed/materializing per the catalogue), unfolds, and
    compares — a custody-side recompute independent of the backend that
    produced ``data``. Operations outside the folded catalogue record an
    honest ``unverified`` verdict.
    """
    op = FOLDED_OPERATOR_CATALOGUE.get(operation)
    if op is None:
        return _unverified(
            "none", f"no folded operator registered for {operation!r}"
        )
    started = time.perf_counter_ns()
    try:
        states = tuple(
            _fold_operand(np.asarray(a), RECHECK_FOLD_DEPTH) for a in arrays
        )
        ref_state, _ = folded_execute(operation, states)
        reference = np.atleast_1d(np.asarray(phi_unfold(ref_state)))
        actual = np.asarray(data)
    except Exception as exc:  # checker failed — honest unverified, no fake
        return _unverified(
            "folded_resident_recompute",
            f"re-check could not run: {type(exc).__name__}: {exc}",
            data=data,
        )
    matched, residual = _compare(
        actual, reference, bit_identical=op.bit_identical
    )
    return _verdict(
        method="folded_resident_recompute",
        matched=matched,
        residual=residual,
        actual=actual,
        reference=reference,
        bit_identical=op.bit_identical,
        elapsed_ns=time.perf_counter_ns() - started,
        detail=(
            "backend output re-derived on the folded-resident path"
            if matched
            else f"backend output diverges from the folded-resident "
            f"recompute (max abs residual {residual})"
        ),
    )


def refuse_on_divergence(verdict: VerificationVerdict, context: str) -> None:
    """Fail closed when an independent re-check diverged.

    Raised before publication: the divergent output never enters custody
    and the request id is never populated.
    """
    if verdict.verdict == VERDICT_FAIL:
        raise TensorVerificationError(
            f"{context}: independent re-verification diverged — "
            f"{verdict.detail}"
        )


__all__ = [
    "REASSOCIATION_RTOL",
    "RECHECK_FOLD_DEPTH",
    "VERDICT_FAIL",
    "VERDICT_PASS",
    "VERDICT_UNVERIFIED",
    "VerificationVerdict",
    "refuse_on_divergence",
    "verify_backend_output",
    "verify_folded_output",
]
