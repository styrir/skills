import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { resolveInjectionArtifacts } from '../src/core/context.js';
import { HexisProfile } from '../src/core/types.js';

function mktempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'setja-context-resolution-test-'));
}

function write(relativePath: string, body: string, cwd: string): void {
  const fullPath = path.join(cwd, relativePath);
  fs.mkdirSync(path.dirname(fullPath), { recursive: true });
  fs.writeFileSync(fullPath, body, 'utf-8');
}

async function withCwd<T>(cwd: string, fn: () => Promise<T> | T): Promise<T> {
  const previous = process.cwd();
  process.chdir(cwd);
  try {
    return await fn();
  } finally {
    process.chdir(previous);
  }
}

test('resolver composes baseline, guides, and boosted docs with deterministic order and dedupe', async () => {
  const tempDir = mktempDir();
  write('context/index.md', '# Index', tempDir);
  write('context/system.md', '# System', tempDir);
  write('context/architecture.md', '# Architecture', tempDir);
  write('context/guides/research.md', '# Research Summary', tempDir);
  write('context/guides/ui.md', '# UI Summary', tempDir);
  write('context/guides/images.md', '# Image Summary', tempDir);
  write('context/decisions/001-auth.md', '# Auth decision', tempDir);
  write('context/decisions/002-queue.md', '# Queue decision', tempDir);
  write('context/state/today.md', '# State snapshot', tempDir);

  const hexis: HexisProfile = {
    name: 'product',
    boost: ['context/decisions', 'context/decisions/001-auth.md', 'context/state']
  };

  const summaries = await withCwd(tempDir, () => resolveInjectionArtifacts(hexis));

  assert.deepEqual(
    summaries.map((summary) => summary.sourcePath),
    [
      'context/index.md',
      'context/system.md',
      'context/architecture.md',
      'context/guides/images.md',
      'context/guides/research.md',
      'context/guides/ui.md',
      'context/decisions/001-auth.md',
      'context/decisions/002-queue.md',
      'context/state/today.md'
    ]
  );
  assert.equal(summaries.find((summary) => summary.sourcePath === 'context/guides/ui.md')?.kind, 'html');
  assert.equal(summaries.find((summary) => summary.sourcePath === 'context/guides/images.md')?.kind, 'image');
  assert.equal(summaries.find((summary) => summary.sourcePath === 'context/decisions/001-auth.md')?.kind, 'research');
});

test('resolver caps boosted additions at five docs and skips hidden/non-markdown files', async () => {
  const tempDir = mktempDir();
  write('context/index.md', '# Index', tempDir);
  write('context/system.md', '# System', tempDir);
  write('context/architecture.md', '# Architecture', tempDir);

  for (const entry of ['01', '02', '03', '04', '05', '06', '07']) {
    write(`context/state/${entry}.md`, `# ${entry}`, tempDir);
  }
  write('context/state/.hidden.md', '# hidden', tempDir);
  write('context/state/ignore.txt', 'ignore me', tempDir);

  const hexis: HexisProfile = {
    name: 'debug',
    boost: ['context/state']
  };

  const summaries = await withCwd(tempDir, () => resolveInjectionArtifacts(hexis));

  assert.deepEqual(
    summaries.map((summary) => summary.sourcePath),
    [
      'context/index.md',
      'context/system.md',
      'context/architecture.md',
      'context/state/01.md',
      'context/state/02.md',
      'context/state/03.md',
      'context/state/04.md',
      'context/state/05.md'
    ]
  );
});
