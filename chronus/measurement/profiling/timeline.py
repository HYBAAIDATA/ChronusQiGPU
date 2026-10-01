"""Timeline capture — ordered measured events over real dispatches.

Invariants:
    TL1: every timeline has at least one event.
    TL2: device busy + device idle = total duration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from .events import profile_kernel


@dataclass
class TimelineEvent:
    name: str
    start_ns: int
    end_ns: int
    duration_ns: int
    kind: str  # "kernel", "transfer", "host"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_ns": self.start_ns,
            "end_ns": self.end_ns,
            "duration_ns": self.duration_ns,
            "kind": self.kind,
        }


@dataclass
class Timeline:
    events: List[TimelineEvent] = field(default_factory=list)
    total_duration_ns: int = 0
    device_busy_ns: int = 0
    device_idle_ns: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "events": [e.as_dict() for e in self.events],
            "total_duration_ns": self.total_duration_ns,
            "device_busy_ns": self.device_busy_ns,
            "device_idle_ns": self.device_idle_ns,
        }


def capture_timeline(
    kernels: List[Tuple[str, Callable[[], Any]]],
    kind: str = "kernel",
) -> Timeline:
    """Each (name, callable) runs once; busy+idle accounts for the whole span."""
    events = []
    for name, dispatch in kernels:
        profile = profile_kernel(name, dispatch, runs=1)[0]
        events.append(
            TimelineEvent(
                name=profile.kernel_name,
                start_ns=profile.start_time_ns,
                end_ns=profile.end_time_ns,
                duration_ns=profile.duration_ns,
                kind=kind,
            )
        )
    if not events:
        return Timeline()
    first = min(e.start_ns for e in events)
    last = max(e.end_ns for e in events)
    total = last - first
    busy = sum(e.duration_ns for e in events)
    return Timeline(
        events=events,
        total_duration_ns=total,
        device_busy_ns=busy,
        device_idle_ns=total - busy,
    )
