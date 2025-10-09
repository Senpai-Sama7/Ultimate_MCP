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
    run('node', ['bin/ultimate-mcp.js', 'init', tempDir, '--force'], {
      cwd: path.resolve(__dirname, '..'),
    });

    const composePath = path.join(tempDir, 'docker-compose.yml');
    const composeContents = readFileSync(composePath, 'utf-8');
    if (!composeContents.includes('${UMCP_BACKEND_IMAGE}')) {
      throw new Error('compose file missing backend image reference placeholder');
    }

    const envPath = path.join(tempDir, '.env');
    const envContents = readFileSync(envPath, 'utf-8');
    if (!envContents.includes('AUTH_TOKEN=')) {
      throw new Error('.env missing AUTH_TOKEN');
    }
    if (!envContents.includes('UMCP_BACKEND_IMAGE=ghcr.io/ultimate-mcp/ultimate-mcp-backend:latest')) {
      throw new Error('.env missing backend image default');
    }

    console.log('Smoke test passed.');
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

main();
