import { SetjaConfig } from '../core/config.js';
import { ArtifactSummary, HexisProfile, RunirRecallResult } from '../core/types.js';

function authHeaders(config: SetjaConfig): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (config.runirApiKey) headers.Authorization = `Bearer ${config.runirApiKey}`;
  return headers;
}

export async function captureBuiltContext(
  config: SetjaConfig,
  hexis: HexisProfile,
  summaries: ArtifactSummary[]
): Promise<void> {
  if (!config.runirEnabled || !config.runirBaseUrl || summaries.length === 0) return;

  const payload = {
    source: 'setja',
    memoryType: 'context_build',
    hexis: {
      name: hexis.name,
      summary_style: hexis.summary_style,
      focus: hexis.focus || [],
      boost: hexis.boost || []
    },
    items: summaries.map((summary) => ({
      title: summary.title,
      text: summary.body,
      metadata: {
        kind: summary.kind,
        sourcePath: summary.sourcePath
      }
    }))
  };

  const response = await fetch(new URL(config.runirCapturePath, config.runirBaseUrl).toString(), {
    method: 'POST',
    headers: authHeaders(config),
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Rúnir capture failed: ${response.status} ${response.statusText}`);
  }
}

export async function recallForInjection(
  config: SetjaConfig,
  input: {
    hexis: HexisProfile;
    query: string;
    currentSummaries: ArtifactSummary[];
  }
): Promise<string> {
  if (!config.runirEnabled || !config.runirBaseUrl || !input.query.trim()) return '';

  const payload = {
    query: input.query,
    hexis: {
      name: input.hexis.name,
      summary_style: input.hexis.summary_style,
      focus: input.hexis.focus || [],
      boost: input.hexis.boost || []
    },
    source: 'setja',
    current_context: input.currentSummaries.map((summary) => ({
      title: summary.title,
      text: summary.body.slice(0, 4000),
      metadata: {
        kind: summary.kind,
        sourcePath: summary.sourcePath
      }
    }))
  };

  const response = await fetch(new URL(config.runirRecallPath, config.runirBaseUrl).toString(), {
    method: 'POST',
    headers: authHeaders(config),
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Rúnir recall failed: ${response.status} ${response.statusText}`);
  }

  const json = await response.json() as Partial<RunirRecallResult> & {
    hits?: Array<{ title?: string; text?: string; score?: number; metadata?: Record<string, unknown> }>;
  };

  const items = json.items || json.hits || [];
  if (items.length === 0) return '';

  return items
    .map((item, index) => {
      const title = item.title || `Memory ${index + 1}`;
      const score = typeof item.score === 'number' ? ` (score: ${item.score.toFixed(3)})` : '';
      return `### ${title}${score}\n\n${item.text || ''}`;
    })
    .join('\n\n');
}
