"""Fail-closed, replayable tensor advice for certified nonce-window ordering."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Protocol, Sequence, runtime_checkable

from hyba.hybrid.lucas_partition import SpanAssignment


class TensorAdviceViolation(ValueError):
    pass


def _normal(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _normal(dataclasses.asdict(value))
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, dict):
        return {str(k): _normal(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_normal(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return _normal(vars(value))
    return repr(value)


def _digest(value: Any) -> str:
    encoded = json.dumps(_normal(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _key(window: SpanAssignment) -> tuple[str, int, int, int]:
    return (window.device_id, window.base_nonce, window.span, window.face)


def _ordered(windows: Sequence[SpanAssignment]) -> list[tuple[str, int, int, int]]:
    return [_key(window) for window in windows]


@runtime_checkable
class WindowRanker(Protocol):
    @property
    def model_id(self) -> str: ...
    def rank(self, job: Any, windows: Sequence[SpanAssignment]) -> Sequence[SpanAssignment]: ...


@dataclass(frozen=True)
class TensorAdviceEvidence:
    model_id: str
    window_count: int
    latency_ns: int
    permutation_valid: bool
    job_digest: str
    input_order_digest: str
    output_order_digest: str
    replay_id: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "window_count": self.window_count,
            "latency_ns": self.latency_ns,
            "permutation_valid": self.permutation_valid,
            "job_digest": self.job_digest,
            "input_order_digest": self.input_order_digest,
            "output_order_digest": self.output_order_digest,
            "replay_id": self.replay_id,
            "truth_class": "measured",
            "effect": "dispatch_order_only",
        }


class IdentityWindowRanker:
    model_id = "identity-v1"
    def rank(self, job: Any, windows: Sequence[SpanAssignment]) -> Sequence[SpanAssignment]:
        del job
        return list(windows)


def apply_tensor_advice(
    ranker: WindowRanker, job: Any, windows: Sequence[SpanAssignment]
) -> tuple[list[SpanAssignment], TensorAdviceEvidence]:
    model_id = str(ranker.model_id).strip()
    if not model_id:
        raise TensorAdviceViolation("ranker.model_id must be non-empty")
    job_before = _digest(job)
    input_digest = _digest(_ordered(windows))
    started = time.monotonic_ns()
    ranked = list(ranker.rank(job, tuple(windows)))
    latency_ns = max(1, time.monotonic_ns() - started)
    if _digest(job) != job_before:
        raise TensorAdviceViolation("tensor advisor mutated the mining job")
    if Counter(map(_key, ranked)) != Counter(map(_key, windows)):
        raise TensorAdviceViolation(
            "tensor advisor must return an exact permutation of certified windows"
        )
    output_digest = _digest(_ordered(ranked))
    replay_id = _digest({
        "model_id": model_id,
        "job_digest": job_before,
        "input_order_digest": input_digest,
        "output_order_digest": output_digest,
    })
    return ranked, TensorAdviceEvidence(
        model_id, len(ranked), latency_ns, True, job_before,
        input_digest, output_digest, replay_id,
    )


def verify_tensor_advice_replay(
    evidence: TensorAdviceEvidence,
    job: Any,
    original: Sequence[SpanAssignment],
    ranked: Sequence[SpanAssignment],
) -> bool:
    expected = _digest({
        "model_id": evidence.model_id,
        "job_digest": _digest(job),
        "input_order_digest": _digest(_ordered(original)),
        "output_order_digest": _digest(_ordered(ranked)),
    })
    return (
        Counter(map(_key, ranked)) == Counter(map(_key, original))
        and evidence.job_digest == _digest(job)
        and evidence.input_order_digest == _digest(_ordered(original))
        and evidence.output_order_digest == _digest(_ordered(ranked))
        and evidence.replay_id == expected
    )


__all__ = [
    "IdentityWindowRanker", "TensorAdviceEvidence", "TensorAdviceViolation",
    "WindowRanker", "apply_tensor_advice", "verify_tensor_advice_replay",
]
