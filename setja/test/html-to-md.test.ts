import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { summarizeHtmlFiles } from '../src/pipeline/html-to-md.js';
import { createSummarizer } from '../src/pipeline/llm-summary.js';
import type { HexisProfile } from '../src/core/types.js';

function mktempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'setja-html-test-'));
}

test('HTML pipeline produces readable markdown-oriented summary output', async () => {
  const tempDir = mktempDir();
  const filePath = path.join(tempDir, 'sample.html');
  fs.writeFileSync(filePath, `<!doctype html>
<html>
  <body>
    <main>
      <h1>Context, arranged for use</h1>
      <p>Setja turns raw project artifacts into curated context for agents.</p>
      <section>
        <h2>Benefits</h2>
        <ul>
          <li>Small context</li>
          <li>Clean boundary</li>
        </ul>
      </section>
      <a href="/pricing">Pricing</a>
    </main>
  </body>
</html>`);

  const hexis: HexisProfile = {
    name: 'product',
    summary_style: 'strategic',
    focus: ['product direction', 'UX clarity']
  };

  const summarizer = createSummarizer({
    summarizer: 'outline',
    runirEnabled: false,
    runirCapturePath: '/hooks/capture',
    runirRecallPath: '/hooks/recall'
  });

  const summary = await summarizeHtmlFiles([filePath], summarizer, hexis);

  assert.doesNotMatch(summary, /\[object Object\]/);
  assert.match(summary, /Context, arranged for use/);
  assert.match(summary, /Benefits/);
  assert.match(summary, /Small context/);
  assert.match(summary, /Pricing/);
});
