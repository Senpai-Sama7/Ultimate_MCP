"""Async Neo4j client wrapper used by the MCP server."""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, TypeVar

from neo4j import AsyncGraphDatabase, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .models import GraphMetrics

# Conditional import for circuit breaker to avoid circular dependency
try:
    from ..utils.circuit_breaker import CircuitBreakerRegistry, CircuitBreakerConfig
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Neo4jClient:
    """Minimal facade around the Neo4j async driver."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str,
        *,
        max_connection_pool_size: int | None = None,
        connection_acquisition_timeout: float | None = None,
        max_connection_lifetime: int = 3600,
        enable_circuit_breaker: bool = True,
    ) -> None:
        """Initialize Neo4j client with optimized connection pooling and resilience patterns.

        Args:
            uri: Neo4j connection URI
            user: Database user
            password: Database password
            database: Database name
            max_connection_pool_size: Maximum connections in pool (auto-calculated if None)
            connection_acquisition_timeout: Timeout for acquiring connection (default: 5.0s)
            max_connection_lifetime: Max lifetime of connections in seconds (default: 3600s)
            enable_circuit_breaker: Enable circuit breaker pattern (default: True)
        """
        # Auto-calculate optimal pool size if not provided
        if max_connection_pool_size is None:
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            # Formula: pool_size = cpu_count * 2 + spare_connections
            # Cap at 100 to prevent resource exhaustion
            max_connection_pool_size = min(cpu_count * 2 + 4, 100)

        # Use shorter timeout for fail-fast behavior
        if connection_acquisition_timeout is None:
            connection_acquisition_timeout = 5.0

        self._driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_lifetime=max_connection_lifetime,
            max_connection_pool_size=max_connection_pool_size,
            connection_acquisition_timeout=connection_acquisition_timeout,
            # Additional optimizations
            keep_alive=True,  # Maintain connections with keepalive
            connection_timeout=10.0,  # Initial connection timeout
            max_transaction_retry_time=15.0,  # Max retry time for transactions
        )
        self._database = database

        logger.info(
            "Neo4j connection pool configured",
            extra={
                "max_pool_size": max_connection_pool_size,
                "acquisition_timeout": connection_acquisition_timeout,
                "max_lifetime": max_connection_lifetime,
            }
        )

        # Initialize circuit breaker registry
        if enable_circuit_breaker and CIRCUIT_BREAKER_AVAILABLE:
            self.circuit_registry = CircuitBreakerRegistry()
            self._read_breaker_config = CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=30.0,
                half_open_max_calls=3,
            )
            self._write_breaker_config = CircuitBreakerConfig(
                failure_threshold=3,  # More strict for writes
                success_threshold=2,
                timeout_seconds=60.0,
                half_open_max_calls=2,
            )
            logger.info("Circuit breaker enabled for Neo4j client")
        else:
            self.circuit_registry = None
            logger.info("Circuit breaker disabled for Neo4j client")

    async def connect(self) -> None:
        await self._driver.verify_connectivity()
        await self._ensure_schema()

    async def close(self) -> None:
        await self._driver.close()

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute read query with circuit breaker and retry logic.

        Features:
        - Circuit breaker protection (fails fast when service is down)
        - Automatic retry with exponential backoff on transient failures
        - Comprehensive error logging

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records

        Raises:
            CircuitBreakerError: When circuit is open (service is down)
            Neo4jError: After exhausting retries
        """
        if self.circuit_registry:
            breaker = await self.circuit_registry.get_or_create(
                "neo4j_read",
                self._read_breaker_config
            )
            return await breaker.call(self._execute_read_internal, query, parameters)
        else:
            return await self._execute_read_internal(query, parameters)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ServiceUnavailable, SessionExpired)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _execute_read_internal(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Internal read implementation with retry logic."""
        params = parameters or {}
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, **params)
            records = await result.data()
            return records

    async def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> None:
        """Execute write query with circuit breaker and retry logic.

        Features:
        - Circuit breaker protection (stricter thresholds for writes)
        - Automatic retry with exponential backoff on transient failures
        - Comprehensive error logging

        Args:
            query: Cypher query string
            parameters: Query parameters

        Raises:
            CircuitBreakerError: When circuit is open (service is down)
            Neo4jError: After exhausting retries
        """
        if self.circuit_registry:
            breaker = await self.circuit_registry.get_or_create(
                "neo4j_write",
                self._write_breaker_config
            )
            return await breaker.call(self._execute_write_internal, query, parameters)
        else:
            return await self._execute_write_internal(query, parameters)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ServiceUnavailable, SessionExpired)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _execute_write_internal(self, query: str, parameters: dict[str, Any] | None = None) -> None:
        """Internal write implementation with retry logic."""
        params = parameters or {}
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(lambda tx: tx.run(query, **params))

    async def execute_write_transaction(
        self, handler: Callable[[AsyncManagedTransaction], Awaitable[T]]
    ) -> T:
        async with self._driver.session(database=self._database) as session:
            return await session.execute_write(handler)

    async def health_check(self) -> bool:
        try:
            await self.execute_read("RETURN 1 AS ok")
            return True
        except Neo4jError:
            return False

    async def get_metrics(self) -> GraphMetrics:
        async with self._driver.session(database=self._database) as session:
            node_result = await session.run("MATCH (n) RETURN count(n) AS count")
            node_record = await node_result.single()
            node_count = int(node_record["count"]) if node_record else 0

            rel_result = await session.run("MATCH ()-[r]->() RETURN count(r) AS count")
            rel_record = await rel_result.single()
            relationship_count = int(rel_record["count"]) if rel_record else 0

            labels_result = await session.run(
                "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS occurrences"
            )
            label_rows = await labels_result.data()
            labels = {row["label"]: int(row["occurrences"]) for row in label_rows}

            rel_types_result = await session.run(
                "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(*) AS occurrences"
            )
            rel_rows = await rel_types_result.data()
            relationship_types = {row["rel_type"]: int(row["occurrences"]) for row in rel_rows}

            degree = 0.0

        return GraphMetrics(
            node_count=node_count,
            relationship_count=relationship_count,
            labels=labels,
            relationship_types=relationship_types,
            average_degree=degree,
        )

    async def _ensure_schema(self) -> None:
        """Ensure database schema including constraints and indexes."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(self._create_constraints)
            await session.execute_write(self._create_performance_indexes)

    @staticmethod
    async def _create_constraints(tx: AsyncManagedTransaction, /) -> None:
        """Create uniqueness constraints for result nodes."""
        statements = [
            (
                "CREATE CONSTRAINT lint_result_id IF NOT EXISTS FOR "
                "(r:LintResult) REQUIRE r.id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT test_result_id IF NOT EXISTS FOR "
                "(r:TestResult) REQUIRE r.id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT exec_result_id IF NOT EXISTS FOR "
                "(r:ExecutionResult) REQUIRE r.id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT gen_result_id IF NOT EXISTS FOR "
                "(r:GeneratedCode) REQUIRE r.id IS UNIQUE"
            ),
            "CREATE INDEX node_key IF NOT EXISTS FOR (n:GraphNode) ON (n.key)",
        ]
        for statement in statements:
            await tx.run(statement)

    @staticmethod
    async def _create_performance_indexes(tx: AsyncManagedTransaction, /) -> None:
        """Create performance indexes for common query patterns."""
        statements = [
            # Indexes for audit and security queries
            (
                "CREATE INDEX audit_event_timestamp IF NOT EXISTS FOR "
                "(n:AuditEvent) ON (n.timestamp)"
            ),
            "CREATE INDEX audit_event_user IF NOT EXISTS FOR (n:AuditEvent) ON (n.user_id)",
            "CREATE INDEX audit_event_type IF NOT EXISTS FOR (n:AuditEvent) ON (n.event_type)",
            
            # Indexes for execution results
            (
                "CREATE INDEX execution_timestamp IF NOT EXISTS FOR "
                "(n:ExecutionResult) ON (n.timestamp)"
            ),
            (
                "CREATE INDEX execution_code_hash IF NOT EXISTS FOR "
                "(n:ExecutionResult) ON (n.code_hash)"
            ),
            (
                "CREATE INDEX execution_language IF NOT EXISTS FOR "
                "(n:ExecutionResult) ON (n.language)"
            ),
            
            # Indexes for lint results
            (
                "CREATE INDEX lint_result_hash IF NOT EXISTS FOR "
                "(n:LintResult) ON (n.code_hash)"
            ),
            (
                "CREATE INDEX lint_result_timestamp IF NOT EXISTS FOR "
                "(n:LintResult) ON (n.timestamp)"
            ),
            
            # Indexes for test results
            (
                "CREATE INDEX test_result_timestamp IF NOT EXISTS FOR "
                "(n:TestResult) ON (n.timestamp)"
            ),
            
            # Composite index for common user + time queries
            (
                "CREATE INDEX execution_user_time IF NOT EXISTS FOR "
                "(n:ExecutionResult) ON (n.user_id, n.timestamp)"
            ),
        ]
        for statement in statements:
            await tx.run(statement)

    @staticmethod
    def encode_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, separators=(",", ":"))


__all__ = ["Neo4jClient"]
