import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf-8',
    stdio: 'pipe',
    ...options,
  });
  if (result.status !== 0) {
    console.error(result.stdout);
    console.error(result.stderr);
    throw new Error(`${command} ${args.join(' ')} failed with code ${result.status}`);
  }
  return result.stdout;
}

function main() {
  const tempDir = mkdtempSync(path.join(tmpdir(), 'umcp-smoke-'));
  try {
    const overrides = {
      backendPort: '8100',
      frontendPort: '3200',
      neo4jHttpPort: '7575',
      neo4jBoltPort: '7787',
      neo4jPassword: 'Neo4jPass1234',
    };

    run('node', [
      'bin/ultimate-mcp.js',
      'init',
      tempDir,
      '--force',
      '--backend-port', overrides.backendPort,
      '--frontend-port', overrides.frontendPort,
      '--neo4j-http-port', overrides.neo4jHttpPort,
      '--neo4j-bolt-port', overrides.neo4jBoltPort,
      '--neo4j-password', overrides.neo4jPassword,
    ], {
      cwd: path.resolve(__dirname, '..'),
    });

    const composePath = path.join(tempDir, 'docker-compose.yml');
    const composeContents = readFileSync(composePath, 'utf-8');
    if (!composeContents.includes('${UMCP_BACKEND_IMAGE}')) {
      throw new Error('compose file missing backend image reference placeholder');
    }
    if (!composeContents.includes('${BACKEND_HTTP_PORT:-8000}:8000')) {
      throw new Error('compose file missing backend port interpolation');
    }
    if (!composeContents.includes('${FRONTEND_HTTP_PORT:-3000}:8080')) {
      throw new Error('compose file missing frontend port interpolation');
    }

    const envPath = path.join(tempDir, '.env');
    const envContents = readFileSync(envPath, 'utf-8');
    if (!envContents.includes('AUTH_TOKEN=')) {
      throw new Error('.env missing AUTH_TOKEN');
    }
    if (!envContents.includes('UMCP_BACKEND_IMAGE=ghcr.io/ultimate-mcp/ultimate-mcp-backend:latest')) {
      throw new Error('.env missing backend image default');
    }
    if (!envContents.includes(`BACKEND_HTTP_PORT=${overrides.backendPort}`)) {
      throw new Error('.env missing backend port override');
    }
    if (!envContents.includes(`FRONTEND_HTTP_PORT=${overrides.frontendPort}`)) {
      throw new Error('.env missing frontend port override');
    }
    if (!envContents.includes(`NEO4J_HTTP_PORT=${overrides.neo4jHttpPort}`)) {
      throw new Error('.env missing neo4j http port override');
    }
    if (!envContents.includes(`NEO4J_BOLT_PORT=${overrides.neo4jBoltPort}`)) {
      throw new Error('.env missing neo4j bolt port override');
    }
    if (!envContents.includes(`NEO4J_PASSWORD=${overrides.neo4jPassword}`)) {
      throw new Error('.env missing overridden neo4j password');
    }

    const projectConfigPath = path.join(tempDir, 'ultimate-mcp.json');
    const projectConfig = JSON.parse(readFileSync(projectConfigPath, 'utf-8'));
    if (projectConfig.ports.backend !== overrides.backendPort) {
      throw new Error('project config missing backend port');
    }
    if (projectConfig.ports.frontend !== overrides.frontendPort) {
      throw new Error('project config missing frontend port');
    }

    console.log('Smoke test passed.');
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

main();
