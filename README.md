# Ultimate MCP Platform

Production-ready Model Context Protocol (MCP) stack that bundles a FastAPI backend, Neo4j graph store, and React front-end for linting, sandboxed execution, test orchestration, graph persistence, and code generation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg)](https://fastapi.tiangolo.com)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.23-008CC1.svg)](https://neo4j.com)

## Highlights

- 🔐 **Security-first** – Bearer auth, SlowAPI rate limits, sandboxed execution, configurable secrets.
- 🧪 **Rich tooling** – Lint code, run pytest suites, execute snippets with resource limits, generate code from templates.
- 🧠 **Graph-native storage** – Persist lint/test/execute results and custom nodes to Neo4j; query them with Cypher.
- 📊 **Observability** – `/health` and `/metrics` endpoints, structured logging, reusable smoke tests.
- 🛠️ **MCP compatible** – Backed by FastMCP so Claude or any MCP client can consume the same tools.

---

## Quickstart

### Option 0 – Local CLI (fastest)

```bash
git clone https://github.com/Senpai-Sama7/Ultimate_MCP.git
cd Ultimate_MCP/cli
npm install
npm run smoke   # optional sanity check
node bin/ultimate-mcp.js init ~/ultimate-mcp-demo
node bin/ultimate-mcp.js start --project ~/ultimate-mcp-demo
```

The CLI scaffolds a deployment directory, generates secrets, and launches Docker Compose. When the package is published you’ll be able to use `npx @ultimate-mcp/cli`; for now run it from the cloned repo. Override backend/frontend images by editing `UMCP_BACKEND_IMAGE` / `UMCP_FRONTEND_IMAGE` in the generated `.env` file if you host custom images.

### Option 1 – Deploy script (from this repo)

```bash
git clone https://github.com/Senpai-Sama7/Ultimate_MCP.git
cd Ultimate_MCP
./deploy.sh
```

- Frontend UI: <http://localhost:3000>
- Backend API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- Neo4j Browser: <http://localhost:7474> (or the ports in `.env.deploy`)

Tear down with:

```bash
docker compose --project-name ultimate-mcp --env-file .env.deploy -f deployment/docker-compose.yml down
```

> **Port conflicts?** After the first run, edit `.env.deploy` and change `FRONTEND_HTTP_PORT`, `NEO4J_HTTP_PORT`, or `NEO4J_BOLT_PORT` before re-running `./deploy.sh`. The backend exposes port 8000 by default; the other ports are configurable via the env file.

### Option 2 – Manual developer setup

```bash
# Clone and install backend
git clone https://github.com/Senpai-Sama7/Ultimate_MCP.git
cd Ultimate_MCP/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_enhanced.txt

# Start Neo4j
export NEO4J_PASSWORD=$(openssl rand -hex 16)
docker run -d --name ultimate-mcp-dev-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e "NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}" \
  neo4j:5.23.0

# Run backend (default token change recommended)
export AUTH_TOKEN=$(openssl rand -hex 24)
uvicorn mcp_server.enhanced_server:app --host 0.0.0.0 --port 8000 --reload

# In another terminal – frontend
cd ../frontend
npm install
npm run dev
```

---

## Full MCP capability demo

With the stack running (via any option above) and `requests` installed, execute the end-to-end demo:

```bash
python demo/full_demo.py --base-url http://localhost:8000 \
  --auth-token $(grep '^AUTH_TOKEN=' .env.deploy | cut -d= -f2-)
```

The script sequentially:
1. Lints a Python snippet.
2. Executes code in the sandbox.
3. Runs pytest.
4. Generates code from a template.
5. Upserts a pair of service nodes + relationship in Neo4j.
6. Queries the graph and prints aggregate metrics.

Use it whenever you need a “show me it works” proof for MCP clients or demos.

---

## Built-in prompt library

```
curl http://localhost:8000/prompts | jq
curl http://localhost:8000/prompts/proceed | jq '.body'
```

Use the MCP tools `list_prompts` and `get_prompt` to retrieve the same definitions from an MCP client.

---

## Core API recipes

> Replace `$AUTH_TOKEN` with the bearer token from `.env.deploy` or your own secret.

### Lint code
```bash
curl --json '{"code":"def add(a, b):\n    return a + b\n","language":"python"}' \
  http://localhost:8000/lint_code
```

### Execute code (auth required)
```bash
curl --json '{"code":"print(6 * 7)","language":"python"}' \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  http://localhost:8000/execute_code
```

### Run pytest (auth required)
```bash
curl --json '{"code":"def test_math():\n    assert 1 + 1 == 2\n","language":"python"}' \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  http://localhost:8000/run_tests
```

### Generate code (auth required)
```bash
curl --json '{"template":"def {{ name }}():\n    return {{ value }}","context":{"name":"answer","value":42}}' \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  http://localhost:8000/generate_code
```

### Graph upsert & query (auth required for upsert)
```bash
curl --json '{"nodes":[{"key":"service_frontend","labels":["Service"],"properties":{"name":"frontend","language":"typescript"}},{"key":"service_backend","labels":["Service"],"properties":{"name":"backend","language":"python"}}],"relationships":[{"start":"service_frontend","end":"service_backend","type":"CALLS","properties":{"latency_ms":120}}]}' \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  http://localhost:8000/graph_upsert

curl --json '{"cypher":"MATCH (s:Service) RETURN s.name AS name, s.language AS language","parameters":{}}' \
  http://localhost:8000/graph_query
```

### Monitoring
```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics | jq
```

---

## Neo4j

- Browser: <http://localhost:7474> (credentials `neo4j` / value in `NEO4J_PASSWORD`).
- All lint/test/execute results and custom graph nodes are persisted automatically.

---

## Contributing & further docs

- `AGENTS.md` – contributor workflow and PR expectations.
- `docs/RELEASE.md` – tagging & publishing instructions.
- `docs/SECURITY_BACKLOG.md` – tracked hardening follow-ups.

Pull requests welcome! Use feature branches off `main` and run the smoke tests (`python scripts/smoke_test.py`, `demo/full_demo.py`) before opening a PR.
