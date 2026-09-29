"""
Conversation Persistence Layer

Provides database persistence for conversations, enabling:
- Historical conversation storage
- Conversation resumption
- Analytics and insights
- Long-term learning
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from .conversational_interface import ConversationSession

logger = logging.getLogger(__name__)


class ConversationPersistence:
    """
    Handles persistence of conversations to MongoDB

    Features:
    - Automatic session saving
    - Conversation history retrieval
    - User conversation analytics
    - Efficient indexing
    """

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """
        Initialize persistence layer

        Args:
            db: MongoDB database instance (optional, will use default if not provided)
        """
        self.db = db
        self.collection_name = "agi_conversations"
        self._initialized = False

    async def initialize(self, db: AsyncIOMotorDatabase):
        """Initialize with database connection"""
        self.db = db
        await self._ensure_indexes()
        self._initialized = True
        logger.info("Conversation persistence initialized")

    async def _ensure_indexes(self):
        """Create necessary indexes for efficient queries"""
        if not self.db:
            return

        collection = self.db[self.collection_name]

        # Create indexes
        await collection.create_index([("session_id", ASCENDING)], unique=True)
        await collection.create_index([("user_id", ASCENDING)])
        await collection.create_index([("started_at", DESCENDING)])
        await collection.create_index([("state", ASCENDING)])
        await collection.create_index([("last_activity", DESCENDING)])

        logger.info("Conversation indexes created")

    async def save_session(self, session: ConversationSession) -> bool:
        """
        Save conversation session to database

        Args:
            session: Conversation session to save

        Returns:
            bool: True if saved successfully
        """
        if not self._initialized or not self.db:
            logger.warning("Persistence not initialized, skipping save")
            return False

        try:
            collection = self.db[self.collection_name]

            # Convert session to document
            document = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "started_at": session.started_at,
                "last_activity": session.last_activity,
                "state": session.state.value,
                "messages": session.messages,
                "context": session.context,
                "user_preferences": session.user_preferences,
                "satisfaction_score": session.satisfaction_score,
                "total_messages": len(session.messages),
                "updated_at": datetime.now(timezone.utc),
            }

            # Upsert (insert or update)
            await collection.update_one(
                {"session_id": session.session_id}, {"$set": document}, upsert=True
            )

            return True

        except Exception as e:
            logger.error(f"Error saving session: {e}")
            return False

    async def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load conversation session from database

        Args:
            session_id: Session ID to load

        Returns:
            Session data or None if not found
        """
        if not self._initialized or not self.db:
            return None

        try:
            collection = self.db[self.collection_name]
            document = await collection.find_one({"session_id": session_id})

            if document:
                # Remove MongoDB _id field
                document.pop("_id", None)
                return document

            return None

        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return None

    async def get_user_conversations(
        self, user_id: str, limit: int = 10, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get user's conversation history

        Args:
            user_id: User ID
            limit: Maximum number of conversations to return
            skip: Number of conversations to skip

        Returns:
            List of conversation summaries
        """
        if not self._initialized or not self.db:
            return []

        try:
            collection = self.db[self.collection_name]

            cursor = (
                collection.find({"user_id": user_id})
                .sort("last_activity", DESCENDING)
                .skip(skip)
                .limit(limit)
            )

            conversations = []
            async for doc in cursor:
                doc.pop("_id", None)
                # Return summary only
                conversations.append(
                    {
                        "session_id": doc["session_id"],
                        "started_at": doc["started_at"],
                        "last_activity": doc["last_activity"],
                        "state": doc["state"],
                        "total_messages": doc.get("total_messages", 0),
                        "satisfaction_score": doc.get("satisfaction_score", 0.0),
                    }
                )

            return conversations

        except Exception as e:
            logger.error(f"Error getting user conversations: {e}")
            return []

    async def get_conversation_analytics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get conversation analytics

        Args:
            user_id: Optional user ID to filter by

        Returns:
            Analytics data
        """
        if not self._initialized or not self.db:
            return {}

        try:
            collection = self.db[self.collection_name]

            # Build query
            query = {"user_id": user_id} if user_id else {}

            # Aggregate statistics
            total_conversations = await collection.count_documents(query)

            # Average satisfaction
            pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": None,
                        "avg_satisfaction": {"$avg": "$satisfaction_score"},
                        "avg_messages": {"$avg": "$total_messages"},
                        "total_messages": {"$sum": "$total_messages"},
                    }
                },
            ]

            result = await collection.aggregate(pipeline).to_list(1)

            if result:
                stats = result[0]
                return {
                    "total_conversations": total_conversations,
                    "average_satisfaction": stats.get("avg_satisfaction", 0.0),
                    "average_messages_per_conversation": stats.get("avg_messages", 0.0),
                    "total_messages": stats.get("total_messages", 0),
                }

            return {
                "total_conversations": total_conversations,
                "average_satisfaction": 0.0,
                "average_messages_per_conversation": 0.0,
                "total_messages": 0,
            }

        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return {}

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete conversation session

        Args:
            session_id: Session ID to delete

        Returns:
            bool: True if deleted successfully
        """
        if not self._initialized or not self.db:
            return False

        try:
            collection = self.db[self.collection_name]
            result = await collection.delete_one({"session_id": session_id})
            return result.deleted_count > 0

        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False

    async def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        Clean up old inactive sessions

        Args:
            days: Delete sessions older than this many days

        Returns:
            Number of sessions deleted
        """
        if not self._initialized or not self.db:
            return 0

        try:
            from datetime import timedelta

            collection = self.db[self.collection_name]
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            result = await collection.delete_many(
                {
                    "last_activity": {"$lt": cutoff_date},
                    "state": {"$in": ["ended", "inactive"]},
                }
            )

            deleted = result.deleted_count
            logger.info(f"Cleaned up {deleted} old sessions")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0


# Global persistence instance
_persistence: Optional[ConversationPersistence] = None


def get_persistence() -> ConversationPersistence:
    """Get global persistence instance"""
    global _persistence
    if _persistence is None:
        _persistence = ConversationPersistence()
    return _persistence


async def initialize_persistence(db: AsyncIOMotorDatabase):
    """Initialize global persistence with database"""
    persistence = get_persistence()
    await persistence.initialize(db)
