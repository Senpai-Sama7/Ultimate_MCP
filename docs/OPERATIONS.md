# Operations Manual

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `NEO4J_URI` | Bolt connection string | `bolt://neo4j:7687` |
| `NEO4J_USER` | Database username | `neo4j` |
| `NEO4J_PASSWORD` | Database password | `password123` |
| `NEO4J_DATABASE` | Target database | `neo4j` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed origins | `http://localhost:3000` |
| `AUTH_TOKEN` | Bearer token for protected endpoints | `change-me` |
| `RATE_LIMIT_RPS` | Requests per second per IP | `10` |

Populate these in `.env` for local development or in deployment secrets.

## Local Development

```bash
# install dependencies
scripts/setup.py

# activate virtualenv
source backend/.venv/bin/activate

# run backend
uvicorn mcp_server.server:app --reload

# run frontend
yarn? -> npm run dev (requires VITE_BACKEND_URL)
npm run dev -- --host 0.0.0.0 --port 3000
```

## Docker Compose

```bash
cp .env.example .env
# optionally edit AUTH_TOKEN and other secrets

# build and start
docker compose -f deployment/docker-compose.yml up --build

# tear down
docker compose -f deployment/docker-compose.yml down
```

### Service Ports

- Backend API: `http://localhost:8000`
- Frontend UI: `http://localhost:3000`
- Neo4j Browser: `http://localhost:7474`

## Logging

- Backend emits JSON logs to stdout; include `request_id`, `method`, `path`, `status_code`.
- Docker Compose logs accessible via `docker compose logs <service>`.
- Neo4j logs stored in `neo4j_logs` volume; inspect via `docker compose exec neo4j tail -f /logs/neo4j.log`.

## Metrics & Health

- `GET /health`: checks API and Neo4j connectivity.
- `GET /metrics`: returns node/relationship counts and degree averages.
- Frontend fetches metrics every 10 seconds using `useMCPClient` hook.

## Backups

1. Stop writes (disable tooling or set rate limit to zero).
2. Run `docker compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups`.
3. Copy dump from volume (`neo4j_data`).

For managed Neo4j services, leverage built-in backup utilities.

## Restoring Neo4j

1. Stop stack: `docker compose down`.
2. Clear data volume or move aside.
3. Start Neo4j container, copy dump, run `neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true`.
4. Restart stack.

## Monitoring Recommendations

- Schedule smoke test (`scripts/smoke_test.py`) via cron/GitHub Actions to verify endpoints.
- Collect request logs (e.g., ship to ELK stack) and monitor rate-limit exceedances.
- Track Neo4j resource usage (CPU, memory) via Docker metrics or external monitoring.

## Upgrades

- **Backend dependencies**: adjust `backend/requirements.txt`, run `scripts/setup.py`, run CI.
- **Frontend dependencies**: update `package.json`, run `npm ci`, `npm run lint`, `npm run build`.
- **Docker images**: `docker compose build` rebuilds from latest base images.
- **Schema**: update `neo4j_client._create_constraints` to add indexes or constraints.
