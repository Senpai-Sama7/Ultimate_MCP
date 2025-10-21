"""Neo4j client with query caching capabilities."""

from __future__ import annotations

import logging
from typing import Any

from .neo4j_client import Neo4jClient
from ..utils.cache import QueryCache, get_cache

logger = logging.getLogger(__name__)


class CachedNeo4jClient(Neo4jClient):
    """Neo4j client with intelligent query caching."""
    
    def __init__(self, *args, cache: QueryCache | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = cache or get_cache()
        
        # Queries that should be cached (read-only, expensive operations)
        self.cacheable_patterns = {
            "MATCH", "RETURN", "WITH", "UNWIND", "CALL db.labels()", 
            "CALL db.relationshipTypes()", "CALL db.schema"
        }
        
        # Queries that invalidate cache (write operations)
        self.invalidating_patterns = {
            "CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP"
        }
    
    def _should_cache(self, query: str) -> bool:
        """Determine if query should be cached."""
        query_upper = query.upper().strip()
        
        # Don't cache write operations
        if any(pattern in query_upper for pattern in self.invalidating_patterns):
            return False
        
        # Cache read operations
        return any(pattern in query_upper for pattern in self.cacheable_patterns)
    
    def _should_invalidate(self, query: str) -> bool:
        """Determine if query should invalidate cache."""
        query_upper = query.upper().strip()
        return any(pattern in query_upper for pattern in self.invalidating_patterns)
    
    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute read query with caching."""
        # Try cache first for cacheable queries
        if self._should_cache(query):
            cached_result = await self.cache.get(query, parameters)
            if cached_result is not None:
                logger.debug("Cache hit", extra={"query_hash": hash(query)})
                return cached_result
        
        # Execute query
        result = await super().execute_read(query, parameters)
        
        # Cache the result if appropriate
        if self._should_cache(query) and result:
            # Use shorter TTL for frequently changing data
            ttl = 60 if "timestamp" in query.lower() else 300
            await self.cache.set(query, result, parameters, ttl)
            logger.debug("Cached query result", extra={"query_hash": hash(query), "ttl": ttl})
        
        return result
    
    async def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> None:
        """Execute write query and invalidate relevant cache entries."""
        # Execute the write
        await super().execute_write(query, parameters)
        
        # Invalidate cache for write operations
        if self._should_invalidate(query):
            # Extract table/label names for targeted invalidation
            query_upper = query.upper()
            if ":" in query:
                # Extract labels like :User, :Service, etc.
                import re
                labels = re.findall(r':(\w+)', query)
                for label in labels:
                    await self.cache.invalidate_pattern(label)
            else:
                # Broad invalidation for complex queries
                await self.cache.invalidate_pattern("")
            
            logger.debug("Invalidated cache", extra={"query_hash": hash(query)})


__all__ = ["CachedNeo4jClient"]
