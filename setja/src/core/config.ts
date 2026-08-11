export interface SetjaConfig {
  summarizer: 'auto' | 'outline' | 'openai-compatible' | 'agent-subprocess';
  llmBaseUrl?: string;
  llmApiKey?: string;
  llmModel?: string;
  visionModel?: string;
  agentBackend?: 'codex';
  agentModel?: string;
  runirEnabled: boolean;
  runirBaseUrl?: string;
  runirCapturePath: string;
  runirRecallPath: string;
  runirApiKey?: string;
}

export function loadConfig(): SetjaConfig {
  return {
    summarizer: (process.env.SETJA_SUMMARIZER as 'auto' | 'outline' | 'openai-compatible' | 'agent-subprocess') || 'auto',
    llmBaseUrl: process.env.SETJA_LLM_BASE_URL,
    llmApiKey: process.env.SETJA_LLM_API_KEY,
    llmModel: process.env.SETJA_LLM_MODEL,
    visionModel: process.env.SETJA_VISION_MODEL,
    agentBackend: process.env.SETJA_AGENT_BACKEND as 'codex' | undefined,
    agentModel: process.env.SETJA_AGENT_MODEL,
    runirEnabled: String(process.env.SETJA_RUNIR_ENABLED || 'false').toLowerCase() === 'true',
    runirBaseUrl: process.env.SETJA_RUNIR_BASE_URL,
    runirCapturePath: process.env.SETJA_RUNIR_CAPTURE_PATH || '/hooks/capture',
    runirRecallPath: process.env.SETJA_RUNIR_RECALL_PATH || '/hooks/recall',
    runirApiKey: process.env.SETJA_RUNIR_API_KEY
  };
}
