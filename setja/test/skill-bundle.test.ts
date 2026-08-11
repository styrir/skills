import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

function read(relativePath: string): string {
  return fs.readFileSync(new URL(`../${relativePath}`, import.meta.url), 'utf-8');
}

test('Codex-native bundled skill exists at skills/setja/SKILL.md', () => {
  assert.equal(fs.existsSync(new URL('../skills/setja/SKILL.md', import.meta.url)), true);
});

test('bundled skill uses YAML frontmatter metadata for discovery', () => {
  const skill = read('skills/setja/SKILL.md');
  assert.match(skill, /^---\nname: setja\ndescription:/);
});

test('bundled skill uses progressive disclosure via references', () => {
  const skill = read('skills/setja/SKILL.md');
  assert.match(skill, /references\/usage\.md/);
  assert.equal(fs.existsSync(new URL('../skills/setja/references/usage.md', import.meta.url)), true);
});

test('repo-local Codex mirror exists for project discovery', () => {
  assert.equal(fs.existsSync(new URL('../.codex/skills/setja/SKILL.md', import.meta.url)), true);
  assert.equal(fs.existsSync(new URL('../.codex/skills/setja/references/usage.md', import.meta.url)), true);
});

test('repo-local Codex mirror stays aligned with the bundled portable skill', () => {
  assert.equal(read('.codex/skills/setja/SKILL.md'), read('skills/setja/SKILL.md'));
  assert.equal(read('.codex/skills/setja/references/usage.md'), read('skills/setja/references/usage.md'));
});

test('README points to the bundled SKILL.md path', () => {
  assert.match(read('README.md'), /skills\/setja\/SKILL\.md/);
});

test('README makes npm link explicit before using the setja command', () => {
  const readme = read('README.md');
  assert.match(readme, /npm link/);
  assert.match(readme, /command not found/i);
});
