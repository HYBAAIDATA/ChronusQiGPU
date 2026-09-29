"""
Real-Time Monitoring Dashboard
===============================

Live visualization and monitoring for Mass Gap Relaxation Engine.

Features:
- Real-time coherence visualization
- Threshold adjustment timeline
- Topic health indicators
- Auto-tuning metrics
- IntelligenceBus activity
"""

import asyncio
import logging
import math
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PHI = (1 + math.sqrt(5)) / 2


class MassGapDashboard:
    """
    Real-time monitoring dashboard for Mass Gap Relaxation system.
    """

    def __init__(
        self,
        mass_gap_engine: Any,
        auto_tuner: Optional[Any] = None,
        bus_adapter: Optional[Any] = None,
    ):
        self.engine = mass_gap_engine
        self.auto_tuner = auto_tuner or (
            mass_gap_engine.auto_tuner if hasattr(mass_gap_engine, "auto_tuner") else None
        )
        self.bus_adapter = bus_adapter

        # Historical data (last 100 data points per topic)
        self.coherence_history: Dict[str, deque] = {}
        self.threshold_history: Dict[str, deque] = {}
        self.absorption_history: Dict[str, deque] = {}

        # Dashboard state
        self.last_update = datetime.now()
        self.update_interval = 5  # seconds
        self.is_monitoring = False

        logger.info("📊 Mass Gap Dashboard initialized")

    async def start_monitoring(self):
        """Start real-time monitoring."""
        self.is_monitoring = True
        logger.info("📊 Dashboard monitoring STARTED")

        while self.is_monitoring:
            try:
                await self._update_metrics()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error updating dashboard: {e}")
                await asyncio.sleep(self.update_interval)

    def stop_monitoring(self):
        """Stop real-time monitoring."""
        self.is_monitoring = False
        logger.info("📊 Dashboard monitoring STOPPED")

    async def _update_metrics(self):
        """Update dashboard metrics."""
        self.last_update = datetime.now()

        # Update historical data from auto-tuner
        if self.auto_tuner:
            for topic, metrics in self.auto_tuner.metrics.items():
                # Initialize history if needed
                if topic not in self.coherence_history:
                    self.coherence_history[topic] = deque(maxlen=100)
                    self.threshold_history[topic] = deque(maxlen=100)
                    self.absorption_history[topic] = deque(maxlen=100)

                # Add latest data
                if metrics.coherence_scores:
                    self.coherence_history[topic].append(
                        {
                            "timestamp": datetime.now(),
                            "value": metrics.coherence_scores[-1],
                        }
                    )

                self.threshold_history[topic].append(
                    {"timestamp": datetime.now(), "value": metrics.threshold}
                )

                if metrics.data_absorbed:
                    self.absorption_history[topic].append(
                        {
                            "timestamp": datetime.now(),
                            "value": metrics.data_absorbed[-1],
                        }
                    )

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data."""
        return {
            "timestamp": self.last_update.isoformat(),
            "system_status": self._get_system_status(),
            "topic_health": self._get_topic_health(),
            "auto_tuning_metrics": self._get_auto_tuning_metrics(),
            "intelligence_bus_status": self._get_bus_status(),
            "historical_data": self._get_historical_data(),
            "recommendations": self._get_recommendations(),
        }

    def _get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        total_topics = len(self.engine.active_topics)
        tracked_topics = len(self.engine.topic_thresholds)

        # Calculate average threshold
        if self.engine.topic_thresholds:
            avg_threshold = sum(self.engine.topic_thresholds.values()) / len(
                self.engine.topic_thresholds
            )
        else:
            avg_threshold = self.engine.current_threshold

        # Determine health status
        if avg_threshold < 0.5:
            health = "excellent"
        elif avg_threshold < 0.7:
            health = "good"
        elif avg_threshold < 0.9:
            health = "fair"
        else:
            health = "needs_attention"

        return {
            "health": health,
            "total_topics": total_topics,
            "tracked_topics": tracked_topics,
            "average_threshold": round(avg_threshold, 6),
            "auto_tuning_enabled": self.auto_tuner is not None,
            "intelligence_bus_connected": self.bus_adapter is not None,
            "phi_resonant": abs(avg_threshold - (1 / PHI)) < 0.05,
        }

    def _get_topic_health(self) -> List[Dict[str, Any]]:
        """Get health status for each topic."""
        health_data = []

        for topic in self.engine.active_topics:
            threshold = self.engine.get_topic_threshold(topic)

            # Get metrics from auto-tuner if available
            coherence = None
            trend = "unknown"
            absorption_rate = 0

            if self.auto_tuner and topic in self.auto_tuner.metrics:
                metrics = self.auto_tuner.metrics[topic]
                coherence = metrics.avg_coherence
                trend = metrics.coherence_trend
                absorption_rate = metrics.absorption_rate

            # Determine health
            if threshold < 0.5:
                health = "excellent"
            elif threshold < 0.7:
                health = "good"
            elif threshold < 0.9:
                health = "fair"
            else:
                health = "critical"

            health_data.append(
                {
                    "topic": topic,
                    "health": health,
                    "threshold": round(threshold, 6),
                    "coherence": round(coherence, 3) if coherence else None,
                    "trend": trend,
                    "absorption_rate": round(absorption_rate, 1),
                    "phi_resonant": abs(threshold - (1 / PHI)) < 0.01,
                }
            )

        return sorted(health_data, key=lambda x: x["threshold"], reverse=True)

    def _get_auto_tuning_metrics(self) -> Optional[Dict[str, Any]]:
        """Get auto-tuning metrics."""
        if not self.auto_tuner:
            return None

        stats = self.auto_tuner.get_stats()

        return {
            "is_running": stats["is_running"],
            "topics_tracked": stats["topics_tracked"],
            "total_adjustments": stats["total_adjustments"],
            "recent_adjustments": stats.get("recent_adjustments", []),
            "optimal_coherence_target": round(1 / PHI, 6),
        }

    def _get_bus_status(self) -> Optional[Dict[str, Any]]:
        """Get IntelligenceBus status."""
        if not self.bus_adapter:
            return None

        return self.bus_adapter.get_status()

    def _get_historical_data(self) -> Dict[str, Any]:
        """Get historical data for charts."""
        historical = {}

        for topic in self.engine.active_topics:
            if topic in self.coherence_history:
                historical[topic] = {
                    "coherence": list(self.coherence_history[topic]),
                    "threshold": list(self.threshold_history[topic]),
                    "absorption": list(self.absorption_history[topic]),
                }

        return historical

    def _get_recommendations(self) -> List[Dict[str, Any]]:
        """Get actionable recommendations."""
        recommendations = []

        # Check for high thresholds
        for topic in self.engine.active_topics:
            threshold = self.engine.get_topic_threshold(topic)

            if threshold > 0.9:
                recommendations.append(
                    {
                        "priority": "high",
                        "topic": topic,
                        "action": "trigger_relaxation",
                        "reason": f"Threshold too high ({threshold:.3f})",
                        "expected_improvement": "Increase data absorption",
                    }
                )
            elif threshold > 0.8:
                recommendations.append(
                    {
                        "priority": "medium",
                        "topic": topic,
                        "action": "monitor",
                        "reason": f"Threshold approaching limit ({threshold:.3f})",
                        "expected_improvement": "Prevent data starvation",
                    }
                )

        # Check for low coherence
        if self.auto_tuner:
            for topic, metrics in self.auto_tuner.metrics.items():
                if metrics.avg_coherence < 0.3:
                    recommendations.append(
                        {
                            "priority": "high",
                            "topic": topic,
                            "action": "raise_threshold",
                            "reason": f"Low coherence ({metrics.avg_coherence:.3f})",
                            "expected_improvement": "Reduce noise, improve quality",
                        }
                    )

        # Check for phi-resonance opportunities
        for topic in self.engine.active_topics:
            threshold = self.engine.get_topic_threshold(topic)
            phi_target = 1 / PHI

            if 0.5 < threshold < 0.7 and abs(threshold - phi_target) > 0.05:
                recommendations.append(
                    {
                        "priority": "low",
                        "topic": topic,
                        "action": "optimize_to_phi",
                        "reason": "Near optimal range, can align to φ⁻¹",
                        "expected_improvement": "Mathematical resonance optimization",
                    }
                )

        return sorted(
            recommendations,
            key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]],
        )

    def get_summary(self) -> str:
        """Get human-readable summary."""
        data = self.get_dashboard_data()
        status = data["system_status"]

        summary = f"""
╔══════════════════════════════════════════════════════════════╗
║         Mass Gap Relaxation - System Dashboard              ║
╠══════════════════════════════════════════════════════════════╣
║ System Health: {status['health'].upper():20s}                    ║
║ Average Threshold: {status['average_threshold']:.6f}                         ║
║ Phi-Resonant: {'YES' if status['phi_resonant'] else 'NO':5s}                                ║
║ Topics Tracked: {status['tracked_topics']}/{status['total_topics']}                                      ║
║ Auto-Tuning: {'ENABLED' if status['auto_tuning_enabled'] else 'DISABLED':8s}                            ║
║ IntelligenceBus: {'CONNECTED' if status['intelligence_bus_connected'] else 'DISCONNECTED':12s}                        ║
╠══════════════════════════════════════════════════════════════╣
║ Topic Health:                                                ║
"""

        for topic_health in data["topic_health"][:5]:  # Show top 5
            summary += f"║   {topic_health['topic'][:30]:30s} | {topic_health['health']:10s} ║\n"

        summary += "╠══════════════════════════════════════════════════════════════╣\n"
        summary += f"║ Recommendations: {len(data['recommendations']):2d}                                       ║\n"

        for rec in data["recommendations"][:3]:  # Show top 3
            summary += (
                f"║   [{rec['priority'][0].upper()}] {rec['action'][:25]:25s}                  ║\n"
            )

        summary += "╚══════════════════════════════════════════════════════════════╝\n"

        return summary


# Global instance
_dashboard = None


def get_dashboard(
    mass_gap_engine: Any,
    auto_tuner: Optional[Any] = None,
    bus_adapter: Optional[Any] = None,
) -> MassGapDashboard:
    """Get global dashboard instance."""
    global _dashboard
    if _dashboard is None:
        _dashboard = MassGapDashboard(mass_gap_engine, auto_tuner, bus_adapter)
    return _dashboard


async def start_dashboard_monitoring(
    mass_gap_engine: Any,
    auto_tuner: Optional[Any] = None,
    bus_adapter: Optional[Any] = None,
):
    """Start dashboard monitoring."""
    dashboard = get_dashboard(mass_gap_engine, auto_tuner, bus_adapter)
    asyncio.create_task(dashboard.start_monitoring())
    return {"status": "started", "message": "Dashboard monitoring activated"}


def stop_dashboard_monitoring():
    """Stop dashboard monitoring."""
    if _dashboard:
        _dashboard.stop_monitoring()
    return {"status": "stopped", "message": "Dashboard monitoring deactivated"}
