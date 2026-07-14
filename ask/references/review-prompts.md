# Ask Codex Prompt Shapes

Use these as starting points. Keep the workspace path, artifact path, and consultation focus explicit.

## Brainstorming / Second Opinion

```text
Consider <question-or-plan> as a second-opinion partner.
Return the strongest options, tradeoffs, open questions, and any concrete next step you would recommend.
Do not edit files.
```

## Plan Review

```text
Review <plan-file> for implementation risk, missing tasks, test gaps, and scope drift.
Return concise findings first, then concrete plan edits.
```

## Build Review

```text
Review the uncommitted changes for bugs, behavior regressions, missing tests, and skill discoverability issues.
Return findings first with file/line references where possible.
```

Optional: add `--research` to the `ask.sh` invocation when the reviewer needs current external evidence. The runner will append instructions for bounded `$styrir-search` web research and Context7 docs lookup; keep the review prompt itself focused on the artifact and risks.

## Closeout Review

```text
Review the completed artifact and verification output. Confirm whether the requested outcome is satisfied, then list residual risks and follow-up tasks.
```
