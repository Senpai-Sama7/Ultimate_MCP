from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    payload = response.json()
    assert response.status_code == 200
    assert payload["service"] == "ok"
    assert payload["neo4j"] is True


@pytest.mark.asyncio
async def test_lint_endpoint_returns_functions(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/lint_code",
        json={"code": "def foo():\n    return 42\n"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "foo" in body["functions"]
    assert body["linter_exit_code"] == 0


@pytest.mark.asyncio
async def test_execute_requires_bearer_token(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/execute_code",
        json={"code": "print('hi')"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_graph_round_trip(client: httpx.AsyncClient) -> None:
    headers = {"Authorization": "Bearer test-token"}
    upsert = await client.post(
        "/graph_upsert",
        json={
            "nodes": [
                {"key": "User:1", "labels": ["User"], "properties": {"name": "Ada"}},
                {"key": "Repo:1", "labels": ["Repository"], "properties": {"name": "Ultimate"}},
            ],
            "relationships": [
                {
                    "start": "User:1",
                    "end": "Repo:1",
                    "type": "OWNS",
                    "properties": {"since": 2025},
                }
            ],
        },
        headers=headers,
    )
    assert upsert.status_code == 200
    metrics = upsert.json()["metrics"]
    assert metrics["node_count"] >= 2

    query = await client.post(
        "/graph_query",
        json={"cypher": "MATCH (u:User)-[r:OWNS]->(repo) RETURN u, r, repo"},
    )
    assert query.status_code == 200
    data = query.json()["results"]
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_run_tests_tool(client: httpx.AsyncClient) -> None:
    headers = {"Authorization": "Bearer test-token"}
    code = """
import pytest

def test_example():
    assert 1 + 1 == 2
"""
    response = await client.post(
        "/run_tests",
        headers=headers,
        json={"code": code},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["return_code"] == 0
