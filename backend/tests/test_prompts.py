from __future__ import annotations

import asyncio

import pytest
from mcp_server.server import (
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
    # pragma: no cover - simple stub
    async def info(self, message: str, extra: dict | None = None) -> None:
        await asyncio.sleep(0)

    # pragma: no cover
    async def debug(self, message: str, extra: dict | None = None) -> None:
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


@pytest.mark.asyncio
async def test_fastmcp_prompt_registration(server_module):
    prompts = await server_module.mcp_server._prompt_manager.list_prompts()
    prompt_map = {prompt.name: prompt for prompt in prompts}
    assert set(prompt_map) >= {definition.slug for definition in PROMPT_DEFINITIONS}

    for definition in PROMPT_DEFINITIONS:
        prompt = prompt_map[definition.slug]
        rendered = await prompt.render()
        assert rendered, f"{definition.slug} prompt should render output"
        first_message = rendered[0]
        assert first_message.role == "assistant"
        assert getattr(first_message.content, "text", "") == definition.body
