# Repository Guidelines

## Project Structure & Module Organization
- `backend/` contains the FastAPI + FastMCP app; key modules live under `mcp_server/` and agent bridges in `agent_integration/`.
- `backend/tests/` mirrors runtime modules and shares Neo4j fixtures via `conftest.py`; extend them when adding endpoints or tools.
- `frontend/` hosts the React + Vite client (`src/components`, `src/hooks`, `src/services`) with global styles in `src/styles.css`.
- `deployment/docker-compose.yml` brings up Neo4j, backend, and frontend; `scripts/` provides local setup and smoke-test automation, while `docs/` captures architecture decisions referenced during reviews.

## Build, Test, and Development Commands
- `python scripts/setup.py [--ci]` provisions the backend virtualenv and installs frontend packages.
- `source backend/.venv/bin/activate && uvicorn mcp_server.enhanced_server:app --reload --host 0.0.0.0 --port 8000` runs the API (expects Neo4j at `bolt://localhost:7687`).
- `cd frontend && npm run dev` starts the SPA pointing to `http://localhost:8000`; use `npm run build` before packaging.
- `docker compose -f deployment/docker-compose.yml up --build` runs the full stack with production-like hardening, followed by `python scripts/smoke_test.py --base-url http://localhost:8000` for verification.
- `./deploy.sh` builds/pulls images, writes `.env.deploy`, and brings the stack up with Docker Compose; use the generated command in the README to tear it back down.
- `npx @ultimate-mcp/cli init demo && cd demo && npx @ultimate-mcp/cli start` spins up a clean deployment using published Docker images; apply `--backend-port/--frontend-port` overrides from v0.1.1 when local ports are busy.
- `python demo/full_demo.py --auth-token $(grep '^AUTH_TOKEN=' .env.deploy | cut -d= -f2-)` exercises lint, execute, tests, graph upsert/query, code generation, and metrics in one run—use it for “show me it works” demos.
- Track outstanding hardening work in `docs/SECURITY_BACKLOG.md` and link issues accordingly.

## Coding Style & Naming Conventions
- Python uses 4-space indentation, type hints, and a 100-character limit enforced by `black` and `ruff`; keep files in `snake_case` and classes like tools in PascalCase.
- Run `backend/.venv/bin/ruff check backend` and `backend/.venv/bin/mypy backend` prior to commits; fix warnings instead of ignoring them.
- Frontend code favors functional React components in PascalCase, camelCase hooks/utilities, and `npm run lint` (ESLint + TypeScript) before pushing.

## Testing Guidelines
- Execute `backend/.venv/bin/pytest backend/tests --cov=backend/mcp_server --cov=backend/agent_integration --cov-fail-under=80`; CI enforces the same threshold and produces `coverage.xml`.
- Reuse fixtures in `backend/tests/conftest.py` for Neo4j connectivity and mark async checks with `@pytest.mark.asyncio`.
- Document the exact validation commands (`pytest`, `ruff`, `mypy`, `npm run lint`) in PRs and attach additional artifacts when integration behavior changes.

## Commit & Pull Request Guidelines
- Write imperative commit titles; optional emojis may precede the scope as seen in `git log` (`🚀 Initial release: …`).
- Consolidate related backend/frontend/infrastructure edits into cohesive commits and squash incidental fixups before pushing.
- PRs require a brief summary, linked issue, testing evidence, and UI screenshots when React work alters the UX; wait for CI to pass before requesting review.
- Before tagging a release, bump `cli/package.json`, ensure `NPM_TOKEN` is present, then push `vX.Y.Z`; `.github/workflows/release.yml` publishes Docker images and the npm CLI automatically. For emergency patches, run `npm publish --access public --otp <code>` from `cli/` after the version bump so the registry reflects the new release immediately.

## Security & Configuration Tips
- Copy `.env.example`, set unique values for `AUTH_TOKEN` and Neo4j credentials, and keep actual secrets out of version control.
- Override Docker credentials via environment variables or a local `.env`; new MCP tools must invoke `EnhancedSecurityManager` utilities to inherit sandbox and rate-limit policies.
