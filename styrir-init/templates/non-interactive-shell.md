# Non-interactive shell operations

Load this document before shell commands that can prompt, overwrite, delete, copy, move, install, or connect externally.

- Use non-interactive flags and batch authentication modes.
- Resolve the exact target before destructive operations.
- Never use a home directory, repository root, unresolved variable, broad glob, or filesystem root as a recursive deletion target.
- Prefer recoverable operations and report removed artifacts.
- Confirm before actions that change shared external state, including repository creation, pushes, messages, deployments, and permission changes.
