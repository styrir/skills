# Contradiction sweep: harness-specific vs general

## Scope and evidence

This sweep covers the ten fetched official/repository sources in `ledger.json` (`[s1]`–`[s10]`). Eight bounded search queries and ten source fetches were used. Search snippets were not used as evidence.

## Findings

| Tension | Factual observations | Resolution for the first-party skill |
| --- | --- | --- |
| Native log formats vs normalized reports | Inspect has `.eval` and `.json` EvalLog files and a Python Log File API (`[s1]`); eval-dashboards consumes `eval-report/v1` JSON emitted by a runner (`[s9]`, `[s10]`). | Keep format-specific ingest adapters separate from the reporting layer. Parse native files with their own API/reader, then emit normalized run/suite/row artifacts. Do not make the HTML reporter parse native session files. |
| Raw trace viewer vs quality report | Inspect View exposes Messages, Scoring, and Metadata (`[s2]`); OpenHands Trajectory Visualizer replays exported trajectory JSON (`[s7]`); eval-dashboards rows carry pass/fail, taxonomy, judge, version, and trace-link fields (`[s10]`). | Use specialized viewers for raw-turn drill-down and eval-dashboards for cross-harness summaries. Link a normalized row to the raw viewer instead of duplicating every transcript in the summary HTML. |
| Harbor artifact presence vs trial score | Harbor's artifact collection is best effort and a collection failure does not fail a trial (`[s5]`), while the trial output separately contains verifier data and `result.json` (`[s5]`). | Report `observability_missing` separately from task failure. A missing trace must not be silently converted into a failed benchmark score. |
| Harbor/Terminal-Bench task runs vs SWE-bench submission assets | Harbor runs dataset/agent/model trials and calls itself the official Terminal-Bench-2.0 harness (`[s4]`); SWE-bench submission metadata points to public `repo`, `logs`, and `trajs` assets (`[s8]`). | Treat benchmark identity, run configuration, and externally hosted assets as distinct provenance dimensions. Build importers for declared assets rather than assuming the two harnesses share a session schema. |
| OpenHands V0/V1 compatibility vs trajectory replay | OpenHands benchmarks is migrating from V0 evaluation code to the SDK V1 infrastructure and warns that benchmark and SDK versions are not universally compatible (`[s6]`); the visualizer documents exported trajectory JSON loading (`[s7]`). | Store SDK commit, benchmark revision, and trajectory format/version in metadata. A visualizer accepting JSON does not prove that all OpenHands generations are schema-compatible. |
| Static bundle deployment vs local viewer | Inspect View is a live local viewer (`[s2]`), while `inspect view bundle` emits static `index.html`, assets, and logs (`[s2]`). The static bundle requires HTTP Range support and Python's built-in server is explicitly unsuitable (`[s2]`). | Offer both local live inspection and a documented static report publish path; test deployment against a Range-capable server. |
| Version trend comparability vs rubric drift | eval-report/v1 has agent/prompt/dataset/rubric/version fields, suite governance, and rolling/champion baselines (`[s10]`); eval-dashboards is v0.x and says the schema/API are stabilizing (`[s9]`). | Pin the reporting contract/tool version and always record agent, skill/prompt, dataset, rubric, and config versions before comparing runs. |
| Submission policy vs generic checks | SWE-bench requires pass@1 and forbids hidden-test fields, hints, and uncontrolled solution browsing (`[s8]`); these are harness policy constraints, not universal transcript checks. | Keep compliance checks in a SWE-bench-specific suite with `riskArea`/category metadata; do not bake them into generic coding-agent checks. |

## License and coverage gaps

- Harbor is identified as Apache-2.0 (`[s4]`); OpenHands Benchmarks and the OpenHands Trajectory Visualizer are identified as MIT (`[s6]`, `[s7]`); eval-dashboards is identified as MIT (`[s9]`).
- The fetched Inspect README did not expose a license declaration. The fetched SWE-bench checklist did not expose the experiments repository license. The standalone Terminal-Bench task repository license was not fetched. These must be resolved from direct LICENSE or repository metadata before recommending vendoring or redistribution.
- The fetched sources do not establish native Claude Code, Codex, Pi, or Grok session schemas or community analyzer licenses. Those are intentionally left as proof gaps for the session-format scouts/follow-up run.

## Practical boundary

**Ingest adapters:** native Claude/Codex/Pi/Grok/OpenHands/Harbor/SWE artifacts, preserving source path, run identity, harness version, agent/skill/prompt version, tool calls, turns, cost/token data where available, redaction status, and raw-trace links.

**Check taxonomy:** `eval-report/v1` rows and suite manifests: `kind`, `severity`, `category`, `datasetId`, `scenarioId`, `rubricId`, `judge*`, `axisScores`, `agentVersion`, `promptVersion`, `toolCalls`, `trace`, plus blocking thresholds and baseline policy (`[s10]`).

**HTML/report layer:** eval-dashboards for runner-agnostic static HTML, history, quality gates, and publishing (`[s9]`, `[s10]`); Inspect bundle, OpenHands Visualizer, and Harbor View as source-specific raw-trace viewers (`[s2]`, `[s5]`, `[s7]`).
