# Security Guide

## Authentication

- Bearer tokens secure all mutating endpoints (`/run_tests`, `/execute_code`, `/generate_code`, `/graph_upsert`).
- Token value supplied via `AUTH_TOKEN` environment variable and forwarded by clients with `Authorization: Bearer <token>`.
- Rotation: update `AUTH_TOKEN`, redeploy backend, and communicate the new token to trusted clients. Tokens are not stored in the database.

## Rate Limiting

- Powered by SlowAPI with Redis-free in-memory limits.
- Default limit is `RATE_LIMIT_RPS` requests per second per IP (10 by default).
- Bursts beyond the configured rate return HTTP `429`.

## Request Hardening

- Maximum body size enforced via middleware (`max_request_bytes`). Oversized requests trigger HTTP `413`.
- Strict CORS allow-list derived from `ALLOWED_ORIGINS`.
- Security headers appended to every response:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Content-Security-Policy: default-src 'self'`
- Request IDs (`X-Request-Id`) generated when absent and surfaced in both logs and responses.

## Execution Safety

- Code execution and testing tools run inside ephemeral subprocesses using the project interpreter.
- Static safety checks block dangerous imports (`os`, `subprocess`, etc.) and builtins (`eval`, `exec`).
- Execution timeout configurable per request (default 8 seconds).

## Graph Safety

- Cypher queries validated to forbid mutating clauses (`DELETE`, `DETACH`, `CALL db.*`, semicolons).
- Nodes and relationship labels validated against strict regex to avoid injection.

## Container Security

- Backend container runs as non-root `appuser`, drops all Linux capabilities, and exposes only port 8000.
- Frontend container uses `nginxinc/nginx-unprivileged` on port 8080; health endpoint served at `/healthz`.
- Compose applies `no-new-privileges` to all services.

## Secrets & Environment

Required environment variables:

| Variable | Purpose | Example |
| --- | --- | --- |
| `NEO4J_URI` | Bolt URI for Neo4j | `bolt://neo4j:7687` |
| `NEO4J_USER` / `NEO4J_PASSWORD` | Database credentials | `neo4j` / `password123` |
| `AUTH_TOKEN` | Bearer token for write endpoints | `change-me` |
| `ALLOWED_ORIGINS` | Comma-delimited origin list | `http://localhost:3000` |
| `RATE_LIMIT_RPS` | Requests per second per IP | `10` |

Store secrets in `.env` during local development; use secret managers (e.g., GitHub Actions secrets, Vault) in production.

## Logging & Monitoring

- Structured JSON logging via Structlog; includes method, path, status, request ID.
- `/metrics` endpoint exposes basic graph counts. Integrate with custom monitoring by invoking this endpoint on schedule.
- Neo4j container exposes standard logs under the `neo4j_logs` volume.

## Dependency Management

- Backend pinned to compatible versions (Python 3.13). CI installs with `pip --no-cache-dir` and fails on dependency conflicts.
- Frontend uses `npm ci` for reproducible installs and ESLint for static analysis.

## Incident Response Checklist

1. Rotate `AUTH_TOKEN`, redeploy backend.
2. Review logs for suspicious request IDs and originating IPs.
3. Snapshot Neo4j data via `neo4j-admin dump` (see operations guide) before applying restorative changes.
4. Audit Docker images with optional scanners (e.g., Trivy).
