import path from 'node:path';
import { ensureDir, writeFileIfMissing } from './fs.js';

const scaffoldFiles: Array<[string, string]> = [
  ['context/index.md', `# Project Context

## Purpose

## Current State
-

## Key Decisions
-

## Rules
- Do NOT scan /workspace directly
- Prefer curated context files
`],
  ['context/system.md', `# System Overview

## Purpose

## Tech Stack

## Main Components

## Constraints
`],
  ['context/architecture.md', `# Architecture

## Components

## Data Flow

## External Dependencies
`],
  ['hexis/default.yaml', `name: default
summary_style: neutral
include:
  - workspace/research
  - workspace/html
  - workspace/screenshots
ignore:
  - workspace/scratch
focus:
  - general understanding
boost:
  - context
`],
  ['hexis/product.yaml', `name: product
summary_style: strategic
include:
  - workspace/research
  - workspace/html
  - workspace/screenshots
ignore:
  - workspace/scratch
focus:
  - product direction
  - UX clarity
boost:
  - context/decisions
  - context/guides
`],
  ['hexis/debug.yaml', `name: debug
summary_style: technical
include:
  - workspace/research
  - workspace/html
  - workspace/screenshots
  - workspace/scratch
ignore: []
focus:
  - implementation details
  - constraints
boost:
  - context/architecture
  - context/state
`]
];

const scaffoldDirs = [
  'context',
  'context/decisions',
  'context/state',
  'context/guides',
  'workspace/assets',
  'workspace/html',
  'workspace/research',
  'workspace/screenshots',
  'workspace/scratch',
  'hexis'
] as const;

export function ensureScaffold(): void {
  for (const dir of scaffoldDirs) ensureDir(path.join(process.cwd(), dir));

  writeFileIfMissing('.gitignore', `workspace/
workspace/**
`);

  for (const [filePath, content] of scaffoldFiles) {
    writeFileIfMissing(filePath, content);
  }
}

export async function runInit(): Promise<void> {
  ensureScaffold();
  console.log('Setja initialized.');
}
