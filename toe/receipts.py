"""Provenance receipts binding a TOE result to the computation that made it.

A receipt records, for one explanation, decision, estimate or counterfactual:

- ``input_sha256``: digest of the input state. The raw input is NOT stored.
- ``config``: model identifier, target, graph digest, intervention; small,
  non-sensitive and stored in full.
- ``output`` and ``output_sha256``: the result artifact and its digest.
- ``execution_evidence``: what ran it (engine, arithmetic, version).
- ``run_id``, ``sequence``, ``timestamp`` and ``prev_sha256``: the hash chain.

``receipt_sha256`` covers every field above, so any edit to a stored receipt
is detected. Chaining through ``prev_sha256`` detects reordering, insertion
and deletion. ``replay`` recomputes the output from its inputs and compares
digests, which detects a changed model parameter or input. Canonical JSON
follows the repository convention (sorted keys, compact separators) and
refuses NaN.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any, Callable, Dict, List, Mapping, Optional

RECEIPT_FORMAT = "toe.receipt/v1"


def _default(value: Any) -> Any:
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    raise TypeError(f"not canonically serialisable: {type(value).__name__}")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=_default
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _plain(value: Any) -> Any:
    """A JSON-plain deep copy, so later edits to the caller's object are inert."""
    return json.loads(canonical_json(value))


@dataclass(frozen=True)
class Receipt:
    kind: str
    run_id: str
    sequence: int
    timestamp: str
    input_sha256: str
    config: Dict[str, Any]
    output: Dict[str, Any]
    output_sha256: str
    execution_evidence: Dict[str, Any]
    prev_sha256: str
    receipt_sha256: str
    format: str = RECEIPT_FORMAT

    def body(self) -> Dict[str, Any]:
        return {
            "format": self.format,
            "kind": self.kind,
            "run_id": self.run_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "input_sha256": self.input_sha256,
            "config": self.config,
            "output": self.output,
            "output_sha256": self.output_sha256,
            "execution_evidence": self.execution_evidence,
            "prev_sha256": self.prev_sha256,
        }

    def recompute(self) -> str:
        return digest(self.body())

    def as_dict(self) -> Dict[str, Any]:
        return {**self.body(), "receipt_sha256": self.receipt_sha256}


class ReceiptLedger:
    """An append-only, hash-chained sequence of receipts for one run."""

    def __init__(self, run_id: Optional[str] = None) -> None:
        self.run_id = run_id or uuid.uuid4().hex
        self._records: List[Receipt] = []

    @property
    def records(self) -> List[Receipt]:
        return list(self._records)

    def issue(
        self,
        kind: str,
        *,
        inputs: Any,
        config: Mapping[str, Any],
        output: Mapping[str, Any],
        execution_evidence: Optional[Mapping[str, Any]] = None,
    ) -> Receipt:
        output_plain = _plain(dict(output))
        body = {
            "format": RECEIPT_FORMAT,
            "kind": str(kind),
            "run_id": self.run_id,
            "sequence": len(self._records),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_sha256": digest(inputs),
            "config": _plain(dict(config)),
            "output": output_plain,
            "output_sha256": digest(output_plain),
            "execution_evidence": _plain(dict(execution_evidence or {})),
            "prev_sha256": self._records[-1].receipt_sha256 if self._records else "",
        }
        receipt = Receipt(
            kind=body["kind"],
            run_id=body["run_id"],
            sequence=body["sequence"],
            timestamp=body["timestamp"],
            input_sha256=body["input_sha256"],
            config=body["config"],
            output=body["output"],
            output_sha256=body["output_sha256"],
            execution_evidence=body["execution_evidence"],
            prev_sha256=body["prev_sha256"],
            receipt_sha256=digest(body),
        )
        self._records.append(receipt)
        return receipt

    def verify(self) -> Dict[str, Any]:
        """Recompute every digest and chain link."""
        return verify_chain(self._records)

    def export(self) -> List[Dict[str, Any]]:
        return [r.as_dict() for r in self._records]


def verify_chain(records: List[Receipt]) -> Dict[str, Any]:
    failures: List[Dict[str, Any]] = []
    prev = ""
    for index, record in enumerate(records):
        if record.sequence != index:
            failures.append({"index": index, "problem": "sequence out of order"})
        if record.prev_sha256 != prev:
            failures.append(
                {"index": index, "problem": "chain broken (reordered, inserted or removed)"}
            )
        if digest(record.output) != record.output_sha256:
            failures.append({"index": index, "problem": "output altered after issue"})
        if record.recompute() != record.receipt_sha256:
            failures.append({"index": index, "problem": "receipt content altered"})
        prev = record.receipt_sha256
    return {"ok": not failures, "records": len(records), "failures": failures}


def verify_binding(
    receipt: Receipt,
    *,
    inputs: Any = None,
    config: Optional[Mapping[str, Any]] = None,
    output: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Check live objects against what the receipt recorded."""
    mismatches: List[str] = []
    if inputs is not None and digest(inputs) != receipt.input_sha256:
        mismatches.append("input state does not match the receipt")
    if config is not None and digest(_plain(dict(config))) != digest(receipt.config):
        mismatches.append("model/config does not match the receipt")
    if output is not None and digest(_plain(dict(output))) != receipt.output_sha256:
        mismatches.append("output does not match the receipt")
    return {"ok": not mismatches, "mismatches": mismatches}


def replay(receipt: Receipt, recompute: Callable[[], Mapping[str, Any]]) -> Dict[str, Any]:
    """Recompute the output and compare it with the recorded digest."""
    output = _plain(dict(recompute()))
    replayed = digest(output)
    return {
        "ok": replayed == receipt.output_sha256,
        "recorded_output_sha256": receipt.output_sha256,
        "replayed_output_sha256": replayed,
    }


__all__ = [
    "RECEIPT_FORMAT",
    "Receipt",
    "ReceiptLedger",
    "canonical_json",
    "digest",
    "replay",
    "verify_binding",
    "verify_chain",
]
