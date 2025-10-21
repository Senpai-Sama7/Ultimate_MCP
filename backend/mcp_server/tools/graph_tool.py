"""Graph persistence and analytics tool with optimized batch operations."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from neo4j.graph import Node, Path, Relationship
from pydantic import BaseModel

from ..database.models import (
    GraphMetrics,
    GraphNode,
    GraphQueryPayload,
    GraphRelationship,
    GraphUpsertPayload,
)
from ..database.neo4j_client import Neo4jClient
from ..utils.validation import ensure_safe_cypher, ensure_valid_identifier

logger = logging.getLogger(__name__)


@dataclass
class GraphQueryResult:
    records: list[dict[str, Any]]


class GraphUpsertResponse(BaseModel):
    metrics: GraphMetrics


class GraphQueryResponse(BaseModel):
    results: list[dict[str, Any]]


class GraphTool:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def upsert(self, payload: GraphUpsertPayload) -> GraphUpsertResponse:
        """Upsert nodes and relationships using batch transactions for performance.

        Uses a single transaction for all operations to improve performance by ~10x
        compared to individual operations.

        Args:
            payload: Graph upsert payload with nodes and relationships

        Returns:
            Response with updated graph metrics
        """
        # Use single transaction for all operations (much faster)
        async def batch_upsert(tx):
            # Batch upsert all nodes
            for node in payload.nodes:
                ensure_valid_identifier(node.key, field="node.key")
                labels = ["GraphNode"] + [self._normalise_label(l) for l in node.labels]
                label_fragment = ":".join(labels)
                await tx.run(
                    f"MERGE (n:{label_fragment} {{key: $key}}) SET n += $props",
                    {"key": node.key, "props": node.properties}
                )

            # Batch upsert all relationships
            for rel in payload.relationships:
                ensure_valid_identifier(rel.start, field="relationship.start")
                ensure_valid_identifier(rel.end, field="relationship.end")
                rel_type = self._normalise_label(rel.type)
                await tx.run(
                    f"MATCH (start:GraphNode {{key: $start}}) "
                    f"MATCH (end:GraphNode {{key: $end}}) "
                    f"MERGE (start)-[r:{rel_type}]->(end) "
                    "SET r += $props",
                    {"start": rel.start, "end": rel.end, "props": rel.properties}
                )

        logger.info(
            "Starting batch graph upsert",
            extra={"node_count": len(payload.nodes), "rel_count": len(payload.relationships)}
        )

        await self._neo4j.execute_write_transaction(batch_upsert)
        metrics = await self._neo4j.get_metrics()

        logger.info(
            "Batch graph upsert completed",
            extra={"total_nodes": metrics.node_count, "total_rels": metrics.relationship_count}
        )

        return GraphUpsertResponse(metrics=metrics)

    async def query(self, payload: GraphQueryPayload) -> GraphQueryResponse:
        ensure_safe_cypher(payload.cypher)
        rows = await self._neo4j.execute_read(payload.cypher, payload.parameters)
        serialised = [self._serialise_row(row) for row in rows]
        return GraphQueryResponse(results=serialised)

    async def _upsert_node(self, node: GraphNode) -> None:
        """Legacy method for single node upsert. Use batch upsert() for better performance."""
        ensure_valid_identifier(node.key, field="node.key")
        labels = ["GraphNode"] + [self._normalise_label(label) for label in node.labels]
        label_fragment = ":".join(labels)
        await self._neo4j.execute_write(
            f"MERGE (n:{label_fragment} {{key: $key}}) SET n += $props",
            {"key": node.key, "props": node.properties},
        )

    async def _upsert_relationship(self, relationship: GraphRelationship) -> None:
        """Legacy method for single relationship upsert. Use batch upsert() for better performance."""
        ensure_valid_identifier(relationship.start, field="relationship.start")
        ensure_valid_identifier(relationship.end, field="relationship.end")
        rel_type = self._normalise_label(relationship.type)
        query = (
            f"MATCH (start:GraphNode {{key: $start}}) "
            f"MATCH (end:GraphNode {{key: $end}}) "
            f"MERGE (start)-[r:{rel_type}]->(end) "
            "SET r += $props"
        )
        await self._neo4j.execute_write(
            query,
            {
                "start": relationship.start,
                "end": relationship.end,
                "props": relationship.properties,
            },
        )

    def _normalise_label(self, label: str) -> str:
        ensure_valid_identifier(label, field="label")
        return label

    def _serialise_row(self, row: dict[str, Any]) -> dict[str, Any]:
        serialised: dict[str, Any] = {}
        for key, value in row.items():
            serialised[key] = self._serialise_value(value)
        return serialised

    def _serialise_value(self, value: object) -> object:
        if isinstance(value, Node):
            return {
                "id": getattr(value, "element_id", ""),
                "labels": list(value.labels),
                "properties": dict(value.items()),
            }
        if isinstance(value, Relationship):
            rel_start = getattr(value, "start_node", None)
            rel_end = getattr(value, "end_node", None)
            return {
                "id": getattr(value, "element_id", ""),
                "type": value.type,
                "properties": dict(value.items()),
                "start": getattr(rel_start, "element_id", ""),
                "end": getattr(rel_end, "element_id", ""),
            }
        if isinstance(value, Path):
            return {
                "nodes": [self._serialise_value(node) for node in value.nodes],
                "relationships": [
                    self._serialise_value(rel) for rel in value.relationships
                ],
            }
        if isinstance(value, list):
            return [self._serialise_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialise_value(val) for key, val in value.items()}
        return value


__all__ = [
    "GraphTool",
    "GraphUpsertResponse",
    "GraphQueryResponse",
]
