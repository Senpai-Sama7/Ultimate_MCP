from __future__ import annotations

from types import ModuleType

import httpx
import pytest

from backend.mcp_server.database.models import GraphQueryPayload
from backend.mcp_server.tools import (
    ExecutionRequest,
    GenerationRequest,
    LintRequest,
)
from backend.mcp_server.utils.enhanced_security import SecurityViolationError
from backend.mcp_server.utils.validation import PayloadValidationError


@pytest.mark.asyncio
async def test_lint_tool_persists_results(
    server_module: ModuleType, client: httpx.AsyncClient
) -> None:
    tool = server_module.registry.lint
    assert tool is not None
    result = await tool.run(LintRequest(code="def add(a, b):\n    return a + b\n"))
    stored = await server_module.neo4j_client.execute_read(
        "MATCH (r:LintResult {id: $id}) RETURN r",
        {"id": result.id},
    )
    assert stored, "Result was not written to Neo4j"


@pytest.mark.asyncio
async def test_generation_tool_renders_template(
    server_module: ModuleType, client: httpx.AsyncClient
) -> None:
    tool = server_module.registry.generate
    assert tool is not None
    response = await tool.run(
        GenerationRequest(
            template="def {{ name }}():\n    return {{ value }}\n",
            context={"name": "meaning", "value": 42},
        )
    )
    assert "return 42" in response.output


@pytest.mark.asyncio
async def test_execution_tool_rejects_unsafe_import(
    server_module: ModuleType, client: httpx.AsyncClient
) -> None:
    tool = server_module.registry.execute
    assert tool is not None
    with pytest.raises(SecurityViolationError):
        await tool.run(ExecutionRequest(code="import os\nprint(os.listdir())\n"))


@pytest.mark.asyncio
async def test_graph_tool_rejects_mutating_cypher(
    server_module: ModuleType, client: httpx.AsyncClient
) -> None:
    graph_tool = server_module.registry.graph
    assert graph_tool is not None
    with pytest.raises(PayloadValidationError):
        await graph_tool.query(
            GraphQueryPayload(cypher="DELETE FROM foo")
        )
