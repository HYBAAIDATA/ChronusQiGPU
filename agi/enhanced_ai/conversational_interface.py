"""
Conversational Interface for Enhanced AGI

This module provides a comprehensive conversational interface that integrates
NLP processing, knowledge base access, and HYBA's computational intelligence
to enable true AGI-level conversations.
"""

import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Import existing HYBA components
from hyba_backend.platform.quantum_core.processor import (
    ProblemDomain,
    UniversalQuantumProcessor,
)
from hyba_backend.platform.resonance import PhiResonanceScorer

from .knowledge_base import EnhancedKnowledgeBase

# Import enhanced AI components
from .nlp_processor import (
    ConversationContext,
    EnhancedNLPProcessor,
    NLPUnderstandingLevel,
    NLPUtterance,
)

logger = logging.getLogger(__name__)


class ConversationState(str, Enum):
    """Conversation states"""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    PROCESSING = "processing"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"


class ResponseType(str, Enum):
    """Types of responses"""

    INFORMATIONAL = "informational"
    MATHEMATICAL = "mathematical"
    PROBLEM_SOLVING = "problem_solving"
    CONVERSATIONAL = "conversational"
    CREATIVE = "creative"
    EXPLANATORY = "explanatory"


@dataclass
class ConversationSession:
    """Represents a conversation session"""

    session_id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime]
    state: ConversationState
    context: ConversationContext
    response_history: List[Dict[str, Any]]
    satisfaction_score: float
    last_activity: datetime


@dataclass
class ConversationResponse:
    """Represents a conversational response"""

    response_text: str
    response_type: ResponseType
    confidence: float
    knowledge_used: List[str]
    computational_complexity: str
    phi_resonance_score: float
    timestamp: datetime


class EnhancedConversationalInterface:
    """
    Advanced conversational interface that integrates all enhanced AI capabilities

    Features:
    - Multi-modal conversation management
    - Context-aware response generation
    - Emotional intelligence and adaptation
    - Knowledge integration and explanation
    - Mathematical and computational problem solving
    - Creative and generative capabilities
    - Quantum-enhanced conversation optimization
    """

    def __init__(self):
        self.phi_scorer = PhiResonanceScorer()
        self.quantum_processor = UniversalQuantumProcessor(max_dimension=2**20)

        # Initialize enhanced components
        self.nlp_processor = EnhancedNLPProcessor()
        self.knowledge_base = EnhancedKnowledgeBase()

        # Conversation management and resource quotas
        self.active_sessions: Dict[str, ConversationSession] = {}
        self.user_preferences: Dict[str, Dict[str, Any]] = {}
        self.max_active_sessions = 1000
        self.session_ttl_seconds = 3600  # 1 hour

        # Response generation
        self.response_templates = self._load_response_templates()
        self.conversation_strategies = self._initialize_strategies()

        logger.info("Enhanced Conversational Interface initialized")

    def _cleanup_expired_sessions(self):
        """Remove sessions that have exceeded TTL"""
        now = datetime.now()
        expired_ids = [
            sid
            for sid, session in self.active_sessions.items()
            if (now - session.last_activity).total_seconds() > self.session_ttl_seconds
        ]
        for sid in expired_ids:
            del self.active_sessions[sid]
            logger.info(f"Cleaned up expired session: {sid}")

    async def start_conversation(
        self,
        user_id: str,
        initial_message: str,
        conversation_context: Optional[Dict[str, Any]] = None,
    ) -> ConversationSession:
        """
        Start a new conversation session with resource management

        Args:
            user_id: Unique user identifier
            initial_message: User's initial message
            conversation_context: Additional context for the conversation
        """
        try:
            self._cleanup_expired_sessions()

            if len(self.active_sessions) >= self.max_active_sessions:
                logger.warning("Max active sessions reached, cannot start new session")
                raise RuntimeError("System capacity reached. Please try again later.")

            session_id = str(uuid.uuid4())

            # Create conversation session
            session = ConversationSession(
                session_id=session_id,
                user_id=user_id,
                start_time=datetime.now(),
                end_time=None,
                state=ConversationState.INITIALIZING,
                context=ConversationContext(
                    user_id=user_id,
                    session_id=session_id,
                    history=[],
                    current_topic="general",
                    emotional_state={},
                    knowledge_gaps=[],
                    last_interaction=datetime.now(),
                ),
                response_history=[],
                satisfaction_score=0.0,
                last_activity=datetime.now(),
            )

            # Process initial message
            utterance = await self.nlp_processor.process_utterance(
                initial_message, user_id, conversation_context
            )

            session.context.history.append(utterance)
            session.state = ConversationState.ACTIVE

            # Store session
            self.active_sessions[session_id] = session

            # Update user preferences
            await self._update_user_preferences(user_id, utterance)

            logger.info(
                f"Started conversation session: {session_id} for user: {user_id}"
            )
            return session

        except Exception as e:
            logger.error(f"Failed to start conversation: {e}")
            raise

    async def process_user_message(
        self, session_id: str, user_message: str
    ) -> ConversationResponse:
        """
        Process a user message and generate a response

        Args:
            session_id: Conversation session ID
            user_message: User's message text
        """
        try:
            if session_id not in self.active_sessions:
                raise ValueError(f"Session {session_id} not found")

            session = self.active_sessions[session_id]
            session.state = ConversationState.PROCESSING
            session.last_activity = datetime.now()

            # Process user utterance
            utterance = await self.nlp_processor.process_utterance(
                user_message, session.user_id, session.context.__dict__
            )

            # Update conversation context
            session.context.history.append(utterance)
            session.context.last_interaction = datetime.now()

            # Determine response strategy
            response_strategy = await self._determine_response_strategy(
                utterance, session
            )

            # Generate response
            response_text = await self._generate_response(
                utterance, session, response_strategy
            )

            # Enhance response with knowledge and computation
            enhanced_response = await self._enhance_response(
                response_text, utterance, session, response_strategy
            )

            # Calculate response metrics
            response_metrics = await self._calculate_response_metrics(
                enhanced_response, utterance, response_strategy
            )

            # Create response object
            response = ConversationResponse(
                response_text=enhanced_response,
                response_type=response_strategy["type"],
                confidence=response_metrics["confidence"],
                knowledge_used=response_metrics["knowledge_used"],
                computational_complexity=response_strategy["complexity"],
                phi_resonance_score=response_metrics["phi_resonance"],
                timestamp=datetime.now(),
            )

            # Store response in history
            session.response_history.append(
                {
                    "utterance": utterance.__dict__,
                    "response": response.__dict__,
                    "strategy": response_strategy,
                }
            )

            session.state = ConversationState.ACTIVE

            logger.info(
                f"Generated response for session {session_id}: {response.response_type}"
            )
            return response

        except Exception as e:
            logger.error(f"Failed to process user message: {e}")
            session.state = ConversationState.ERROR
            raise

    async def end_conversation(
        self, session_id: str, satisfaction_feedback: Optional[str] = None
    ) -> bool:
        """
        End a conversation session and process feedback

        Args:
            session_id: Conversation session ID
            satisfaction_feedback: User satisfaction feedback
        """
        try:
            if session_id not in self.active_sessions:
                return False

            session = self.active_sessions[session_id]
            session.end_time = datetime.now()
            session.state = ConversationState.COMPLETED

            # Process satisfaction feedback
            if satisfaction_feedback:
                satisfaction_score = await self._calculate_satisfaction_score(
                    satisfaction_feedback
                )
                session.satisfaction_score = satisfaction_score

                # Update knowledge base with feedback
                await self.knowledge_base.learn_from_interaction(
                    (
                        session.response_history[-1]["utterance"]["text"]
                        if session.response_history
                        else ""
                    ),
                    (
                        session.response_history[-1]["response"]["response_text"]
                        if session.response_history
                        else ""
                    ),
                    satisfaction_feedback,
                )

            # Clean up session
            del self.active_sessions[session_id]

            logger.info(f"Ended conversation session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to end conversation: {e}")
            return False

    async def get_conversation_context(
        self, session_id: str
    ) -> Optional[ConversationContext]:
        """Get the current conversation context"""
        if session_id in self.active_sessions:
            return self.active_sessions[session_id].context
        return None

    async def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get the conversation history for a session"""
        if session_id in self.active_sessions:
            return self.active_sessions[session_id].response_history
        return []

    async def stream_conversation(
        self, session_id: str, user_messages: AsyncGenerator[str, None]
    ) -> AsyncGenerator[ConversationResponse, None]:
        """
        Stream conversation responses for multiple user messages

        Args:
            session_id: Conversation session ID
            user_messages: Async generator of user messages
        """
        try:
            async for message in user_messages:
                response = await self.process_user_message(session_id, message)
                yield response

        except Exception as e:
            logger.error(f"Conversation streaming failed: {e}")
            raise

    def _load_response_templates(self) -> Dict[str, List[str]]:
        """Load response templates for different conversation types"""
        return {
            "greeting": [
                "Hello! I'm an advanced AI with computational intelligence capabilities. How can I assist you today?",
                "Greetings! I'm here to help with mathematical analysis, general knowledge, and problem-solving. What can I do for you?",
                "Welcome! I have access to extensive knowledge and computational abilities. How may I serve you?",
            ],
            "mathematical": [
                "Let me analyze this mathematically...",
                "This problem can be solved using computational methods...",
                "I'll apply mathematical reasoning to this question...",
            ],
            "knowledge": [
                "Based on my knowledge base...",
                "From what I understand...",
                "Let me share information about this topic...",
            ],
            "problem_solving": [
                "Let's approach this systematically...",
                "I can help solve this using optimization techniques...",
                "Let me analyze the problem and propose solutions...",
            ],
            "creative": [
                "Let me think creatively about this...",
                "Here's an innovative approach...",
                "I'll generate some creative solutions for you...",
            ],
        }

    def _initialize_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize conversation strategies"""
        return {
            "mathematical_query": {
                "type": ResponseType.MATHEMATICAL,
                "complexity": "high",
                "requires_computation": True,
                "templates": self.response_templates["mathematical"],
            },
            "general_knowledge": {
                "type": ResponseType.INFORMATIONAL,
                "complexity": "medium",
                "requires_computation": False,
                "templates": self.response_templates["knowledge"],
            },
            "problem_solving": {
                "type": ResponseType.PROBLEM_SOLVING,
                "complexity": "high",
                "requires_computation": True,
                "templates": self.response_templates["problem_solving"],
            },
            "conversational": {
                "type": ResponseType.CONVERSATIONAL,
                "complexity": "low",
                "requires_computation": False,
                "templates": self.response_templates["greeting"],
            },
            "creative": {
                "type": ResponseType.CREATIVE,
                "complexity": "medium",
                "requires_computation": False,
                "templates": self.response_templates["creative"],
            },
        }

    async def _determine_response_strategy(
        self, utterance: NLPUtterance, session: ConversationSession
    ) -> Dict[str, Any]:
        """Determine the best response strategy based on intent and context"""
        intent = utterance.intent

        if intent in self.conversation_strategies:
            return self.conversation_strategies[intent]

        # Default strategy based on understanding level
        understanding_level = self.nlp_processor.get_understanding_level(
            session.user_id
        )

        if understanding_level in [
            NLPUnderstandingLevel.ADVANCED,
            NLPUnderstandingLevel.EXPERT,
        ]:
            return self.conversation_strategies["problem_solving"]
        elif understanding_level == NLPUnderstandingLevel.INTERMEDIATE:
            return self.conversation_strategies["general_knowledge"]
        else:
            return self.conversation_strategies["conversational"]

    async def _generate_response(
        self,
        utterance: NLPUtterance,
        session: ConversationSession,
        strategy: Dict[str, Any],
    ) -> str:
        """Generate a response based on the determined strategy"""
        try:
            # Get user preferences
            user_prefs = self.user_preferences.get(session.user_id, {})

            # Generate base response using NLP processor
            base_response = await self.nlp_processor.generate_response(
                utterance, session.user_id
            )

            # Apply strategy-specific enhancements
            if strategy["type"] == ResponseType.MATHEMATICAL:
                base_response = await self._enhance_mathematical_response(
                    base_response, utterance
                )
            elif strategy["type"] == ResponseType.INFORMATIONAL:
                base_response = await self._enhance_informational_response(
                    base_response, utterance
                )
            elif strategy["type"] == ResponseType.PROBLEM_SOLVING:
                base_response = await self._enhance_problem_solving_response(
                    base_response, utterance
                )
            elif strategy["type"] == ResponseType.CREATIVE:
                base_response = await self._enhance_creative_response(
                    base_response, utterance
                )

            # Apply user preference enhancements
            if user_prefs.get("formal_tone", False):
                base_response = self._apply_formal_tone(base_response)
            elif user_prefs.get("casual_tone", False):
                base_response = self._apply_casual_tone(base_response)

            return base_response

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return "I apologize, but I'm having difficulty generating a response at the moment."

    async def _enhance_response(
        self,
        response_text: str,
        utterance: NLPUtterance,
        session: ConversationSession,
        strategy: Dict[str, Any],
    ) -> str:
        """Enhance response with knowledge and computational capabilities"""
        try:
            enhanced_text = response_text

            # Add knowledge base information if relevant
            if strategy["requires_computation"]:
                knowledge_entries = await self.knowledge_base.query_knowledge(
                    utterance.text, context={"session_id": session.session_id}
                )

                if knowledge_entries:
                    knowledge_summary = self._summarize_knowledge(knowledge_entries)
                    enhanced_text += f"\n\nAdditional context: {knowledge_summary}"

            # Apply quantum optimization if response is complex
            if strategy["complexity"] == "high" and len(enhanced_text) > 200:
                enhanced_text = await self._quantum_optimize_response(
                    enhanced_text, utterance
                )

            # Add conversational elements
            enhanced_text = self._add_conversational_elements(
                enhanced_text, session.context.emotional_state
            )

            return enhanced_text

        except Exception as e:
            logger.error(f"Response enhancement failed: {e}")
            return response_text

    async def _calculate_response_metrics(
        self, response_text: str, utterance: NLPUtterance, strategy: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate response quality metrics"""
        try:
            # Calculate confidence based on multiple factors
            base_confidence = utterance.confidence
            knowledge_confidence = 0.8  # Default if no knowledge used
            computational_confidence = 0.9  # Default if computation used

            # Adjust based on strategy
            if strategy["requires_computation"]:
                confidence = (base_confidence + computational_confidence) / 2
            else:
                confidence = (base_confidence + knowledge_confidence) / 2

            # Calculate phi resonance score
            phi_score = self.phi_scorer.score(
                {
                    "response_length": len(response_text),
                    "utterance_confidence": utterance.confidence,
                    "strategy_complexity": strategy["complexity"],
                }
            )

            # Extract knowledge used
            knowledge_used = []
            if "knowledge" in response_text.lower():
                # Extract concepts mentioned in response
                for concept in self.knowledge_base.knowledge_entries.keys():
                    if concept.lower() in response_text.lower():
                        knowledge_used.append(concept)

            return {
                "confidence": confidence,
                "phi_resonance": phi_score,
                "knowledge_used": knowledge_used,
            }

        except Exception as e:
            logger.error(f"Response metrics calculation failed: {e}")
            return {"confidence": 0.5, "phi_resonance": 0.5, "knowledge_used": []}

    async def _enhance_mathematical_response(
        self, response: str, utterance: NLPUtterance
    ) -> str:
        """Enhance response for mathematical queries"""
        entities = utterance.entities

        if "mathematical_concept" in entities:
            concept = entities["mathematical_concept"][0]
            return f"Regarding {concept}, let me provide a mathematically rigorous explanation: {response}"

        return f"Let me approach this with mathematical precision: {response}"

    async def _enhance_informational_response(
        self, response: str, utterance: NLPUtterance
    ) -> str:
        """Enhance response for informational queries"""
        return f"Based on my comprehensive knowledge base, here's what I can tell you: {response}"

    async def _enhance_problem_solving_response(
        self, response: str, utterance: NLPUtterance
    ) -> str:
        """Enhance response for problem-solving queries"""
        return f"Let's solve this systematically using computational intelligence: {response}"

    async def _enhance_creative_response(
        self, response: str, utterance: NLPUtterance
    ) -> str:
        """Enhance response for creative queries"""
        return (
            f"Here's a creative approach informed by computational analysis: {response}"
        )

    def _summarize_knowledge(self, entries: List[Any]) -> str:
        """Summarize knowledge base entries"""
        if not entries:
            return "No additional context available."

        concepts = [entry.concept for entry in entries[:3]]  # Limit to top 3
        return f"Related concepts: {', '.join(concepts)}"

    async def _quantum_optimize_response(
        self, response: str, utterance: NLPUtterance
    ) -> str:
        """Use quantum processing to optimize response quality"""
        try:
            # Create optimization problem
            problem_data = {
                "response": response,
                "utterance": utterance.entities,
                "phi_score": self.phi_scorer.score(utterance.entities),
            }

            problem_id, state = self.quantum_processor.create_problem(
                name="response_optimization",
                domain=ProblemDomain.OPTIMIZATION,
                data=problem_data,
            )

            # Solve for optimal response
            quantum_result = self.quantum_processor.solve(
                problem_id, algorithm="phi_resonance", iterations=30
            )

            return quantum_result.get("solution", response)

        except Exception as e:
            logger.warning(f"Quantum response optimization failed: {e}")
            return response

    def _add_conversational_elements(
        self, response: str, emotional_state: Dict[str, float]
    ) -> str:
        """Add conversational elements based on emotional state"""
        if "positive" in emotional_state and emotional_state["positive"] > 0.7:
            return f"Great question! {response}"
        elif "curious" in emotional_state and emotional_state["curious"] > 0.7:
            return f"An excellent inquiry! {response}"
        else:
            return response

    def _apply_formal_tone(self, response: str) -> str:
        """Apply formal tone to response"""
        # Simple implementation - could be enhanced with more sophisticated text processing
        return response.replace("I'm", "I am").replace("I'll", "I will")

    def _apply_casual_tone(self, response: str) -> str:
        """Apply casual tone to response"""
        # Simple implementation - could be enhanced with more sophisticated text processing
        return response.replace("I am", "I'm").replace("I will", "I'll")

    async def _update_user_preferences(self, user_id: str, utterance: NLPUtterance):
        """Update user preferences based on interaction"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {
                "interaction_count": 0,
                "preferred_domains": [],
                "tone_preference": "neutral",
                "complexity_preference": "medium",
            }

        prefs = self.user_preferences[user_id]
        prefs["interaction_count"] += 1

        # Update preferred domains based on query intent
        if utterance.intent in ["mathematical_query", "problem_solving"]:
            if "mathematics" not in prefs["preferred_domains"]:
                prefs["preferred_domains"].append("mathematics")

        # Update tone preference based on emotional state
        emotional_state = utterance.context.get("emotional_state", {})
        if "positive" in emotional_state and emotional_state["positive"] > 0.8:
            prefs["tone_preference"] = "casual"
        elif "curious" in emotional_state and emotional_state["curious"] > 0.8:
            prefs["tone_preference"] = "formal"

    async def _calculate_satisfaction_score(self, feedback: str) -> float:
        """Calculate user satisfaction score from feedback"""
        feedback_lower = feedback.lower()

        positive_words = [
            "good",
            "great",
            "excellent",
            "helpful",
            "accurate",
            "perfect",
        ]
        negative_words = [
            "bad",
            "terrible",
            "unhelpful",
            "wrong",
            "confusing",
            "frustrating",
        ]

        score = 0.5  # Base score

        for word in positive_words:
            if word in feedback_lower:
                score += 0.1

        for word in negative_words:
            if word in feedback_lower:
                score -= 0.1

        return max(0.0, min(1.0, score))

    def get_session_statistics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a conversation session"""
        if session_id not in self.active_sessions:
            return None

        session = self.active_sessions[session_id]

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "duration": (
                session.end_time or datetime.now() - session.start_time
            ).total_seconds(),
            "message_count": len(session.response_history),
            "satisfaction_score": session.satisfaction_score,
            "last_activity": session.last_activity.isoformat(),
            "state": session.state.value,
        }

    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a user across all sessions"""
        user_sessions = [
            s for s in self.active_sessions.values() if s.user_id == user_id
        ]

        if not user_sessions:
            return {
                "user_id": user_id,
                "total_sessions": 0,
                "total_duration": 0,
                "total_messages": 0,
                "average_satisfaction": 0.0,
            }

        total_duration = sum(
            (s.end_time or datetime.now() - s.start_time).total_seconds()
            for s in user_sessions
        )
        total_messages = sum(len(s.response_history) for s in user_sessions)
        avg_satisfaction = sum(s.satisfaction_score for s in user_sessions) / len(
            user_sessions
        )

        return {
            "user_id": user_id,
            "total_sessions": len(user_sessions),
            "total_duration": total_duration,
            "total_messages": total_messages,
            "average_satisfaction": avg_satisfaction,
        }
