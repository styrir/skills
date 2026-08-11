#!/usr/bin/env node
import 'dotenv/config';
import { Command } from 'commander';
import { runInit } from '../core/init.js';
import { runBuild } from '../core/build.js';
import { runInject } from '../core/inject.js';
import { runPrepare } from '../core/prepare.js';

const program = new Command();

type HexisOptions = {
  hexis: string;
  product?: boolean;
  debug?: boolean;
  default?: boolean;
};

function resolveHexisName(options: HexisOptions): string {
  if (options.product) return 'product';
  if (options.debug) return 'debug';
  if (options.default) return 'default';
  return options.hexis;
}

function resolveQuery(queryParts: string[] | undefined, explicitQuery?: string): string {
  if (explicitQuery && explicitQuery.trim()) return explicitQuery.trim();
  return (queryParts || []).join(' ').trim();
}

program
  .name('setja')
  .description('Context construction and injection layer for AI agents')
  .version('0.2.0');

program
  .command('init')
  .description('Initialize Setja project structure')
  .action(async () => {
    await runInit();
  });

program
  .command('build')
  .description('Construct curated context from workspace')
  .option('--hexis <name>', 'Hexis profile name', 'default')
  .option('--product', 'Use the product Hexis profile')
  .option('--debug', 'Use the debug Hexis profile')
  .option('--default', 'Use the default Hexis profile')
  .action(async (options: HexisOptions) => {
    await runBuild({ hexisName: resolveHexisName(options) });
  });

program
  .command('inject')
  .description('Print agent-ready context')
  .argument('[query...]', 'Optional task/query to bias injection')
  .option('--hexis <name>', 'Hexis profile name', 'default')
  .option('--query <query>', 'Task/query to bias recall and injection', '')
  .option('--product', 'Use the product Hexis profile')
  .option('--debug', 'Use the debug Hexis profile')
  .option('--default', 'Use the default Hexis profile')
  .action(async (queryParts: string[], options: HexisOptions & { query: string }) => {
    await runInject({
      hexisName: resolveHexisName(options),
      query: resolveQuery(queryParts, options.query),
    });
  });

program
  .command('prepare')
  .description('Build then inject')
  .argument('[query...]', 'Optional task/query to bias injection')
  .option('--hexis <name>', 'Hexis profile name', 'default')
  .option('--query <query>', 'Task/query to bias recall and injection', '')
  .option('--product', 'Use the product Hexis profile')
  .option('--debug', 'Use the debug Hexis profile')
  .option('--default', 'Use the default Hexis profile')
  .action(async (queryParts: string[], options: HexisOptions & { query: string }) => {
    await runPrepare({
      hexisName: resolveHexisName(options),
      query: resolveQuery(queryParts, options.query),
    });
  });

await program.parseAsync(process.argv);
