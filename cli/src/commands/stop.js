import ora from 'ora';
import chalk from 'chalk';

import { ensureDocker, runCompose } from '../utils/docker.js';
import { resolveProjectDirectory, logProjectHeading } from '../utils/project.js';

export async function stopProject(options) {
  ensureDocker();

  const projectDir = await resolveProjectDirectory(options.project);
  logProjectHeading(`Stopping Ultimate MCP in ${projectDir}`);

  const spinner = ora('Running docker compose down').start();
  try {
    await runCompose(['down'], { cwd: projectDir });
    spinner.succeed('Containers stopped and network removed');
  } catch (error) {
    spinner.fail('Failed to stop containers');
    throw error;
  }

  console.log(chalk.green('\nStack stopped successfully.'));
}
