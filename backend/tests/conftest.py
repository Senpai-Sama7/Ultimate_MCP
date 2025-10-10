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

CONTAINER_NAME = "ultimate_mcp_neo4j_test"
BOLT_PORT = 7688
HTTP_PORT = 7475
PASSWORD = "test-password!"


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
    os.environ["ALLOWED_ORIGINS"] = "http://localhost"
    os.environ["AUTH_TOKEN"] = "test-token"
    os.environ["RATE_LIMIT_RPS"] = "50"
    module = importlib.import_module("mcp_server.server")
    return module


@pytest_asyncio.fixture
async def client(server_module: ModuleType) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=server_module.app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
