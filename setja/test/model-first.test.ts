import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import { loadConfig } from '../src/core/config.js';
import { createSummarizer } from '../src/pipeline/llm-summary.js';
import type { HexisProfile } from '../src/core/types.js';

function read(relativePath: string): string {
  return fs.readFileSync(new URL(`../${relativePath}`, import.meta.url), 'utf-8');
}

test('loadConfig defaults summarizer mode to auto', () => {
  const previous = process.env.SETJA_SUMMARIZER;
  delete process.env.SETJA_SUMMARIZER;
  try {
    assert.equal(loadConfig().summarizer, 'auto');
  } finally {
    if (previous === undefined) delete process.env.SETJA_SUMMARIZER;
    else process.env.SETJA_SUMMARIZER = previous;
  }
});

test('auto mode uses model-backed summarization when endpoint config is present', async () => {
  const hexis: HexisProfile = { name: 'product' };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ choices: [{ message: { content: '- model summary' } }] }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });

  try {
    const summarizer = createSummarizer({
      summarizer: 'auto',
      llmBaseUrl: 'http://localhost:1234/v1',
      llmModel: 'local-vision-model',
      runirEnabled: false,
      runirCapturePath: '/hooks/capture',
      runirRecallPath: '/hooks/recall'
    });

    const result = await summarizer.summarizeText('hello world', { hexis, sourcePath: 'sample.txt' });
    assert.equal(result, '- model summary');
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test('auto mode can infer codex subprocess backend when available', async () => {
  const hexis: HexisProfile = { name: 'product' };
  const summarizer = createSummarizer({
    summarizer: 'auto',
    runirEnabled: false,
    runirCapturePath: '/hooks/capture',
    runirRecallPath: '/hooks/recall'
  }, {
    agentBackendAvailable: () => true,
    agentRunner: async () => '- inferred subprocess summary'
  });

  const result = await summarizer.summarizeText('hello world', { hexis, sourcePath: 'sample.txt' });
  assert.equal(result, '- inferred subprocess summary');
});

test('README describes model-backed summarization as the recommended default', () => {
  const readme = read('README.md');
  assert.match(readme, /model-backed summarization/i);
  assert.match(readme, /local vision/i);
  assert.match(readme, /outline.*fallback/i);
});
