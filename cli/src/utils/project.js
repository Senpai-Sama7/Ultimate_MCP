import path from 'node:path';

import chalk from 'chalk';

import { pathExists } from './fs.js';

export async function resolveProjectDirectory(projectOption = '.') {
  const projectPath = path.resolve(process.cwd(), projectOption);
  const composeExists = await pathExists(projectPath, 'docker-compose.yml');
  if (!composeExists) {
    throw new Error(`No docker-compose.yml found in ${projectPath}. Run 'ultimate-mcp init' first.`);
  }
  return projectPath;
}

export function logProjectHeading(message) {
  console.log(`\n${chalk.cyan(message)}\n`);
}
