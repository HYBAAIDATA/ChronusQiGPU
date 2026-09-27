"""
Coherence-Based Auto-Tuning System
===================================

Automatically adjusts Mass Gap Relaxation thresholds based on integration
coherence feedback. Implements OPTIMISE autonomy level for self-tuning.

Part of Phase 2 enhancements for the Mass Gap Relaxation Engine.
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PHI = (1 + math.sqrt(5)) / 2


@dataclass
class CoherenceMetrics:
    """Tracks coherence metrics for a topic over time."""

    topic: str
    threshold: float
    coherence_scores: List[float] = field(default_factory=list)
    data_absorbed: List[int] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)

    @property
    def avg_coherence(self) -> float:
        """Calculate average coherence."""
        return (
            sum(self.coherence_scores) / len(self.coherence_scores)
            if self.coherence_scores
            else 0.0
        )

    @property
    def coherence_trend(self) -> str:
        """Determine if coherence is improving, declining, or stable."""
        if len(self.coherence_scores) < 2:
            return "insufficient_data"

        recent = self.coherence_scores[-3:]
        if len(recent) < 2:
            return "stable"

        trend = sum(recent[i + 1] - recent[i] for i in range(len(recent) - 1))

        if trend > 0.1:
            return "improving"
        elif trend < -0.1:
            return "declining"
        else:
            return "stable"

    @property
    def absorption_rate(self) -> float:
        """Calculate average data absorption rate."""
        return (
            sum(self.data_absorbed) / len(self.data_absorbed)
            if self.data_absorbed
            else 0.0
        )


class CoherenceBasedAutoTuner:
    """
    Automatically tunes Mass Gap Relaxation thresholds based on coherence feedback.

    Implements adaptive threshold management:
    - Lowers threshold if coherence is high but absorption is low
    - Raises threshold if coherence is low (too much noise)
    - Maintains phi-resonant relationships in adjustments
    """

    def __init__(self, mass_gap_engine: Optional[Any] = None):
        self.engine = mass_gap_engine
        self.metrics: Dict[str, CoherenceMetrics] = {}
        self.is_running = False
        self.tuning_interval = 300  # 5 minutes
        self.min_threshold = 0.382  # φ^-2
        self.max_threshold = 0.999945
        self.optimal_coherence = 1 / PHI  # φ^-1 ≈ 0.618
        self.tuning_history: List[Dict[str, Any]] = []

    async def start(self):
        """Start auto-tuning loop."""
        self.is_running = True
        logger.info("🎛️  Coherence-Based Auto-Tuner STARTED")

        while self.is_running:
            try:
                await self._tuning_cycle()
                await asyncio.sleep(self.tuning_interval)
            except Exception as e:
                logger.error(f"Error in auto-tuning cycle: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop auto-tuning loop."""
        self.is_running = False
        logger.info("🎛️  Coherence-Based Auto-Tuner STOPPED")

    async def _tuning_cycle(self):
        """Execute one auto-tuning cycle."""
        logger.info("🔧 Starting auto-tuning cycle...")

        if not self.engine:
            logger.warning("No Mass Gap Engine connected - skipping tuning")
            return

        adjustments_made = 0

        for topic, metrics in self.metrics.items():
            if len(metrics.coherence_scores) < 2:
                continue  # Need at least 2 data points

            adjustment = await self._calculate_adjustment(metrics)

            if adjustment != 0:
                new_threshold = self._apply_adjustment(metrics.threshold, adjustment)

                # Update engine threshold
                if hasattr(self.engine, "topic_thresholds"):
                    self.engine.topic_thresholds[topic] = new_threshold

                # Update metrics
                metrics.threshold = new_threshold

                # Record tuning action
                self.tuning_history.append(
                    {
                        "timestamp": datetime.now(),
                        "topic": topic,
                        "old_threshold": metrics.threshold,
                        "new_threshold": new_threshold,
                        "adjustment": adjustment,
                        "reason": self._get_adjustment_reason(metrics),
                        "avg_coherence": metrics.avg_coherence,
                        "trend": metrics.coherence_trend,
                    }
                )

                adjustments_made += 1
                logger.info(
                    f"🎯 Adjusted '{topic}': {metrics.threshold:.6f} → {new_threshold:.6f}"
                )

        logger.info(
            f"✅ Auto-tuning cycle complete: {adjustments_made} adjustments made"
        )

    async def _calculate_adjustment(self, metrics: CoherenceMetrics) -> float:
        """
        Calculate threshold adjustment based on coherence metrics.

        Returns:
            Adjustment factor (positive = raise threshold, negative = lower threshold)
        """
        avg_coherence = metrics.avg_coherence
        trend = metrics.coherence_trend
        absorption_rate = metrics.absorption_rate

        # Target: coherence near φ^-1 (0.618)
        coherence_delta = avg_coherence - self.optimal_coherence

        # Decision logic
        if trend == "declining" and avg_coherence < 0.5:
            # Too much noise - raise threshold
            return 0.1 / PHI  # Phi-resonant increase

        elif trend == "improving" and avg_coherence > 0.7 and absorption_rate < 5:
            # High quality but low volume - lower threshold
            return -0.1 / PHI  # Phi-resonant decrease

        elif abs(coherence_delta) < 0.05:
            # Near optimal - no adjustment
            return 0.0

        elif coherence_delta > 0.15:
            # Too strict - lower threshold
            return -0.05 / PHI

        elif coherence_delta < -0.15:
            # Too loose - raise threshold
            return 0.05 / PHI

        return 0.0

    def _apply_adjustment(self, current: float, adjustment: float) -> float:
        """Apply adjustment while respecting min/max bounds."""
        new_threshold = current + adjustment
        return max(self.min_threshold, min(self.max_threshold, new_threshold))

    def _get_adjustment_reason(self, metrics: CoherenceMetrics) -> str:
        """Generate human-readable reason for adjustment."""
        trend = metrics.coherence_trend
        avg_coherence = metrics.avg_coherence

        if trend == "declining":
            return f"Declining coherence ({avg_coherence:.3f}) - reducing noise"
        elif trend == "improving":
            return f"Improving coherence ({avg_coherence:.3f}) - increasing absorption"
        else:
            return f"Optimizing toward φ⁻¹ target (current: {avg_coherence:.3f})"

    def record_integration(
        self, topic: str, threshold: float, coherence: float, data_absorbed: int
    ):
        """Record integration results for auto-tuning analysis."""
        if topic not in self.metrics:
            self.metrics[topic] = CoherenceMetrics(topic=topic, threshold=threshold)

        metrics = self.metrics[topic]
        metrics.coherence_scores.append(coherence)
        metrics.data_absorbed.append(data_absorbed)
        metrics.timestamps.append(datetime.now())
        metrics.threshold = threshold

        # Keep only recent history (last 20 integrations)
        if len(metrics.coherence_scores) > 20:
            metrics.coherence_scores = metrics.coherence_scores[-20:]
            metrics.data_absorbed = metrics.data_absorbed[-20:]
            metrics.timestamps = metrics.timestamps[-20:]

    def get_stats(self) -> Dict[str, Any]:
        """Get auto-tuner statistics."""
        return {
            "is_running": self.is_running,
            "topics_tracked": len(self.metrics),
            "total_adjustments": len(self.tuning_history),
            "recent_adjustments": [
                {
                    "topic": h["topic"],
                    "new_threshold": h["new_threshold"],
                    "reason": h["reason"],
                    "timestamp": h["timestamp"].isoformat(),
                }
                for h in self.tuning_history[-5:]
            ],
            "topic_metrics": {
                topic: {
                    "threshold": m.threshold,
                    "avg_coherence": m.avg_coherence,
                    "trend": m.coherence_trend,
                    "absorption_rate": m.absorption_rate,
                    "data_points": len(m.coherence_scores),
                }
                for topic, m in self.metrics.items()
            },
        }

    def get_recommendations(self) -> List[Dict[str, Any]]:
        """Get tuning recommendations without applying them."""
        recommendations = []

        for topic, metrics in self.metrics.items():
            if len(metrics.coherence_scores) < 2:
                continue

            # Calculate adjustment synchronously for recommendations
            adjustment = self._calculate_adjustment_sync(metrics)

            if adjustment != 0:
                new_threshold = self._apply_adjustment(metrics.threshold, adjustment)
                recommendations.append(
                    {
                        "topic": topic,
                        "current_threshold": metrics.threshold,
                        "recommended_threshold": new_threshold,
                        "adjustment": adjustment,
                        "reason": self._get_adjustment_reason(metrics),
                        "avg_coherence": metrics.avg_coherence,
                        "trend": metrics.coherence_trend,
                    }
                )

        return recommendations

    def _calculate_adjustment_sync(self, metrics: CoherenceMetrics) -> float:
        """Synchronous version of calculate_adjustment for recommendations."""
        avg_coherence = metrics.avg_coherence
        trend = metrics.coherence_trend
        absorption_rate = metrics.absorption_rate

        coherence_delta = avg_coherence - self.optimal_coherence

        if trend == "declining" and avg_coherence < 0.5:
            return 0.1 / PHI
        elif trend == "improving" and avg_coherence > 0.7 and absorption_rate < 5:
            return -0.1 / PHI
        elif abs(coherence_delta) < 0.05:
            return 0.0
        elif coherence_delta > 0.15:
            return -0.05 / PHI
        elif coherence_delta < -0.15:
            return 0.05 / PHI

        return 0.0


# Global instance
_auto_tuner = None


def get_auto_tuner(mass_gap_engine: Optional[Any] = None) -> CoherenceBasedAutoTuner:
    """Get global auto-tuner instance."""
    global _auto_tuner
    if _auto_tuner is None:
        _auto_tuner = CoherenceBasedAutoTuner(mass_gap_engine)
    return _auto_tuner


async def start_auto_tuning(mass_gap_engine: Optional[Any] = None):
    """Start auto-tuning in background."""
    tuner = get_auto_tuner(mass_gap_engine)
    asyncio.create_task(tuner.start())
    return {"status": "started", "message": "Coherence-based auto-tuning activated"}


def stop_auto_tuning():
    """Stop auto-tuning."""
    tuner = get_auto_tuner()
    tuner.stop()
    return {"status": "stopped", "message": "Coherence-based auto-tuning deactivated"}
