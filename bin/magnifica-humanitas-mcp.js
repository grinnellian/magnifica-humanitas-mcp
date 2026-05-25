#!/usr/bin/env node
/**
 * Thin shim: delegates to the Python implementation via uvx.
 * Requires `uv` to be installed: https://docs.astral.sh/uv/getting-started/installation/
 */
const { spawn } = require('child_process');

const proc = spawn('uvx', ['magnifica-humanitas-mcp', ...process.argv.slice(2)], {
  stdio: 'inherit',
});

proc.on('error', (err) => {
  if (err.code === 'ENOENT') {
    console.error('Error: `uvx` not found. Install uv: https://docs.astral.sh/uv/getting-started/installation/');
  } else {
    console.error(err.message);
  }
  process.exit(1);
});

proc.on('exit', (code) => process.exit(code ?? 0));
