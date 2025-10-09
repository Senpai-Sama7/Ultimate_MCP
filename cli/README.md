# Ultimate MCP CLI

This package provides a cross-platform installer and runtime manager for the Ultimate MCP stack.

```bash
npx @ultimate-mcp/cli init my-ultimate-mcp
cd my-ultimate-mcp
npx @ultimate-mcp/cli start
```

## Commands

- `ultimate-mcp init [directory]` – scaffold a deployment directory, generate secrets, and write a Docker Compose stack.
- `ultimate-mcp start` – launch the stack via Docker Compose and wait for the backend health check.
- `ultimate-mcp stop` – stop all containers and clean up resources.
- `ultimate-mcp upgrade` – pull the latest images and restart the stack.

The CLI stores generated secrets in `.env` (chmod `0600`) and uses Docker Compose for easy orchestration. The default configuration pulls published backend/frontend images; add `--local-images` when working directly from the source tree and you prefer local builds.
