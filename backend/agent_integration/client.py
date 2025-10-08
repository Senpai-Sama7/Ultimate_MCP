"""Utilities that connect Ultimate MCP to the OpenAI Agents SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, cast

from fastmcp import Client as MCPClient
from fastmcp.client.transports import StreamableHttpTransport

try:  # Optional dependency during test runs without OpenAI credentials.
    from openai import OpenAI
except Exception:  # pragma: no cover - OpenAI is optional for local testing
    OpenAI = None  # type: ignore


@dataclass(slots=True)
class AgentToolResult:
    name: str
    call_arguments: dict[str, Any]
    response: dict[str, Any] | list[Any] | str | None


class AgentDiscovery:
    """High-level client that interacts with the MCP server over HTTP."""

    def __init__(self, base_url: str, auth_token: str | None = None, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        headers: dict[str, str] = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        self._transport = StreamableHttpTransport(f"{self._base_url}/mcp", headers=headers)
        self._timeout = timeout

    async def list_tools(self) -> list[str]:
        async with MCPClient(self._transport, timeout=self._timeout) as client:
            tools = await client.list_tools()
            return sorted(tool.name for tool in tools)

    async def invoke(self, name: str, arguments: dict[str, Any]) -> AgentToolResult:
        async with MCPClient(self._transport, timeout=self._timeout) as client:
            result = await client.call_tool(name, arguments)
        blocks: list[Any] = []
        for block in result.content:
            if hasattr(block, "model_dump"):
                blocks.append(block.model_dump())
            else:
                blocks.append(block)
        payload: dict[str, Any] = {"content": blocks}
        if result.structured_content is not None:
            payload["structured"] = result.structured_content
        if result.data is not None:
            payload["data"] = result.data
        payload["is_error"] = result.is_error
        return AgentToolResult(name=name, call_arguments=arguments, response=payload)

    async def lint_round_trip(self, code: str) -> AgentToolResult:
        request = {"code": code, "language": "python"}
        return await self.invoke("lint_code", request)


class OpenAIAgentBridge:
    """Helper that wires the MCP server into an OpenAI Agent."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        instructions: str | None = None,
    ) -> None:
        if OpenAI is None:  # pragma: no cover - handled in runtime not tests
            raise RuntimeError("openai package is required for OpenAIAgentBridge")
        self._base_url = base_url.rstrip("/")
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._instructions = instructions or (
            "You are an engineering co-pilot that uses the Ultimate MCP tooling to deliver "
            "linted, tested, and production-ready code with minimal iterations."
        )

    def bootstrap_agent(self) -> str:
        agent = self._client.agents.create(  # type: ignore[attr-defined]
            name="Ultimate MCP Agent",
            model=self._model,
            instructions=self._instructions,
            tools=[
                {
                    "type": "mcp_server",
                    "server_url": f"{self._base_url}/mcp",
                    "server_name": "Ultimate MCP",
                }
            ],
        )
        return cast(str, getattr(agent, "id"))

    def run_prompt(self, agent_id: str, prompt: str) -> dict[str, Any]:
        run = self._client.responses.create(  # type: ignore[attr-defined]
            agent_id=agent_id,
            input=[{"role": "user", "content": prompt}],
        )
        return cast(dict[str, Any], json.loads(run.model_dump_json()))


async def demonstrate_agent_flow(
    *,
    base_url: str,
    auth_token: str | None = None,
    sample_code: str,
    on_result: Callable[[AgentToolResult], None] | None = None,
) -> AgentToolResult:
    """Convenience coroutine that discovers tools and lint checks a snippet."""

    discovery = AgentDiscovery(base_url, auth_token=auth_token)
    tools = await discovery.list_tools()
    if "lint_code" not in tools:
        raise RuntimeError("lint_code tool not exposed by MCP server")
    result = await discovery.lint_round_trip(sample_code)
    if on_result:
        on_result(result)
    return result


__all__ = [
    "AgentDiscovery",
    "AgentToolResult",
    "OpenAIAgentBridge",
    "demonstrate_agent_flow",
]
