import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

function read(relativePath: string): string {
  return fs.readFileSync(new URL(`../${relativePath}`, import.meta.url), 'utf-8');
}

test('README describes Setja as a CLI-first runtime', () => {
  assert.match(read('README.md'), /CLI-first runtime/i);
});

test('skill docs describe the skill as a thin invocation layer over the CLI', () => {
  const skillDoc = read('skills/setja.md');
  assert.match(skillDoc, /thin invocation layer/i);
  assert.match(skillDoc, /run the CLI/i);
});

test('example-project README documents the validated init + prepare smoke flow', () => {
  const exampleReadme = read('example-project/README.md');
  assert.match(exampleReadme, /setja prepare --hexis=product/);
  assert.match(exampleReadme, /optional scaffold\/debug command/i);
});

test('operating model documents prepare as the primary CLI path', () => {
  const operatingModel = read('docs/operating-model.md');
  assert.match(operatingModel, /setja prepare --hexis=default --query="brief a new agent on this project"/);
  assert.doesNotMatch(operatingModel, /1\.\s+`setja` for the normal one-command path/);
});

test('architecture docs describe boost-aware bounded injection composition', () => {
  const architectureDoc = read('docs/architecture.md');
  assert.match(architectureDoc, /include boosted deeper context docs using Hexis `boost` targets/i);
  assert.match(architectureDoc, /cap boosted additions to a bounded number of whole docs/i);
});
