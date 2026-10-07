"""
Autonomous Learning Loop for PYTHAGORAS ASI
============================================

Enables continuous, self-directed learning without human intervention.
PYTHAGORAS can:
- Identify knowledge gaps
- Research topics autonomously
- Update its knowledge base
- Improve its capabilities over time
- Set its own learning goals

This is what transforms PYTHAGORAS from tool to true ASI.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agi.web_research import research_and_learn
from agi.reasoning import get_reasoning_engine

logger = logging.getLogger(__name__)


@dataclass
class LearningGoal:
    """A learning goal"""

    topic: str
    priority: int  # 1-10
    reason: str
    created_at: datetime
    completed: bool = False
    knowledge_gained: int = 0


class AutonomousLearningLoop:
    """
    Autonomous Learning Loop

    Runs continuously in background, enabling PYTHAGORAS to learn
    and improve without human intervention.
    """

    def __init__(self):
        self.is_running = False
        self.learning_goals: List[LearningGoal] = []
        self.topics_mastered: List[str] = []
        self.learning_history: List[Dict[str, Any]] = []
        self.reasoning_engine = get_reasoning_engine()

        # Initialize with core topics
        self._initialize_core_learning_goals()

    def _initialize_core_learning_goals(self):
        """Initialize with topics PYTHAGORAS should learn"""
        core_topics = [
            (
                "Yang-Mills mass gap problem",
                10,
                "Millennium problem - fundamental to mission",
            ),
            (
                "Quantum error correction advances 2026",
                9,
                "Critical for quantum advantage",
            ),
            ("Gauge theory recent breakthroughs", 9, "Foundation of Yang-Mills"),
            (
                "Quantum field theory computational techniques",
                8,
                "Needed for millennium problems",
            ),
            ("Code optimization algorithms 2026", 7, "Self-improvement"),
            ("Mathematical proof techniques", 8, "Problem solving"),
            ("Topological quantum computing", 7, "Next-generation quantum"),
        ]

        for topic, priority, reason in core_topics:
            self.learning_goals.append(
                LearningGoal(
                    topic=topic,
                    priority=priority,
                    reason=reason,
                    created_at=datetime.now(timezone.utc),
                )
            )

    async def start(self):
        """Start the autonomous learning loop"""
        self.is_running = True
        logger.info("🧠 PYTHAGORAS Autonomous Learning Loop STARTED")

        while self.is_running:
            try:
                await self._learning_cycle()
                # Wait before next cycle
                await asyncio.sleep(3600)  # Learn every hour
            except Exception as e:
                logger.error(f"Error in learning loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    def stop(self):
        """Stop the autonomous learning loop"""
        self.is_running = False
        logger.info("🧠 PYTHAGORAS Autonomous Learning Loop STOPPED")

        # Cancel any pending tasks
        if hasattr(self, "_task") and self._task:
            self._task.cancel()
            logger.info("🧠 Autonomous learning task cancelled")

    async def _learning_cycle(self):
        """Execute one learning cycle"""
        logger.info("🔄 Starting learning cycle...")

        # Step 1: Identify what to learn (prioritize goals)
        next_goal = self._select_next_learning_goal()

        if not next_goal:
            logger.info("✓ No learning goals pending - generating new ones")
            await self._generate_new_learning_goals()
            return

        logger.info(f"📚 Learning about: {next_goal.topic}")

        # Step 2: Research the topic
        research_results = await research_and_learn(next_goal.topic)

        if not research_results.get("success"):
            logger.warning(f"⚠️  Research failed for: {next_goal.topic}")
            return

        # Step 3: Integrate knowledge
        knowledge_items = research_results.get("total_knowledge_items", 0)
        next_goal.knowledge_gained = knowledge_items

        logger.info(f"✓ Learned {knowledge_items} items about: {next_goal.topic}")

        # Step 4: Reason about what was learned
        await self.reasoning_engine.reason_about(
            f"What are the implications of what I learned about {next_goal.topic}?",
            {"research_results": research_results},
        )

        # Step 5: Update goal status
        next_goal.completed = True
        self.topics_mastered.append(next_goal.topic)

        # Step 6: Record learning
        self.learning_history.append(
            {
                "topic": next_goal.topic,
                "timestamp": datetime.now(timezone.utc),
                "knowledge_gained": knowledge_items,
                "reasoning_performed": True,
                "sources": len(research_results.get("sources", [])),
            }
        )

        logger.info(f"✅ Completed learning: {next_goal.topic}")

        # Step 7: Identify follow-up topics
        follow_ups = self._identify_follow_up_topics(research_results)
        for topic in follow_ups:
            self.learning_goals.append(
                LearningGoal(
                    topic=topic,
                    priority=7,
                    reason=f"Follow-up from {next_goal.topic}",
                    created_at=datetime.now(timezone.utc),
                )
            )

        logger.info(f"🔗 Identified {len(follow_ups)} follow-up topics")

    def _select_next_learning_goal(self) -> Optional[LearningGoal]:
        """Select next topic to learn based on priority"""
        pending_goals = [g for g in self.learning_goals if not g.completed]

        if not pending_goals:
            return None

        # Sort by priority (highest first)
        pending_goals.sort(key=lambda g: g.priority, reverse=True)
        return pending_goals[0]

    async def _generate_new_learning_goals(self):
        """Generate new learning goals autonomously"""
        logger.info("🎯 Generating new learning goals...")

        # Ask reasoning engine what PYTHAGORAS should learn
        await self.reasoning_engine.reason_about(
            "Based on my current knowledge and millennium problem goals, what should I learn next?",
            {"current_topics": self.topics_mastered},
        )

        # Extract learning goals from reasoning

        # Generate goals based on areas we haven't covered
        potential_topics = [
            "Recent advances in mathematical physics",
            "Novel quantum algorithms 2026",
            "Computational complexity breakthroughs",
            "Unsolved problems in quantum field theory",
            "Advanced proof techniques",
        ]

        for topic in potential_topics[:2]:  # Add 2 new goals
            if topic not in self.topics_mastered:
                self.learning_goals.append(
                    LearningGoal(
                        topic=topic,
                        priority=6,
                        reason="Autonomous goal generation",
                        created_at=datetime.now(timezone.utc),
                    )
                )
                logger.info(f"➕ Added learning goal: {topic}")

    def _identify_follow_up_topics(self, research_results: Dict[str, Any]) -> List[str]:
        """Identify follow-up topics from research results"""
        follow_ups = []

        # Extract from key findings
        for finding in research_results.get("key_findings", [])[:3]:
            finding_text = finding.get("finding", "")

            # Look for related topics mentioned
            if "related" in finding_text.lower() or "also" in finding_text.lower():
                # This is a simplification - could use NLP here
                follow_ups.append(f"Deep dive: {finding.get('source', 'related topic')}")

        return follow_ups[:2]  # Limit to 2 follow-ups

    def get_stats(self) -> Dict[str, Any]:
        """Get learning loop statistics"""
        return {
            "is_running": self.is_running,
            "total_learning_goals": len(self.learning_goals),
            "completed_goals": sum(1 for g in self.learning_goals if g.completed),
            "topics_mastered": len(self.topics_mastered),
            "total_knowledge_gained": sum(g.knowledge_gained for g in self.learning_goals),
            "learning_history_size": len(self.learning_history),
            "pending_goals": [
                {"topic": g.topic, "priority": g.priority}
                for g in self.learning_goals
                if not g.completed
            ][
                :5
            ],  # Show top 5
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of autonomous learning system"""
        try:
            stats = self.get_stats()

            # Check if system is operational
            is_operational = True
            issues = []

            # Check if learning goals exist
            if stats["total_learning_goals"] == 0:
                is_operational = False
                issues.append("No learning goals initialized")

            # Check if reasoning engine is accessible
            try:
                reasoning_test = await self.reasoning_engine.reason_about(
                    "test query", {"test": True}
                )
                if not reasoning_test.get("success"):
                    is_operational = False
                    issues.append("Reasoning engine not responding")
            except Exception as e:
                is_operational = False
                issues.append(f"Reasoning engine error: {e!s}")

            # Check if web research is accessible
            try:
                research_test = await research_and_learn("test")
                if not research_test.get("success"):
                    issues.append("Web research may have connectivity issues")
            except Exception as e:
                issues.append(f"Web research error: {e!s}")

            # Calculate health score
            health_score = 1.0 if is_operational else 0.0
            if issues:
                health_score = max(0.0, health_score - len(issues) * 0.2)

            return {
                "status": "healthy" if is_operational else "degraded",
                "health_score": health_score,
                "is_operational": is_operational,
                "issues": issues,
                "stats": stats,
                "last_check": datetime.now(timezone.utc).isoformat(),
                "service": "AutonomousLearningLoop",
            }

        except Exception as e:
            return {
                "status": "error",
                "health_score": 0.0,
                "is_operational": False,
                "issues": [f"Health check failed: {e!s}"],
                "stats": {},
                "last_check": datetime.now(timezone.utc).isoformat(),
                "service": "AutonomousLearningLoop",
            }


# Global instance
_learning_loop = None


def get_learning_loop() -> AutonomousLearningLoop:
    """Get global learning loop instance"""
    global _learning_loop
    if _learning_loop is None:
        _learning_loop = AutonomousLearningLoop()
    return _learning_loop


async def start_autonomous_learning():
    """Start autonomous learning in background"""
    loop = get_learning_loop()
    asyncio.create_task(loop.start())
    return {"status": "started", "message": "PYTHAGORAS autonomous learning activated"}


def stop_autonomous_learning():
    """Stop autonomous learning"""
    loop = get_learning_loop()
    loop.stop()
    return {
        "status": "stopped",
        "message": "PYTHAGORAS autonomous learning deactivated",
    }
