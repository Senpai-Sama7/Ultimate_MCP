"""Caching utilities with in-memory and Redis-backed implementations."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, TypeVar

try:
    import redis.asyncio as redis  # type: ignore[import-untyped]

    REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    redis = None
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

R = TypeVar("R")


@dataclass
class CacheEntry(Generic[R]):
    """Cache entry containing value, expiry, and hit count."""

    value: R
    expires_at: float
    hits: int = 0

    def is_expired(self, now: float | None = None) -> bool:
        return (now or time.monotonic()) >= self.expires_at


@dataclass
class CacheMetrics:
    """Aggregate cache metrics for observability."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class InMemoryCache:
    """Async-safe LRU cache with TTL and metrics."""

    def __init__(self, max_size: int = 1024, default_ttl: float = 300.0) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        if default_ttl <= 0:
            raise ValueError("default_ttl must be positive")

        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: OrderedDict[str, CacheEntry[Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        self.metrics = CacheMetrics()

    async def get(self, key: str) -> Any | None:
        now = time.monotonic()
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.metrics.misses += 1
                return None
            if entry.is_expired(now):
                self._store.pop(key, None)
                self.metrics.misses += 1
                return None

            self.metrics.hits += 1
            entry.hits += 1
            self._store.move_to_end(key)
            return entry.value

    async def set(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        expires_at = time.monotonic() + (ttl or self.default_ttl)
        async with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=expires_at)
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)
                self.metrics.evictions += 1

    async def delete(self, key: str) -> bool:
        async with self._lock:
            existed = key in self._store
            self._store.pop(key, None)
            return existed

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    async def cleanup_expired(self) -> int:
        now = time.monotonic()
        removed = 0
        async with self._lock:
            stale_keys = [key for key, entry in self._store.items() if entry.is_expired(now)]
            for key in stale_keys:
                self._store.pop(key, None)
            removed = len(stale_keys)
        if removed:
            logger.debug("Cache cleanup removed entries", extra={"count": removed})
        return removed

    def get_stats(self) -> dict[str, Any]:
        size = len(self._store)
        return {
            "size": size,
            "max_size": self.max_size,
            "utilization": size / self.max_size,
            "metrics": {
                "hits": self.metrics.hits,
                "misses": self.metrics.misses,
                "evictions": self.metrics.evictions,
                "hit_rate": self.metrics.hit_rate,
            },
        }

    def _generate_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        serialized = json.dumps(
            {"args": args, "kwargs": kwargs},
            default=repr,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"

    def cached(self, *, ttl: float | None = None) -> Callable[[Callable[..., R]], Callable[..., Awaitable[R]]]:
        def decorator(func: Callable[..., R]) -> Callable[..., Awaitable[R]]:
            is_coroutine = asyncio.iscoroutinefunction(func)
            prefix = func.__qualname__

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> R:
                key = self._generate_key(prefix, *args, **kwargs)
                cached_result = await self.get(key)
                if cached_result is not None:
                    return cached_result  # type: ignore[return-value]

                if is_coroutine:
                    result = await func(*args, **kwargs)  # type: ignore[misc]
                else:
                    result = await asyncio.to_thread(func, *args, **kwargs)

                await self.set(key, result, ttl=ttl)
                return result

            return wrapper

        return decorator


class CacheWarmer:
    """Background task that periodically cleans expired cache entries."""

    def __init__(self, cache: InMemoryCache, cleanup_interval: float = 30.0) -> None:
        if cleanup_interval <= 0:
            raise ValueError("cleanup_interval must be positive")
        self.cache = cache
        self.cleanup_interval = cleanup_interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="cache-warmer")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    async def _run(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(self.cleanup_interval)
                await self.cache.cleanup_expired()
        except asyncio.CancelledError:  # pragma: no cover - cooperative cancellation
            pass
        finally:
            self._running = False


class QueryCache:
    """High-performance query cache with Redis backend and in-memory fallback."""

    def __init__(
        self,
        redis_url: str | None = None,
        *,
        default_ttl: float = 300.0,
        max_memory_size: int = 1024,
    ) -> None:
        self.default_ttl = default_ttl
        self.memory_cache = InMemoryCache(max_size=max_memory_size, default_ttl=default_ttl)
        self.redis_client: "redis.Redis[str] | None" = None

        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=2.0,
                    retry_on_timeout=True,
                )
                logger.info("Redis cache initialised", extra={"url": redis_url})
            except Exception as error:  # pragma: no cover - best effort
                logger.warning("Redis initialisation failed; falling back to memory cache", extra={"error": str(error)})
                self.redis_client = None
        elif redis_url:
            logger.warning("redis.asyncio not installed; using in-memory cache", extra={"url": redis_url})

    @staticmethod
    def _make_key(query: str, parameters: dict[str, Any] | None = None) -> str:
        payload = json.dumps(parameters or {}, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{query}:{payload}".encode("utf-8")).hexdigest()
        return f"query:{digest}"

    async def get(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]] | None:
        key = self._make_key(query, parameters)
        if self.redis_client:
            try:
                cached = await self.redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except Exception as error:
                logger.warning("Redis get failed; falling back to memory cache", extra={"error": str(error), "key": key})

        return await self.memory_cache.get(key)

    async def set(
        self,
        query: str,
        result: list[dict[str, Any]],
        *,
        parameters: dict[str, Any] | None = None,
        ttl: float | None = None,
    ) -> None:
        key = self._make_key(query, parameters)
        ttl = ttl or self.default_ttl

        if self.redis_client:
            try:
                await self.redis_client.setex(key, ttl, json.dumps(result, separators=(",", ":")))
                return
            except Exception as error:
                logger.warning("Redis set failed; storing in memory cache", extra={"error": str(error), "key": key})

        await self.memory_cache.set(key, result, ttl=ttl)

    async def invalidate_pattern(self, pattern: str) -> None:
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(f"query:*{pattern}*")
                if keys:
                    await self.redis_client.delete(*keys)
            except Exception as error:
                logger.warning("Redis invalidate failed", extra={"error": str(error), "pattern": pattern})

        await self.memory_cache.clear()

    async def close(self) -> None:
        if self.redis_client:
            await self.redis_client.close()


_cache_instance: QueryCache | None = None


def get_cache() -> QueryCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = QueryCache()
    return _cache_instance


def init_cache(redis_url: str | None = None, **kwargs: Any) -> QueryCache:
    global _cache_instance
    _cache_instance = QueryCache(redis_url, **kwargs)
    return _cache_instance
