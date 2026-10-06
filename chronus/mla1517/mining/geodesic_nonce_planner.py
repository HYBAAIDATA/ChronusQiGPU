"""Mining-local geodesic nonce ordering.

This module owns only bounded candidate ordering for PYTHIA mining. It has no
PULVINI/data dependency and no consensus authority. The planner may only
permute a caller-supplied set of unique uint32 nonces; SHA-256d, target,
freshness and pool acknowledgement remain the proof authorities.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Protocol

PHI = (1.0 + math.sqrt(5.0)) / 2.0


class DistanceMetric(Protocol):
    def distance(self, a: float, b: float) -> float: ...


@dataclass(frozen=True)
class MiningGeodesicMetric:
    """Substrate-neutral scalar metric for mining candidate ordering."""

    kind: str = "phi_scaled"
    scale: float = PHI

    def __post_init__(self) -> None:
        if self.scale <= 0 or not math.isfinite(self.scale):
            raise ValueError("metric scale must be finite and positive")
        if self.kind not in {"euclidean", "phi_scaled", "hyperbolic"}:
            raise ValueError(f"unsupported mining geodesic metric: {self.kind}")

    def distance(self, a: float, b: float) -> float:
        delta = abs(float(a) - float(b))
        if self.kind == "euclidean":
            return delta
        if self.kind == "phi_scaled":
            return delta / self.scale
        return math.asinh(delta / self.scale)


class GeodesicNoncePlanner:
    """Bounded mining planner that can only permute supplied uint32 nonces."""

    consensus_authority = False
    proof_authority = False

    def __init__(
        self,
        metric: DistanceMetric | None = None,
        *,
        fold_depth: int = 0,
    ) -> None:
        # ``fold_depth`` is retained only as an input-compatibility field for
        # older callers. Mining no longer performs PULVINI folding, so changing
        # this value cannot change ordering or create a data-authority edge.
        self.metric: DistanceMetric = metric or MiningGeodesicMetric()
        self.legacy_fold_depth = int(fold_depth)
        if self.legacy_fold_depth < 0:
            raise ValueError("fold_depth must be non-negative")
        self.last_report: dict[str, Any] | None = None

    @staticmethod
    def _validate_window(candidates: Iterable[int]) -> list[int]:
        window = list(candidates)
        if len(set(window)) != len(window):
            raise ValueError("candidate window contains duplicates")
        for nonce in window:
            if isinstance(nonce, bool) or not isinstance(nonce, int):
                raise TypeError("candidate window must contain integer nonces")
            if not 0 <= nonce <= 0xFFFFFFFF:
                raise ValueError("nonce outside uint32")
        return window

    @staticmethod
    def _metric_name(metric: DistanceMetric) -> str:
        kind = getattr(metric, "kind", "custom")
        return str(getattr(kind, "value", kind))

    def order_window(
        self,
        candidates: Iterable[int],
        *,
        anchor: int | None = None,
    ) -> list[int]:
        window = self._validate_window(candidates)
        if not window:
            self.last_report = {
                "count": 0,
                "passed": True,
                "membership_verified": True,
                "permutation_preserved": True,
                "consensus_authority": False,
                "proof_authority": False,
                "pulvini_dependency": False,
            }
            return []

        origin = int(window[0] if anchor is None else anchor)
        ordered = sorted(
            enumerate(window),
            key=lambda item: (self.metric.distance(origin, item[1]), item[0]),
        )
        result = [nonce for _, nonce in ordered]
        if sorted(result) != sorted(window):
            raise ArithmeticError("planner changed nonce membership")

        self.last_report = {
            "count": len(window),
            "passed": True,
            "membership_verified": True,
            "permutation_preserved": True,
            "consensus_authority": False,
            "proof_authority": False,
            "metric": self._metric_name(self.metric),
            "pulvini_dependency": False,
            "folding_used": False,
            "legacy_fold_depth": self.legacy_fold_depth,
        }
        return result


__all__ = ["GeodesicNoncePlanner", "MiningGeodesicMetric"]
