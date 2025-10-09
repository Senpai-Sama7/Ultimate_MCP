import ora from 'ora';
import chalk from 'chalk';

import { ensureDocker, runCompose } from '../utils/docker.js';
import { resolveProjectDirectory, logProjectHeading } from '../utils/project.js';

export async function upgradeProject(options) {
  ensureDocker();

  const projectDir = await resolveProjectDirectory(options.project);
  logProjectHeading(`Upgrading Ultimate MCP in ${projectDir}`);

  if (!options.skipPull) {
    const pullSpinner = ora('Pulling latest container images').start();
    try {
      await runCompose(['pull'], { cwd: projectDir });
      pullSpinner.succeed('Images pulled');
    } catch (error) {
      pullSpinner.fail('Failed to pull images');
      throw error;
    }
  } else {
    console.log(chalk.gray('Skipping image pull as requested.'));
  }

  const restartSpinner = ora('Restarting stack').start();
  try {
    await runCompose(['up', '-d'], { cwd: projectDir });
    restartSpinner.succeed('Stack running with latest images');
  } catch (error) {
    restartSpinner.fail('Failed to restart stack');
    throw error;
  }

  console.log(chalk.green('\nUpgrade complete.')); 
}
