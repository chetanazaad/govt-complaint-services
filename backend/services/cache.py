"""In-memory LRU cache for LLM responses to avoid redundant API calls."""

from collections import OrderedDict
from typing import Optional, Any
import time
import logging

logger = logging.getLogger(__name__)

MAX_CACHE_SIZE = 200
TTL_SECONDS = 3600  # 1 hour


class LRUCache:
    """Thread-safe LRU cache with TTL expiration."""

    def __init__(self, max_size: int = MAX_CACHE_SIZE, ttl: int = TTL_SECONDS):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    def _normalize_key(self, key: str) -> str:
        """Normalize query to improve cache hit rate."""
        return key.strip().lower()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache, returns None if not found or expired."""
        normalized = self._normalize_key(key)

        if normalized not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[normalized]

        # Check TTL
        if time.time() - entry["timestamp"] > self._ttl:
            del self._cache[normalized]
            self._misses += 1
            logger.debug("Cache entry expired for key: %s", normalized[:50])
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(normalized)
        self._hits += 1
        logger.debug("Cache hit for key: %s", normalized[:50])
        return entry["value"]

    def set(self, key: str, value: Any) -> None:
        """Store a value in cache with current timestamp."""
        normalized = self._normalize_key(key)

        # If key exists, update it
        if normalized in self._cache:
            self._cache.move_to_end(normalized)
            self._cache[normalized] = {"value": value, "timestamp": time.time()}
            return

        # Evict oldest if at capacity
        if len(self._cache) >= self._max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug("Cache evicted key: %s", evicted_key[:50])

        self._cache[normalized] = {"value": value, "timestamp": time.time()}
        logger.debug("Cache set for key: %s", normalized[:50])

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
        }


# Singleton cache instance
cache = LRUCache()
