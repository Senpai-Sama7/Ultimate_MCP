"""Distributed caching layer for improved performance."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    created_at: float
    ttl: float
    hit_count: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.created_at > self.ttl
    
    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hit_count += 1


class CacheMetrics:
    """Cache performance metrics."""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.errors = 0
        self.total_get_time = 0.0
        self.total_set_time = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def avg_get_time(self) -> float:
        """Calculate average get operation time."""
        total_ops = self.hits + self.misses
        return self.total_get_time / total_ops if total_ops > 0 else 0.0
    
    @property
    def avg_set_time(self) -> float:
        """Calculate average set operation time."""
        return self.total_set_time / self.sets if self.sets > 0 else 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "errors": self.errors,
            "hit_rate": self.hit_rate,
            "avg_get_time_ms": self.avg_get_time * 1000,
            "avg_set_time_ms": self.avg_set_time * 1000,
        }


class InMemoryCache:
    """High-performance in-memory cache with TTL and LRU eviction.
    
    Features:
    - TTL-based expiration
    - LRU eviction when max size reached
    - Comprehensive metrics
    - Thread-safe async operations
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 3600.0,
    ):
        """Initialize cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []  # LRU tracking
        self._lock = asyncio.Lock()
        self.metrics = CacheMetrics()
    
    def _generate_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    async def get(self, key: str) -> Any | None:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        start_time = time.time()
        
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self.metrics.misses += 1
                self.metrics.total_get_time += time.time() - start_time
                return None
            
            if entry.is_expired:
                # Remove expired entry
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self.metrics.misses += 1
                self.metrics.evictions += 1
                self.metrics.total_get_time += time.time() - start_time
                return None
            
            # Update LRU order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            entry.record_hit()
            self.metrics.hits += 1
            self.metrics.total_get_time += time.time() - start_time
            
            logger.debug(
                f"Cache hit for key {key}",
                extra={"hit_count": entry.hit_count},
            )
            
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: use default_ttl)
        """
        start_time = time.time()
        
        async with self._lock:
            # Evict if at capacity
            if key not in self._cache and len(self._cache) >= self.max_size:
                await self._evict_lru()
            
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl or self.default_ttl,
            )
            
            self._cache[key] = entry
            
            # Update LRU order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            self.metrics.total_set_time += time.time() - start_time
            
            logger.debug(f"Cache set for key {key}", extra={"ttl": entry.ttl})
    
    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._access_order:
            return
        
        lru_key = self._access_order.pop(0)
        if lru_key in self._cache:
            del self._cache[lru_key]
            self.metrics.evictions += 1
            logger.debug(f"Evicted LRU key {lru_key}")
    
    async def delete(self, key: str) -> bool:
        """Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all entries from cache."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            logger.info("Cache cleared")
    
    async def cleanup_expired(self) -> int:
        """Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        # Create a snapshot of items to check for expiry without holding the lock
        # during the entire iteration.
        items_snapshot = list(self._cache.items())
        expired_keys = [
            key for key, entry in items_snapshot
            if entry.is_expired
        ]

        if not expired_keys:
            return 0

        async with self._lock:
            # Re-check for existence before deleting as entries might have been
            # removed or updated since the snapshot was taken.
            cleaned_count = 0
            for key in expired_keys:
                if key in self._cache and self._cache[key].is_expired:
                    del self._cache[key]
                    if key in self._access_order:
                        self._access_order.remove(key)
                    cleaned_count += 1
        
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired entries")
        
            return cleaned_count
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "utilization": len(self._cache) / self.max_size if self.max_size > 0 else 0,
            "metrics": self.metrics.to_dict(),
        }
    
    def cached(
        self,
        ttl: float | None = None,
        key_func: Callable[..., str] | None = None,
    ) -> Callable:
        """Decorator to cache function results.
        
        Args:
            ttl: Cache TTL (default: use default_ttl)
            key_func: Function to generate cache key from args
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Generate cache key
                if key_func is not None:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_key(func.__name__, *args, **kwargs)
                
                # Try to get from cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Store in cache
                await self.set(cache_key, result, ttl)
                
                return result
            
            return wrapper
        
        return decorator


class CacheWarmer:
    """Background task for cache warming and maintenance."""
    
    def __init__(self, cache: InMemoryCache, cleanup_interval: float = 300.0):
        """Initialize cache warmer.
        
        Args:
            cache: Cache instance to maintain
            cleanup_interval: Cleanup interval in seconds
        """
        self.cache = cache
        self.cleanup_interval = cleanup_interval
        self._task: asyncio.Task | None = None
        self._running = False
    
    async def start(self) -> None:
        """Start background maintenance task."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._maintenance_loop())
        logger.info("Cache warmer started")
    
    async def stop(self) -> None:
        """Stop background maintenance task."""
        if not self._running:
            return
        
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Cache warmer stopped")
    
    async def _maintenance_loop(self) -> None:
        """Run periodic maintenance tasks."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # Cleanup expired entries
                expired_count = await self.cache.cleanup_expired()
                
                # Log stats periodically
                stats = self.cache.get_stats()
                logger.info(
                    "Cache maintenance completed",
                    extra={
                        "expired_removed": expired_count,
                        "cache_size": stats["size"],
                        "hit_rate": stats["metrics"]["hit_rate"],
                    },
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache maintenance error: {e}")
                await asyncio.sleep(60)  # Wait before retrying


__all__ = [
    "CacheEntry",
    "CacheMetrics",
    "CacheWarmer",
    "InMemoryCache",
]
