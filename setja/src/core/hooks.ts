type HookPayload = Record<string, unknown>;
type HookHandler = (payload: HookPayload) => Promise<void>;

const registry = new Map<string, HookHandler[]>();

export function registerHook(stage: string, handler: HookHandler): void {
  const existing = registry.get(stage) || [];
  existing.push(handler);
  registry.set(stage, existing);
}

export async function runHooks(stage: string, payload: HookPayload): Promise<void> {
  const handlers = registry.get(stage) || [];
  for (const handler of handlers) {
    await handler(payload);
  }
}
