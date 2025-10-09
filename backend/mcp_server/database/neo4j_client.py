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

    def __init__(self, uri: str, user: str, password: str, database: str) -> None:
        self._driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_lifetime=300,
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
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(self._create_constraints)

    @staticmethod
    async def _create_constraints(tx: AsyncManagedTransaction, /) -> None:
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
    def encode_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, separators=(",", ":"))


__all__ = ["Neo4jClient"]
