"""Validated tensor advisory boundary for nonce-window ordering.

A model may reorder already-certified windows. It may not create, remove,
resize, retarget or reassign them. Its output affects scheduling only; host
SHA-256d verification remains the sole proof-of-work acceptance boundary.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Protocol, Sequence, runtime_checkable

from hyba.hybrid.lucas_partition import SpanAssignment


class TensorAdviceViolation(ValueError):
    """Raised when advisory output changes certified work."""


@runtime_checkable
class WindowRanker(Protocol):
    """Enterprise model adapter: rank a fixed set of certified windows."""

    @property
    def model_id(self) -> str: ...

    def rank(
        self, job: Any, windows: Sequence[SpanAssignment]
    ) -> Sequence[SpanAssignment]: ...


@dataclass(frozen=True)
class TensorAdviceEvidence:
    model_id: str
    window_count: int
    latency_ns: int
    permutation_valid: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "window_count": self.window_count,
            "latency_ns": self.latency_ns,
            "permutation_valid": self.permutation_valid,
            "truth_class": "measured",
            "effect": "dispatch_order_only",
        }


class IdentityWindowRanker:
    """Deterministic baseline used when testing the advisory contract."""

    model_id = "identity-v1"

    def rank(
        self, job: Any, windows: Sequence[SpanAssignment]
    ) -> Sequence[SpanAssignment]:
        del job
        return list(windows)


def _key(window: SpanAssignment) -> tuple[str, int, int, int]:
    return (window.device_id, window.base_nonce, window.span, window.face)


def apply_tensor_advice(
    ranker: WindowRanker,
    job: Any,
    windows: Sequence[SpanAssignment],
) -> tuple[list[SpanAssignment], TensorAdviceEvidence]:
    """Run and validate a ranker, rejecting any mutation of certified work."""
    model_id = str(ranker.model_id).strip()
    if not model_id:
        raise TensorAdviceViolation("ranker.model_id must be non-empty")
    started = time.monotonic_ns()
    ranked = list(ranker.rank(job, tuple(windows)))
    latency_ns = max(1, time.monotonic_ns() - started)
    if Counter(map(_key, ranked)) != Counter(map(_key, windows)):
        raise TensorAdviceViolation(
            "tensor advisor must return an exact permutation of certified windows"
        )
    return ranked, TensorAdviceEvidence(
        model_id=model_id,
        window_count=len(ranked),
        latency_ns=latency_ns,
        permutation_valid=True,
    )


__all__ = [
    "IdentityWindowRanker",
    "TensorAdviceEvidence",
    "TensorAdviceViolation",
    "WindowRanker",
    "apply_tensor_advice",
]
