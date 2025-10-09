#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
COMPOSE_FILE="$PROJECT_ROOT/deployment/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env.deploy"
PROJECT_NAME=${PROJECT_NAME:-ultimate-mcp}
BACKEND_IMAGE_DEFAULT="ghcr.io/ultimate-mcp/ultimate-mcp-backend:latest"
FRONTEND_IMAGE_DEFAULT="ghcr.io/ultimate-mcp/ultimate-mcp-frontend:latest"

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required but not installed." >&2
  exit 1
}

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Docker Compose plugin is required." >&2
  exit 1
fi

generate_secret() {
  local bytes="$1"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  else
    python3 - "$bytes" <<'PY'
import secrets
import sys
n = int(sys.argv[1])
print(secrets.token_hex(n))
PY
  fi
}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Generating $ENV_FILE with random secrets"
  AUTH_TOKEN="$(generate_secret 24)"
  SECRET_KEY="$(generate_secret 32)"
  NEO4J_PASSWORD="$(generate_secret 24)"
  cat >"$ENV_FILE" <<EOF2
# Generated $(date --iso-8601=seconds)
AUTH_TOKEN=$AUTH_TOKEN
SECRET_KEY=$SECRET_KEY
NEO4J_PASSWORD=$NEO4J_PASSWORD
UMCP_BACKEND_IMAGE=${UMCP_BACKEND_IMAGE:-$BACKEND_IMAGE_DEFAULT}
UMCP_FRONTEND_IMAGE=${UMCP_FRONTEND_IMAGE:-$FRONTEND_IMAGE_DEFAULT}
ALLOWED_ORIGINS=http://localhost:3000
EOF2
  chmod 600 "$ENV_FILE"
else
  echo "Using existing $ENV_FILE"
fi

export AUTH_TOKEN=$(grep '^AUTH_TOKEN=' "$ENV_FILE" | cut -d= -f2-)
export SECRET_KEY=$(grep '^SECRET_KEY=' "$ENV_FILE" | cut -d= -f2-)
export NEO4J_PASSWORD=$(grep '^NEO4J_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)
export UMCP_BACKEND_IMAGE=$(grep '^UMCP_BACKEND_IMAGE=' "$ENV_FILE" | cut -d= -f2-)
export UMCP_FRONTEND_IMAGE=$(grep '^UMCP_FRONTEND_IMAGE=' "$ENV_FILE" | cut -d= -f2-)

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose file not found at $COMPOSE_FILE" >&2
  exit 1
fi

${COMPOSE_CMD[@]} --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up --build -d

echo "\nUltimate MCP is starting..."
echo "UI:      http://localhost:3000"
echo "API:     http://localhost:8000/docs"
echo "Health:  http://localhost:8000/health"
echo "Secrets: $ENV_FILE"
