import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const packageJson = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf-8')) as {
  scripts?: Record<string, string>;
};

test('package.json exposes a deterministic test harness script', () => {
  assert.equal(
    packageJson.scripts?.test,
    'SETJA_SUMMARIZER=outline SETJA_RUNIR_ENABLED=false tsx --test test/**/*.test.ts'
  );
});
