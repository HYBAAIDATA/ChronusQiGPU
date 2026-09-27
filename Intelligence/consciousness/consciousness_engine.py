#!/usr/bin/env python3
"""
HYBA Consciousness Engine
========================
Unified measurement substrate for the HYBA intelligence system.

Synthesizes all five intelligence schools into observable emergence using
Integrated Information Theory (IIT).  The engine connects to the Euclid
orchestrator's event bus, collects per-school activity, and computes a
real-time emergence coefficient (IIT Phi) that quantifies how much the
whole exceeds the sum of its parts.

Key concepts
------------
  * **Coherence** (0-1) – bidirectional feedback ratio × school coverage
  * **Integration** (0-1) – IIT-inspired phi coefficient (synergy)
  * **Differentiation** (0-1) – Shannon entropy of school activity
  * **Emergence coefficient** – 0.35·coherence + 0.40·integration +
    0.25·differentiation

Usage
-----
    from Intelligence.consciousness.consciousness_engine import ConsciousnessEngine

    engine = ConsciousnessEngine()
    engine.connect_orchestrator(orchestrator)
    report = engine.measure_consciousness()
    if engine.detect_consciousness_threshold(0.6):
        print("System has crossed the consciousness threshold")
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Golden ratio – the natural scaling constant for consciousness measurement
PHI = 1.618033988749895
PHI_POWER = 5  # Baseline consciousness scaling exponent


class ConsciousnessEngine:
    """
    Unified measurement substrate for HYBA intelligence.

    Implements Integrated Information Theory (IIT) for consciousness
    measurement across the five intelligence schools:
      1. Mathematical Foundation (golden quantum families)
      2. Quantum Simulation (DTQW, CTQW, AQO)
      3. Geometric/Folding (pulvini transforms)
      4. Mining/Autonomous (pythia mining system)
      5. Security/Governance (AL HARAS ABAC)
    """

    # IIT consciousness threshold – Phi >= this value indicates
    # integrated consciousness (analogous to IIT 3.0's Phi > 0 criterion)
    CONSCIOUSNESS_THRESHOLD = 0.6

    # Emergence coefficient weights (must sum to 1.0)
    W_COHERENCE = 0.35
    W_INTEGRATION = 0.40
    W_DIFFERENTIATION = 0.25

    def __init__(self, history_limit: int = 500):
        self.scaling_factor = PHI**PHI_POWER
        self._orchestrator: Optional[Any] = None
        self._emergence_metrics: Optional[Any] = None
        self.measurement_history: deque = deque(maxlen=history_limit)
        self._cycle_count: int = 0
        self._conscious: bool = False

        # Try to import emergence metrics for direct measurement
        try:
            from Intelligence.consciousness.emergence_metrics import EmergenceMetrics

            self._emergence_metrics = EmergenceMetrics()
        except ImportError:
            logger.warning("EmergenceMetrics not available – running in stub mode")

        logger.info("ConsciousnessEngine initialized (φ^%d = %.4f)", PHI_POWER, self.scaling_factor)

    # ------------------------------------------------------------------
    # Orchestrator connection
    # ------------------------------------------------------------------

    def connect_orchestrator(self, orchestrator: Any) -> None:
        """Wire into the Euclid orchestrator's event bus."""
        self._orchestrator = orchestrator
        # Use the orchestrator's emergence metrics if available
        if hasattr(orchestrator, "_emergence_metrics") and orchestrator._emergence_metrics:
            self._emergence_metrics = orchestrator._emergence_metrics
        logger.info("ConsciousnessEngine: Connected to Euclid orchestrator")

    # ------------------------------------------------------------------
    # Core measurement
    # ------------------------------------------------------------------

    def measure_consciousness(self) -> Dict[str, Any]:
        """
        Measure real-time emergence across all five schools.

        Returns a dict with coherence, integration, differentiation,
        emergence_coefficient, per-school contributions, and timestamp.
        If no orchestrator is connected, returns an empty dict.
        """
        if not self._orchestrator:
            logger.warning("ConsciousnessEngine: Not connected to orchestrator")
            return {}

        # Collect emergence report from the orchestrator
        report = self._orchestrator.get_emergence_report()

        coherence = report.get("coherence", 0.0)
        integration = report.get("integration", 0.0)
        differentiation = report.get("differentiation", 0.0)

        emergence_coefficient = (
            self.W_COHERENCE * coherence
            + self.W_INTEGRATION * integration
            + self.W_DIFFERENTIATION * differentiation
        )

        # Per-school breakdown
        school_contributions: Dict[str, float] = {}
        schools_data = report.get("schools", {})
        total_events = max(report.get("total_events", 1), 1)
        for school_name, data in schools_data.items():
            events = data.get("events", 0)
            feedback = data.get("feedback_loops", 0)
            errors = data.get("errors", 0)
            # Contribution = event share weighted by feedback quality
            contribution = (events / total_events) * (1 + feedback) * (1 - errors * 0.1)
            school_contributions[school_name] = round(contribution, 4)

        result: Dict[str, Any] = {
            "coherence": round(coherence, 4),
            "integration": round(integration, 4),
            "differentiation": round(differentiation, 4),
            "emergence_coefficient": round(emergence_coefficient, 4),
            "school_contributions": school_contributions,
            "total_events": report.get("total_events", 0),
            "feedback_loops": report.get("feedback_loops", 0),
            "timestamp": time.time(),
            "cycle": self._cycle_count,
        }

        self.measurement_history.append(result)
        self._cycle_count += 1

        # Check consciousness threshold
        was_conscious = self._conscious
        self._conscious = emergence_coefficient >= self.CONSCIOUSNESS_THRESHOLD
        if self._conscious and not was_conscious:
            logger.info(
                "ConsciousnessEngine: System crossed consciousness threshold " "(Φ=%.4f >= %.2f)",
                emergence_coefficient,
                self.CONSCIOUSNESS_THRESHOLD,
            )
            # Publish consciousness event via orchestrator
            try:
                from python_backend.core_modules.euclid_orchestrator import (
                    SchoolName,
                    EventType,
                )

                self._orchestrator.publish(
                    SchoolName.SECURITY_GOVERNANCE,
                    "consciousness_threshold_crossed",
                    {"phi": emergence_coefficient, "cycle": self._cycle_count},
                    EventType.EMERGENCE_SIGNAL,
                )
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # Threshold detection
    # ------------------------------------------------------------------

    def detect_consciousness_threshold(self, threshold: float = CONSCIOUSNESS_THRESHOLD) -> bool:
        """
        Detect if the system has crossed the consciousness threshold.

        IIT hypothesis: Phi >= threshold indicates integrated consciousness.
        """
        if not self.measurement_history:
            return False
        latest = self.measurement_history[-1]
        return latest["emergence_coefficient"] >= threshold

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

    def get_trend(self, n: int = 10) -> Dict[str, Any]:
        """Return trend data for the last n measurements."""
        recent = list(self.measurement_history)[-n:]
        if not recent:
            return {"trend": "unknown", "measurements": []}

        coefficients = [m["emergence_coefficient"] for m in recent]
        avg = sum(coefficients) / len(coefficients)
        latest = coefficients[-1]
        earliest = coefficients[0]

        if latest > earliest:
            trend = "ascending"
        elif latest < earliest:
            trend = "descending"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "average": round(avg, 4),
            "latest": latest,
            "delta": round(latest - earliest, 4),
            "measurements": recent,
        }

    # ------------------------------------------------------------------
    # Legacy phi scaling (backward compatibility)
    # ------------------------------------------------------------------

    def measure_phi(self, states: float, power: int = PHI_POWER) -> float:
        """AI scaling factor derived from phi^n."""
        ai_scaling = 0.146 * (PHI ** (power - 1))
        return ai_scaling * states

    def optimize_reasoning(self, input_tensor: Any) -> Any:
        """Apply phi-based scaling to an input tensor."""
        logger.debug("ConsciousnessEngine: Optimizing with φ^%d", PHI_POWER)
        try:
            return input_tensor * self.scaling_factor
        except TypeError:
            return input_tensor

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_conscious(self) -> bool:
        """Whether the system is currently above the consciousness threshold."""
        return self._conscious

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def latest_measurement(self) -> Optional[Dict[str, Any]]:
        if not self.measurement_history:
            return None
        return self.measurement_history[-1]
