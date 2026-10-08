"""
Emergence Metrics Framework
==========================
Scientific measurement framework for observable intelligence emergence
across the five HYBA intelligence schools.

Based on Integrated Information Theory (IIT) concepts, this module provides:
  - Coherence: How well schools work together
  - Integration: IIT-inspired phi coefficient (synergy above linear sum)
  - Differentiation: Diversity of school outputs
  - Emergence Coefficient: Composite metric of system-level intelligence

Usage:
    from Intelligence.consciousness.emergence_metrics import EmergenceMetrics

    metrics = EmergenceMetrics()
    metrics.record_event(event)
    metrics.snapshot()
    report = metrics.get_report()
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class SchoolActivity:
    """Activity record for a single school in a time window."""

    school: str
    events: int = 0
    feedback_loops: int = 0
    error_count: int = 0
    healing_proposals: int = 0
    last_value: float = 0.0
    activity_log: deque = field(default_factory=lambda: deque(maxlen=100))


@dataclass
class EmergenceSnapshot:
    """A point-in-time snapshot of emergence metrics."""

    timestamp: float
    coherence: float
    integration: float
    differentiation: float
    emergence_coefficient: float
    school_activities: Dict[str, SchoolActivity]
    total_events: int
    feedback_loops: int


class EmergenceMetrics:
    """
    Scientific measurement framework for observable intelligence emergence.

    Measures four key properties:
    1. Coherence (0-1): Bidirectional feedback ratio × school coverage
    2. Integration (0-1): IIT-inspired phi coefficient
    3. Differentiation (0-1): Shannon entropy of school activity
    4. Emergence Coefficient (0-1): Weighted composite
    """

    def __init__(self, window_size: int = 100, snapshot_interval: float = 5.0):
        self._window_size = window_size
        self._snapshot_interval = snapshot_interval
        self._events: deque = deque(maxlen=window_size)
        self._snapshots: deque = deque(maxlen=200)
        self._school_activities: Dict[str, SchoolActivity] = {}
        self._last_snapshot_time = time.time()
        self._last_delta: float = 0.0
        self._total_events: int = 0
        self._feedback_loops: int = 0
        self._init_schools()

    def _init_schools(self) -> None:
        for s in [
            "math_foundation",
            "quantum_simulation",
            "geometric_folding",
            "mining_autonomous",
            "security_governance",
        ]:
            self._school_activities[s] = SchoolActivity(school=s)

    def record_event(self, event: Any) -> float:
        """Record an event and return the emergence delta."""
        self._events.append(event)
        self._total_events += 1

        school = event.source.value if hasattr(event.source, "value") else str(event.source)
        if school not in self._school_activities:
            self._school_activities[school] = SchoolActivity(school=school)

        activity = self._school_activities[school]
        activity.events += 1
        activity.last_value = time.time()
        activity.activity_log.append(event.timestamp)

        if hasattr(event, "event_type") and event.event_type.value == "feedback_loop":
            self._feedback_loops += 1
            activity.feedback_loops += 1
        if hasattr(event, "event_type") and event.event_type.value == "healing_proposal":
            activity.healing_proposals += 1
        if hasattr(event, "topic") and "error" in str(event.topic):
            activity.error_count += 1

        prev_coeff = self._snapshots[-1].emergence_coefficient if self._snapshots else 0.0
        self.snapshot()
        new_coeff = self._snapshots[-1].emergence_coefficient
        self._last_delta = new_coeff - prev_coeff
        return self._last_delta

    def _calculate_coherence(self) -> float:
        if self._total_events == 0:
            return 0.0
        feedback_ratio = self._feedback_loops / max(self._total_events, 1)
        active_schools = sum(1 for a in self._school_activities.values() if a.events > 0)
        school_coverage = active_schools / len(self._school_activities)
        if feedback_ratio == 0 or school_coverage == 0:
            return 0.0
        return math.sqrt(feedback_ratio * school_coverage)

    def _calculate_integration(self) -> float:
        if not self._events:
            return 0.0
        total_events = sum(a.events for a in self._school_activities.values())
        if total_events == 0:
            return 0.0
        system_entropy = self._shannon_entropy([a.events for a in self._school_activities.values()])
        parts_entropy = 0.0
        for activity in self._school_activities.values():
            if activity.events > 0:
                rate = activity.events / total_events
                if 0 < rate < 1:
                    parts_entropy += -rate * math.log2(rate)
        if system_entropy == 0:
            return 0.0
        phi = max(0.0, system_entropy - parts_entropy)
        max_phi = math.log2(len(self._school_activities))
        return phi / max_phi if max_phi > 0 else 0.0

    def _calculate_differentiation(self) -> float:
        activities = [a.events for a in self._school_activities.values()]
        total = sum(activities)
        if total == 0:
            return 0.0
        return self._shannon_entropy(activities)

    def _shannon_entropy(self, values: List[int]) -> float:
        total = sum(values)
        if total == 0:
            return 0.0
        entropy = 0.0
        for v in values:
            if v > 0:
                p = v / total
                entropy -= p * math.log2(p)
        return entropy

    def snapshot(self) -> EmergenceSnapshot:
        now = time.time()
        coherence = self._calculate_coherence()
        integration = self._calculate_integration()
        differentiation = self._calculate_differentiation()
        # Emergence coefficient = measured mean of the three components;
        # the former 0.35/0.40/0.25 invented weighting is gone.
        emergence = (coherence + integration + differentiation) / 3.0
        snap = EmergenceSnapshot(
            timestamp=now,
            coherence=coherence,
            integration=integration,
            differentiation=differentiation,
            emergence_coefficient=emergence,
            school_activities={
                k: SchoolActivity(
                    school=v.school,
                    events=v.events,
                    feedback_loops=v.feedback_loops,
                    error_count=v.error_count,
                    healing_proposals=v.healing_proposals,
                    last_value=v.last_value,
                )
                for k, v in self._school_activities.items()
            },
            total_events=self._total_events,
            feedback_loops=self._feedback_loops,
        )
        self._snapshots.append(snap)
        self._last_snapshot_time = now
        return snap

    def get_report(self) -> Dict[str, Any]:
        if not self._snapshots:
            self.snapshot()
        latest = self._snapshots[-1]
        return {
            "timestamp": latest.timestamp,
            "emergence_coefficient": round(latest.emergence_coefficient, 4),
            "coherence": round(latest.coherence, 4),
            "integration": round(latest.integration, 4),
            "differentiation": round(latest.differentiation, 4),
            "total_events": latest.total_events,
            "feedback_loops": latest.feedback_loops,
            "schools": {
                name: {
                    "events": act.events,
                    "feedback_loops": act.feedback_loops,
                    "errors": act.error_count,
                    "healing_proposals": act.healing_proposals,
                }
                for name, act in latest.school_activities.items()
            },
            "history_size": len(self._snapshots),
            "last_delta": round(self._last_delta, 6),
        }

    def get_time_series(self, n: int = 50) -> List[Dict[str, float]]:
        snaps = list(self._snapshots)[-n:]
        return [
            {
                "timestamp": s.timestamp,
                "emergence": s.emergence_coefficient,
                "coherence": s.coherence,
                "integration": s.integration,
                "differentiation": s.differentiation,
            }
            for s in snaps
        ]

    @property
    def last_delta(self) -> float:
        return self._last_delta

    @property
    def current_emergence(self) -> float:
        if not self._snapshots:
            return 0.0
        return self._snapshots[-1].emergence_coefficient
