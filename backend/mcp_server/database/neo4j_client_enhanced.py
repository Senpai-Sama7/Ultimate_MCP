"""Extended Neo4j client with retry-aware helpers used by enhanced tooling."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

from neo4j.exceptions import Neo4jError

from .neo4j_client import Neo4jClient

_T = TypeVar("_T")


class EnhancedNeo4jClient(Neo4jClient):
    """Neo4j client that adds lightweight retry semantics for transient errors."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str,
        *,
        max_retries: int = 3,
        initial_backoff_seconds: float = 0.2,
    ) -> None:
        super().__init__(uri, user, password, database)
        self._max_retries = max(1, max_retries)
        self._initial_backoff = max(0.05, initial_backoff_seconds)

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
        delay = self._initial_backoff
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return await func()
            except Neo4jError as exc:  # pragma: no cover - depends on server behaviour
                last_error = exc
                if attempt == self._max_retries:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        assert last_error is not None
        raise last_error


__all__ = ["EnhancedNeo4jClient"]
