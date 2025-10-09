"""Database-facing models shared across tools."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class TimestampedModel(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "extra": "forbid",
    }


class LintResult(TimestampedModel):
    id: str
    code_hash: str
    language: str
    functions: list[str]
    classes: list[str]
    imports: list[str]
    complexity: float
    linter_exit_code: int
    linter_output: str


class TestResult(TimestampedModel):
    id: str
    framework: str
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class ExecutionResult(TimestampedModel):
    id: str
    language: str
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class GeneratedCode(TimestampedModel):
    id: str
    language: str
    template_used: str
    context_keys: list[str]
    output: str


class GraphMetrics(BaseModel):
    node_count: int
    relationship_count: int
    labels: dict[str, int]
    relationship_types: dict[str, int]
    average_degree: float

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "extra": "forbid",
    }


class GraphNode(BaseModel):
    key: str
    labels: list[str]
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    start: str
    end: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphUpsertPayload(BaseModel):
    nodes: list[GraphNode]
    relationships: list[GraphRelationship] = Field(default_factory=list)


class GraphQueryPayload(BaseModel):
    cypher: str
    parameters: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "LintResult",
    "TestResult",
    "ExecutionResult",
    "GeneratedCode",
    "GraphMetrics",
    "GraphNode",
    "GraphRelationship",
    "GraphUpsertPayload",
    "GraphQueryPayload",
]
