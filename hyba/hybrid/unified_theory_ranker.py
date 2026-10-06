"""Golden Unified Theory ordering adapter for the hybrid GPU/ASIC fabric.

The adapter may only permute already certified, disjoint nonce windows. It
cannot change a window, target, job identity, device capability, or validity
predicate. Its effect is therefore measurable and reversible.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Sequence

from hyba.hybrid.lucas_partition import SpanAssignment
from toe.golden_unified import GOLDEN_UNIFIED_THEORY


class GoldenUnifiedWindowRanker:
    """Deterministic experimental window ordering bound to the theory digest."""

    def __init__(self) -> None:
        self.theory = GOLDEN_UNIFIED_THEORY
        self.model_id = "golden-unified-hybrid-v1:" + self.theory.theory_digest[:16]

    @staticmethod
    def _score(job: Any, window: SpanAssignment, theory_digest: str):
        seed = hashlib.sha256(
            bytes(getattr(job, "header80", b""))
            + str(getattr(job, "job_id", "")).encode("utf-8")
            + int(window.base_nonce).to_bytes(8, "little")
            + int(window.span).to_bytes(8, "little")
            + int(window.face).to_bytes(4, "little", signed=True)
            + theory_digest.encode("ascii")
        ).digest()
        unit = int.from_bytes(seed[:8], "big") / float(1 << 64)
        golden_phase = (int(window.base_nonce) / ((1.0 + math.sqrt(5.0)) / 2.0)) % 1.0
        return (abs(golden_phase - unit), int(window.face), int(window.base_nonce))

    def rank(
        self, job: Any, windows: Sequence[SpanAssignment]
    ) -> Sequence[SpanAssignment]:
        metadata = {
            "job_id": str(getattr(job, "job_id", "")),
            "window_count": len(windows),
            "base_nonces": [int(window.base_nonce) for window in windows],
            "spans": [int(window.span) for window in windows],
        }
        observation = self.theory.compile(metadata, goal="hybrid_asic_window_order")
        if observation.foundation_digest != self.theory.foundation.digest:
            raise RuntimeError("theory observation is not bound to the active foundation")
        return sorted(
            windows,
            key=lambda window: self._score(job, window, observation.theory_digest),
        )


__all__ = ["GoldenUnifiedWindowRanker"]
