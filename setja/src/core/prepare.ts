import { runBuild } from './build.js';
import { ensureScaffold } from './init.js';
import { runInject } from './inject.js';
import { InjectOptions } from './types.js';

export async function runPrepare(options: InjectOptions): Promise<void> {
  ensureScaffold();
  await runBuild({ hexisName: options.hexisName });
  await runInject(options);
}
