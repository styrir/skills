import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { createAgentSubprocessRunner, type AgentSubprocessArtifacts, type AgentSubprocessConfig, type AgentSubprocessRunner } from '../src/pipeline/llm-summary.js';

function mktempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'setja-agent-prompt-test-'));
}

test('agent subprocess prompt includes explicit summary contract and uncertainty rules', async () => {
  const tempDir = mktempDir();
  let seen: AgentSubprocessArtifacts | null = null;
  const runner: AgentSubprocessRunner = async (artifacts) => {
    seen = artifacts;
    fs.writeFileSync(artifacts.outputPath, JSON.stringify({ summary: '- ok' }), 'utf-8');
  };

  const invoke = createAgentSubprocessRunner({ tempRoot: tempDir, runner });
  await invoke({
    config: {
      summarizer: 'agent-subprocess',
      agentBackend: 'codex',
      runirEnabled: false,
      runirCapturePath: '/hooks/capture',
      runirRecallPath: '/hooks/recall'
    } as AgentSubprocessConfig,
    mode: 'image',
    payload: 'describe image',
    context: {
      hexis: { name: 'product', summary_style: 'strategic', focus: ['clarity', 'UX'] },
      sourcePath: 'workspace/screenshots/example.png',
      task: 'summarize what matters for a PM handoff'
    },
    imagePath: '/tmp/example.png'
  });

  const prompt = fs.readFileSync(seen!.promptPath, 'utf-8');
  assert.match(prompt, /Return JSON matching response\.schema\.json only/);
  assert.match(prompt, /Do not invent facts/i);
  assert.match(prompt, /If something is uncertain, say so explicitly/i);
  assert.match(prompt, /Respect the Hexis frame/i);
  assert.match(prompt, /The request artifact is authoritative/i);
  assert.match(prompt, /Treat `sourcePath` as a logical label/i);
  assert.match(prompt, /Do not inspect the filesystem/i);
  assert.match(prompt, /Embedded request JSON:/i);
  assert.match(prompt, /downstream agent/i);
  assert.match(prompt, /No prose outside the JSON object/i);
  assert.match(prompt, /workspace\/screenshots\/example\.png/);
  assert.match(prompt, /summarize what matters for a PM handoff/);
});
