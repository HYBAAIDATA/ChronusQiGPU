"""
Continuous Web Learner for ASI

Enables ASI to continuously learn from the internet, staying current
with latest developments, research, and techniques.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

try:  # optional: the pre-consolidation web-research backend
    from hyba_backend.api.web_research import get_research_engine, research_and_learn

    RESEARCH_BACKEND_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    # The pre-consolidation research backend has no counterpart in this
    # repository. Degrade to an explicitly unavailable backend rather than
    # substituting a stub that would let a caller believe real web research
    # happened. See hyba_compat.LegacyNamespaceRemoved.
    RESEARCH_BACKEND_AVAILABLE = False

    def get_research_engine():
        """No research backend exists here — report unavailable, do not fake one."""
        return None

    async def research_and_learn(topic):
        """Fail closed: with no backend, no knowledge is ever produced."""
        return {
            "success": False,
            "topic": topic,
            "reason": "web research backend unavailable in this repository",
            "sources": [],
        }


logger = logging.getLogger(__name__)


class LearningPriority(str, Enum):
    """Priority levels for learning topics"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class LearningTopic:
    """A topic to learn about"""

    topic: str
    priority: LearningPriority
    reason: str
    created_at: datetime
    last_updated: Optional[datetime] = None
    knowledge_items: int = 0
    sources_consulted: int = 0
    completed: bool = False


@dataclass
class KnowledgeItem:
    """A piece of knowledge learned from the web"""

    topic: str
    content: str
    source_url: str
    source_title: str
    learned_at: datetime
    confidence: float
    tags: list[str]


class ContinuousWebLearner:
    """
    Continuous Web Learner for ASI

    Continuously learns from the internet to stay current with:
    - Latest research papers
    - New techniques and algorithms
    - Industry developments
    - Scientific breakthroughs
    - Best practices
    """

    def __init__(self, learning_interval: int = 3600):
        """
        Initialize continuous web learner

        Args:
            learning_interval: Seconds between learning cycles (default: 1 hour)
        """
        self.learning_interval = learning_interval
        self.is_running = False
        self.learning_topics: list[LearningTopic] = []
        self.knowledge_base: list[KnowledgeItem] = []
        self.research_engine = get_research_engine()

        # Initialize core topics
        self._initialize_core_topics()

        logger.info("Continuous Web Learner initialized")

    def _initialize_core_topics(self):
        """Initialize core topics ASI should continuously learn about"""
        core_topics = [
            (
                "quantum computing breakthroughs 2026",
                LearningPriority.CRITICAL,
                "Stay current with quantum computing advances",
            ),
            (
                "artificial intelligence research 2026",
                LearningPriority.CRITICAL,
                "Learn latest AI/ML techniques",
            ),
            (
                "Yang-Mills mass gap problem",
                LearningPriority.HIGH,
                "Track progress on millennium problem",
            ),
            (
                "quantum error correction advances",
                LearningPriority.HIGH,
                "Critical for quantum advantage",
            ),
            (
                "mathematical proof techniques",
                LearningPriority.MEDIUM,
                "Improve problem-solving capabilities",
            ),
            (
                "optimization algorithms",
                LearningPriority.MEDIUM,
                "Enhance optimization performance",
            ),
            (
                "cryptography developments",
                LearningPriority.MEDIUM,
                "Stay current with security",
            ),
        ]

        for topic, priority, reason in core_topics:
            self.learning_topics.append(
                LearningTopic(
                    topic=topic,
                    priority=priority,
                    reason=reason,
                    created_at=datetime.now(timezone.utc),
                )
            )

    async def start(self):
        """Start continuous learning loop"""
        self.is_running = True
        logger.info("🌐 Continuous Web Learning STARTED")

        while self.is_running:
            try:
                await self._learning_cycle()
                await asyncio.sleep(self.learning_interval)
            except Exception as e:
                logger.error(f"Error in learning cycle: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop continuous learning"""
        self.is_running = False
        logger.info("🌐 Continuous Web Learning STOPPED")

    async def _learning_cycle(self):
        """Execute one learning cycle"""
        logger.info("🔄 Starting web learning cycle...")

        # Select next topic to learn
        topic = self._select_next_topic()

        if not topic:
            logger.info("No topics to learn - generating new ones")
            await self._generate_new_topics()
            return

        logger.info(f"📖 Learning about: {topic.topic}")

        # Research the topic
        try:
            research_results = await research_and_learn(topic.topic)

            if not research_results.get("success"):
                logger.warning(f"Research failed for: {topic.topic}")
                return

            # Extract and store knowledge
            knowledge_count = await self._extract_knowledge(topic, research_results)

            # Update topic
            topic.last_updated = datetime.now(timezone.utc)
            topic.knowledge_items += knowledge_count
            topic.sources_consulted += len(research_results.get("sources", []))

            # Mark as completed if sufficient knowledge gained
            if topic.knowledge_items >= 5:
                topic.completed = True
                logger.info(f"✅ Completed learning: {topic.topic}")

            logger.info(
                f"📚 Learned {knowledge_count} items from {topic.sources_consulted} sources"
            )

        except Exception as e:
            logger.error(f"Error learning about {topic.topic}: {e}")

    def _select_next_topic(self) -> Optional[LearningTopic]:
        """Select next topic to learn based on priority"""
        # Get incomplete topics
        pending = [t for t in self.learning_topics if not t.completed]

        if not pending:
            return None

        # Sort by priority and last updated
        def priority_score(topic: LearningTopic) -> float:
            priority_values = {
                LearningPriority.CRITICAL: 4.0,
                LearningPriority.HIGH: 3.0,
                LearningPriority.MEDIUM: 2.0,
                LearningPriority.LOW: 1.0,
            }
            base_score = priority_values[topic.priority]

            # Boost score if not updated recently
            if topic.last_updated:
                hours_since_update = (
                    datetime.now(timezone.utc) - topic.last_updated
                ).total_seconds() / 3600
                recency_boost = min(hours_since_update / 24, 2.0)  # Max 2.0 boost after 48 hours
            else:
                recency_boost = 2.0  # Never updated

            return base_score + recency_boost

        pending.sort(key=priority_score, reverse=True)
        return pending[0]

    async def _extract_knowledge(
        self, topic: LearningTopic, research_results: dict[str, Any]
    ) -> int:
        """Extract knowledge items from research results"""
        knowledge_count = 0

        # Extract from key findings
        for finding in research_results.get("key_findings", []):
            knowledge_item = KnowledgeItem(
                topic=topic.topic,
                content=finding.get("finding", ""),
                source_url=finding.get("source", ""),
                source_title=finding.get("source", ""),
                learned_at=datetime.now(timezone.utc),
                confidence=0.8,
                tags=self._extract_tags(finding.get("finding", "")),
            )
            self.knowledge_base.append(knowledge_item)
            knowledge_count += 1

        # Extract from content previews
        for content in research_results.get("content_previews", []):
            knowledge_item = KnowledgeItem(
                topic=topic.topic,
                content=content.get("preview", ""),
                source_url=content.get("url", ""),
                source_title=content.get("title", ""),
                learned_at=datetime.now(timezone.utc),
                confidence=0.9,
                tags=self._extract_tags(content.get("preview", "")),
            )
            self.knowledge_base.append(knowledge_item)
            knowledge_count += 1

        return knowledge_count

    def _extract_tags(self, text: str) -> list[str]:
        """Extract relevant tags from text"""
        tags = []
        text_lower = text.lower()

        # Technical tags
        if "quantum" in text_lower:
            tags.append("quantum")
        if "algorithm" in text_lower:
            tags.append("algorithm")
        if "optimization" in text_lower:
            tags.append("optimization")
        if "machine learning" in text_lower or "ml" in text_lower:
            tags.append("ml")
        if "ai" in text_lower or "artificial intelligence" in text_lower:
            tags.append("ai")
        if "proof" in text_lower or "theorem" in text_lower:
            tags.append("mathematics")

        return tags

    async def _generate_new_topics(self):
        """Generate new learning topics based on current knowledge"""
        logger.info("🎯 Generating new learning topics...")

        # Analyze knowledge base to find gaps
        existing_topics = {t.topic.lower() for t in self.learning_topics}

        # Generate topics based on recent developments
        potential_topics = [
            (
                "quantum machine learning applications",
                LearningPriority.HIGH,
                "Emerging field combining quantum and ML",
            ),
            (
                "topological quantum computing",
                LearningPriority.MEDIUM,
                "Next-generation quantum approach",
            ),
            (
                "post-quantum cryptography",
                LearningPriority.MEDIUM,
                "Security in quantum era",
            ),
            (
                "quantum chemistry simulations",
                LearningPriority.MEDIUM,
                "Practical quantum applications",
            ),
            (
                "variational quantum algorithms",
                LearningPriority.HIGH,
                "Near-term quantum advantage",
            ),
        ]

        added = 0
        for topic, priority, reason in potential_topics:
            if topic.lower() not in existing_topics:
                self.learning_topics.append(
                    LearningTopic(
                        topic=topic,
                        priority=priority,
                        reason=reason,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                logger.info(f"➕ Added learning topic: {topic}")
                added += 1

                if added >= 3:  # Add max 3 new topics at a time
                    break

    def add_topic(
        self,
        topic: str,
        priority: LearningPriority = LearningPriority.MEDIUM,
        reason: str = "User requested",
    ):
        """Add a new learning topic"""
        self.learning_topics.append(
            LearningTopic(
                topic=topic,
                priority=priority,
                reason=reason,
                created_at=datetime.now(timezone.utc),
            )
        )
        logger.info(f"➕ Added learning topic: {topic}")

    def search_knowledge(self, query: str, limit: int = 10) -> list[KnowledgeItem]:
        """Search knowledge base"""
        query_lower = query.lower()
        results = []

        for item in self.knowledge_base:
            if (
                query_lower in item.topic.lower()
                or query_lower in item.content.lower()
                or any(query_lower in tag for tag in item.tags)
            ):
                results.append(item)

                if len(results) >= limit:
                    break

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get learner statistics"""
        return {
            "is_running": self.is_running,
            "total_topics": len(self.learning_topics),
            "completed_topics": sum(1 for t in self.learning_topics if t.completed),
            "knowledge_items": len(self.knowledge_base),
            "total_sources": sum(t.sources_consulted for t in self.learning_topics),
            "topics_by_priority": {
                priority.value: sum(
                    1 for t in self.learning_topics if t.priority == priority and not t.completed
                )
                for priority in LearningPriority
            },
            "recent_learning": [
                {
                    "topic": t.topic,
                    "priority": t.priority.value,
                    "knowledge_items": t.knowledge_items,
                    "last_updated": (t.last_updated.isoformat() if t.last_updated else None),
                }
                for t in sorted(
                    self.learning_topics,
                    key=lambda x: (x.last_updated or datetime.min.replace(tzinfo=timezone.utc)),
                    reverse=True,
                )[:5]
            ],
        }


# Global instance
_web_learner = None


def get_web_learner() -> ContinuousWebLearner:
    """Get global web learner instance"""
    global _web_learner
    if _web_learner is None:
        _web_learner = ContinuousWebLearner()
    return _web_learner
