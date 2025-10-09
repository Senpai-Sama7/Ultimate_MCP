import { Command } from 'commander';
import chalk from 'chalk';
import { createRequire } from 'module';

import { initProject } from './commands/init.js';
import { startProject } from './commands/start.js';
import { stopProject } from './commands/stop.js';
import { upgradeProject } from './commands/upgrade.js';
import { DEFAULT_PORTS } from './config/defaults.js';

const require = createRequire(import.meta.url);
const { version } = require('../package.json');

const program = new Command();

program
  .name('ultimate-mcp')
  .description('Installer and runtime manager for the Ultimate MCP platform')
  .version(version);

program
  .command('init [directory]')
  .description('Create a ready-to-run Ultimate MCP deployment directory')
  .option('--force', 'Overwrite existing files if the directory is not empty', false)
  .option('--local-images', 'Build backend/frontend images locally instead of pulling release images', false)
  .option('--backend-image <name>', 'Override backend image reference')
  .option('--frontend-image <name>', 'Override frontend image reference')
  .option('--backend-port <number>', `Host port exposed for the backend API (default ${DEFAULT_PORTS.backend})`)
  .option('--frontend-port <number>', `Host port exposed for the frontend UI (default ${DEFAULT_PORTS.frontend})`)
  .option('--neo4j-http-port <number>', `Host port exposed for the Neo4j browser (default ${DEFAULT_PORTS.neo4jHttp})`)
  .option('--neo4j-bolt-port <number>', `Host port exposed for the Neo4j bolt protocol (default ${DEFAULT_PORTS.neo4jBolt})`)
  .option('--neo4j-password <password>', 'Override the generated Neo4j password (must satisfy Neo4j password policy)')
  .action(async (directory, options) => {
    try {
      await initProject(directory, options);
    } catch (error) {
      console.error(chalk.red(`\n✖ init failed: ${error.message}`));
      process.exitCode = 1;
    }
  });

program
  .command('start')
  .description('Launch the Ultimate MCP stack (docker compose up)')
  .option('--detached', 'Run without waiting for health checks', false)
  .option('--project <path>', 'Specify the project directory', '.')
  .action(async (options) => {
    try {
      await startProject(options);
    } catch (error) {
      console.error(chalk.red(`\n✖ start failed: ${error.message}`));
      process.exitCode = 1;
    }
  });

program
  .command('stop')
  .description('Stop the Ultimate MCP stack (docker compose down)')
  .option('--project <path>', 'Specify the project directory', '.')
  .action(async (options) => {
    try {
      await stopProject(options);
    } catch (error) {
      console.error(chalk.red(`\n✖ stop failed: ${error.message}`));
      process.exitCode = 1;
    }
  });

program
  .command('upgrade')
  .description('Pull the latest images and restart the stack')
  .option('--project <path>', 'Specify the project directory', '.')
  .option('--skip-pull', 'Restart without pulling images', false)
  .action(async (options) => {
    try {
      await upgradeProject(options);
    } catch (error) {
      console.error(chalk.red(`\n✖ upgrade failed: ${error.message}`));
      process.exitCode = 1;
    }
  });

program.parseAsync(process.argv);
