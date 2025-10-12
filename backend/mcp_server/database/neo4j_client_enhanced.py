"""Extended Neo4j client with retry-aware helpers used by enhanced tooling."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

from neo4j.exceptions import Neo4jError

from .neo4j_client import Neo4jClient
from ..utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

_T = TypeVar("_T")
logger = logging.getLogger(__name__)


class EnhancedNeo4jClient(Neo4jClient):
    """Neo4j client that adds lightweight retry semantics for transient errors.
    
    Also includes circuit breaker protection to prevent cascading failures.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str,
        *,
        max_retries: int = 3,
        initial_backoff_seconds: float = 0.2,
        enable_circuit_breaker: bool = True,
    ) -> None:
        super().__init__(uri, user, password, database)
        self._max_retries = max(1, max_retries)
        self._initial_backoff = max(0.05, initial_backoff_seconds)
        self._enable_circuit_breaker = enable_circuit_breaker
        
        # Initialize circuit breaker if enabled
        if enable_circuit_breaker:
            breaker_config = CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=60.0,
                half_open_max_calls=3,
            )
            self._circuit_breaker = CircuitBreaker("neo4j_client", breaker_config)
        else:
            self._circuit_breaker = None

    async def execute_write_with_retry(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Execute a write query with simple exponential backoff."""

        parent_execute_write = super().execute_write
        await self._run_with_retry(lambda: parent_execute_write(query, parameters))

    async def execute_read_with_retry(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read query with simple exponential backoff."""

        parent_execute_read = super().execute_read
        return await self._run_with_retry(lambda: parent_execute_read(query, parameters))

    async def execute_write_transaction_with_retry(
        self,
        handler: Callable[..., Awaitable[_T]],
    ) -> _T:
        """Execute a transactional write with retry handling."""

        parent_execute_tx = super().execute_write_transaction
        return await self._run_with_retry(lambda: parent_execute_tx(handler))

    async def _run_with_retry(self, func: Callable[[], Awaitable[_T]]) -> _T:
        """Execute function with retry logic and optional circuit breaker."""
        # Wrap with circuit breaker if enabled
        if self._circuit_breaker is not None:
            return await self._circuit_breaker.call(self._execute_with_backoff, func)
        else:
            return await self._execute_with_backoff(func)
    
    async def _execute_with_backoff(self, func: Callable[[], Awaitable[_T]]) -> _T:
        """Execute function with exponential backoff retries."""
        delay = self._initial_backoff
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return await func()
            except Neo4jError as exc:  # pragma: no cover - depends on server behaviour
                last_error = exc
                logger.warning(
                    f"Neo4j operation failed (attempt {attempt}/{self._max_retries})",
                    extra={"error": str(exc), "attempt": attempt},
                )
                if attempt == self._max_retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        assert last_error is not None
        raise last_error
    
    def get_circuit_breaker_metrics(self) -> dict[str, Any] | None:
        """Get circuit breaker metrics if enabled.
        
        Returns:
            Circuit breaker metrics or None if disabled
        """
        if self._circuit_breaker is not None:
            return self._circuit_breaker.get_metrics()
        return None


__all__ = ["EnhancedNeo4jClient"]
