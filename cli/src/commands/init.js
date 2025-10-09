import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { createRequire } from 'module';

import chalk from 'chalk';
import ora from 'ora';

import { ensureDocker } from '../utils/docker.js';
import { ensureProjectDirectory, writeFile } from '../utils/fs.js';
import { DEFAULT_PORTS } from '../config/defaults.js';

const require = createRequire(import.meta.url);
const { version: cliVersion } = require('../../package.json');

const DEFAULT_BACKEND_IMAGE = 'ghcr.io/ultimate-mcp/ultimate-mcp-backend:latest';
const DEFAULT_FRONTEND_IMAGE = 'ghcr.io/ultimate-mcp/ultimate-mcp-frontend:latest';

function generateSecret(prefix, bytes = 24) {
  return `${prefix}_${crypto.randomBytes(bytes).toString('hex')}`;
}

function validatePort(value, label) {
  const numeric = Number.parseInt(value, 10);
  if (!Number.isInteger(numeric) || numeric <= 0 || numeric > 65535) {
    throw new Error(`${label} must be a valid TCP port (1-65535). Received "${value}".`);
  }
  return String(numeric);
}

function resolvePorts(options) {
  return {
    neo4jHttp: options.neo4jHttpPort ? validatePort(options.neo4jHttpPort, 'neo4j-http-port') : DEFAULT_PORTS.neo4jHttp,
    neo4jBolt: options.neo4jBoltPort ? validatePort(options.neo4jBoltPort, 'neo4j-bolt-port') : DEFAULT_PORTS.neo4jBolt,
    backend: options.backendPort ? validatePort(options.backendPort, 'backend-port') : DEFAULT_PORTS.backend,
    frontend: options.frontendPort ? validatePort(options.frontendPort, 'frontend-port') : DEFAULT_PORTS.frontend,
  };
}

function ensureNeo4jPassword(password) {
  if (password.length < 12) {
    throw new Error('Neo4j password must be at least 12 characters for the default password policy.');
  }
  if (!/[a-zA-Z]/.test(password) || !/[0-9]/.test(password)) {
    throw new Error('Neo4j password must include both letters and numbers.');
  }
  if (/\s/.test(password)) {
    throw new Error('Neo4j password cannot contain whitespace characters.');
  }
  return password;
}

function buildComposeContents({ localImages }) {
  const backendSection = localImages
    ? `    build:\n      context: ./backend\n      dockerfile: Dockerfile\n`
    : '    image: ${UMCP_BACKEND_IMAGE}\n';

  const frontendSection = localImages
    ? `    build:\n      context: ./frontend\n      dockerfile: Dockerfile\n`
    : '    image: ${UMCP_FRONTEND_IMAGE}\n';

  return `version: "3.9"

services:
  neo4j:
    image: neo4j:5.23.0
    restart: unless-stopped
    environment:
      - NEO4J_AUTH=neo4j:${'${NEO4J_PASSWORD}'}
    ports:
      - "${'${NEO4J_HTTP_PORT:-7474}'}:7474"
      - "${'${NEO4J_BOLT_PORT:-7687}'}:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p ${'${NEO4J_PASSWORD}'} 'RETURN 1'"]
      interval: 15s
      timeout: 10s
      retries: 10
    security_opt:
      - no-new-privileges:true

  backend:
${backendSection}    restart: unless-stopped
    env_file:
      - .env
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${'${NEO4J_PASSWORD}'}
      AUTH_TOKEN: ${'${AUTH_TOKEN}'}
      ALLOWED_ORIGINS: http://localhost:${'${FRONTEND_HTTP_PORT:-3000}'}
    ports:
      - "${'${BACKEND_HTTP_PORT:-8000}'}:8000"
    depends_on:
      neo4j:
        condition: service_healthy
    security_opt:
      - no-new-privileges:true

  frontend:
${frontendSection}    restart: unless-stopped
    environment:
      VITE_BACKEND_URL: http://backend:8000
    ports:
      - "${'${FRONTEND_HTTP_PORT:-3000}'}:8080"
    depends_on:
      backend:
        condition: service_started
    security_opt:
      - no-new-privileges:true

volumes:
  neo4j_data:
  neo4j_logs:
`;
}

function buildEnvContents({ authToken, secretKey, neo4jPassword, backendImage, frontendImage, ports }) {
  return `# Generated ${new Date().toISOString()}
# Ultimate MCP deployment secrets
AUTH_TOKEN=${authToken}
SECRET_KEY=${secretKey}
NEO4J_PASSWORD=${neo4jPassword}
NEO4J_HTTP_PORT=${ports.neo4jHttp}
NEO4J_BOLT_PORT=${ports.neo4jBolt}
BACKEND_HTTP_PORT=${ports.backend}
FRONTEND_HTTP_PORT=${ports.frontend}
ALLOWED_ORIGINS=http://localhost:${ports.frontend}
UMCP_BACKEND_IMAGE=${backendImage}
UMCP_FRONTEND_IMAGE=${frontendImage}
`;
}

function buildGitignore() {
  return `# Ultimate MCP deployment
.env
neo4j_data/
neo4j_logs/
`;
}

function buildProjectReadme({ localImages, ports }) {
  const backendUrl = `http://localhost:${ports.backend}`;
  const frontendUrl = `http://localhost:${ports.frontend}`;
  const dockerNote = localImages
    ? `The compose file is configured to build backend/frontend images from local sources.
Ensure the Ultimate MCP repository is checked out with \`backend\` and \`frontend\` folders beside this deployment directory.`
    : 'Docker images are pulled from the published registry. Override via `UMCP_BACKEND_IMAGE` / `UMCP_FRONTEND_IMAGE` in `.env` if needed.';

  return `# Ultimate MCP Deployment

This directory was created by \`ultimate-mcp init\`. Use the commands below to manage the stack:

- \`npx @ultimate-mcp/cli start\` – launch the services
- \`npx @ultimate-mcp/cli stop\` – stop all services
- \`npx @ultimate-mcp/cli upgrade\` – pull the latest images and restart

${dockerNote}

Services:
- Backend API: ${backendUrl}
- Frontend UI: ${frontendUrl}
`;
}

export async function initProject(directory = 'ultimate-mcp', options) {
  ensureDocker();

  const spinner = ora('Scaffolding Ultimate MCP deployment').start();

  const targetDir = path.resolve(process.cwd(), directory);
  await ensureProjectDirectory(targetDir, { force: options.force });

  const backendImage = options.backendImage ?? DEFAULT_BACKEND_IMAGE;
  const frontendImage = options.frontendImage ?? DEFAULT_FRONTEND_IMAGE;
  const localImages = Boolean(options.localImages);
  const ports = resolvePorts(options);

  const neo4jPassword = ensureNeo4jPassword(
    options.neo4jPassword ?? generateSecret('neo4j'),
  );

  const secrets = {
    authToken: generateSecret('umcp_auth'),
    secretKey: generateSecret('umcp_secret'),
    neo4jPassword,
  };

  const composeContents = buildComposeContents({ localImages });
  const envContents = buildEnvContents({ ...secrets, backendImage, frontendImage, ports });
  const readmeContents = buildProjectReadme({ localImages, ports });

  await writeFile(targetDir, 'docker-compose.yml', composeContents);
  await writeFile(targetDir, '.env', envContents, { mode: 0o600 });
  await writeFile(targetDir, '.gitignore', buildGitignore());
  await writeFile(targetDir, 'README.md', readmeContents);

  const config = {
    createdAt: new Date().toISOString(),
    backendImage,
    frontendImage,
    localImages,
    ports,
    machine: os.hostname(),
    cliVersion,
  };
  await writeFile(targetDir, 'ultimate-mcp.json', `${JSON.stringify(config, null, 2)}\n`);

  spinner.succeed('Deployment directory ready');

  console.log(`\n${chalk.green('Next steps:')}`);
  console.log(`  cd ${path.relative(process.cwd(), targetDir) || '.'}`);
  console.log('  npx @ultimate-mcp/cli start');
  console.log(`\nDashboard: http://localhost:${ports.frontend}`);
  console.log(`API docs: http://localhost:${ports.backend}/docs`);
  console.log(`Secrets stored in ${path.join(targetDir, '.env')} (permissions ${chalk.gray('0600')})`);
  if (localImages) {
    console.log(chalk.yellow('\nLocal image mode enabled. Ensure backend/ and frontend/ sources exist beside this directory before running start.'));
  }
  console.log('\n');
}
