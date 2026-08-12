# Non-interactive shell operations

Load this document before shell commands that can prompt, overwrite, delete, copy, move, install, or connect externally.

- Use non-interactive flags and batch authentication modes.
- Resolve the exact target before destructive operations.
- Never use a home directory, repository root, unresolved variable, broad glob, or filesystem root as a recursive deletion target.
- Prefer recoverable operations and report removed artifacts.
- A focused local Git commit and routine Beads/Dolt closeout for completed, verified work are standing repository authority; do not ask for repeated approval.
- Confirm before Git source pushes, creating or changing remotes, creating a remote repository, force-pushing, rewriting published history, sending messages, deploying, changing permissions, or taking another destructive or newly shared-state action outside routine Beads/Dolt closeout.
