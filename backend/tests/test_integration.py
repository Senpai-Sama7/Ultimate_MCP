from __future__ import annotations

import asyncio
from types import ModuleType
from typing import AsyncGenerator

import pytest
import pytest_asyncio
import uvicorn
from agent_integration.client import AgentDiscovery

TEST_TOKEN = "test-token"

@pytest_asyncio.fixture
async def live_server(server_module: ModuleType) -> AsyncGenerator[str, None]:
    config = uvicorn.Config(server_module.app, host="127.0.0.1", port=8055, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not getattr(server, "started", False):
        await asyncio.sleep(0.1)
    try:
        yield "http://127.0.0.1:8055"
    finally:
        server.should_exit = True
        await task


@pytest.mark.asyncio
async def test_agent_discovery_round_trip(live_server: str) -> None:
    discovery = AgentDiscovery(base_url=live_server, auth_token=TEST_TOKEN)
    tools = await discovery.list_tools()
    assert "lint_code" in tools
    result = await discovery.lint_round_trip("def sample() -> int:\n    return 1\n")
    assert isinstance(result.response, dict)
    response_payload = result.response
    assert response_payload.get("is_error") is False
    assert result.call_arguments["language"] == "python"
