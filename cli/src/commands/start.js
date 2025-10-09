import ora from 'ora';
import chalk from 'chalk';
import path from 'node:path';

import { ensureDocker, runCompose } from '../utils/docker.js';
import { resolveProjectDirectory, logProjectHeading } from '../utils/project.js';
import { waitForEndpoint } from '../utils/http.js';
import { readProjectEnv } from '../utils/env.js';
import { DEFAULT_PORTS } from '../config/defaults.js';

function resolvePort(value, fallback) {
  if (!value) {
    return fallback;
  }
  const numeric = Number.parseInt(value, 10);
  if (!Number.isInteger(numeric) || numeric <= 0 || numeric > 65535) {
    console.warn(`Invalid port value "${value}" in .env – falling back to ${fallback}.`);
    return fallback;
  }
  return String(numeric);
}

export async function startProject(options) {
  ensureDocker();

  const projectDir = await resolveProjectDirectory(options.project);
  logProjectHeading(`Starting Ultimate MCP in ${projectDir}`);

  const envVars = await readProjectEnv(projectDir);
  const backendPort = resolvePort(envVars.BACKEND_HTTP_PORT, DEFAULT_PORTS.backend);
  const frontendPort = resolvePort(envVars.FRONTEND_HTTP_PORT, DEFAULT_PORTS.frontend);
  const backendHealthUrl = `http://localhost:${backendPort}/health`;
  const backendDocsUrl = `http://localhost:${backendPort}/docs`;
  const frontendUrl = `http://localhost:${frontendPort}`;

  const spinner = ora('Running docker compose up -d').start();
  try {
    await runCompose(['up', '-d'], { cwd: projectDir });
    spinner.succeed('Containers launched');
  } catch (error) {
    spinner.fail('Failed to start containers');
    throw error;
  }

  if (!options.detached) {
    const healthSpinner = ora('Waiting for backend health check').start();
    try {
      await waitForEndpoint(backendHealthUrl, { timeoutMs: 180000, intervalMs: 4000 });
      healthSpinner.succeed(`Backend healthy at ${backendHealthUrl}`);
    } catch (error) {
      healthSpinner.fail('Backend health check failed – the stack may still be starting');
      console.warn(chalk.yellow(error.message));
    }
  } else {
    console.log(chalk.gray('Detached mode enabled – skipping health checks.'));
  }

  console.log(`\n${chalk.green('Services available:')}`);
  console.log(`  API docs:      ${backendDocsUrl}`);
  console.log(`  Health probe:  ${backendHealthUrl}`);
  console.log(`  Frontend UI:   ${frontendUrl}`);
  console.log(`\n${chalk.gray('Project directory:')} ${projectDir}`);
  console.log(`Compose file: ${path.join(projectDir, 'docker-compose.yml')}`);
  console.log('\nUse `ultimate-mcp stop` to shut everything down.');
}
