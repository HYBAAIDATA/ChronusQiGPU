"""Commercial Context & Trajectory Cache Manager — Governed by PYTHIA.

Provides prompt caching, trajectory snapshot storage, and context compression
to dramatically reduce token cost and latency for commercial repeated workloads.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class CachedContext:
    cache_key: str
    response_payload: Any
    created_at: float
    hits: int = 0


class ContextCacheManager:
    """Enterprise prompt & context caching system powered by PYTHIA."""

    def __init__(self, *, ttl_seconds: float = 3600.0, max_entries: int = 10_000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, CachedContext] = {}
        self._stats = {"hits": 0, "misses": 0}

    def compute_key(self, prompt_text: str, context_prefix: str = "") -> str:
        """Compute cryptographic hash key for content matching."""
        hasher = hashlib.sha256()
        hasher.update(context_prefix.encode("utf-8"))
        hasher.update(prompt_text.encode("utf-8"))
        return hasher.hexdigest()

    def get(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached payload if valid and within TTL."""
        now = time.time()
        entry = self._cache.get(cache_key)
        if entry is None:
            self._stats["misses"] += 1
            return None

        if (now - entry.created_at) > self.ttl_seconds:
            del self._cache[cache_key]
            self._stats["misses"] += 1
            return None

        self._stats["hits"] += 1
        # Update hits count
        self._cache[cache_key] = CachedContext(
            cache_key=entry.cache_key,
            response_payload=entry.response_payload,
            created_at=entry.created_at,
            hits=entry.hits + 1,
        )
        return entry.response_payload

    def set(self, cache_key: str, payload: Any) -> None:
        """Store payload in cache, evicting oldest if max_entries reached."""
        if len(self._cache) >= self.max_entries:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
            del self._cache[oldest_key]

        self._cache[cache_key] = CachedContext(
            cache_key=cache_key,
            response_payload=payload,
            created_at=time.time(),
            hits=0,
        )

    def stats(self) -> Dict[str, Any]:
        """Return cache performance telemetry."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_ratio = (self._stats["hits"] / total) if total > 0 else 0.0
        return {
            "cached_entries": len(self._cache),
            "total_hits": self._stats["hits"],
            "total_misses": self._stats["misses"],
            "hit_ratio": hit_ratio,
        }
