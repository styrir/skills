import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { runInit } from '../src/core/init.js';
import { runBuild } from '../src/core/build.js';
import { runInject } from '../src/core/inject.js';

process.env.SETJA_SUMMARIZER = 'outline';
process.env.SETJA_RUNIR_ENABLED = 'false';

function mktempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'setja-inject-test-'));
}

function copyDir(source: string, destination: string): void {
  fs.mkdirSync(destination, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const src = path.join(source, entry.name);
    const dest = path.join(destination, entry.name);
    if (entry.isDirectory()) copyDir(src, dest);
    else fs.copyFileSync(src, dest);
  }
}

async function withCwd<T>(cwd: string, fn: () => Promise<T>): Promise<T> {
  const previous = process.cwd();
  process.chdir(cwd);
  try {
    return await fn();
  } finally {
    process.chdir(previous);
  }
}

test('inject labels research guides as research, not html', async () => {
  const tempDir = mktempDir();
  copyDir(path.resolve('example-project'), tempDir);

  let output = '';
  await withCwd(tempDir, async () => {
    await runInit();
    await runBuild({ hexisName: 'product' });

    const originalLog = console.log;
    console.log = (...args: unknown[]) => {
      output += `${args.join(' ')}\n`;
    };
    try {
      await runInject({ hexisName: 'product', query: 'summarize what matters for a PM handoff' });
    } finally {
      console.log = originalLog;
    }
  });

  assert.match(output, /Source: context\/guides\/research\.md\nKind: research/);
});
