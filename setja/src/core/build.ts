import path from 'node:path';
import { targetGuidePath, writeSummaryFile } from './context.js';
import { loadConfig } from './config.js';
import { loadHexisProfile, shouldIncludePath } from './hexis.js';
import { runHooks } from './hooks.js';
import { BuildOptions, ArtifactSummary } from './types.js';
import { listFilesRecursive, relativeToCwd } from './fs.js';
import { summarizeResearchFiles } from '../pipeline/research-summary.js';
import { summarizeHtmlFiles } from '../pipeline/html-to-md.js';
import { summarizeImageFiles } from '../pipeline/image-analysis.js';
import { createSummarizer } from '../pipeline/llm-summary.js';
import { captureBuiltContext } from '../adapters/runir.js';

export async function runBuild(options: BuildOptions): Promise<void> {
  const hexis = loadHexisProfile(options.hexisName);
  const config = loadConfig();
  const summarizer = createSummarizer(config);

  const researchFiles = listFilesRecursive(path.join(process.cwd(), 'workspace', 'research'))
    .map(relativeToCwd)
    .filter((filePath) => shouldIncludePath(filePath, hexis));

  const htmlFiles = listFilesRecursive(path.join(process.cwd(), 'workspace', 'html'))
    .map(relativeToCwd)
    .filter((filePath) => shouldIncludePath(filePath, hexis));

  const imageFiles = listFilesRecursive(path.join(process.cwd(), 'workspace', 'screenshots'))
    .map(relativeToCwd)
    .filter((filePath) => shouldIncludePath(filePath, hexis));

  const builtSummaries: ArtifactSummary[] = [];

  if (researchFiles.length > 0) {
    const researchBody = await summarizeResearchFiles(researchFiles, summarizer, hexis);
    writeSummaryFile(targetGuidePath('research.md'), 'Research Summary', researchBody);
    builtSummaries.push({
      title: 'Research Summary',
      body: researchBody,
      sourcePath: 'context/guides/research.md',
      kind: 'research'
    });
  }

  if (htmlFiles.length > 0) {
    const uiBody = await summarizeHtmlFiles(htmlFiles, summarizer, hexis);
    writeSummaryFile(targetGuidePath('ui.md'), 'UI Summary', uiBody);
    builtSummaries.push({
      title: 'UI Summary',
      body: uiBody,
      sourcePath: 'context/guides/ui.md',
      kind: 'html'
    });
  }

  if (imageFiles.length > 0) {
    const imageBody = await summarizeImageFiles(imageFiles, summarizer, hexis);
    writeSummaryFile(targetGuidePath('images.md'), 'Image Summary', imageBody);
    builtSummaries.push({
      title: 'Image Summary',
      body: imageBody,
      sourcePath: 'context/guides/images.md',
      kind: 'image'
    });
  }

  await runHooks('afterBuild', {
    hexisName: hexis.name,
    summaries: builtSummaries
  });

  await captureBuiltContext(config, hexis, builtSummaries);

  console.log(`Setja build complete for Hexis "${hexis.name}".`);
}
