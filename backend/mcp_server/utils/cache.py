"""Query caching implementation with Redis fallback to in-memory cache."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from collections import OrderedDict

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache with TTL support."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, tuple[Any, datetime]] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self.cache:
                return None
            
            value, expires_at = self.cache[key]
            if datetime.utcnow() > expires_at:
                del self.cache[key]
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            ttl = ttl or self.default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            self.cache[key] = (value, expires_at)
            self.cache.move_to_end(key)
            
            # Evict oldest if over capacity
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    async def delete(self, key: str) -> None:
        async with self._lock:
            self.cache.pop(key, None)
    
    async def clear(self) -> None:
        async with self._lock:
            self.cache.clear()


class QueryCache:
    """High-performance query cache with Redis backend and in-memory fallback."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = 300,
        max_memory_size: int = 1000,
    ):
        self.default_ttl = default_ttl
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache = LRUCache(max_memory_size, default_ttl)
        
        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=True,
                )
                logger.info("Redis cache initialized", extra={"url": redis_url})
            except Exception as e:
                logger.warning("Redis connection failed, using memory cache", extra={"error": str(e)})
        else:
            logger.info("Using in-memory cache (Redis not available)")
    
    def _make_key(self, query: str, parameters: dict[str, Any] | None = None) -> str:
        """Create cache key from query and parameters."""
        params_str = json.dumps(parameters or {}, sort_keys=True, separators=(',', ':'))
        content = f"{query}:{params_str}"
        return f"query:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
    
    async def get(self, query: str, parameters: dict[str, Any] | None = None) -> Optional[list[dict[str, Any]]]:
        """Get cached query result."""
        key = self._make_key(query, parameters)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached = await self.redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Redis get failed", extra={"key": key, "error": str(e)})
        
        # Fallback to memory cache
        return await self.memory_cache.get(key)
    
    async def set(
        self,
        query: str,
        result: list[dict[str, Any]],
        parameters: dict[str, Any] | None = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Cache query result."""
        key = self._make_key(query, parameters)
        ttl = ttl or self.default_ttl
        
        # Try Redis first
        if self.redis_client:
            try:
                await self.redis_client.setex(key, ttl, json.dumps(result, separators=(',', ':')))
                return
            except Exception as e:
                logger.warning("Redis set failed", extra={"key": key, "error": str(e)})
        
        # Fallback to memory cache
        await self.memory_cache.set(key, result, ttl)
    
    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(f"query:*{pattern}*")
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info("Invalidated Redis cache entries", extra={"pattern": pattern, "count": len(keys)})
            except Exception as e:
                logger.warning("Redis invalidation failed", extra={"pattern": pattern, "error": str(e)})
        
        # Memory cache doesn't support pattern matching, clear all
        await self.memory_cache.clear()
    
    async def close(self) -> None:
        """Close cache connections."""
        if self.redis_client:
            await self.redis_client.close()


# Global cache instance
_cache_instance: Optional[QueryCache] = None


def get_cache() -> QueryCache:
    """Get global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = QueryCache()
    return _cache_instance


def init_cache(redis_url: Optional[str] = None, **kwargs) -> QueryCache:
    """Initialize global cache instance."""
    global _cache_instance
    _cache_instance = QueryCache(redis_url, **kwargs)
    return _cache_instance
