# Styrir Search Handoff Manifest

Use this reference when `scripts/styrir-route.ts` selects `deep_search_local` or `nvidia_aiq_handoff`.

## Canonical Shape

```json
{
  "manifestVersion": 1,
  "createdAt": "2026-07-02T00:00:00.000Z",
  "mode": "deep_search_local",
  "nextSystem": "deep-search-cli",
  "question": "Make this report grade",
  "objective": "Produce a reusable cited report",
  "sourceScope": ["official docs"],
  "ledgerPath": "/tmp/styrir-ledger.json",
  "gateStatus": "pass",
  "commands": [
    "cd /Users/brooks/Code/refs/deep-search",
    "# Create <run-dir>, register sources/evidence/claims, and draft report.candidate.md per /Users/brooks/Code/skills/research/deep-search-cli/references/gated-report-mode.md before running verification commands.",
    ".venv/bin/deep-search-mcp plan-research-lanes --query \"Make this report grade\"",
    ".venv/bin/deep-search-mcp verify-claims --dir <run-dir> --strict",
    ".venv/bin/deep-search-mcp verify-citations --report <run-dir>/report.candidate.md --strict --no-network",
    ".venv/bin/deep-search-mcp validate-report --report <run-dir>/report.candidate.md",
    ".venv/bin/deep-search-mcp render-report-bundle --strict --dir <run-dir> --draft-report <run-dir>/report.candidate.md"
  ],
  "blockers": []
}
```

## Lane Rules

- Local Deep Search manifests must include the checklist commands above.
- The comment line must point to `/Users/brooks/Code/skills/research/deep-search-cli/references/gated-report-mode.md`.
- `<run-dir>` must exist with source, evidence, claim, and candidate-report artifacts before strict verification commands run.
- NVIDIA AI-Q manifests without `aiqBaseUrl` must set `nextSystem` to `NVIDIA AI-Q`, set `commands` to `[]`, set `aiqContract` to `handoff_only`, and include blocker text beginning `No configured local AI-Q target`.
- NVIDIA AI-Q manifests with `aiqBaseUrl` must set `aiqContract` to `rest_api`, keep a blocker that health is unverified until the operator runs the check, and include commands in this order: `curl -sf <base>/health`, create request JSON, POST to `<base>/v1/jobs/async`, fetch `<base>/v1/jobs/async/<job-id>/status`, then fetch `<base>/v1/jobs/async/<job-id>/report`.
- Never include AI-Q execution commands without an explicit local target.
