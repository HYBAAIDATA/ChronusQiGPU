"""
Natural Language Processing Module for Enhanced AGI

This module provides NLP capabilities to broaden the AI's scope beyond mathematical computation.
It enables natural language understanding, conversational abilities, and general knowledge processing.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Import existing HYBA components
from hyba_backend.platform.quantum_core.processor import (
    ProblemDomain,
    UniversalQuantumProcessor,
)
from hyba_backend.platform.resonance import PhiResonanceScorer

logger = logging.getLogger(__name__)


class NLPUnderstandingLevel(str, Enum):
    """Levels of NLP understanding"""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class NLPUtterance:
    """Represents a natural language utterance"""

    text: str
    intent: str
    entities: Dict[str, Any]
    confidence: float
    context: Dict[str, Any]
    timestamp: datetime


@dataclass
class ConversationContext:
    """Maintains conversation state"""

    user_id: str
    session_id: str
    history: List[NLPUtterance]
    current_topic: str
    emotional_state: Dict[str, float]
    knowledge_gaps: List[str]
    last_interaction: datetime


class EnhancedNLPProcessor:
    """
    Advanced NLP processor that integrates with HYBA's mathematical capabilities

    Features:
    - Intent recognition and classification
    - Entity extraction and resolution
    - Context-aware understanding
    - Emotional state detection
    - Knowledge base integration
    - Multimodal input processing
    """

    def __init__(self):
        self.phi_scorer = PhiResonanceScorer()
        self.quantum_processor = UniversalQuantumProcessor(max_dimension=2**16)

        # Initialize language models and patterns
        self.intent_patterns = self._initialize_intent_patterns()
        self.entity_patterns = self._initialize_entity_patterns()
        self.emotional_patterns = self._initialize_emotional_patterns()

        # Knowledge base integration
        self.knowledge_base = {}
        self.conversation_memory = {}

        logger.info("Enhanced NLP Processor initialized with quantum integration")

    async def process_utterance(
        self,
        text: str,
        user_id: str = "default",
        context: Optional[Dict[str, Any]] = None,
    ) -> NLPUtterance:
        """
        Process a natural language utterance with full context understanding

        Args:
            text: Input text to process
            user_id: User identifier for personalization
            context: Additional context information
        """
        start_time = datetime.now()

        try:
            # Preprocess text
            cleaned_text = self._clean_text(text)

            # Extract intent
            intent, intent_confidence = await self._classify_intent(cleaned_text)

            # Extract entities
            entities = await self._extract_entities(cleaned_text)

            # Analyze emotional state
            emotional_state = await self._analyze_emotion(cleaned_text)

            # Context integration
            session_context = self._get_or_create_context(user_id, context)
            session_context.last_interaction = start_time

            # Knowledge base lookup and enhancement
            enhanced_entities = await self._enhance_with_knowledge(entities, intent)
            # Calculate overall confidence
            # Extract max emotion value if emotional_state is a dict
            max_emotion = (
                max(emotional_state.values())
                if isinstance(emotional_state, dict) and emotional_state
                else 0.0
            )

            confidence = self._calculate_confidence(intent_confidence, len(entities), max_emotion)
            # Create utterance
            utterance = NLPUtterance(
                text=text,
                intent=intent,
                entities=enhanced_entities,
                confidence=confidence,
                context=session_context.__dict__,
                timestamp=start_time,
            )

            # Store in conversation history
            session_context.history.append(utterance)

            # Update knowledge gaps
            await self._update_knowledge_gaps(utterance, session_context)

            logger.info(f"Processed utterance: {intent} with confidence {confidence:.2f}")
            return utterance

        except Exception as e:
            logger.error(f"NLP processing failed: {e}")
            return NLPUtterance(
                text=text,
                intent="error",
                entities={},
                confidence=0.0,
                context=context or {},
                timestamp=start_time,
            )

    async def generate_response(self, utterance: NLPUtterance, user_id: str = "default") -> str:
        """
        Generate a natural language response based on the processed utterance

        Args:
            utterance: Processed utterance with intent and entities
            user_id: User identifier for personalized responses
        """
        try:
            session_context = self._get_or_create_context(user_id)

            # Determine response strategy based on intent
            if utterance.intent == "mathematical_query":
                response = await self._generate_mathematical_response(utterance)
            elif utterance.intent == "general_knowledge":
                response = await self._generate_knowledge_response(utterance)
            elif utterance.intent == "conversational":
                response = await self._generate_conversational_response(utterance, session_context)
            elif utterance.intent == "problem_solving":
                response = await self._generate_problem_solving_response(utterance)
            else:
                response = await self._generate_default_response(utterance)

            # Enhance response with emotional awareness
            enhanced_response = self._enhance_response_with_emotion(
                response, session_context.emotional_state
            )

            # Apply quantum optimization for response quality
            if len(response) > 100:
                optimized_response = await self._quantum_optimize_response(
                    enhanced_response, utterance
                )
                return optimized_response

            return enhanced_response

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return "I apologize, but I'm having difficulty generating a response at the moment."

    def _initialize_intent_patterns(self) -> Dict[str, List[str]]:
        """Initialize intent classification patterns"""
        return {
            "mathematical_query": [
                r"(solve|calculate|compute|find|determine).*",
                r"(equation|formula|function|derivative|integral).*",
                r"(optimization|probability|statistics|analysis).*",
                r"(quantum|mathematical|numerical).*",
            ],
            "general_knowledge": [
                r"(what|who|when|where|why|how).*",
                r"(explain|describe|define|tell me about).*",
                r"(history|science|technology|culture).*",
            ],
            "problem_solving": [
                r"(help|assist|solve|fix|resolve).*",
                r"(strategy|approach|method|solution).*",
                r"(decision|choice|recommendation).*",
            ],
            "conversational": [
                r"(hello|hi|hey|greetings).*",
                r"(how are you|how do you do|what's up).*",
                r"(chat|talk|discuss|converse).*",
            ],
            "creative": [
                r"(write|create|generate|compose|design).*",
                r"(story|poem|code|idea|concept).*",
                r"(imagine|innovate|invent|brainstorm).*",
            ],
        }

    def _initialize_entity_patterns(self) -> Dict[str, str]:
        """Initialize entity extraction patterns"""
        return {
            "mathematical_concept": r"\b(algebra|calculus|geometry|trigonometry|statistics|probability|linear algebra|differential equations)\b",
            "number": r"\b\d+(\.\d+)?\b",
            "variable": r"\b[a-zA-Z][a-zA-Z0-9_]*\b",
            "date": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            "location": r"\b[A-Z][a-zA-Z\s]+(?:, [A-Z]{2})?\b",
            "organization": r"\b[A-Z][a-zA-Z\s]+(?:[A-Z][a-zA-Z\s]+)*\b",
        }

    def _initialize_emotional_patterns(self) -> Dict[str, List[str]]:
        """Initialize emotional state detection patterns"""
        return {
            "positive": [
                r"\b(happy|excited|great|wonderful|amazing|excellent)\b",
                r"\b(thank|appreciate|love)\b",
            ],
            "negative": [
                r"\b(angry|frustrated|upset|sad|disappointed|terrible)\b",
                r"\b(hate|dislike|annoyed)\b",
            ],
            "neutral": [r"\b(okay|fine|alright|normal|standard)\b"],
            "curious": [
                r"\b(wonder|curious|interested|fascinated|intrigued)\b",
                r"\b(why|how|what|when|where)\b",
            ],
            "urgent": [
                r"\b(immediately|urgent|quick|fast|now|asap)\b",
                r"\b(emergency|crisis|problem)\b",
            ],
        }

    async def _classify_intent(self, text: str) -> Tuple[str, float]:
        """Classify the intent of the text"""
        text_lower = text.lower()
        scores = {}

        for intent, patterns in self.intent_patterns.items():
            score = 0.0
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                score += len(matches) * 0.1

            scores[intent] = min(score, 1.0)

        # Select intent with highest score
        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent]

        return best_intent, confidence

    async def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text"""
        entities = {}

        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                entities[entity_type] = list(set(matches))  # Remove duplicates

        return entities

    async def _analyze_emotion(self, text: str) -> Dict[str, float]:
        """Analyze emotional state from text"""
        text_lower = text.lower()
        emotions = {}

        for emotion, patterns in self.emotional_patterns.items():
            score = 0.0
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                score += len(matches) * 0.2

            emotions[emotion] = min(score, 1.0)

        return emotions

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text.strip())

        # Remove special characters but keep punctuation
        text = re.sub(r"[^\w\s\.\,\!\?\:\
        \-\(\)]", "", text)

        return text

    def _get_or_create_context(
        self, user_id: str, context: Optional[Dict[str, Any]] = None
    ) -> ConversationContext:
        """Get or create conversation context for user"""
        if user_id not in self.conversation_memory:
            self.conversation_memory[user_id] = ConversationContext(
                user_id=user_id,
                session_id=f"session_{datetime.now().timestamp()}",
                history=[],
                current_topic="general",
                emotional_state={},
                knowledge_gaps=[],
                last_interaction=datetime.now(),
            )

        return self.conversation_memory[user_id]

    async def _enhance_with_knowledge(
        self, entities: Dict[str, List[str]], intent: str
    ) -> Dict[str, Any]:
        """Enhance entities with knowledge base information"""
        enhanced_entities = entities.copy()

        # Add knowledge base lookups for mathematical concepts
        if "mathematical_concept" in entities:
            for concept in entities["mathematical_concept"]:
                if concept in self.knowledge_base:
                    enhanced_entities[f"{concept}_details"] = self.knowledge_base[concept]

        # Add contextual information
        enhanced_entities["intent_context"] = {
            "primary_intent": intent,
            "timestamp": datetime.now().isoformat(),
            "phi_resonance": self.phi_scorer.score(entities),
        }

        return enhanced_entities

    def _calculate_confidence(
        self,
        intent_confidence: float,
        entity_count: int,
        emotional_state: Dict[str, float],
    ) -> float:
        """Calculate overall confidence score"""
        entity_confidence = min(entity_count * 0.1, 0.5)
        emotion_confidence = max(emotional_state.values()) * 0.3

        total_confidence = intent_confidence + entity_confidence + emotion_confidence
        return min(total_confidence, 1.0)

    async def _update_knowledge_gaps(self, utterance: NLPUtterance, context: ConversationContext):
        """Update knowledge gaps based on conversation"""
        # Simple implementation - identify unknown entities
        for entity_type, entities in utterance.entities.items():
            for entity in entities:
                if entity not in self.knowledge_base:
                    if entity not in context.knowledge_gaps:
                        context.knowledge_gaps.append(entity)

    async def _generate_mathematical_response(self, utterance: NLPUtterance) -> str:
        """Generate response for mathematical queries"""
        entities = utterance.entities

        if "mathematical_concept" in entities:
            concept = entities["mathematical_concept"][0]
            return f"I can help you with {concept}. This involves mathematical analysis and computation. Would you like me to solve a specific problem or explain the concept?"

        return "I can assist with mathematical computations and analysis. Please provide the specific problem or concept you'd like help with."

    async def _generate_knowledge_response(self, utterance: NLPUtterance) -> str:
        """Generate response for general knowledge queries"""
        entities = utterance.entities

        if "number" in entities:
            number = entities["number"][0]
            return f"The number {number} is an interesting value. In mathematical terms, this could represent various concepts depending on the context."

        return "I can provide information on a wide range of topics. Please specify what you'd like to know more about."

    async def _generate_conversational_response(
        self, utterance: NLPUtterance, context: ConversationContext
    ) -> str:
        """Generate conversational response"""
        emotional_state = context.emotional_state

        if "positive" in emotional_state and emotional_state["positive"] > 0.5:
            return "I'm glad to hear that! How can I assist you today?"
        elif "negative" in emotional_state and emotional_state["negative"] > 0.5:
            return "I understand you might be frustrated. Let me help you with whatever you need."
        else:
            return "Hello! How can I help you today?"

    async def _generate_problem_solving_response(self, utterance: NLPUtterance) -> str:
        """Generate problem-solving response"""
        return "I can help you solve problems using mathematical analysis, optimization techniques, and logical reasoning. Please describe the problem you're facing."

    async def _generate_default_response(self, utterance: NLPUtterance) -> str:
        """Generate default response"""
        return f"I understand you're asking about {utterance.intent}. Let me process this for you with my computational intelligence capabilities."

    def _enhance_response_with_emotion(
        self, response: str, emotional_state: Dict[str, float]
    ) -> str:
        """Enhance response based on detected emotional state"""
        if "positive" in emotional_state and emotional_state["positive"] > 0.7:
            return f"Great question! {response}"
        elif "curious" in emotional_state and emotional_state["curious"] > 0.7:
            return f"An excellent inquiry! {response}"
        elif "urgent" in emotional_state and emotional_state["urgent"] > 0.7:
            return f"Let me address this quickly: {response}"
        else:
            return response

    async def _quantum_optimize_response(self, response: str, utterance: NLPUtterance) -> str:
        """Use quantum processing to optimize response quality"""
        try:
            # Create optimization problem for response quality
            problem_id, state = self.quantum_processor.create_problem(
                name="response_optimization",
                domain=ProblemDomain.OPTIMIZATION,
                data={
                    "response": response,
                    "utterance_context": utterance.entities,
                    "phi_resonance_score": self.phi_scorer.score(utterance.entities),
                },
            )

            # Solve for optimal response
            quantum_result = self.quantum_processor.solve(
                problem_id, algorithm="phi_resonance", iterations=20
            )

            optimized_response = quantum_result.get("solution", response)
            return optimized_response

        except Exception as e:
            logger.warning(f"Quantum response optimization failed: {e}")
            return response

    async def add_to_knowledge_base(self, concept: str, information: Dict[str, Any]):
        """Add new information to the knowledge base"""
        self.knowledge_base[concept] = information
        logger.info(f"Added {concept} to knowledge base")

    def get_understanding_level(self, user_id: str) -> NLPUnderstandingLevel:
        """Get the current understanding level for a user"""
        if user_id not in self.conversation_memory:
            return NLPUnderstandingLevel.BASIC

        context = self.conversation_memory[user_id]
        history_length = len(context.history)

        if history_length < 5:
            return NLPUnderstandingLevel.BASIC
        elif history_length < 20:
            return NLPUnderstandingLevel.INTERMEDIATE
        elif history_length < 50:
            return NLPUnderstandingLevel.ADVANCED
        else:
            return NLPUnderstandingLevel.EXPERT
