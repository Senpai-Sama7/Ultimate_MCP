# API Reference

Base URL defaults to `http://localhost:8000`. All responses are JSON unless noted.

## Authentication

- `POST /run_tests`
- `POST /graph_upsert`
- `POST /execute_code`
- `POST /generate_code`

These endpoints require a bearer token when `AUTH_TOKEN` is set. Include the header:

```
Authorization: Bearer <token>
```

Rate limiting is applied to all POST requests. Exceeding the configured threshold returns HTTP `429` with a JSON error payload.

## Endpoints

### GET `/health`

Returns service and Neo4j status.

```json
{
  "service": "ok",
  "neo4j": true,
  "timestamp": "2025-10-08T01:32:10.015Z"
}
```

### GET `/metrics`

Aggregated Neo4j graph metrics.

```json
{
  "node_count": 12,
  "relationship_count": 18,
  "labels": {"LintResult": 4, "TestResult": 2},
  "relationship_types": {"OWNS": 3},
  "average_degree": 2.1
}
```

### POST `/lint_code`

Body:

```json
{
  "code": "def add(a, b):\n    return a + b\n",
  "language": "python"
}
```

Response:

```json
{
  "id": "8d6e59a7-...",
  "code_hash": "...",
  "functions": ["add"],
  "classes": [],
  "imports": [],
  "complexity": 1.0,
  "linter_exit_code": 0,
  "linter_output": ""
}
```

### POST `/run_tests`

Requires auth.

```json
{
  "code": "import pytest\n\ndef test_math():\n    assert 1 + 1 == 2\n",
  "timeout_seconds": 15.0
}
```

Response:

```json
{
  "id": "f0d1...",
  "framework": "pytest",
  "return_code": 0,
  "stdout": "1 passed in 0.05s",
  "stderr": "",
  "duration_seconds": 0.08
}
```

### POST `/graph_upsert`

Requires auth. Creates/updates nodes & relationships.

```json
{
  "nodes": [
    {"key": "User:1", "labels": ["User"], "properties": {"name": "Ada"}}
  ],
  "relationships": [
    {"start": "User:1", "end": "Repo:1", "type": "OWNS", "properties": {"since": 2025}}
  ]
}
```

Response is metrics payload identical to `/metrics`.

### POST `/graph_query`

Read-only Cypher query (mutating clauses rejected).

```json
{
  "cypher": "MATCH (u:User)-[r:OWNS]->(repo) RETURN u, repo",
  "parameters": {}
}
```

Response:

```json
{
  "results": [
    {
      "u": {"id": "123", "labels": ["User"], "properties": {"name": "Ada"}},
      "repo": {"id": "234", "labels": ["Repository"], "properties": {"name": "Ultimate"}}
    }
  ]
}
```

### POST `/execute_code`

Requires auth. Executes Python snippet in sandbox.

```json
{
  "code": "print('hello world')",
  "language": "python",
  "timeout_seconds": 8.0
}
```

Response:

```json
{
  "id": "1d2c...",
  "return_code": 0,
  "stdout": "hello world\n",
  "stderr": "",
  "duration_seconds": 0.02
}
```

### POST `/generate_code`

Requires auth. Uses Jinja2 template rendering.

```json
{
  "template": "def {{ name }}():\n    return {{ value }}\n",
  "context": {"name": "ultimate", "value": 42},
  "language": "python"
}
```

Response:

```json
{
  "id": "9aa7...",
  "language": "python",
  "output": "def ultimate():\n    return 42\n"
}
```

## MCP Endpoint

- `POST /mcp/...`: Handled by FastMCP streamable HTTP transport. Tools available:
  - `lint_code`
  - `run_tests`
  - `graph_upsert`
  - `graph_query`
  - `execute_code`
  - `generate_code`

Use an MCP-compatible client (e.g., `fastmcp.Client`) or OpenAI Agent integration.
