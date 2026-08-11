import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { loadConfig } from '../src/core/config.js';
import {
  createAgentSubprocessRunner,
  createSummarizer,
  type AgentSubprocessArtifacts,
  type AgentSubprocessConfig,
  type AgentSubprocessRunner,
} from '../src/pipeline/llm-summary.js';
import type { HexisProfile } from '../src/core/types.js';

function mktempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'setja-agent-subprocess-test-'));
}

test('loadConfig reads agent subprocess backend settings', () => {
  const prevBackend = process.env.SETJA_AGENT_BACKEND;
  const prevModel = process.env.SETJA_AGENT_MODEL;
  process.env.SETJA_AGENT_BACKEND = 'codex';
  process.env.SETJA_AGENT_MODEL = 'gpt-5.4';
  try {
    const config = loadConfig();
    assert.equal(config.agentBackend, 'codex');
    assert.equal(config.agentModel, 'gpt-5.4');
  } finally {
    if (prevBackend === undefined) delete process.env.SETJA_AGENT_BACKEND;
    else process.env.SETJA_AGENT_BACKEND = prevBackend;
    if (prevModel === undefined) delete process.env.SETJA_AGENT_MODEL;
    else process.env.SETJA_AGENT_MODEL = prevModel;
  }
});

test('auto mode prefers agent subprocess when configured', async () => {
  const hexis: HexisProfile = { name: 'product' };
  const tempDir = mktempDir();
  const calls: AgentSubprocessArtifacts[] = [];
  const runner: AgentSubprocessRunner = async (artifacts) => {
    calls.push(artifacts);
    fs.writeFileSync(artifacts.outputPath, JSON.stringify({ summary: '- agent subprocess summary' }), 'utf-8');
  };

  const summarizer = createSummarizer({
    summarizer: 'auto',
    agentBackend: 'codex',
    agentModel: 'gpt-5.4',
    runirEnabled: false,
    runirCapturePath: '/hooks/capture',
    runirRecallPath: '/hooks/recall'
  }, {
    agentRunner: createAgentSubprocessRunner({
      tempRoot: tempDir,
      runner,
    })
  });

  const result = await summarizer.summarizeText('hello agent', { hexis, sourcePath: 'sample.txt' });
  assert.equal(result, '- agent subprocess summary');
  assert.equal(calls.length, 1);
  const request = fs.readFileSync(calls[0].requestPath, 'utf-8');
  assert.match(request, /hello agent/);
  assert.match(request, /"schema_version"\s*:\s*1/);
  assert.match(request, /"kind"\s*:\s*"setja_summarizer_request"/);
});

test('agent subprocess artifacts use JSON files plus prompt instructions', async () => {
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
    mode: 'text',
    payload: 'summarize me',
    context: {
      hexis: { name: 'product', focus: ['clarity'] },
      sourcePath: 'workspace/research/note.md'
    }
  });

  assert.ok(seen);
  assert.equal(fs.existsSync(seen!.requestPath), true);
  assert.equal(fs.existsSync(seen!.schemaPath), true);
  assert.equal(fs.existsSync(seen!.promptPath), true);
  assert.match(fs.readFileSync(seen!.requestPath, 'utf-8'), /"schema_version"\s*:\s*1/);
  assert.match(fs.readFileSync(seen!.requestPath, 'utf-8'), /"kind"\s*:\s*"setja_summarizer_request"/);
  assert.match(fs.readFileSync(seen!.schemaPath, 'utf-8'), /"summary"/);
  assert.match(fs.readFileSync(seen!.promptPath, 'utf-8'), /Return JSON/);
});
