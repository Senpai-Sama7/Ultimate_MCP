# Repository Guidelines for Agentic Coding Agents

## Project Structure & Module Organization
`backend/` contains the FastAPI MCP service; core runtime lives in `mcp_server/` and cross-agent glue in `agent_integration/`. Tests mirror runtime code under `backend/tests/` with fixtures in `conftest.py`. `frontend/` is the Vite + React client (`src/components`, `src/hooks`, `src/services`). `cli/` ships the Node installer via `bin/ultimate-mcp.js` and supporting modules in `src/`. Refer to `deployment/` for Compose assets, `scripts/` for automation, `docs/` for architecture notes, and `demo/full_demo.py` for the supervised walk-through.

## Build, Test, and Development Commands
- Setup: `python scripts/setup.py [--ci]` (prepares backend/.venv and installs Node deps)
- Run API: `source backend/.venv/bin/activate && uvicorn mcp_server.enhanced_server:app --reload --port 8000 --host 0.0.0.0`
- Run UI: `cd frontend && npm run dev`
- Run tests: `backend/.venv/bin/pytest backend/tests`
- Run single test: `backend/.venv/bin/pytest backend/tests/test_file.py::test_function_name`
- Lint Python: `backend/.venv/bin/ruff check backend`
- Type check Python: `backend/.venv/bin/mypy backend`
- Lint frontend: `cd frontend && npm run lint`

## Coding Style & Naming Conventions
- Python: 4-space indentation, full type hints, 100-char limit (enforced by black/ruff)
- Naming: snake_case for modules/functions, PascalCase for classes, descriptive MCP tool IDs
- Error handling: Use specific exceptions, log appropriately, don't suppress silently
- Imports: Standard library first, then third-party, then local; alphabetical within groups
- Frontend: ESLint enforced; React components in PascalCase, hooks/utilities in camelCase

## Testing Guidelines
- Mandatory coverage: `backend/.venv/bin/pytest backend/tests --cov=backend/mcp_server --cov=backend/agent_integration --cov-report=term-missing`
- Backend tests spin up Neo4j test container via Docker; ensure Docker daemon is running
- Validate workflow: `python demo/full_demo.py --base-url http://localhost:8000 --auth-token <token>` then `python scripts/smoke_test.py`
- CLI/UI updates: Run `cd cli && npm run smoke` and record manual checks

## Commit & Pull Request Guidelines
- Commits: Imperative one-line subjects (e.g., `Refine cache eviction`) with optional context
- Group related changes per commit; avoid mixing generated assets with source updates
- PRs: Include summary, linked issue, and exact validation commands run

## Security & Configuration
- Copy `.env.example` to `.env.deploy`, set unique `AUTH_TOKEN` and Neo4j secrets
- Route new tools/jobs through `mcp_server/enhanced_security` helpers for consistent rate limiting and audit logging