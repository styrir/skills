# Codex Adapter — Setja

When a project is new:
- run `setja init`

Before reasoning:
- run `setja build --hexis=<name>`

Before final output:
- run `setja inject --hexis=<name> --query="<current task>"`

Rules:
- always call the CLI
- do not reimplement Setja behavior inside the agent
- use injected context as the primary input
