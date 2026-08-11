---
name: styrir-init
description: Initialize or adopt a repository with Styrir conventions: safe local Git setup, Beads/Dolt tracking, GitNexus configuration, DOX guidance, generated-workspace directories, and deterministic verification. Use when the user says "initialize this repo", "bootstrap Styrir", "set up Git and Beads/Dolt", "create the standard Styrir files", or runs /styrir-init.
---

# Styrir Init

Use this skill to establish a repeatable repository foundation without re-researching local conventions.

## Default contract

The initializer performs **local, reversible setup only**:

- preserves existing hidden and visible files;
- initializes new Git repositories on `main` but never renames an existing branch;
- initializes or safely bootstraps repository-local Beads with embedded Dolt;
- installs Beads Git hooks and defaults an unset `beads.role` to `maintainer`;
- creates standard ignore rules, GitNexus configuration, root DOX guidance, topic guidance, and the `.styrir/` workspace layout;
- installs the standing closeout contract for future work: each completed, verified tranche is committed, pushed to the already-configured Git and Beads/Dolt `origin` remotes, independently verified, and left with a clean checkout without repeated approval;
- does not itself install dependencies, leave a Git commit, create remote repositories, add Git remotes, push Git, explicitly commit Dolt changes, add Dolt remotes, or push Dolt. Beads still creates the embedded database's required internal history.

The initialization run remains local-only. Later ordinary non-force tranche publication to intended, already-configured origins is standing authority; remote creation/replacement, force pushes, and destructive history rewrites remain separate confirmation gates.

## Workflow

1. **Identify the target.** Use the user-specified directory; otherwise use the current repository root. Derive a project name and Beads prefix from the directory name unless the user supplies them.
2. **Read existing instructions.** If the target already contains `AGENTS.md`, `CLAUDE.md`, or child instruction files, read the applicable chain before changing it. The deterministic script never overwrites those files.
3. **Preflight.** Confirm the target is not `/`, the user's home directory, a symlink, or an unowned subdirectory inside another Git repository. Inspect existing Git and `.beads/` state before running.
4. **Preview when useful:**

   ```bash
   ~/.grok/skills/styrir-init/scripts/styrir-init.sh \
     --target <path> \
     --project-name "<name>" \
     --prefix <beads-prefix> \
     --dry-run
   ```

5. **Initialize locally:**

   ```bash
   ~/.grok/skills/styrir-init/scripts/styrir-init.sh \
     --target <path> \
     --project-name "<name>" \
     --prefix <beads-prefix>
   ```

6. **Review existing-guidance skips.** When `AGENTS.md`, `CLAUDE.md`, `.gitnexusrc`, or a topic guide already existed, inspect it and integrate missing contracts manually rather than overwriting it.
7. **Verify.** Check the generated layout, `git status`, branch, `bd where`, `bd dolt remote list`, hooks, issue-prefix resolution, ignored runtime state, and absence of unintended commits/remotes/pushes.
8. **Run GitNexus after a real commit exists.** If `gitnexus` is installed and the repository has `HEAD`, run `gitnexus analyze .` and `gitnexus status`. Do not claim branch-aware indexing from an unborn repository.

## Generated layout

The script creates missing entries and preserves existing ones:

```text
<target>/
├── .git/                         # local Git metadata
├── .beads/                       # repository-local embedded Dolt tracker
├── .styrir/
│   ├── runs/
│   ├── analysis/raw/
│   ├── analysis/reports/
│   ├── pipelines/
│   ├── build/
│   ├── cache/
│   ├── logs/
│   └── tmp/
├── agent-guidance/
│   ├── beads-and-dolt.md
│   ├── gitnexus.md
│   ├── non-interactive-shell.md
│   └── styrir-workspace.md
├── .gitignore
├── .gitnexusignore
├── .gitnexusrc
├── AGENTS.md
└── CLAUDE.md
```

Beads additionally owns its generated `.beads/` metadata, ignore file, README, embedded database, and tracked `issues.jsonl` interchange snapshot.

## Publication boundary

The initializer creates no remote repository, remote, commit, or push. Establishing the initial shared target still requires deliberate setup:

1. inspect existing GitHub namespaces, repository ownership conventions, remotes, authentication, and repository visibility;
2. state the exact proposed repository owner/name, visibility, remote name, Git branch, Git remote URL, Dolt remote URL, and commands that will run;
3. ask for confirmation before creating the remote repository or adding/replacing either remote unless the user's current request already authorizes that exact target and operation;
4. seed Git and Dolt deliberately, verify Git `refs/heads/<branch>` and `refs/dolt/data` independently, and smoke-test a fresh clone with `bd bootstrap --yes` before claiming reproducibility.

Once the intended `origin` remotes exist, future completed and verified tranches are ordinary repository closeout: commit the coherent change, push Beads/Dolt, push Git, verify both refs, and leave the checkout clean without repeated approval. A current instruction can pause publication for a tranche. Force pushes, destructive history rewrites, and remote creation or replacement always require separate confirmation.

Git publication and Dolt synchronization are separate. Neither is current unless its own push succeeds.

## Self-test

Run the deterministic fixture test after editing this skill:

```bash
~/.grok/skills/styrir-init/scripts/test-styrir-init.sh
```

The test creates a randomly named disposable project with pre-existing hidden and visible files/directories, initializes it twice, verifies every expected generated path, proves the original content was preserved, confirms idempotence, and confirms that no commit or remote was created.

Set `KEEP_FIXTURE=1` to retain the random fixture for manual inspection.
