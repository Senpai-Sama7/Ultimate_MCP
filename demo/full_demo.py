#!/usr/bin/env python3
"""End-to-end demonstration of the Ultimate MCP API surface.

This script exercises every major capability:
  1. Lints a Python snippet.
  2. Executes code in the sandbox.
  3. Runs a pytest.
  4. Generates code from a template.
  5. Upserts graph data and queries it.
  6. Reads back aggregate metrics.

Run from the repository root:
    python demo/full_demo.py \
        --base-url http://localhost:8000 \
        --auth-token $(grep '^AUTH_TOKEN=' .env.deploy | cut -d= -f2-)
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class DemoConfig:
    base_url: str
    auth_token: str | None
    timeout: float


class DemoClient:
    def __init__(self, config: DemoConfig) -> None:
        self.config = config
        self.session = requests.Session()

    def _post(self, path: str, payload: dict[str, Any], *, auth: bool = False) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}{path}"
        headers = {"Content-Type": "application/json"}
        if auth:
            if not self.config.auth_token:
                raise RuntimeError("This endpoint requires --auth-token.")
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        response = self.session.post(url, headers=headers, json=payload, timeout=self.config.timeout)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - runtime feedback
            detail = exc.response.text if exc.response is not None else ""
            raise RuntimeError(f"{path} failed: {exc}\n{detail}") from exc
        return response.json()

    def lint_code(self) -> dict[str, Any]:
        payload = {
            "code": "def add(a, b):\n    return a + b\n",
            "language": "python",
        }
        return self._post("/lint_code", payload)

    def execute_code(self) -> dict[str, Any]:
        payload = {
            "code": "def multiply(a, b):\n    return a * b\n\nprint(multiply(6, 7))",
            "language": "python",
        }
        return self._post("/execute_code", payload, auth=True)

    def run_tests(self) -> dict[str, Any]:
        payload = {
            "code": "def test_math():\n    assert 1 + 1 == 2\n",
            "language": "python",
        }
        return self._post("/run_tests", payload, auth=True)

    def generate_code(self) -> dict[str, Any]:
        payload = {
            "template": "def {{ name }}():\n    return {{ value }}",
            "context": {"name": "answer", "value": 42},
        }
        return self._post("/generate_code", payload, auth=True)

    def graph_upsert(self) -> dict[str, Any]:
        suffix = uuid.uuid4().hex[:8]
        frontend_key = f"service_frontend_{suffix}"
        backend_key = f"service_backend_{suffix}"
        payload = {
            "nodes": [
                {
                    "key": frontend_key,
                    "labels": ["Service"],
                    "properties": {"name": "frontend", "language": "typescript"},
                },
                {
                    "key": backend_key,
                    "labels": ["Service"],
                    "properties": {"name": "backend", "language": "python"},
                },
            ],
            "relationships": [
                {
                    "start": frontend_key,
                    "end": backend_key,
                    "type": "CALLS",
                    "properties": {"latency_ms": 120},
                }
            ],
        }
        result = self._post("/graph_upsert", payload, auth=True)
        return {"result": result, "frontend_key": frontend_key, "backend_key": backend_key}

    def graph_query(self, frontend_key: str) -> dict[str, Any]:
        payload = {
            "cypher": "MATCH (s:Service) WHERE s.key STARTS WITH $prefix RETURN s.name AS name, s.language AS language",
            "parameters": {"prefix": frontend_key.split("_")[0]},
        }
        return self._post("/graph_query", payload)

    def metrics(self) -> dict[str, Any]:
        response = self.session.get(f"{self.config.base_url.rstrip('/')}/metrics", timeout=self.config.timeout)
        response.raise_for_status()
        return response.json()


def format_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a full Ultimate MCP API demo")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the backend API")
    parser.add_argument("--auth-token", default=None, help="Bearer token for protected endpoints (execute/tests/graph/generate)")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    config = DemoConfig(base_url=args.base_url, auth_token=args.auth_token, timeout=args.timeout)
    client = DemoClient(config)

    print("➡️  Linting sample code...")
    lint = client.lint_code()
    print(format_json(lint))
    print()

    print("➡️  Executing code in sandbox...")
    execute = client.execute_code()
    print(format_json(execute))
    print()

    print("➡️  Running pytest...")
    tests = client.run_tests()
    print(format_json(tests))
    print()

    print("➡️  Generating code from template...")
    generated = client.generate_code()
    print(format_json(generated))
    print()

    print("➡️  Upserting graph data...")
    upsert = client.graph_upsert()
    print(format_json(upsert["result"]))
    frontend_key = upsert["frontend_key"]
    print(f"Inserted service keys: {frontend_key}, {upsert['backend_key']}")
    print()

    time.sleep(0.5)
    print("➡️  Querying graph for services...")
    graph = client.graph_query(frontend_key)
    print(format_json(graph))
    print()

    print("➡️  Retrieving aggregate metrics...")
    metrics = client.metrics()
    print(format_json(metrics))

    print("\n✅ Demo complete – all MCP capabilities exercised.")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as exc:  # pragma: no cover - runtime assistance
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - runtime assistance
        print(textwrap.dedent(f"""
            ❌ Demo failed: {exc}
            Ensure the stack is running (see README Option 0) and retry.
        """).strip(), file=sys.stderr)
        sys.exit(1)
