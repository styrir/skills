# Non-interactive shell operations

Load this document before shell commands that can prompt, overwrite, delete, copy, move, install, or connect externally.

- Use non-interactive flags and batch authentication modes.
- Resolve the exact target before destructive operations.
- Never use a home directory, repository root, unresolved variable, broad glob, or filesystem root as a recursive deletion target.
- Prefer recoverable operations and report removed artifacts.
- Focused commits and ordinary non-force Git plus Beads/Dolt pushes for completed, verified work to already-configured intended `origin` remotes are standing repository authority; do not ask for repeated approval.
- Confirm before creating or changing remotes, creating a remote repository, force-pushing, rewriting published history, sending messages, deploying, changing permissions, or taking another destructive or newly shared-state action outside ordinary tranche publication.
