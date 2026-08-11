import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

function mktempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'setja-cli-ux-test-'));
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

test('CLI prepare accepts positional query and --product shorthand', async () => {
  const repoRoot = process.cwd();
  const tempDir = mktempDir();
  copyDir(path.join(repoRoot, 'example-project'), tempDir);

  const env = {
    ...process.env,
    SETJA_SUMMARIZER: 'outline',
    SETJA_RUNIR_ENABLED: 'false'
  };

  const { stdout } = await execFileAsync('node', [path.join(repoRoot, 'node_modules', 'tsx', 'dist', 'cli.mjs'), path.join(repoRoot, 'src', 'bin', 'setja.ts'), 'prepare', '--product', 'summarize', 'what', 'matters', 'for', 'a', 'PM', 'handoff'], {
    cwd: tempDir,
    env
  });

  assert.match(stdout, /Hexis: product/);
  assert.match(stdout, /Task: summarize what matters for a PM handoff/);
  assert.equal(fs.existsSync(path.join(tempDir, 'context', 'index.md')), true);
});

test('CLI --default shorthand selects the default profile', async () => {
  const repoRoot = process.cwd();
  const tempDir = mktempDir();
  copyDir(path.join(repoRoot, 'example-project'), tempDir);

  const env = {
    ...process.env,
    SETJA_SUMMARIZER: 'outline',
    SETJA_RUNIR_ENABLED: 'false'
  };

  const { stdout } = await execFileAsync('node', [path.join(repoRoot, 'node_modules', 'tsx', 'dist', 'cli.mjs'), path.join(repoRoot, 'src', 'bin', 'setja.ts'), 'prepare', '--hexis', 'product', '--default', 'brief', 'the', 'project'], {
    cwd: tempDir,
    env
  });

  assert.match(stdout, /Hexis: default/);
  assert.match(stdout, /Task: brief the project/);
});
