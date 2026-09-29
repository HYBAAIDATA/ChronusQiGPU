"""
Intelligent Caching Layer for Enhanced AGI

Provides multi-level caching for:
- Knowledge base queries
- NLP processing results
- Quantum computation results
- Conversation context
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class InMemoryCache:
    """
    High-performance in-memory cache with TTL support

    Features:
    - LRU eviction
    - TTL expiration
    - Size limits
    - Hit/miss tracking
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        Initialize cache

        Args:
            max_size: Maximum number of items to cache
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: dict[str, dict[str, Any]] = {}
        self.access_times: dict[str, datetime] = {}

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = (
            f"{prefix}:{json.dumps(args, sort_keys=True)}:{json.dumps(kwargs, sort_keys=True)}"
        )
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # Check expiration
        if entry["expires_at"] < datetime.now(timezone.utc):
            del self.cache[key]
            del self.access_times[key]
            self.misses += 1
            return None

        # Update access time
        self.access_times[key] = datetime.now(timezone.utc)
        self.hits += 1

        return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        # Evict if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict_lru()

        ttl = ttl or self.default_ttl
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        self.cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }
        self.access_times[key] = datetime.now(timezone.utc)

    def _evict_lru(self):
        """Evict least recently used item"""
        if not self.access_times:
            return

        lru_key = min(self.access_times.items(), key=lambda x: x[1])[0]
        del self.cache[lru_key]
        del self.access_times[lru_key]
        self.evictions += 1

    def delete(self, key: str):
        """Delete key from cache"""
        self.cache.pop(key, None)
        self.access_times.pop(key, None)

    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        self.access_times.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }


class AGICacheManager:
    """
    Centralized cache manager for AGI system

    Manages multiple cache layers:
    - Knowledge base cache
    - NLP processing cache
    - Quantum computation cache
    - Response cache
    """

    def __init__(self):
        """Initialize cache manager"""
        self.knowledge_cache = InMemoryCache(max_size=500, default_ttl=7200)  # 2 hours
        self.nlp_cache = InMemoryCache(max_size=1000, default_ttl=3600)  # 1 hour
        self.quantum_cache = InMemoryCache(max_size=200, default_ttl=1800)  # 30 min
        self.response_cache = InMemoryCache(max_size=500, default_ttl=1800)  # 30 min

        logger.info("AGI cache manager initialized")

    def cache_knowledge_query(self, query: str, domain: Optional[str] = None):
        """Decorator to cache knowledge queries"""

        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.knowledge_cache._generate_key("knowledge", query, domain)

                # Check cache
                cached = self.knowledge_cache.get(cache_key)
                if cached is not None:
                    logger.debug(f"Knowledge cache hit: {query[:50]}")
                    return cached

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                self.knowledge_cache.set(cache_key, result)
                logger.debug(f"Knowledge cached: {query[:50]}")

                return result

            return wrapper

        return decorator

    def cache_nlp_processing(self, text: str):
        """Decorator to cache NLP processing"""

        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.nlp_cache._generate_key("nlp", text)

                # Check cache
                cached = self.nlp_cache.get(cache_key)
                if cached is not None:
                    logger.debug(f"NLP cache hit: {text[:50]}")
                    return cached

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                self.nlp_cache.set(cache_key, result)
                logger.debug(f"NLP cached: {text[:50]}")

                return result

            return wrapper

        return decorator

    def cache_quantum_computation(self, problem_type: str, data: Any):
        """Decorator to cache quantum computations"""

        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.quantum_cache._generate_key(
                    "quantum", problem_type, str(data)[:100]
                )

                # Check cache
                cached = self.quantum_cache.get(cache_key)
                if cached is not None:
                    logger.debug(f"Quantum cache hit: {problem_type}")
                    return cached

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                self.quantum_cache.set(cache_key, result)
                logger.debug(f"Quantum cached: {problem_type}")

                return result

            return wrapper

        return decorator

    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all caches"""
        return {
            "knowledge_cache": self.knowledge_cache.get_stats(),
            "nlp_cache": self.nlp_cache.get_stats(),
            "quantum_cache": self.quantum_cache.get_stats(),
            "response_cache": self.response_cache.get_stats(),
        }

    def clear_all(self):
        """Clear all caches"""
        self.knowledge_cache.clear()
        self.nlp_cache.clear()
        self.quantum_cache.clear()
        self.response_cache.clear()
        logger.info("All caches cleared")


# Global cache manager
_cache_manager: Optional[AGICacheManager] = None


def get_cache_manager() -> AGICacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = AGICacheManager()
    return _cache_manager
