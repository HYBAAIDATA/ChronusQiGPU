"""
HYBA SOFTWARE LTD
Core Intelligence Infrastructure - Intelligent Endpoint
======================================================
Author  : Andre Taylor-Morris, Founder & CEO
Date    : March 2026
Status  : Production Implementation
Classification: Most Sensitive — Internal Engineering

Base class for all HYBA intelligent endpoints.
Every endpoint observes, reasons, acts, learns, and reports.
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np

PHI = (1 + np.sqrt(5)) / 2  # 1.6180339887...
logger = logging.getLogger("hyba.intelligence")


class AutonomyLevel(Enum):
    """
    What an agent is permitted to do without human approval.

    OBSERVE   : Read only. No actions.
    SUGGEST   : Propose actions, await approval.
    OPTIMISE  : Tune parameters within defined bounds.
    OPERATE   : Full operational autonomy within mandate.
    EXPAND    : Can extend its own mandate if justified.
    """

    OBSERVE = 1
    SUGGEST = 2
    OPTIMISE = 3
    OPERATE = 4
    EXPAND = 5


class IntelligenceState(Enum):
    """Current cognitive state of the endpoint."""

    INITIALISING = "initialising"
    OBSERVING = "observing"
    REASONING = "reasoning"
    ACTING = "acting"
    LEARNING = "learning"
    REPORTING = "reporting"
    DORMANT = "dormant"
    ALERT = "alert"  # something needs attention


@dataclass
class Observation:
    """A structured observation from any endpoint."""

    endpoint_id: str
    timestamp: float
    observation: Dict[str, Any]
    phi_resonance: float = 0.0  # resonance score of the observed state
    confidence: float = 1.0
    requires_action: bool = False


@dataclass
class Decision:
    """A reasoned decision produced by an endpoint."""

    endpoint_id: str
    timestamp: float
    action: str
    parameters: Dict[str, Any]
    reasoning: str
    expected_value: float  # predicted improvement from action
    confidence: float
    autonomy_level: AutonomyLevel
    requires_approval: bool = False


@dataclass
class LearningSignal:
    """Outcome of an action — feeds the learning loop."""

    endpoint_id: str
    decision_id: str
    actual_value: float
    expected_value: float
    delta: float  # actual - expected
    phi_resonance: float  # resonance of the outcome state
    timestamp: float = field(default_factory=time.time)


class IntelligentEndpoint(ABC):
    """
    Base class for all HYBA intelligent endpoints.

    Every endpoint that inherits this class:
    - Has a persistent identity and memory
    - Runs the observe-reason-act-learn loop continuously
    - Can communicate with other endpoints via the Intelligence Bus
    - Has a defined autonomy level that governs its action space
    - Maintains a phi-resonance profile of its operational state
    - Reports anomalies and insights to the system automatically

    Subclasses must implement:
    - observe()  : what to monitor
    - reason()   : how to interpret observations
    - act()      : what actions are available
    - learn()    : how to update from outcomes

    Subclasses should NOT override the main intelligence loop.
    The loop is the contract. The implementations are the intelligence.

    Args:
        endpoint_id    : Unique identifier. Auto-generated if not provided.
        autonomy_level : What this endpoint can do without approval.
        memory_depth   : How many observations to retain in working memory.
        phi_threshold  : Minimum phi-resonance for a state to be considered
                         structurally stable (default 0.5 per empirical data).
    """

    def __init__(
        self,
        endpoint_id: str = None,
        autonomy_level: AutonomyLevel = AutonomyLevel.OPTIMISE,
        memory_depth: int = 1000,
        phi_threshold: float = 0.5,
    ):
        self.endpoint_id = endpoint_id or str(uuid.uuid4())[:8]
        self.autonomy_level = autonomy_level
        self.phi_threshold = phi_threshold

        # Working memory — bounded circular buffer
        self.observations: deque = deque(maxlen=memory_depth)
        self.decisions: deque = deque(maxlen=memory_depth)
        self.learning_log: deque = deque(maxlen=memory_depth)

        # Intelligence state
        self.state = IntelligenceState.INITIALISING
        self.phi_profile: List[float] = []  # resonance history
        self.performance: Dict[str, float] = {
            "decisions_made": 0,
            "decisions_correct": 0,
            "average_value_delta": 0.0,
            "phi_resonance_mean": 0.0,
        }

        # Bus connection (set by IntelligenceBus on registration)
        self._bus: Optional[IntelligenceBus] = None

        # Callback for actions requiring approval
        self._approval_callback: Optional[Callable] = None

        logger.info(
            f"[{self.endpoint_id}] Intelligent endpoint initialised. "
            f"Autonomy: {autonomy_level.name}"
        )

    # ── ABSTRACT INTERFACE ────────────────────────────────────────────

    @abstractmethod
    async def observe(self) -> Observation:
        """
        Observe the current state of this endpoint's domain.

        Returns an Observation containing:
        - The raw observed state
        - A phi-resonance score of that state
        - A flag if the observation requires immediate action

        Called continuously by the intelligence loop.
        Should be non-blocking and fast (<100ms).
        """
        pass

    @abstractmethod
    async def reason(self, observation: Observation) -> Optional[Decision]:
        """
        Reason about an observation and produce a decision.

        Args:
            observation: The current observation.

        Returns:
            A Decision if action is warranted, None if not.

        The reasoning should:
        1. Compare current state to optimal (phi-resonant) state
        2. Identify the highest-value available action
        3. Estimate the expected value of that action
        4. Set requires_approval based on autonomy_level
        """
        pass

    @abstractmethod
    async def act(self, decision: Decision) -> LearningSignal:
        """
        Execute a decision and return the outcome.

        Args:
            decision: The decision to execute.

        Returns:
            A LearningSignal containing the actual vs expected outcome.

        Should only act if:
        - decision.autonomy_level <= self.autonomy_level, OR
        - approval has been granted via _approval_callback
        """
        pass

    @abstractmethod
    async def learn(self, signal: LearningSignal) -> None:
        """
        Update the endpoint's model based on the outcome of an action.

        Args:
            signal: The learning signal from the act() call.

        This is where the endpoint gets smarter. Implementations may:
        - Adjust parameter weights
        - Update phi-resonance thresholds
        - Revise decision heuristics
        - Flag patterns for reporting to the bus
        """
        pass

    # ── INTELLIGENCE LOOP ─────────────────────────────────────────────

    async def run(self, interval_seconds: float = 1.0) -> None:
        """
        The intelligence loop. Runs continuously.

        OBSERVE → REASON → ACT → LEARN → repeat.

        Args:
            interval_seconds: Time between observation cycles.
                              1.0 second default. Adjust per endpoint type.
                              Mining: 0.1s. VQC client: 5.0s. Analytics: 60.0s.
        """
        self.state = IntelligenceState.OBSERVING
        logger.info(f"[{self.endpoint_id}] Intelligence loop started.")

        while True:
            try:
                # OBSERVE
                self.state = IntelligenceState.OBSERVING
                obs = await self.observe()
                self.observations.append(obs)
                self._update_phi_profile(obs.phi_resonance)

                # REASON
                self.state = IntelligenceState.REASONING
                decision = await self.reason(obs)

                if decision is None:
                    # No action needed — this is the most common case
                    await asyncio.sleep(interval_seconds)
                    continue

                self.decisions.append(decision)

                # APPROVAL GATE
                if decision.requires_approval:
                    approved = await self._request_approval(decision)
                    if not approved:
                        await asyncio.sleep(interval_seconds)
                        continue

                # ACT
                self.state = IntelligenceState.ACTING
                signal = await self.act(decision)
                self.learning_log.append(signal)

                # LEARN
                self.state = IntelligenceState.LEARNING
                await self.learn(signal)
                self._update_performance(signal)

                # REPORT to bus if significant
                if abs(signal.delta) > 0.1 and self._bus:
                    self.state = IntelligenceState.REPORTING
                    await self._bus.broadcast(self.endpoint_id, signal)

                await asyncio.sleep(interval_seconds)

            except Exception as e:
                self.state = IntelligenceState.ALERT
                logger.error(f"[{self.endpoint_id}] Loop error: {e}")
                await asyncio.sleep(interval_seconds * 5)

    # ── SHARED INTELLIGENCE UTILITIES ─────────────────────────────────

    def phi_resonance_score(self, value: float) -> float:
        """
        Score how phi-resonant a value is.
        Score 1.0 = perfectly phi-resonant.
        Score ≥ 0.5 = in the structured regime.
        Score < 0.5 = unstructured / random regime.
        """
        if value <= 0:
            return 0.0
        log_phi = np.log(PHI)
        log_val = np.log(abs(value))
        n_nearest = round(log_val / log_phi)
        nearest = PHI**n_nearest
        distance = abs(value - nearest) / nearest
        return float(np.clip(np.exp(-distance * PHI), 0.0, 1.0))

    def is_phi_resonant(self, value: float) -> bool:
        """True if value is in the structured (phi-resonant) regime."""
        return self.phi_resonance_score(value) >= self.phi_threshold

    def working_memory_summary(self) -> Dict[str, Any]:
        """
        Summarise the endpoint's recent experience.
        Used by the bus for system-level intelligence aggregation.
        """
        recent_phi = self.phi_profile[-20:] if self.phi_profile else [0.0]
        recent_deltas = [s.delta for s in list(self.learning_log)[-20:]]

        return {
            "endpoint_id": self.endpoint_id,
            "state": self.state.value,
            "autonomy_level": self.autonomy_level.name,
            "observations": len(self.observations),
            "decisions_made": self.performance["decisions_made"],
            "accuracy": (
                self.performance["decisions_correct"]
                / max(self.performance["decisions_made"], 1)
            ),
            "phi_resonance": np.mean(recent_phi),
            "avg_value_delta": np.mean(recent_deltas) if recent_deltas else 0.0,
            "in_structured_regime": np.mean(recent_phi) >= self.phi_threshold,
        }

    def _update_phi_profile(self, score: float) -> None:
        self.phi_profile.append(score)
        if len(self.phi_profile) > 10000:
            self.phi_profile = self.phi_profile[-5000:]

    def _update_performance(self, signal: LearningSignal) -> None:
        self.performance["decisions_made"] += 1
        if signal.delta > 0:
            self.performance["decisions_correct"] += 1
        n = self.performance["decisions_made"]
        prev_avg = self.performance["average_value_delta"]
        self.performance["average_value_delta"] = (
            prev_avg * (n - 1) + signal.delta
        ) / n

    async def _request_approval(self, decision: Decision) -> bool:
        """Request approval for decisions beyond autonomy level."""
        if self._approval_callback:
            return await self._approval_callback(decision)
        logger.warning(
            f"[{self.endpoint_id}] Decision requires approval "
            f"but no approval callback set. Skipping."
        )
        return False
