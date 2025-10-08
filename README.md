# Ultimate MCP Coding Platform

![CI](https://github.com/donovan/Ultimate_MCP/actions/workflows/ci.yml/badge.svg)

Ultimate MCP is a production-ready Model Context Protocol platform that turns any LLM into a coding co-pilot. It ships with a FastAPI + FastMCP backend, Neo4j graph persistence, OpenAI Agent integration, a React frontend, and Docker Compose orchestration.

## Features

- Real MCP server with lint, test, execution, generation, and graph tools
- Neo4j persistence for tool artefacts with aggregation metrics
- REST API mirroring MCP tools and secured by bearer token + rate limiting
- Structured logging, strict CORS, security headers, and per-request IDs
- React + Vite frontend for human operators
- OpenAI Agents SDK bridge for autonomous tool discovery and execution
- Complete CI pipeline (lint, type-check, tests with coverage, Docker builds)
- Docker Compose for one-command local deployment

## Repository Layout

```
backend/              FastAPI MCP server and tool implementations
frontend/             React TypeScript application
scripts/              Developer automation (setup & smoke tests)
deployment/           Docker Compose specification
docs/                 Architecture, API, security, and operations guides
```

## Quickstart

### 1. Dependencies

- Python 3.13+
- Node.js 20+
- Docker & Docker Compose (for containerised runs)

### 2. Bootstrap Environment

```bash
scripts/setup.py
```

This creates `backend/.venv`, installs Python requirements, and runs `npm install` for the frontend.

### 3. Run Locally (Developer Mode)

Backend:

```bash
source backend/.venv/bin/activate
uvicorn mcp_server.server:app --reload
```

Frontend:

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 3000
```

Open the UI at `http://localhost:3000`. The API docs live at `http://localhost:8000/docs`.

### 4. Run with Docker Compose

```bash
cp .env.example .env  # set AUTH_TOKEN before production use
docker compose -f deployment/docker-compose.yml up --build
```

Expose:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- Neo4j Browser: `http://localhost:7474`

## Testing

```bash
# lint & type-check
backend/.venv/bin/ruff check backend
backend/.venv/bin/mypy backend

# run pytest with coverage
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=password123 \
AUTH_TOKEN=test-token \
backend/.venv/bin/pytest backend/tests --cov=backend/mcp_server --cov=backend/agent_integration --cov-report=term-missing --cov-fail-under=80

# frontend lint + build
cd frontend
npm run lint
npm run build
```

A ready-made smoke test hits key endpoints:

```bash
scripts/smoke_test.py --base-url http://localhost:8000
```

## MCP & Agent Integration

- MCP server mounted at `/mcp` using FastMCP streamable HTTP transport.
- `backend/agent_integration/client.py` provides `AgentDiscovery` for listing/invoking tools and an `OpenAIAgentBridge` to register the server with OpenAI Agents.

Example usage:

```python
from backend.agent_integration.client import AgentDiscovery
import asyncio

async def main():
    discovery = AgentDiscovery("http://localhost:8000", auth_token="change-me")
    print(await discovery.list_tools())

asyncio.run(main())
```

## Security Highlights

- Bearer token auth on all mutating endpoints
- SlowAPI rate limiting (default 10 req/s per IP)
- Request size checks and security headers (`CSP`, `X-Frame-Options`, etc.)
- Non-root Docker images with capabilities dropped

Detailed guidance in [`docs/SECURITY.md`](docs/SECURITY.md).

## Configuration

See `.env.example` for required variables:

```
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
NEO4J_DATABASE=neo4j
ALLOWED_ORIGINS=http://localhost:3000
AUTH_TOKEN=change-me
RATE_LIMIT_RPS=10
```

## Documentation

- [API Reference](docs/API.md)
- [Security Guide](docs/SECURITY.md)
- [Operations Manual](docs/OPERATIONS.md)
- [Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)

## Release Packaging

Create an archive for distribution:

```bash
zip -r Ultimate_MCP-release.zip \
  backend frontend deployment docs scripts \
  pyproject.toml README.md .env.example
```

## License

MIT License © 2025 Ultimate MCP maintainers.
# Ultimate_MCP
