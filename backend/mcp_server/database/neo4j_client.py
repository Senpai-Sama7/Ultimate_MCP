"""Async Neo4j client wrapper used by the MCP server."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, TypeVar

from neo4j import AsyncGraphDatabase, AsyncManagedTransaction
from neo4j.exceptions import Neo4jError

from .models import GraphMetrics

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
        max_connection_pool_size: int = 100,
        connection_acquisition_timeout: float = 60.0,
    ) -> None:
        """Initialize Neo4j client with connection pooling.
        
        Args:
            uri: Neo4j connection URI
            user: Database user
            password: Database password
            database: Database name
            max_connection_pool_size: Maximum connections in pool (default: 100)
            connection_acquisition_timeout: Timeout for acquiring connection (default: 60s)
        """
        self._driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_lifetime=300,
            max_connection_pool_size=max_connection_pool_size,
            connection_acquisition_timeout=connection_acquisition_timeout,
        )
        self._database = database

    async def connect(self) -> None:
        await self._driver.verify_connectivity()
        await self._ensure_schema()

    async def close(self) -> None:
        await self._driver.close()

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        params = parameters or {}
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, **params)
            records = await result.data()
            return records

    async def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> None:
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
