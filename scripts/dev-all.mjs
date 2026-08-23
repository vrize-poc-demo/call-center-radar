#!/usr/bin/env node

import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { platform } from 'node:process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(root, '..');
const isWindows = platform === 'win32';
const npmCommand = isWindows ? 'npm.cmd' : 'npm';

function pythonCommand() {
  const candidates = isWindows
    ? ['.venv/Scripts/python.exe', '.venv/Scripts/python']
    : ['.venv/bin/python'];

  for (const relative of candidates) {
    const absolute = resolve(repoRoot, relative);
    if (existsSync(absolute)) {
      return absolute;
    }
  }

  return null;
}

function start(name, command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: repoRoot,
    stdio: 'inherit',
    shell: false,
    ...options,
  });

  child.on('error', (error) => {
    console.error(`[${name}] failed to start: ${error.message}`);
    shutdown(1);
  });

  child.on('exit', (code, signal) => {
    if (signal || code !== 0) {
      const reason = signal ? `signal ${signal}` : `exit code ${code}`;
      console.error(`[${name}] stopped with ${reason}`);
      shutdown(code ?? 1);
    }
  });

  return child;
}

let shuttingDown = false;
let exitCode = 0;
const children = [];

function shutdown(code = 0) {
  if (shuttingDown) {
    return;
  }

  shuttingDown = true;
  exitCode = code;

  for (const child of children) {
    if (!child.killed) {
      child.kill();
    }
  }

  setTimeout(() => process.exit(exitCode), 250).unref();
}

process.on('SIGINT', () => shutdown(0));
process.on('SIGTERM', () => shutdown(0));

const python = pythonCommand();
if (!python) {
  console.error('Could not find the Python interpreter inside .venv.');
  console.error('Expected one of: .venv/bin/python or .venv/Scripts/python.exe');
  process.exit(1);
}

console.log('[runner] starting web and API services');
console.log(`[runner] using python: ${python}`);

children.push(
  start('web', npmCommand, ['run', 'dev', '--workspace=@call-center-radar/web'])
);

children.push(
  start('api', python, [
    '-m',
    'uvicorn',
    'app.main:app',
    '--app-dir',
    'apps/api/src',
    '--reload',
    '--host',
    '127.0.0.1',
    '--port',
    '8000',
  ])
);
