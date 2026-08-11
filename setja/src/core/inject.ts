import { buildInjectionEnvelope, resolveInjectionArtifacts } from './context.js';
import { loadConfig } from './config.js';
import { loadHexisProfile } from './hexis.js';
import { runHooks } from './hooks.js';
import { InjectOptions } from './types.js';
import { recallForInjection } from '../adapters/runir.js';

export async function runInject(options: InjectOptions): Promise<void> {
  const hexis = loadHexisProfile(options.hexisName);
  const config = loadConfig();

  const summaries = resolveInjectionArtifacts(hexis);

  await runHooks('beforeInject', {
    hexisName: hexis.name,
    query: options.query || '',
    summaries
  });

  const runirSection = await recallForInjection(config, {
    hexis,
    query: options.query || '',
    currentSummaries: summaries
  });

  const envelope = buildInjectionEnvelope({
    hexisName: hexis.name,
    query: options.query,
    summaries,
    runirSection
  });

  console.log(envelope);
}
