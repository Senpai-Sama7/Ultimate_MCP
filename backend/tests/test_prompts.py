from __future__ import annotations

import asyncio

import pytest

from backend.mcp_server.server import (
    PROMPT_DEFINITIONS,
    PromptRequest,
    mcp_get_prompt,
    mcp_list_prompts,
)


@pytest.mark.asyncio
async def test_prompt_endpoints(client):
    response = await client.get("/prompts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(item["slug"] == "proceed" for item in data)

    response = await client.get("/prompts/proceed")
    assert response.status_code == 200
    assert response.json()["slug"] == "proceed"

    response = await client.get("/prompts/unknown")
    assert response.status_code == 404


class _DummyContext:
    async def info(self, message: str, extra: dict | None = None) -> None:  # pragma: no cover - simple stub
        await asyncio.sleep(0)

    async def debug(self, message: str, extra: dict | None = None) -> None:  # pragma: no cover
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_mcp_prompt_tools(server_module):
    context = _DummyContext()
    catalog = await mcp_list_prompts(context)  # type: ignore[arg-type]
    assert len(catalog.prompts) == len(PROMPT_DEFINITIONS)

    prompt = await mcp_get_prompt(PromptRequest(slug="proceed"), context)  # type: ignore[arg-type]
    assert prompt.prompt.slug == "proceed"

    with pytest.raises(ValueError):
        await mcp_get_prompt(PromptRequest(slug="unknown"), context)  # type: ignore[arg-type]
