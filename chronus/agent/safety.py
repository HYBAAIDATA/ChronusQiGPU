"""Thread-safe external stop, suspension/quarantine and explicit high-risk approval."""

from dataclasses import dataclass, field
import threading
from .capabilities import RiskTier
from .identity import LifecycleState


@dataclass
class SafetyEnvelope:
    prohibited_actions: frozenset
    preauthorised_actions: frozenset
    _kill: threading.Event = field(default_factory=threading.Event, repr=False)

    def stop(self):
        self._kill.set()

    @property
    def stopped(self):
        return self._kill.is_set()

    def admits(self, request, task):
        if self.stopped or request.action in self.prohibited_actions:
            return False
        if task.risk_tier >= RiskTier.T4_EXTERNAL_CONSEQUENTIAL:
            return request.id in self.preauthorised_actions
        return True


def quarantine(agent, *, now, reason):
    agent.audit.append("agent_quarantined", {"reason": reason}, now=now)
    agent.safety.stop()
    agent.lifecycle = LifecycleState.QUARANTINED
    # Host consumes this event to revoke outstanding signed snapshots.
    # Runtime itself has no mutable trust profile or governance keys.
