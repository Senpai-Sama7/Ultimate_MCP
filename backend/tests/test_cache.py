"""Tests for caching layer."""

from __future__ import annotations

import asyncio

import pytest
from mcp_server.utils.cache import CacheWarmer, InMemoryCache


@pytest.fixture
def cache():
    """Create cache instance for testing."""
    return InMemoryCache(max_size=5, default_ttl=1.0)


@pytest.mark.asyncio
async def test_cache_set_and_get(cache):
    """Test basic set and get operations."""
    await cache.set("key1", "value1")
    result = await cache.get("key1")
    assert result == "value1"


@pytest.mark.asyncio
async def test_cache_get_missing(cache):
    """Test getting non-existent key."""
    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_cache_get_expired(cache):
    """Test getting expired entry."""
    await cache.set("key1", "value1", ttl=0.1)
    await asyncio.sleep(0.2)
    result = await cache.get("key1")
    assert result is None


@pytest.mark.asyncio
async def test_cache_ttl_custom(cache):
    """Test custom TTL."""
    await cache.set("key1", "value1", ttl=0.5)
    
    # Should still exist
    result = await cache.get("key1")
    assert result == "value1"
    
    # Should expire
    await asyncio.sleep(0.6)
    result = await cache.get("key1")
    assert result is None


@pytest.mark.asyncio
async def test_cache_lru_eviction(cache):
    """Test LRU eviction when max size reached."""
    # Fill cache to max
    for i in range(5):
        await cache.set(f"key{i}", f"value{i}")
    
    # Access key0 to make it recently used
    await cache.get("key0")
    
    # Add new key - should evict key1 (least recently used)
    await cache.set("key5", "value5")
    
    assert await cache.get("key0") == "value0"  # Still there (accessed recently)
    assert await cache.get("key1") is None  # Evicted (least recently used)
    assert await cache.get("key5") == "value5"  # New entry


@pytest.mark.asyncio
async def test_cache_update_existing(cache):
    """Test updating existing entry."""
    await cache.set("key1", "value1")
    await cache.set("key1", "value2")
    result = await cache.get("key1")
    assert result == "value2"


@pytest.mark.asyncio
async def test_cache_delete(cache):
    """Test deleting entry."""
    await cache.set("key1", "value1")
    deleted = await cache.delete("key1")
    assert deleted is True
    
    result = await cache.get("key1")
    assert result is None


@pytest.mark.asyncio
async def test_cache_delete_missing(cache):
    """Test deleting non-existent entry."""
    deleted = await cache.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_cache_clear(cache):
    """Test clearing all entries."""
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    
    await cache.clear()
    
    assert await cache.get("key1") is None
    assert await cache.get("key2") is None


@pytest.mark.asyncio
async def test_cache_cleanup_expired(cache):
    """Test cleanup of expired entries."""
    # Add entries with short TTL
    await cache.set("key1", "value1", ttl=0.1)
    await cache.set("key2", "value2", ttl=0.1)
    await cache.set("key3", "value3", ttl=10.0)  # Won't expire
    
    await asyncio.sleep(0.2)
    
    removed = await cache.cleanup_expired()
    
    assert removed == 2
    assert await cache.get("key1") is None
    assert await cache.get("key2") is None
    assert await cache.get("key3") == "value3"


@pytest.mark.asyncio
async def test_cache_metrics_hits_and_misses(cache):
    """Test metrics collection for hits and misses."""
    await cache.set("key1", "value1")
    
    # Hit
    await cache.get("key1")
    assert cache.metrics.hits == 1
    assert cache.metrics.misses == 0
    
    # Miss
    await cache.get("nonexistent")
    assert cache.metrics.hits == 1
    assert cache.metrics.misses == 1
    
    # Hit rate
    assert cache.metrics.hit_rate == 0.5


@pytest.mark.asyncio
async def test_cache_metrics_evictions(cache):
    """Test metrics collection for evictions."""
    # Fill to capacity and add one more
    for i in range(6):
        await cache.set(f"key{i}", f"value{i}")
    
    # Should have evicted one
    assert cache.metrics.evictions >= 1


@pytest.mark.asyncio
async def test_cache_stats(cache):
    """Test cache statistics."""
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    
    stats = cache.get_stats()
    
    assert stats["size"] == 2
    assert stats["max_size"] == 5
    assert stats["utilization"] == 0.4
    assert "metrics" in stats


@pytest.mark.asyncio
async def test_cache_decorator_basic(cache):
    """Test cache decorator basic functionality."""
    call_count = 0
    
    @cache.cached(ttl=1.0)
    async def expensive_function(x: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return x * 2
    
    # First call - cache miss
    result1 = await expensive_function(5)
    assert result1 == 10
    assert call_count == 1
    
    # Second call - cache hit
    result2 = await expensive_function(5)
    assert result2 == 10
    assert call_count == 1  # Not called again
    
    # Different argument - cache miss
    result3 = await expensive_function(10)
    assert result3 == 20
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_decorator_expiration(cache):
    """Test cache decorator with TTL expiration."""
    call_count = 0
    
    @cache.cached(ttl=0.1)
    async def func() -> str:
        nonlocal call_count
        call_count += 1
        return "result"
    
    # First call
    await func()
    assert call_count == 1
    
    # Second call before expiration
    await func()
    assert call_count == 1
    
    # Wait for expiration
    await asyncio.sleep(0.2)
    
    # Third call after expiration
    await func()
    assert call_count == 2


@pytest.mark.asyncio
async def test_cache_decorator_sync_function(cache):
    """Test cache decorator with synchronous function."""
    call_count = 0
    
    @cache.cached(ttl=1.0)
    def sync_func(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x + 1
    
    result1 = await sync_func(5)
    assert result1 == 6
    assert call_count == 1
    
    result2 = await sync_func(5)
    assert result2 == 6
    assert call_count == 1  # Cached


@pytest.mark.asyncio
async def test_cache_warmer_start_stop():
    """Test cache warmer lifecycle."""
    cache = InMemoryCache(max_size=10)
    warmer = CacheWarmer(cache, cleanup_interval=0.1)
    
    await warmer.start()
    assert warmer._running is True
    
    await asyncio.sleep(0.05)
    
    await warmer.stop()
    assert warmer._running is False


@pytest.mark.asyncio
async def test_cache_warmer_cleanup():
    """Test cache warmer performs cleanup."""
    cache = InMemoryCache(max_size=10)
    warmer = CacheWarmer(cache, cleanup_interval=0.1)
    
    # Add expired entries
    await cache.set("key1", "value1", ttl=0.05)
    await cache.set("key2", "value2", ttl=0.05)
    
    await warmer.start()
    
    # Wait for cleanup to run
    await asyncio.sleep(0.2)
    
    await warmer.stop()
    
    # Entries should be cleaned up
    assert await cache.get("key1") is None
    assert await cache.get("key2") is None


@pytest.mark.asyncio
async def test_cache_concurrent_access(cache):
    """Test cache handles concurrent access correctly."""
    async def worker(worker_id: int, iterations: int):
        for i in range(iterations):
            key = f"key{i % 3}"
            value = f"worker{worker_id}_{i}"
            await cache.set(key, value)
            result = await cache.get(key)
            # Result might be from another worker due to race
            assert result is not None
    
    # Run multiple workers concurrently
    workers = [worker(i, 10) for i in range(5)]
    await asyncio.gather(*workers)
    
    # Cache should be consistent
    stats = cache.get_stats()
    assert stats["size"] <= cache.max_size


@pytest.mark.asyncio
async def test_cache_hit_count(cache):
    """Test cache entry hit count tracking."""
    await cache.set("key1", "value1")
    
    # Access multiple times
    for _ in range(5):
        await cache.get("key1")
    
    # Hit count should be tracked (we can't directly access it,
    # but metrics should reflect the hits)
    assert cache.metrics.hits == 5


@pytest.mark.asyncio
async def test_cache_generate_key_consistency():
    """Test cache key generation is consistent."""
    cache = InMemoryCache()
    
    key1 = cache._generate_key("func", 1, 2, x=3)
    key2 = cache._generate_key("func", 1, 2, x=3)
    
    assert key1 == key2
    
    # Different args should generate different keys
    key3 = cache._generate_key("func", 1, 3, x=3)
    assert key1 != key3
