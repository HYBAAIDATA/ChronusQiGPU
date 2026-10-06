"""Execution receipts: one bound evidence record per ``tensor.execute`` call.

Every completed execution — lifted-folded, declared-materializing, or
backend — publishes an :class:`ExecutionReceipt` that binds the request and
operator identity, the inputs and outputs (by id and content hash), the
backend and device that actually ran, declared vs. measured work, the
precision executed, residency and transfer traffic, the timing scope, and
the correctness result.

Measured bytes and analytical byte estimates are distinct fields — a
receipt never lets an estimate masquerade as traffic. ``truth_class``
mirrors :class:`tensor.contracts.TruthClass` end-to-end; ``timing_scope``
is ``"end_to_end"`` for host-timed executions and ``"device_event"`` only
when a physical device event produced the measurement.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Tuple

from .contracts import TruthClass


TIMING_END_TO_END = "end_to_end"
TIMING_DEVICE_EVENT = "device_event"

CORRECTNESS_UNVALIDATED = "unvalidated"
CORRECTNESS_VERIFIED = "verified"
CORRECTNESS_FAILED = "failed"


@dataclass(frozen=True)
class ExecutionReceipt:
    """One bound receipt for a completed execution.

    Byte accounting, all in bytes:

    * ``bytes_logical_inputs`` / ``bytes_logical_output`` — the dense sizes
      of what the operation consumed and produced.
    * ``bytes_resident`` — folded-custody bytes held by the operation's
      inputs (the segment payloads, not the logical sizes).
    * ``bytes_decoded`` — *measured* bytes decoded out of folded custody
      (zero for lifted paths; full logical size for materialized ones).
    * ``bytes_transferred`` — *measured* bytes moved through the backend
      path (arrays in, result out).
    * ``bytes_analytical`` — the naive dense estimate (logical inputs +
      logical output); never merged with the measured fields.
    """

    request_id: str
    operation: str
    backend: str
    device: str
    path: str  # "lifted" | "committed" | "materialized" | "backend"
    precision: str
    input_ids: Tuple[str, ...]
    input_hashes: Tuple[str, ...]
    output_id: str
    output_hash: str
    operations_declared: int
    operations_measured: int
    bytes_logical_inputs: int
    bytes_logical_output: int
    bytes_resident: int
    bytes_decoded: int
    bytes_transferred: int
    bytes_analytical: int
    elapsed_ns: int
    timing_scope: str
    fallback_used: bool
    fallback_reason: str
    correctness: str
    max_residual: Optional[float]
    truth_class: str
    cancelled: bool
    started_ns: int
    published_ns: int
    #: Independent re-verification evidence (see ``tensor.verification``):
    #: the alternate-path verdict bound to this receipt. ``None`` means no
    #: re-check ran — emitted as an explicit unverified record, never a
    #: silent pass.
    verification: Optional[dict] = None

    def as_dict(self) -> dict:
        return {
            "schema_version": "tensor.receipt/1",
            "request_id": self.request_id,
            "operation": self.operation,
            "backend": self.backend,
            "device": self.device,
            "path": self.path,
            "precision": self.precision,
            "input_ids": list(self.input_ids),
            "input_hashes": list(self.input_hashes),
            "output_id": self.output_id,
            "output_hash": self.output_hash,
            "operations_declared": self.operations_declared,
            "operations_measured": self.operations_measured,
            "bytes_logical_inputs": self.bytes_logical_inputs,
            "bytes_logical_output": self.bytes_logical_output,
            "bytes_resident": self.bytes_resident,
            "bytes_decoded": self.bytes_decoded,
            "bytes_transferred": self.bytes_transferred,
            "bytes_analytical": self.bytes_analytical,
            "elapsed_ns": self.elapsed_ns,
            "timing_scope": self.timing_scope,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "correctness": self.correctness,
            "max_residual": self.max_residual,
            "truth_class": self.truth_class,
            "cancelled": self.cancelled,
            "started_ns": self.started_ns,
            "published_ns": self.published_ns,
            "verification": (
                self.verification
                if self.verification is not None
                else {
                    "recomputed": False,
                    "method": "none",
                    "verdict": "unverified",
                    "detail": "no independent re-verification ran",
                }
            ),
        }


def _correctness_for(verification) -> str:
    """Correctness verdict driven by the independent re-check.

    A passing alternate-path recompute is the only source of
    ``verified``; a ``fail`` verdict never reaches this point (the runtime
    refuses publication first), and anything else stays honestly
    ``unvalidated``.
    """
    if verification is not None and getattr(verification, "verdict", None) == "pass":
        return CORRECTNESS_VERIFIED
    return CORRECTNESS_UNVALIDATED


def _verification_dict(verification) -> Optional[dict]:
    """Bind the verdict's evidence dict to the receipt (or None)."""
    if verification is None:
        return None
    if hasattr(verification, "as_dict"):
        return verification.as_dict()
    return dict(verification)


def resident_bytes(state) -> int:
    """Measured payload bytes of a numeric folded state (all segments)."""
    import numpy as np

    itemsize = np.dtype(state.dtype).itemsize
    segments = (state.retained,) + tuple(state.complements)
    return sum(int(np.asarray(seg).size) * itemsize for seg in segments)


def logical_bytes(state) -> int:
    import numpy as np

    return int(state.original_size) * np.dtype(state.dtype).itemsize


def build_folded_receipt(
    *,
    request_id: str,
    operation: str,
    states,
    output_name: str,
    out_state,
    fold_receipt,
    elapsed_ns: int,
    cancelled: bool = False,
    started_ns: int = 0,
    published_ns: Optional[int] = None,
    verification=None,
) -> ExecutionReceipt:
    """Receipt for a folded-resident execution.

    ``fold_receipt`` is the :class:`tensor.folded.FoldedReceipt` from
    ``folded_execute``; ``elapsed_ns`` is the end-to-end measurement that
    wrapped it (>= the inner elapsed). ``verification`` is the
    :class:`tensor.verification.VerificationVerdict` from the independent
    re-check; a passing verdict promotes correctness to ``verified``.
    """
    bytes_in = sum(logical_bytes(s) for s in states)
    bytes_out = logical_bytes(out_state)
    return ExecutionReceipt(
        request_id=request_id,
        operation=operation,
        backend=f"tensor.folded:{operation}",
        device="aethel-resident",
        path=fold_receipt.path,
        precision=str(out_state.dtype),
        input_ids=tuple(f"state:{i}" for i, _ in enumerate(states)),
        input_hashes=tuple(s.content_hash for s in states),
        output_id=output_name,
        output_hash=out_state.content_hash,
        operations_declared=sum(s.original_size for s in states),
        operations_measured=sum(s.original_size for s in states),
        bytes_logical_inputs=bytes_in,
        bytes_logical_output=bytes_out,
        bytes_resident=sum(resident_bytes(s) for s in states),
        bytes_decoded=fold_receipt.decoded_bytes,
        bytes_transferred=0,
        bytes_analytical=bytes_in + bytes_out,
        elapsed_ns=int(elapsed_ns),
        timing_scope=TIMING_END_TO_END,
        fallback_used=fold_receipt.path != "lifted",
        fallback_reason=(
            "" if fold_receipt.path == "lifted"
            else (
                "committed coordinate write-back; dependency cone decoded"
                if fold_receipt.path == "committed"
                else "no lifted implementation; declared materializing"
            )
        ),
        correctness=_correctness_for(verification),
        max_residual=None,
        truth_class=TruthClass.MEASURED.value,
        cancelled=cancelled,
        started_ns=started_ns,
        published_ns=published_ns if published_ns is not None else time.perf_counter_ns(),
        verification=_verification_dict(verification),
    )


def build_backend_receipt(
    *,
    request_id: str,
    operation: str,
    arrays,
    decoded_input_bytes: int,
    result,
    output_id: str,
    elapsed_ns: int,
    started_ns: int = 0,
    published_ns: Optional[int] = None,
    verification=None,
) -> ExecutionReceipt:
    """Receipt for a backend-engine execution.

    ``decoded_input_bytes`` counts any resident operands that had to be
    fully decoded to feed the backend — an honest residency cost that a
    pure array call reports as zero.
    """
    import numpy as np

    measurement = result.measurement
    provenance = result.provenance
    bytes_in = sum(int(np.asarray(a).nbytes) for a in arrays)
    bytes_out = int(np.asarray(result.data).nbytes)
    return ExecutionReceipt(
        request_id=request_id,
        operation=operation,
        backend=provenance.backend.name,
        device=provenance.backend.device_id or "cpu",
        path="backend",
        precision=str(np.asarray(result.data).dtype),
        input_ids=tuple(f"operand:{i}" for i, _ in enumerate(arrays)),
        input_hashes=(provenance.input_digest,),
        output_id=output_id,
        output_hash=provenance.output_digest,
        operations_declared=measurement.operations,
        operations_measured=measurement.operations,
        bytes_logical_inputs=bytes_in,
        bytes_logical_output=bytes_out,
        bytes_resident=0,
        bytes_decoded=int(decoded_input_bytes),
        bytes_transferred=bytes_in + bytes_out,
        bytes_analytical=bytes_in + bytes_out,
        elapsed_ns=int(elapsed_ns),
        timing_scope=TIMING_END_TO_END,
        fallback_used=measurement.fallback_used,
        fallback_reason=measurement.fallback_reason,
        correctness=_correctness_for(verification),
        max_residual=None,
        truth_class=result.truth_class.value,
        cancelled=False,
        started_ns=started_ns,
        published_ns=published_ns if published_ns is not None else time.perf_counter_ns(),
        verification=_verification_dict(verification),
    )


__all__ = [
    "CORRECTNESS_FAILED",
    "CORRECTNESS_UNVALIDATED",
    "CORRECTNESS_VERIFIED",
    "ExecutionReceipt",
    "TIMING_DEVICE_EVENT",
    "TIMING_END_TO_END",
    "build_backend_receipt",
    "build_folded_receipt",
    "logical_bytes",
    "resident_bytes",
]
