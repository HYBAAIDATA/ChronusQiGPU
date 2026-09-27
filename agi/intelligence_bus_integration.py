"""
Phase 3: IntelligenceBus Integration
=====================================

Integrates Mass Gap Relaxation Engine with HYBA's IntelligenceBus for:
- Cross-service learning propagation
- System-wide optimization signals
- Phi-resonance threshold sharing
- Autonomous operation coordination
"""

import asyncio
import logging
import math
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

PHI = (1 + math.sqrt(5)) / 2


class MassGapIntelligenceBusAdapter:
    """
    Adapts Mass Gap Relaxation Engine to IntelligenceBus protocol.

    Enables:
    - Publishing threshold updates to other services
    - Receiving coherence feedback from distributed agents
    - Coordinating global relaxation across service mesh
    """

    def __init__(self, mass_gap_engine: Any, intelligence_bus: Any):
        self.engine = mass_gap_engine
        self.bus = intelligence_bus
        self.component_name = "mass_gap_relaxation"

        # Subscribe to relevant topics
        self.bus.subscribe("coherence_feedback", self._handle_coherence_feedback)
        self.bus.subscribe("threshold_request", self._handle_threshold_request)
        self.bus.subscribe("global_optimization", self._handle_global_optimization)

        # Register as component
        self.bus.register_component(self.component_name, self)

        logger.info("🔌 Mass Gap Relaxation Engine connected to IntelligenceBus")

    async def _handle_coherence_feedback(self, message: Dict[str, Any]):
        """Handle coherence feedback from other services."""
        topic = message.get("research_topic")
        coherence = message.get("coherence")
        source = message.get("source")

        if not topic or coherence is None:
            return

        logger.info(
            f"📥 Received coherence feedback: {topic} = {coherence:.3f} from {source}"
        )

        # Record in auto-tuner if available
        if self.engine.auto_tuner:
            threshold = self.engine.get_topic_threshold(topic)
            self.engine.auto_tuner.record_integration(topic, threshold, coherence, 0)

    async def _handle_threshold_request(self, message: Dict[str, Any]):
        """Handle threshold requests from other services."""
        topic = message.get("topic")
        requester = message.get("requester")

        if not topic:
            return

        threshold = self.engine.get_topic_threshold(topic)

        # Publish threshold response
        await self.bus.publish(
            "threshold_response",
            {
                "topic": topic,
                "threshold": threshold,
                "source": self.component_name,
                "requester": requester,
            },
        )

        logger.info(f"📤 Sent threshold for '{topic}': {threshold:.6f} to {requester}")

    async def _handle_global_optimization(self, message: Dict[str, Any]):
        """Handle global optimization signals."""
        optimization_type = message.get("type")

        if optimization_type == "relax_all":
            logger.info("🌊 Received global relaxation signal")
            await self.engine.run_global_relaxation(parallel=True)

            # Publish completion
            await self.bus.publish(
                "optimization_complete",
                {
                    "type": "mass_gap_relaxation",
                    "source": self.component_name,
                    "topics_relaxed": len(self.engine.active_topics),
                },
            )

    async def publish_threshold_update(
        self, topic: str, old_threshold: float, new_threshold: float
    ):
        """Publish threshold update to IntelligenceBus."""
        await self.bus.publish(
            "threshold_update",
            {
                "topic": topic,
                "old_threshold": old_threshold,
                "new_threshold": new_threshold,
                "source": self.component_name,
                "phi_resonant": abs(new_threshold - (1 / PHI)) < 0.01,
            },
        )

        logger.info(
            f"📡 Published threshold update: {topic} {old_threshold:.6f} → {new_threshold:.6f}"
        )

    async def publish_relaxation_complete(self, results: List[Dict[str, Any]]):
        """Publish relaxation completion with results."""
        total_absorbed = sum(r["data_absorbed"] for r in results)
        avg_coherence = sum(r["coherence"] for r in results) / len(results)

        await self.bus.publish(
            "relaxation_complete",
            {
                "source": self.component_name,
                "topics": [r["topic"] for r in results],
                "total_data_absorbed": total_absorbed,
                "average_coherence": avg_coherence,
                "results": results,
            },
        )

        logger.info(
            f"✅ Published relaxation completion: {total_absorbed} data points, {avg_coherence:.3f} coherence"
        )

    def get_status(self) -> Dict[str, Any]:
        """Get adapter status for IntelligenceBus."""
        return {
            "component": self.component_name,
            "connected": True,
            "topics_tracked": len(self.engine.topic_thresholds),
            "auto_tuning_enabled": self.engine.auto_tuner is not None,
            "active_topics": self.engine.active_topics,
        }


class AutonomousMassGapOrchestrator:
    """
    Autonomous orchestrator for Mass Gap Relaxation.

    Implements OPTIMISE autonomy level:
    - Automatic relaxation triggering
    - Self-healing threshold management
    - Predictive relaxation scheduling
    """

    def __init__(self, mass_gap_engine: Any, intelligence_bus: Any):
        self.engine = mass_gap_engine
        self.bus = intelligence_bus
        self.adapter = MassGapIntelligenceBusAdapter(mass_gap_engine, intelligence_bus)
        self.is_running = False
        self.check_interval = 600  # 10 minutes
        self.auto_relax_threshold = 0.9  # Trigger relaxation if threshold > 0.9
        self.min_coherence = 0.3  # Trigger if coherence < 0.3

    async def start(self):
        """Start autonomous orchestration."""
        self.is_running = True
        logger.info("🤖 Autonomous Mass Gap Orchestrator STARTED")

        while self.is_running:
            try:
                await self._orchestration_cycle()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in orchestration cycle: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop autonomous orchestration."""
        self.is_running = False
        logger.info("🤖 Autonomous Mass Gap Orchestrator STOPPED")

    async def _orchestration_cycle(self):
        """Execute one orchestration cycle."""
        logger.info("🔄 Starting autonomous orchestration cycle...")

        # Check if any topics need relaxation
        topics_needing_relaxation = []

        for topic in self.engine.active_topics:
            threshold = self.engine.get_topic_threshold(topic)

            # Check if threshold is too high
            if threshold > self.auto_relax_threshold:
                topics_needing_relaxation.append(topic)
                logger.info(
                    f"🎯 Topic '{topic}' needs relaxation (threshold: {threshold:.6f})"
                )

        # Check auto-tuner metrics for low coherence
        if self.engine.auto_tuner:
            for topic, metrics in self.engine.auto_tuner.metrics.items():
                if (
                    metrics.avg_coherence < self.min_coherence
                    and topic not in topics_needing_relaxation
                ):
                    topics_needing_relaxation.append(topic)
                    logger.info(
                        f"🎯 Topic '{topic}' needs relaxation (low coherence: {metrics.avg_coherence:.3f})"
                    )

        # Trigger relaxation for identified topics
        if topics_needing_relaxation:
            logger.info(
                f"🌊 Triggering autonomous relaxation for {len(topics_needing_relaxation)} topics"
            )

            results = []
            for topic in topics_needing_relaxation:
                result = await self.engine.trigger_relaxation(topic)
                results.append(result)

            # Publish results to IntelligenceBus
            await self.adapter.publish_relaxation_complete(results)
        else:
            logger.info("✅ All topics within optimal thresholds")

    async def request_global_relaxation(self):
        """Request global relaxation across all services."""
        await self.bus.publish(
            "global_optimization",
            {
                "type": "relax_all",
                "source": "autonomous_orchestrator",
                "reason": "scheduled_maintenance",
            },
        )

        logger.info("📢 Requested global relaxation via IntelligenceBus")


# Global instances
_bus_adapter = None
_orchestrator = None


def get_bus_adapter(
    mass_gap_engine: Any, intelligence_bus: Any
) -> MassGapIntelligenceBusAdapter:
    """Get global IntelligenceBus adapter instance."""
    global _bus_adapter
    if _bus_adapter is None:
        _bus_adapter = MassGapIntelligenceBusAdapter(mass_gap_engine, intelligence_bus)
    return _bus_adapter


def get_orchestrator(
    mass_gap_engine: Any, intelligence_bus: Any
) -> AutonomousMassGapOrchestrator:
    """Get global autonomous orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AutonomousMassGapOrchestrator(mass_gap_engine, intelligence_bus)
    return _orchestrator


async def start_autonomous_operation(mass_gap_engine: Any, intelligence_bus: Any):
    """Start autonomous Mass Gap operation with IntelligenceBus integration."""
    orchestrator = get_orchestrator(mass_gap_engine, intelligence_bus)
    asyncio.create_task(orchestrator.start())
    return {
        "status": "started",
        "message": "Autonomous Mass Gap operation activated with IntelligenceBus integration",
    }


def stop_autonomous_operation():
    """Stop autonomous Mass Gap operation."""
    if _orchestrator:
        _orchestrator.stop()
    return {"status": "stopped", "message": "Autonomous Mass Gap operation deactivated"}
