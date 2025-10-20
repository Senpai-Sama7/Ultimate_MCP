from __future__ import annotations

import importlib
import os
import socket
import subprocess
import time
from collections.abc import AsyncIterator
from types import ModuleType
from typing import Iterator

import httpx
import pytest_asyncio
from neo4j import GraphDatabase
from agent_integration.client import AgentDiscovery
from mcp_server.tools import (
    ExecutionTool,
    GenerationTool,
    GraphTool,
    LintTool,
    TestTool,
)

CONTAINER_NAME = "ultimate_mcp_neo4j_test"
BOLT_PORT = 7688
HTTP_PORT = 7475
PASSWORD = "test-password!"

# Ensure deterministic test configuration before modules import settings.
os.environ.setdefault("NEO4J_URI", f"bolt://127.0.0.1:{BOLT_PORT}")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", PASSWORD)
os.environ.setdefault("NEO4J_DATABASE", "neo4j")
os.environ.setdefault("ALLOWED_ORIGINS", '["http://localhost"]')
os.environ.setdefault("AUTH_TOKEN", "test-token")
os.environ.setdefault("RATE_LIMIT_RPS", "50")


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest_asyncio.fixture(scope="session")
def neo4j_service() -> Iterator[str]:
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], check=False, stdout=subprocess.DEVNULL)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "-p",
            f"{BOLT_PORT}:7687",
            "-p",
            f"{HTTP_PORT}:7474",
            "-e",
            f"NEO4J_AUTH=neo4j/{PASSWORD}",
            "neo4j:5.23.0",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    deadline = time.time() + 120
    while time.time() < deadline:
        if _port_is_open(BOLT_PORT):
            try:
                driver = GraphDatabase.driver(
                    f"bolt://127.0.0.1:{BOLT_PORT}", auth=("neo4j", PASSWORD)
                )
                driver.verify_connectivity()
                driver.close()
                break
            except Exception:
                time.sleep(1)
        else:
            time.sleep(1)
    else:  # pragma: no cover
        raise RuntimeError("Neo4j test container failed to start")

    yield f"bolt://127.0.0.1:{BOLT_PORT}"

    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], check=False, stdout=subprocess.DEVNULL)


@pytest_asyncio.fixture(scope="session")
def server_module(neo4j_service: str) -> ModuleType:
    os.environ["NEO4J_URI"] = neo4j_service
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = PASSWORD
    os.environ["NEO4J_DATABASE"] = "neo4j"
    os.environ["ALLOWED_ORIGINS"] = '["http://localhost"]'
    os.environ["AUTH_TOKEN"] = "test-token"
    os.environ["RATE_LIMIT_RPS"] = "50"
    module = importlib.import_module("mcp_server.server")
    return module


@pytest_asyncio.fixture
async def client(server_module: ModuleType) -> AsyncIterator[httpx.AsyncClient]:
    await server_module.neo4j_client.connect()
    registry = server_module.registry
    registry.lint = LintTool(server_module.neo4j_client)
    registry.tests = TestTool(server_module.neo4j_client)
    registry.graph = GraphTool(server_module.neo4j_client)
    registry.execute = ExecutionTool(server_module.neo4j_client)
    registry.generate = GenerationTool(server_module.neo4j_client)

    app = server_module.app
    app.state.settings = server_module.settings
    app.state.neo4j = server_module.neo4j_client
    app.state.tools = registry
    app.state.agent_discovery = AgentDiscovery(base_url="http://localhost:8000")

    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        await server_module.neo4j_client.close()
        registry.lint = None
        registry.tests = None
        registry.graph = None
        registry.execute = None
        registry.generate = None
