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
const ollamaCommand = process.env.CALL_RADAR_OLLAMA_COMMAND ?? 'ollama';
const ollamaBaseUrl = process.env.CALL_RADAR_OLLAMA_BASE_URL ?? 'http://127.0.0.1:11434';
const ollamaModel = process.env.CALL_RADAR_OLLAMA_MODEL ?? 'qwen2.5:7b';
const shouldStartOllama = process.env.CALL_RADAR_START_OLLAMA !== 'false';
const shouldPullOllamaModel = process.env.CALL_RADAR_PULL_OLLAMA_MODEL !== 'false';

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

function delay(ms) {
  return new Promise((resolveDelay) => {
    setTimeout(resolveDelay, ms);
  });
}

async function fetchJson(url, timeoutMs = 1500) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

async function waitForOllamaReady(maxWaitMs = 15000) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < maxWaitMs) {
    const tags = await fetchJson(`${ollamaBaseUrl}/api/tags`);
    if (tags) {
      return tags;
    }
    await delay(500);
  }

  return null;
}

function runCommand(name, command, args) {
  return new Promise((resolveRun, rejectRun) => {
    const child = spawn(command, args, {
      cwd: repoRoot,
      stdio: 'inherit',
      shell: false,
    });

    child.on('error', (error) => {
      rejectRun(new Error(`[${name}] failed to start: ${error.message}`));
    });

    child.on('exit', (code, signal) => {
      if (signal || code !== 0) {
        const reason = signal ? `signal ${signal}` : `exit code ${code}`;
        rejectRun(new Error(`[${name}] stopped with ${reason}`));
        return;
      }

      resolveRun();
    });
  });
}

function hasModel(tags) {
  return tags?.models?.some((model) => model?.name === ollamaModel);
}

async function ensureOllama() {
  if (!shouldStartOllama) {
    console.log('[runner] skipping Ollama startup because CALL_RADAR_START_OLLAMA=false');
    return;
  }

  console.log(`[runner] checking local LLM at ${ollamaBaseUrl}`);
  let tags = await fetchJson(`${ollamaBaseUrl}/api/tags`);

  if (!tags) {
    console.log('[runner] Ollama is not running; starting `ollama serve`');
    children.push(start('ollama', ollamaCommand, ['serve']));
    tags = await waitForOllamaReady();
  }

  if (shuttingDown) {
    throw new Error('[runner] Ollama startup failed.');
  }

  if (!tags) {
    throw new Error(
      '[runner] Ollama did not become ready. Install Ollama, or start it manually with: ollama serve'
    );
  }

  if (hasModel(tags)) {
    console.log(`[runner] local LLM model ready: ${ollamaModel}`);
    return;
  }

  if (!shouldPullOllamaModel) {
    throw new Error(
      `[runner] Ollama is running, but model ${ollamaModel} is missing. ` +
        `Pull it manually with: ollama pull ${ollamaModel}`
    );
  }

  console.log(`[runner] pulling local LLM model: ${ollamaModel}`);
  await runCommand('ollama-pull', ollamaCommand, ['pull', ollamaModel]);
  tags = await fetchJson(`${ollamaBaseUrl}/api/tags`, 5000);

  if (!hasModel(tags)) {
    throw new Error(`[runner] model ${ollamaModel} was not found after pull.`);
  }

  console.log(`[runner] local LLM model ready: ${ollamaModel}`);
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

async function main() {
  const python = pythonCommand();
  if (!python) {
    console.error('Could not find the Python interpreter inside .venv.');
    console.error('Expected one of: .venv/bin/python or .venv/Scripts/python.exe');
    process.exit(1);
  }

  await ensureOllama();

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
}

main().catch((error) => {
  console.error(error.message);
  shutdown(1);
});
