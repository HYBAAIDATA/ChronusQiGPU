"""ASI compatibility facade for canonical Salamander self-healing.

ASI is not a self-healing authority.  This module preserves the historical
SelfHealingEngine API while delegating health decisions to Salamander.  It
never fabricates metrics, never mutates another subsystem, and never reports a
repair as applied without a canonical Salamander result.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Iterable, Mapping

from salamander.control_plane import ActionRegistry, AutonomicControlPlane
from salamander.models import Availability, HealthDecision, HealthObservation, HealthState


class IssueType(str, Enum):
    PERFORMANCE_DEGRADATION = "performance_degradation"
    ERROR_RATE_SPIKE = "error_rate_spike"
    MEMORY_LEAK = "memory_leak"
    RESPONSE_TIME_INCREASE = "response_time_increase"
    ACCURACY_DECLINE = "accuracy_decline"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    INTEGRATION_FAILURE = "integration_failure"


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SystemIssue:
    issue_id: str
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    detected_at: datetime
    metrics: dict[str, Any]
    root_cause: str | None = None
    fix_applied: bool = False
    fix_description: str | None = None


ObservationProvider = Callable[
    [],
    Iterable[HealthObservation]
    | HealthObservation
    | Awaitable[Iterable[HealthObservation] | HealthObservation],
]


class SelfHealingEngine:
    """Observe through Salamander without creating a second healing authority."""

    def __init__(
        self,
        control_plane: AutonomicControlPlane | None = None,
        observation_provider: ObservationProvider | None = None,
        *,
        monitor_interval: float = 60.0,
        policy_id: str = "asi-salamander-delegation-v1",
    ) -> None:
        if monitor_interval <= 0:
            raise ValueError("monitor_interval must be positive")
        self.control_plane = control_plane or AutonomicControlPlane(
            registry=ActionRegistry()
        )
        self.observation_provider = observation_provider
        self.monitor_interval = float(monitor_interval)
        self.policy_id = policy_id
        self.monitoring_active = False
        self.issues_detected: list[SystemIssue] = []
        self.fixes_applied: list[dict[str, Any]] = []
        self.healing_knowledge: dict[str, list[Any]] = {}
        self._last_decision: HealthDecision | None = None
        self._cycles = 0
        self._stop = asyncio.Event()

    async def _collect_observations(self) -> tuple[HealthObservation, ...]:
        if self.observation_provider is None:
            return (
                HealthObservation(
                    subsystem="asi",
                    dimension="runtime_observation",
                    availability=Availability.UNAVAILABLE,
                    value=None,
                    observed_at_ns=0,
                    source="asi.self_healing:no_observation_provider",
                    tenant_id="system",
                ),
            )
        raw = self.observation_provider()
        if inspect.isawaitable(raw):
            raw = await raw
        if isinstance(raw, HealthObservation):
            values = (raw,)
        else:
            values = tuple(raw)
        if not values:
            return (
                HealthObservation(
                    subsystem="asi",
                    dimension="runtime_observation",
                    availability=Availability.NOT_MEASURED,
                    value=None,
                    observed_at_ns=0,
                    source="asi.self_healing:empty_observation",
                    tenant_id="system",
                ),
            )
        if not all(isinstance(item, HealthObservation) for item in values):
            raise TypeError("observation_provider must return HealthObservation values")
        return values

    async def run_once(self) -> HealthDecision:
        """Perform one bounded observation and diagnosis cycle."""
        try:
            observations = await self._collect_observations()
        except Exception as exc:
            observations = (
                HealthObservation(
                    subsystem="asi",
                    dimension="runtime_observation",
                    availability=Availability.UNAVAILABLE,
                    value=None,
                    observed_at_ns=0,
                    source=f"asi.self_healing:{type(exc).__name__}",
                    tenant_id="system",
                ),
            )
        decision = self.control_plane.observe(observations, policy_id=self.policy_id)
        self._last_decision = decision
        self._cycles += 1
        if decision.state not in {HealthState.HEALTHY, HealthState.UNKNOWN}:
            self.issues_detected.append(
                SystemIssue(
                    issue_id=f"issue_{len(self.issues_detected) + 1}",
                    issue_type=IssueType.INTEGRATION_FAILURE,
                    severity=(
                        IssueSeverity.CRITICAL
                        if decision.state in {HealthState.FAILED, HealthState.UNAVAILABLE}
                        else IssueSeverity.HIGH
                    ),
                    description=(
                        "Canonical Salamander health decision: "
                        + decision.state.value
                    ),
                    detected_at=datetime.now(timezone.utc),
                    metrics={"reasons": list(decision.reasons)},
                    root_cause="; ".join(decision.reasons) or "Unavailable",
                )
            )
        return decision

    async def start_monitoring(self, *, max_cycles: int = 1) -> bool:
        """Run a finite number of cycles.

        Long-lived scheduling belongs to the process supervisor.  A finite
        default prevents the historical ASI forever-loop from leaking a task.
        """
        if max_cycles <= 0:
            raise ValueError("max_cycles must be positive")
        if self.monitoring_active:
            return False
        self.monitoring_active = True
        self._stop.clear()
        try:
            for cycle in range(max_cycles):
                if self._stop.is_set():
                    break
                await self.run_once()
                if cycle + 1 < max_cycles:
                    try:
                        await asyncio.wait_for(
                            self._stop.wait(), timeout=self.monitor_interval
                        )
                    except asyncio.TimeoutError:
                        pass
        finally:
            self.monitoring_active = False
        return True

    def stop_monitoring(self) -> None:
        self._stop.set()
        self.monitoring_active = False

    def is_monitoring(self) -> bool:
        return self.monitoring_active

    async def _heal_issue(self, issue: SystemIssue) -> tuple[bool, str]:
        """Compatibility endpoint: ASI never applies a repair."""
        issue.fix_applied = False
        issue.fix_description = (
            "DELEGATED_TO_SALAMANDER: remediation requires a canonical "
            "ActionRequest, AL HARAS authorization and independent verification"
        )
        return False, issue.fix_description

    async def optimize_system(self) -> dict[str, Any]:
        """Do not fabricate proactive optimisations."""
        return {
            "authority": "SALAMANDER",
            "status": "DELEGATED",
            "optimizations_applied": 0,
            "reason": (
                "ASI has no optimisation actuation authority; use the canonical "
                "Salamander measured policy lifecycle"
            ),
        }

    def get_health_report(self) -> dict[str, Any]:
        decision = self._last_decision
        return {
            "authority": "SALAMANDER",
            "monitoring_active": self.monitoring_active,
            "cycles_observed": self._cycles,
            "health_state": decision.state.value if decision else "UNAVAILABLE",
            "reasons": list(decision.reasons) if decision else ["not observed"],
            "total_issues_detected": len(self.issues_detected),
            "total_fixes_applied": 0,
            "evidence_head": self.control_plane.ledger.head,
            "claim_boundary": "ASI_DELEGATES_HEALING_TO_SALAMANDER",
        }
