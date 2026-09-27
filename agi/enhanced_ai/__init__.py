"""
Enhanced AI Module for True AGI

This module integrates all enhanced AI capabilities to create a comprehensive
Artificial General Intelligence system that goes beyond mathematical computation
to include natural language understanding, general knowledge, and conversational abilities.

Key Features:
- Natural Language Processing with emotional intelligence
- Comprehensive knowledge base with multi-domain coverage
- Advanced conversational interface with context awareness
- Integration with HYBA's quantum computational intelligence
- Self-improving and adaptive learning capabilities
- Quantum-enhanced optimization and problem solving
"""

from .conversational_interface import (
    ConversationResponse,
    ConversationSession,
    ConversationState,
    EnhancedConversationalInterface,
    ResponseType,
)
from .knowledge_base import (
    EnhancedKnowledgeBase,
    KnowledgeDomain,
    KnowledgeEntry,
    KnowledgeQuery,
)
from .nlp_processor import (
    ConversationContext,
    EnhancedNLPProcessor,
    NLPUnderstandingLevel,
    NLPUtterance,
)
from .test_enhanced_agi import EnhancedAGITester

__version__ = "1.0.0"
__author__ = "HYBA Enhanced AI Team"
__description__ = (
    "Comprehensive AGI system with NLP, knowledge integration, and quantum computation"
)

# Export main classes for easy import
__all__ = [
    "ConversationContext",
    "ConversationResponse",
    "ConversationSession",
    "ConversationState",
    # Testing and Validation
    "EnhancedAGITester",
    # Conversational Interface Components
    "EnhancedConversationalInterface",
    # Knowledge Base Components
    "EnhancedKnowledgeBase",
    # NLP Components
    "EnhancedNLPProcessor",
    "KnowledgeDomain",
    "KnowledgeEntry",
    "KnowledgeQuery",
    "NLPUnderstandingLevel",
    "NLPUtterance",
    "ResponseType",
]


def create_enhanced_agi_system() -> EnhancedConversationalInterface:
    """
    Create and initialize a complete enhanced AGI system

    Returns:
        EnhancedConversationalInterface: Fully integrated AGI system
    """
    from .conversational_interface import EnhancedConversationalInterface

    # Initialize the enhanced conversational interface
    # This automatically initializes all dependent components
    agi_system = EnhancedConversationalInterface()

    return agi_system


def demonstrate_agi_capabilities():
    """
    Demonstrate the enhanced AGI capabilities with sample interactions
    """
    import asyncio

    async def run_demo():
        # Create AGI system
        agi = create_enhanced_agi_system()

        print("🚀 Enhanced AGI System Demo")
        print("=" * 50)

        # Start conversation
        session = await agi.start_conversation(
            "demo_user",
            "Hello! I'm interested in learning about quantum computing and its applications.",
        )

        print(f"✅ Conversation started: {session.session_id}")

        # Process various types of queries
        demo_queries = [
            "Can you explain what quantum computing is?",
            "How does quantum computing differ from classical computing?",
            "What are some real-world applications of quantum algorithms?",
            "Can you solve this optimization problem: maximize f(x) = -x² + 4x + 5?",
            "What's the relationship between quantum computing and artificial intelligence?",
        ]

        for i, query in enumerate(demo_queries, 1):
            print(f"\n📝 Query {i}: {query}")

            response = await agi.process_user_message(session.session_id, query)

            print(f"🤖 Response: {response.response_text}")
            print(f"📊 Confidence: {response.confidence:.2f}")
            print(f"🎯 Type: {response.response_type.value}")
            print(f"⚛️  Phi Resonance: {response.phi_resonance_score:.2f}")

        # End conversation
        await agi.end_conversation(
            session.session_id, "Excellent explanations, thank you!"
        )

        print("\n✅ Demo completed successfully!")
        print("📈 Overall system confidence demonstrated")

    # Run the demo
    asyncio.run(run_demo())


if __name__ == "__main__":
    demonstrate_agi_capabilities()
