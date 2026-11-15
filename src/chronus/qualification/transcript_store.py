"""Process-local store for sealed qualification audit transcripts.

Transcripts are keyed by evidence hash and by workload class. This is not
durable custody: restart clears the store. Customers see the evidence hash on
the workload; operators can re-verify against the stored transcript.
"""

from __future__ import annotations

import copy
from threading import Lock
from typing import Any

from chronus.qualification.harness import QualificationResult

_LOCK = Lock()
_BY_HASH: dict[str, dict[str, Any]] = {}
_BY_CLASS: dict[str, QualificationResult] = {}


def remember(result: QualificationResult) -> None:
    """Persist a deep copy of the latest qualification result."""
    with _LOCK:
        _BY_HASH[result.evidence_hash] = copy.deepcopy(result.audit_transcript)
        _BY_CLASS[str(result.audit_transcript.get("workload_class", ""))] = copy.deepcopy(
            result
        )


def recall_by_class(workload_class: str) -> QualificationResult | None:
    with _LOCK:
        stored = _BY_CLASS.get(workload_class)
        return copy.deepcopy(stored) if stored is not None else None


def recall_by_hash(evidence_hash: str) -> dict[str, Any] | None:
    with _LOCK:
        transcript = _BY_HASH.get(evidence_hash)
        return copy.deepcopy(transcript) if transcript is not None else None


def clear() -> None:
    """Test helper — drop all process-local transcripts."""
    with _LOCK:
        _BY_HASH.clear()
        _BY_CLASS.clear()
