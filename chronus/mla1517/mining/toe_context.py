"""Observed-only TOE context for canonical PYTHIA mining decisions."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


class TOEContextUnavailable(RuntimeError):
    """Required observed context is missing or malformed."""


@dataclass(frozen=True)
class ObservedTransition:
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    observed_at_ns: int
    event: str

    def __post_init__(self) -> None:
        if self.observed_at_ns <= 0 or not self.event:
            raise TOEContextUnavailable("transition requires timestamp and event")


@dataclass(frozen=True)
class TOEContext:
    stratum_job: Mapping[str, Any]
    hardware_state: bytes
    lane_id: int
    node_id: int
    sequence: int
    watermark: int
    telemetry: Mapping[str, Any]
    transitions: tuple[ObservedTransition, ...]
    synthetic: bool = False

    def __post_init__(self) -> None:
        if self.synthetic:
            raise TOEContextUnavailable("synthetic TOE context is prohibited")
        if not self.stratum_job.get("job_id"):
            raise TOEContextUnavailable("live Stratum job id is required")
        if len(self.hardware_state) != 64:
            raise TOEContextUnavailable("hardware state must be exactly 64 bytes")
        if min(self.lane_id, self.node_id, self.sequence, self.watermark) < 0:
            raise TOEContextUnavailable("context coordinates cannot be negative")
        if not self.telemetry:
            raise TOEContextUnavailable("observed telemetry is required")

    def observation(self) -> Mapping[str, Any]:
        """Return immutable observed inputs; no prediction or validity claim."""
        return MappingProxyType(
            {
                "stratum_job": MappingProxyType(dict(self.stratum_job)),
                "hardware_state": self.hardware_state,
                "lane_id": self.lane_id,
                "node_id": self.node_id,
                "sequence": self.sequence,
                "watermark": self.watermark,
                "telemetry": MappingProxyType(dict(self.telemetry)),
                "transitions": self.transitions,
                "sha256d_authority": "external_consensus_validator",
            }
        )


class TOEContextBuilder:
    """Build a context only when every required input is observed."""

    def __init__(self) -> None:
        self._job: Mapping[str, Any] | None = None
        self._state: bytes | None = None
        self._lane: int | None = None
        self._node: int | None = None
        self._sequence: int | None = None
        self._watermark: int | None = None
        self._telemetry: Mapping[str, Any] | None = None
        self._transitions: list[ObservedTransition] = []

    def with_job(self, job: Mapping[str, Any]) -> "TOEContextBuilder":
        if not isinstance(job, Mapping) or not job.get("job_id"):
            raise TOEContextUnavailable("observed job must contain job_id")
        self._job = dict(job)
        return self

    def with_hardware_state(self, state: bytes) -> "TOEContextBuilder":
        if not isinstance(state, bytes) or len(state) != 64:
            raise TOEContextUnavailable("hardware state must be exactly 64 bytes")
        self._state = state
        return self

    def with_coordinates(self, *, lane_id: int, node_id: int, sequence: int, watermark: int) -> "TOEContextBuilder":
        if min(lane_id, node_id, sequence, watermark) < 0:
            raise TOEContextUnavailable("context coordinates cannot be negative")
        self._lane, self._node = lane_id, node_id
        self._sequence, self._watermark = sequence, watermark
        return self

    def with_telemetry(self, telemetry: Mapping[str, Any]) -> "TOEContextBuilder":
        if not isinstance(telemetry, Mapping) or not telemetry:
            raise TOEContextUnavailable("observed telemetry is required")
        self._telemetry = dict(telemetry)
        return self

    def add_transition(self, transition: ObservedTransition) -> "TOEContextBuilder":
        self._transitions.append(transition)
        return self

    def build(self) -> TOEContext:
        values = (self._job, self._state, self._lane, self._node, self._sequence, self._watermark, self._telemetry)
        if any(value is None for value in values):
            raise TOEContextUnavailable("job, hardware, coordinates, and telemetry are all required")
        return TOEContext(
            stratum_job=self._job,  # type: ignore[arg-type]
            hardware_state=self._state,  # type: ignore[arg-type]
            lane_id=self._lane,  # type: ignore[arg-type]
            node_id=self._node,  # type: ignore[arg-type]
            sequence=self._sequence,  # type: ignore[arg-type]
            watermark=self._watermark,  # type: ignore[arg-type]
            telemetry=self._telemetry,  # type: ignore[arg-type]
            transitions=tuple(self._transitions),
        )
