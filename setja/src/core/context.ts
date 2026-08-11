import fs from 'node:fs';
import path from 'node:path';
import { ArtifactSummary, HexisProfile } from './types.js';
import { writeUtf8, exists, readUtf8, listFilesRecursive, relativeToCwd } from './fs.js';

const baselineContextFiles = [
  ['context/index.md', 'Project Context'],
  ['context/system.md', 'System Overview'],
  ['context/architecture.md', 'Architecture']
] as const;

const guideTitles: Record<string, string> = {
  'research.md': 'Research Summary',
  'ui.md': 'UI Summary',
  'images.md': 'Image Summary'
};

const maxBoostedDocs = 5;

export function buildInjectionEnvelope(input: {
  hexisName: string;
  query?: string;
  summaries: ArtifactSummary[];
  runirSection?: string;
}): string {
  const sections: string[] = [];

  sections.push('# Injected Context');
  sections.push('');
  sections.push(`- Hexis: ${input.hexisName}`);
  if (input.query) sections.push(`- Task: ${input.query}`);
  sections.push('');

  for (const summary of input.summaries) {
    sections.push(`## ${summary.title}`);
    sections.push(`Source: ${summary.sourcePath}`);
    sections.push(`Kind: ${summary.kind}`);
    sections.push('');
    sections.push(summary.body.trim());
    sections.push('');
  }

  if (input.runirSection) {
    sections.push('## Rúnir Recall');
    sections.push('');
    sections.push(input.runirSection.trim());
    sections.push('');
  }

  return sections.join('\n').trim() + '\n';
}

export function writeSummaryFile(filePath: string, title: string, body: string): void {
  writeUtf8(filePath, `# ${title}\n\n${body.trim()}\n`);
}

export function loadCoreContextFiles(): ArtifactSummary[] {
  return baselineContextFiles
    .filter(([filePath]) => exists(filePath))
    .map(([filePath, title]) => ({
      title,
      body: readUtf8(filePath),
      sourcePath: filePath,
      kind: 'research' as const
    }));
}

export function targetGuidePath(name: string): string {
  return path.join('context', 'guides', name);
}

export function inferArtifactKind(filePath: string): ArtifactSummary['kind'] {
  if (filePath.endsWith('/ui.md')) return 'html';
  if (filePath.endsWith('/images.md')) return 'image';
  return 'research';
}

function normalizePath(filePath: string): string {
  return filePath.replaceAll('\\', '/');
}

function isEligibleMarkdownPath(filePath: string): boolean {
  const normalized = normalizePath(filePath);
  if (!normalized.endsWith('.md')) return false;
  return normalized.split('/').every((segment) => segment.length > 0 && !segment.startsWith('.'));
}

function titleFromPath(filePath: string): string {
  const baseName = path.basename(filePath);
  const guideTitle = guideTitles[baseName];
  if (guideTitle) return guideTitle;

  return baseName
    .replace(/\.md$/i, '')
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function artifactSummaryFromPath(filePath: string, title?: string): ArtifactSummary {
  return {
    title: title || titleFromPath(filePath),
    body: readUtf8(filePath),
    sourcePath: normalizePath(filePath),
    kind: inferArtifactKind(filePath)
  };
}

function listMarkdownFiles(rootPath: string): string[] {
  if (!exists(rootPath)) return [];

  const stats = fs.statSync(rootPath);
  if (stats.isFile()) {
    return isEligibleMarkdownPath(rootPath) ? [normalizePath(rootPath)] : [];
  }

  return listFilesRecursive(rootPath)
    .map(relativeToCwd)
    .map(normalizePath)
    .filter(isEligibleMarkdownPath)
    .sort((left, right) => left.localeCompare(right));
}

export function resolveInjectionArtifacts(hexis: HexisProfile): ArtifactSummary[] {
  const baseline = loadCoreContextFiles();
  const guides = listMarkdownFiles(path.join('context', 'guides')).map((filePath) => artifactSummaryFromPath(filePath));

  const seen = new Set<string>([...baseline, ...guides].map((summary) => summary.sourcePath));
  const boosted: ArtifactSummary[] = [];

  for (const target of hexis.boost || []) {
    for (const filePath of listMarkdownFiles(target)) {
      if (seen.has(filePath)) continue;
      if (boosted.length >= maxBoostedDocs) break;

      seen.add(filePath);
      boosted.push(artifactSummaryFromPath(filePath));
    }

    if (boosted.length >= maxBoostedDocs) break;
  }

  return [...baseline, ...guides, ...boosted];
}
