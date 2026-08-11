# Slash-command efficacy test: DeepSearch CLI router

Use this reference when validating that `/deep-search-cli ...` is behaving as a small router skill rather than re-injecting an old monolithic research manual.

## Clean test recipe

1. Start a fresh Hermes context if possible.
2. Run `/reload-skills` so slash-command/picker layers discover newly added split skills.
3. Run `/reset` so the agent context does not carry previous large skill blocks or critique.
4. Invoke a representative user-facing command, e.g.:

```text
/deep-search-cli tell me about the latest knowledge about dark matter like i'm a phd astrophysicist
```

If testing a specific model/provider and the active default differs, launch Hermes with explicit flags such as `--provider openai-codex -m gpt-5.5` so the banner/session metadata match the test target.

## Expected trace

The visible flow should show:

- `/deep-search-cli` loads only the small router skill at invocation.
- The agent loads the narrow subskill required by the task, commonly `deep-search-p1-retrieval` for web/source research.
- Provider/setup subskills such as `deep-search-provider-setup` are loaded only after a real provider/setup failure.
- Broad sibling skills such as `arxiv`, `research-and-recon`, and `parallel-cli` are not loaded reflexively.
- Early work is done through visible `deep-search-mcp` CLI calls such as `plan-research-lanes`, `web-search --provider parallel`, and `web-fetch`.
- `execute_code` may appear later for batching, JSON parsing, or output reduction, but should not be the first opaque path.

## Output richness rubric

A smoke-test answer is rich enough when it proves the router produced a real source-led synthesis, not merely a command transcript. Look for:

- Domain-appropriate framing for the requested audience.
- Coverage across multiple relevant source families.
- Fetched-source-backed numerical claims where the topic needs precision.
- A source ledger with URLs observed through the DeepSearch path.
- A boundary note naming the CLI/provider path and any non-DeepSearch contributors.

For the dark-matter PhD test, a good quick answer covered cosmology, direct detection, axions/ALPs, ultralight/fuzzy DM, SIDM, PBHs, and indirect detection; included concrete constraints from LZ, XENONnT, PandaX, Planck, ADMX, DESI/S8, etc.; and ended with a source ledger.

## Not enough for a gated report

A rich smoke-test answer is not the same as a gated DeepSearch report. For reusable or high-stakes research artifacts, route onward to:

- `deep-search-p0-ledgers` for source/evidence/claim ledgers.
- `deep-search-p2-orchestration` for planning gates, contradiction checks, temporal checks, and red-team review.
- `deep-search-report-delivery` for citation/report validation.

In other words: quick expert briefing can be source-led prose; gated report needs claim-level artifacts and validation.