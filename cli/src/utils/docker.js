import { spawnSync } from 'node:child_process';

import { runCommand } from './process.js';

let composeInvocation;

export function ensureDocker() {
  const result = spawnSync('docker', ['--version'], { stdio: 'ignore' });
  if (result.error || result.status !== 0) {
    throw new Error('Docker is required but was not found in PATH. Install Docker Desktop or the Docker Engine.');
  }
}

function detectCompose() {
  if (composeInvocation) {
    return composeInvocation;
  }

  const dockerCompose = spawnSync('docker', ['compose', 'version'], { stdio: 'ignore' });
  if (!dockerCompose.error && dockerCompose.status === 0) {
    composeInvocation = { command: 'docker', baseArgs: ['compose'] };
    return composeInvocation;
  }

  const legacyCompose = spawnSync('docker-compose', ['version'], { stdio: 'ignore' });
  if (!legacyCompose.error && legacyCompose.status === 0) {
    composeInvocation = { command: 'docker-compose', baseArgs: [] };
    return composeInvocation;
  }

  throw new Error('Neither "docker compose" nor "docker-compose" is available. Install the Docker Compose plugin.');
}

export async function runCompose(args, options = {}) {
  const invocation = detectCompose();
  const fullArgs = [...invocation.baseArgs, ...args];
  await runCommand(invocation.command, fullArgs, options);
}
