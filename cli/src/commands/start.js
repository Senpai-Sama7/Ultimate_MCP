import ora from 'ora';
import chalk from 'chalk';
import path from 'node:path';

import { ensureDocker, runCompose } from '../utils/docker.js';
import { resolveProjectDirectory, logProjectHeading } from '../utils/project.js';
import { waitForEndpoint } from '../utils/http.js';

export async function startProject(options) {
  ensureDocker();

  const projectDir = await resolveProjectDirectory(options.project);
  logProjectHeading(`Starting Ultimate MCP in ${projectDir}`);

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
      await waitForEndpoint('http://localhost:8000/health', { timeoutMs: 180000, intervalMs: 4000 });
      healthSpinner.succeed('Backend healthy at http://localhost:8000/health');
    } catch (error) {
      healthSpinner.fail('Backend health check failed – the stack may still be starting');
      console.warn(chalk.yellow(error.message));
    }
  } else {
    console.log(chalk.gray('Detached mode enabled – skipping health checks.'));
  }

  console.log(`\n${chalk.green('Services available:')}`);
  console.log('  API docs:      http://localhost:8000/docs');
  console.log('  Health probe:  http://localhost:8000/health');
  console.log('  Frontend UI:   http://localhost:3000');
  console.log(`\n${chalk.gray('Project directory:')} ${projectDir}`);
  console.log(`Compose file: ${path.join(projectDir, 'docker-compose.yml')}`);
  console.log('\nUse `ultimate-mcp stop` to shut everything down.');
}
