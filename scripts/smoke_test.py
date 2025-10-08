#!/usr/bin/env python3
"""Run a minimal smoke test against a running Ultimate MCP deployment."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import httpx

DEFAULT_BACKEND = "http://localhost:8000"


async def check_health(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/health")
    response.raise_for_status()
    return response.json()


async def check_metrics(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/metrics")
    response.raise_for_status()
    return response.json()


async def lint_sample(client: httpx.AsyncClient) -> dict[str, Any]:
    payload = {"code": "def ping():\n    return 'pong'\n", "language": "python"}
    response = await client.post("/lint_code", json=payload)
    response.raise_for_status()
    return response.json()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ultimate MCP smoke test runner")
    parser.add_argument("--base-url", default=DEFAULT_BACKEND, help="Backend base URL")
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=args.base_url, timeout=10.0) as client:
        health = await check_health(client)
        metrics = await check_metrics(client)
        lint = await lint_sample(client)

    print("Health:")
    print(json.dumps(health, indent=2))
    print("Metrics:")
    print(json.dumps(metrics, indent=2))
    print("Lint:")
    print(json.dumps(lint, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
