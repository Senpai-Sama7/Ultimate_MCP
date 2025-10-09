#!/usr/bin/env node

import('../src/index.js').catch((error) => {
  console.error('Failed to start Ultimate MCP CLI:\n', error);
  process.exitCode = 1;
});
