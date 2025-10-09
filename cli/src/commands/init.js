import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { createRequire } from 'module';

import chalk from 'chalk';
import ora from 'ora';

import { ensureDocker } from '../utils/docker.js';
import { ensureProjectDirectory, writeFile } from '../utils/fs.js';

const require = createRequire(import.meta.url);
const { version: cliVersion } = require('../../package.json');

const DEFAULT_BACKEND_IMAGE = 'ghcr.io/ultimate-mcp/ultimate-mcp-backend:latest';
const DEFAULT_FRONTEND_IMAGE = 'ghcr.io/ultimate-mcp/ultimate-mcp-frontend:latest';

function generateSecret(prefix, bytes = 24) {
  return `${prefix}_${crypto.randomBytes(bytes).toString('hex')}`;
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
      - "7474:7474"
      - "7687:7687"
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
      ALLOWED_ORIGINS: http://localhost:3000
    ports:
      - "8000:8000"
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
      - "3000:8080"
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

function buildEnvContents({ authToken, secretKey, neo4jPassword, backendImage, frontendImage }) {
  return `# Generated ${new Date().toISOString()}
# Ultimate MCP deployment secrets
AUTH_TOKEN=${authToken}
SECRET_KEY=${secretKey}
NEO4J_PASSWORD=${neo4jPassword}
ALLOWED_ORIGINS=http://localhost:3000
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

function buildProjectReadme({ localImages }) {
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

  const secrets = {
    authToken: generateSecret('umcp_auth'),
    secretKey: generateSecret('umcp_secret'),
    neo4jPassword: generateSecret('neo4j'),
  };

  const composeContents = buildComposeContents({ localImages });
  const envContents = buildEnvContents({ ...secrets, backendImage, frontendImage });
  const readmeContents = buildProjectReadme({ localImages });

  await writeFile(targetDir, 'docker-compose.yml', composeContents);
  await writeFile(targetDir, '.env', envContents, { mode: 0o600 });
  await writeFile(targetDir, '.gitignore', buildGitignore());
  await writeFile(targetDir, 'README.md', readmeContents);

  const config = {
    createdAt: new Date().toISOString(),
    backendImage,
    frontendImage,
    localImages,
    machine: os.hostname(),
    cliVersion,
  };
  await writeFile(targetDir, 'ultimate-mcp.json', `${JSON.stringify(config, null, 2)}\n`);

  spinner.succeed('Deployment directory ready');

  console.log(`\n${chalk.green('Next steps:')}`);
  console.log(`  cd ${path.relative(process.cwd(), targetDir) || '.'}`);
  console.log('  npx @ultimate-mcp/cli start');
  console.log('\nDashboard: http://localhost:3000');
  console.log('API docs: http://localhost:8000/docs');
  console.log(`Secrets stored in ${path.join(targetDir, '.env')} (permissions ${chalk.gray('0600')})`);
  if (localImages) {
    console.log(chalk.yellow('\nLocal image mode enabled. Ensure backend/ and frontend/ sources exist beside this directory before running start.'));
  }
  console.log('\n');
}
