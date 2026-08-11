import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { SetjaConfig } from '../core/config.js';
import { Summarizer, SummarizerContext } from '../core/types.js';

const AGENT_SUBPROCESS_TIMEOUT_MS = 60_000;
const AGENT_SUBPROCESS_POLL_MS = 250;
const AGENT_SUBPROCESS_OUTPUT_GRACE_MS = 1_000;

function hasOpenAICompatibleConfig(config: SetjaConfig): boolean {
  return Boolean(config.llmBaseUrl && config.llmModel);
}

function hasAgentSubprocessConfig(config: SetjaConfig): boolean {
  return config.agentBackend === 'codex';
}

let cachedCodexAvailability: boolean | null = null;

function isCodexAvailable(): boolean {
  if (cachedCodexAvailability != null) return cachedCodexAvailability;
  const result = spawnSync('codex', ['--version'], { stdio: 'ignore' });
  cachedCodexAvailability = result.status === 0;
  return cachedCodexAvailability;
}

export type AgentSubprocessConfig = SetjaConfig;

export interface AgentSubprocessArtifacts {
  cwd: string;
  requestPath: string;
  schemaPath: string;
  promptPath: string;
  outputPath: string;
  imagePaths: string[];
  backend: 'codex';
  model?: string;
}

export type AgentSubprocessRunner = (artifacts: AgentSubprocessArtifacts) => Promise<void>;

interface AgentSubprocessInvocation {
  config: AgentSubprocessConfig;
  mode: 'text' | 'image';
  payload: string;
  context: SummarizerContext;
  imagePath?: string;
}

interface AgentSubprocessFactoryOptions {
  tempRoot?: string;
  runner?: AgentSubprocessRunner;
}

function buildAgentPrompt(invocation: AgentSubprocessInvocation): string {
  const hexisFocus = invocation.context.hexis.focus?.length
    ? invocation.context.hexis.focus.join(', ')
    : 'none provided';
  const summaryStyle = invocation.context.hexis.summary_style || 'default';

  return [
    'You are a Setja summarizer subprocess.',
    'Read request.json for the task payload and context.',
    'Return JSON matching response.schema.json only.',
    'Write the JSON field `summary` as concise markdown bullets that are useful to a downstream agent.',
    invocation.mode === 'image'
      ? 'Use the attached image and request context to produce an image-aware summary for an agent.'
      : 'Summarize the provided material into concise markdown bullets suitable for an agent.',
    'Respect the Hexis frame from request.json.',
    `Hexis name: ${invocation.context.hexis.name}`,
    `Hexis summary style: ${summaryStyle}`,
    `Hexis focus: ${hexisFocus}`,
    `Source path: ${invocation.context.sourcePath}`,
    `Task: ${invocation.context.task || 'none provided'}`,
    'The request artifact is authoritative. Work from the provided request payload and attached image only.',
    'Treat `sourcePath` as a logical label unless the request explicitly says the file contents are not embedded.',
    'Do not inspect the filesystem, do not run shell commands, and do not probe the repository.',
    'Prefer concrete observations from the artifact over generic restatement.',
    'Do not invent facts.',
    'If something is uncertain, say so explicitly.',
    'Optimize for what matters to a downstream agent making decisions or taking action next.',
    'No prose outside the JSON object.',
  ].join('\n');
}

async function defaultAgentRunner(artifacts: AgentSubprocessArtifacts): Promise<void> {
  const args = [
    'exec',
    '--skip-git-repo-check',
    '--sandbox',
    'read-only',
    '--output-schema',
    artifacts.schemaPath,
    '--output-last-message',
    artifacts.outputPath,
    '-C',
    artifacts.cwd,
  ];

  if (artifacts.model) {
    args.push('--model', artifacts.model);
  }

  for (const imagePath of artifacts.imagePaths) {
    args.push('--image', imagePath);
  }

  args.push('-');

  const prompt = fs.readFileSync(artifacts.promptPath, 'utf-8');
  await new Promise<void>((resolve, reject) => {
    const child = spawn('codex', args, {
      cwd: artifacts.cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stderr = '';
    let settled = false;
    let outputSeenAt: number | null = null;
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    const cleanup = () => {
      clearInterval(poll);
      clearTimeout(timeout);
    };

    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      cleanup();
      fn();
    };

    child.on('error', (error) => finish(() => reject(error)));
    child.on('close', (code) => {
      if (settled) return;
      if (code === 0 && fs.existsSync(artifacts.outputPath)) {
        finish(resolve);
        return;
      }
      finish(() => reject(new Error(`Agent subprocess failed with code ${code}: ${stderr.trim()}`)));
    });

    const poll = setInterval(() => {
      if (!fs.existsSync(artifacts.outputPath)) return;
      const text = fs.readFileSync(artifacts.outputPath, 'utf-8').trim();
      if (!text) return;

      try {
        const parsed = JSON.parse(text) as { summary?: string };
        if (typeof parsed.summary !== 'string') return;
      } catch {
        return;
      }

      if (outputSeenAt == null) {
        outputSeenAt = Date.now();
        return;
      }

      if (Date.now() - outputSeenAt >= AGENT_SUBPROCESS_OUTPUT_GRACE_MS) {
        if (!child.killed) {
          child.kill('SIGTERM');
        }
        finish(resolve);
      }
    }, AGENT_SUBPROCESS_POLL_MS);

    const timeout = setTimeout(() => {
      if (!child.killed) {
        child.kill('SIGTERM');
      }
      finish(() => reject(new Error(`Agent subprocess timed out after ${AGENT_SUBPROCESS_TIMEOUT_MS}ms: ${stderr.trim()}`)));
    }, AGENT_SUBPROCESS_TIMEOUT_MS);

    child.stdin.write(prompt);
    child.stdin.end();
  });
}

export function createAgentSubprocessRunner(
  options: AgentSubprocessFactoryOptions = {},
): (invocation: AgentSubprocessInvocation) => Promise<string> {
  const baseTempRoot = options.tempRoot || fs.mkdtempSync(path.join(os.tmpdir(), 'setja-agent-'));
  const runner = options.runner || defaultAgentRunner;

  return async (invocation: AgentSubprocessInvocation): Promise<string> => {
    const runDir = fs.mkdtempSync(path.join(baseTempRoot, 'run-'));
    const requestPath = path.join(runDir, 'request.json');
    const schemaPath = path.join(runDir, 'response.schema.json');
    const promptPath = path.join(runDir, 'prompt.md');
    const outputPath = path.join(runDir, 'response.json');

    fs.writeFileSync(requestPath, JSON.stringify({
      schema_version: 1,
      kind: 'setja_summarizer_request',
      mode: invocation.mode,
      payload: invocation.payload,
      context: {
        hexis: invocation.context.hexis,
        sourcePath: invocation.context.sourcePath,
        task: invocation.context.task ?? '',
      },
      imagePath: invocation.imagePath,
    }, null, 2), 'utf-8');

    fs.writeFileSync(schemaPath, JSON.stringify({
      type: 'object',
      additionalProperties: false,
      required: ['summary'],
      properties: {
        summary: { type: 'string' },
      },
    }, null, 2), 'utf-8');

    fs.writeFileSync(
      promptPath,
      `${buildAgentPrompt(invocation)}\n\nEmbedded request JSON:\n${fs.readFileSync(requestPath, 'utf-8')}\n\nArtifacts:\n- request: ${requestPath}\n- schema: ${schemaPath}\n- output: ${outputPath}\n`,
      'utf-8',
    );

    await runner({
      cwd: process.cwd(),
      requestPath,
      schemaPath,
      promptPath,
      outputPath,
      imagePaths: invocation.imagePath ? [invocation.imagePath] : [],
      backend: 'codex',
      model: invocation.config.agentModel,
    });

    const parsed = JSON.parse(fs.readFileSync(outputPath, 'utf-8')) as { summary?: string };
    return parsed.summary?.trim() || '';
  };
}

class OutlineSummarizer implements Summarizer {
  async summarizeText(input: string, context: SummarizerContext): Promise<string> {
    const lines = input
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 12);

    const focus = context.hexis.focus?.length ? `Focus: ${context.hexis.focus.join(', ')}.` : '';
    const style = context.hexis.summary_style ? `Style: ${context.hexis.summary_style}.` : '';

    return [`${style} ${focus}`.trim(), '', ...lines.map((line) => `- ${line}`)]
      .filter(Boolean)
      .join('\n');
  }

  async summarizeStructured(input: Record<string, unknown>, context: SummarizerContext): Promise<string> {
    const focus = context.hexis.focus?.length ? `Focus: ${context.hexis.focus.join(', ')}.` : '';
    return `${focus}\n\n` + Object.entries(input)
      .map(([key, value]) => `- ${key}: ${String(value)}`)
      .join('\n');
  }

  async summarizeImage(input: { sourcePath: string; metadata: Record<string, unknown> }, context: SummarizerContext): Promise<string> {
    const focus = context.hexis.focus?.length ? `Focus: ${context.hexis.focus.join(', ')}.` : '';
    return [
      focus,
      `- file: ${input.sourcePath}`,
      ...Object.entries(input.metadata).map(([key, value]) => `- ${key}: ${String(value)}`)
    ].filter(Boolean).join('\n');
  }
}

class OpenAICompatibleSummarizer implements Summarizer {
  constructor(private readonly config: SetjaConfig) {}

  private headers(): Record<string, string> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (this.config.llmApiKey) headers.Authorization = `Bearer ${this.config.llmApiKey}`;
    return headers;
  }

  private async chat(messages: Array<Record<string, unknown>>, modelOverride?: string): Promise<string> {
    if (!this.config.llmBaseUrl || !this.config.llmModel) {
      throw new Error('Missing SETJA_LLM_BASE_URL or SETJA_LLM_MODEL for OpenAI-compatible summarizer.');
    }

    const response = await fetch(new URL('/chat/completions', this.config.llmBaseUrl).toString(), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({
        model: modelOverride || this.config.llmModel,
        messages,
        temperature: 0.2
      })
    });

    if (!response.ok) {
      throw new Error(`Summarizer request failed: ${response.status} ${response.statusText}`);
    }

    const json = await response.json() as {
      choices?: Array<{ message?: { content?: string } }>;
    };

    return json.choices?.[0]?.message?.content?.trim() || '';
  }

  async summarizeText(input: string, context: SummarizerContext): Promise<string> {
    const prompt = [
      'Summarize the material for an agent.',
      `Hexis: ${context.hexis.name}.`,
      context.hexis.summary_style ? `Style: ${context.hexis.summary_style}.` : '',
      context.hexis.focus?.length ? `Focus on: ${context.hexis.focus.join(', ')}.` : '',
      'Return concise markdown bullet points and a short takeaway.'
    ].filter(Boolean).join(' ');

    return this.chat([
      { role: 'system', content: prompt },
      { role: 'user', content: input.slice(0, 16000) }
    ]);
  }

  async summarizeStructured(input: Record<string, unknown>, context: SummarizerContext): Promise<string> {
    const prompt = [
      'Summarize this structured artifact for an agent.',
      `Hexis: ${context.hexis.name}.`,
      context.hexis.summary_style ? `Style: ${context.hexis.summary_style}.` : '',
      'Return concise markdown.'
    ].join(' ');

    return this.chat([
      { role: 'system', content: prompt },
      { role: 'user', content: JSON.stringify(input, null, 2) }
    ]);
  }

  async summarizeImage(input: {
    sourcePath: string;
    mimeType: string;
    bytes: string;
    metadata: Record<string, unknown>;
  }, context: SummarizerContext): Promise<string> {
    const model = this.config.visionModel || this.config.llmModel;
    const prompt = [
      'Describe this screenshot or image for an agent.',
      `Hexis: ${context.hexis.name}.`,
      context.hexis.summary_style ? `Style: ${context.hexis.summary_style}.` : '',
      context.hexis.focus?.length ? `Focus on: ${context.hexis.focus.join(', ')}.` : '',
      'Mention likely UI purpose, notable elements, and anything important for project context.'
    ].filter(Boolean).join(' ');

    const dataUrl = `data:${input.mimeType};base64,${input.bytes}`;

    return this.chat([
      { role: 'system', content: prompt },
      {
        role: 'user',
        content: [
          { type: 'text', text: `Metadata:\n${JSON.stringify(input.metadata, null, 2)}` },
          { type: 'image_url', image_url: { url: dataUrl } }
        ]
      }
    ], model);
  }
}

class AgentSubprocessSummarizer implements Summarizer {
  constructor(
    private readonly config: AgentSubprocessConfig,
    private readonly invoke: (invocation: AgentSubprocessInvocation) => Promise<string>,
  ) {}

  async summarizeText(input: string, context: SummarizerContext): Promise<string> {
    return this.invoke({
      config: this.config,
      mode: 'text',
      payload: input,
      context,
    });
  }

  async summarizeStructured(input: Record<string, unknown>, context: SummarizerContext): Promise<string> {
    return this.invoke({
      config: this.config,
      mode: 'text',
      payload: JSON.stringify(input, null, 2),
      context,
    });
  }

  async summarizeImage(input: {
    sourcePath: string;
    mimeType: string;
    bytes: string;
    metadata: Record<string, unknown>;
  }, context: SummarizerContext): Promise<string> {
    return this.invoke({
      config: this.config,
      mode: 'image',
      payload: JSON.stringify({
        sourcePath: input.sourcePath,
        mimeType: input.mimeType,
        metadata: input.metadata,
      }, null, 2),
      context,
      imagePath: input.sourcePath,
    });
  }
}

export function createSummarizer(
  config: SetjaConfig,
  options: {
    agentRunner?: (invocation: AgentSubprocessInvocation) => Promise<string>;
    agentBackendAvailable?: () => boolean;
  } = {},
): Summarizer {
  if (config.summarizer === 'agent-subprocess') {
    return new AgentSubprocessSummarizer(config, options.agentRunner || createAgentSubprocessRunner());
  }
  if (config.summarizer === 'openai-compatible') {
    return new OpenAICompatibleSummarizer(config);
  }
  if (config.summarizer === 'auto' && (hasAgentSubprocessConfig(config) || ((options.agentBackendAvailable || isCodexAvailable)() && !hasOpenAICompatibleConfig(config)))) {
    return new AgentSubprocessSummarizer(config, options.agentRunner || createAgentSubprocessRunner());
  }
  if (config.summarizer === 'auto' && hasOpenAICompatibleConfig(config)) {
    return new OpenAICompatibleSummarizer(config);
  }
  return new OutlineSummarizer();
}

export function guessMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.png') return 'image/png';
  if (ext === '.jpg' || ext === '.jpeg') return 'image/jpeg';
  if (ext === '.webp') return 'image/webp';
  return 'application/octet-stream';
}

export function readBase64(filePath: string): string {
  return fs.readFileSync(filePath).toString('base64');
}
