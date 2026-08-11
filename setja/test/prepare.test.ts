import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

process.env.SETJA_SUMMARIZER = 'outline';
process.env.SETJA_RUNIR_ENABLED = 'false';

function mktempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'setja-test-'));
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

test('runPrepare initializes build+inject flow for a temp example project', async () => {
  const tempDir = mktempDir();
  const fixtureDir = path.join(tempDir, 'fixture');
  copyDir(path.resolve('example-project'), fixtureDir);

  const { runPrepare } = await import('../src/core/prepare.js');

  let output = '';
  await withCwd(fixtureDir, async () => {
    const originalLog = console.log;
    console.log = (...args: unknown[]) => {
      output += `${args.join(' ')}\n`;
    };
    try {
      await runPrepare({ hexisName: 'product', query: 'summarize what matters for a PM handoff' });
    } finally {
      console.log = originalLog;
    }
  });

  assert.equal(fs.existsSync(path.join(fixtureDir, 'context', 'index.md')), true);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'context', 'system.md')), true);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'context', 'architecture.md')), true);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'hexis', 'product.yaml')), true);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'context', 'guides', 'research.md')), true);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'context', 'guides', 'ui.md')), true);
  assert.match(output, /# Injected Context/);
  assert.match(output, /Hexis: product/);
  assert.match(output, /Task: summarize what matters for a PM handoff/);
});

test('runPrepare bootstraps missing scaffold without overwriting existing files', async () => {
  const tempDir = mktempDir();
  const fixtureDir = path.join(tempDir, 'fixture');
  copyDir(path.resolve('example-project'), fixtureDir);

  const customIndex = '# Custom Context\n\nDo not overwrite me.\n';
  fs.mkdirSync(path.join(fixtureDir, 'context'), { recursive: true });
  fs.writeFileSync(path.join(fixtureDir, 'context', 'index.md'), customIndex, 'utf-8');

  const { runPrepare } = await import('../src/core/prepare.js');

  await withCwd(fixtureDir, async () => {
    await runPrepare({ hexisName: 'default', query: 'brief a new agent on this project' });
  });

  assert.equal(fs.readFileSync(path.join(fixtureDir, 'context', 'index.md'), 'utf-8'), customIndex);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'context', 'system.md')), true);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'context', 'architecture.md')), true);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'hexis', 'default.yaml')), true);
  assert.equal(fs.existsSync(path.join(fixtureDir, 'workspace', 'research')), true);
});
