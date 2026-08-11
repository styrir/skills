# Claude Code Adapter — Setja

Preferred flow:
1. `setja build --hexis=<name>`
2. `setja inject --hexis=<name> --query="<current task>"`

Fallback:
- if CLI execution is unavailable, follow `skills/setja.md` manually
- keep the output shape aligned with Setja's context model

Rules:
- do not scan `workspace` directly
- prefer `context/*` files
- keep token usage low via curated context
