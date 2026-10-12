> **Unverified AI-Q output (deep-AIQ lane, 2026-10-12).** Several figures are misattributed or unsourced; read `review.md` before relying on this.

# Exhaustive Catalog of Jev (jev-1.13) Integration Patterns for Agentic Workflows

*As of October 12, 2026*

---

## 1. Technical Primer: Jev 1.13 Specifications

### 1.1 Model Identity
Jev (version **jev-1.13**) is TypeSafe's **System One decision model** — not a generative LLM. It does not write text, code, summaries, or explanations. Instead, it answers **typed, structured questions** with **calibrated probabilities** in ~70–500 ms. Its purpose is to replace expensive, slow LLM calls for decision-shaped tasks: routing, gating, verification, classification, scoring, and triage.

### 1.2 Three Question Types
| Type | Purpose | Output Structure | Max Options/Levels |
|------|---------|------------------|-------------------|
| **Noul** | Yes/no gate (probability 0–1) | `noul: number` (no separate confidence field) | — |
| **Choice** | Pick one from a set (router) | `choice: string`, `probabilities: Record<string, number>`, `confidence: number` | 255 options |
| **Score** | Rate on ordered rubric (prioritizer) | `score: number` (probability-weighted mean), `probabilities: Record<number, number>`, `confidence: number`, `legend: Record<number, string>` | 2–10 ordered levels |

All three types can be asked in a **single API call** against the same input state, enabling multi-dimensional decisions without repeated context passes.

### 1.3 Request/Response Contract
- **Endpoint**: `POST /evaluation` (Bearer auth)
- **Request**: `{ state: string | object, model: "jev-latest" | "jev-1.13.0", questions: Record<string, { type: "noul"|"choice"|"score", instructions: string, criteria: object|array|boolean }> }`
- **Response**: `{ answers: Record<string, { type: string,...typed_output }> }`

### 1.4 Performance & Cost
| Metric | Value |
|--------|-------|
| Context window | ~32,000 tokens (state + longest question) |
| Latency | 70–500 ms (typical ~300–400 ms) |
| Input cost | $0.042 / M tokens |
| Output cost | **Free** |
| Per-call cost (typical) | ~$0.00003 |
| Throughput | Suitable for real-time loops (1,700 emails triaged for $0.18) |

### 1.5 Providers
| Provider | Access Method | Notes |
|----------|---------------|-------|
| **TypeSafe Direct** | API key via `typesafe.ai` | Primary source, version pinning (`jev-1.13.0`) |
| **OpenRouter** | `typesafe/jev-1.13` model slug | Cookbooks, Decisions API, model aliases |
| **Requesty** | Via Requesty gateway | Less documented; same model artifact |

### 1.6 Documented Failure Modes (Jaggedness)
TypeSafe's official jaggedness guide documents **nine failure modes** — these are not bugs but inherent limitations of a decision-only model:

| # | Failure Mode | Mitigation |
|---|--------------|------------|
| 1 | **Literal reading** — cannot infer implicit intent | Write exact conditions; do conversions in code; pass computed numbers/named buckets |
| 2 | **Math & numbers** — unreliable arithmetic, counting, interpolation | Keep arithmetic in code |
| 3 | **Date/time comparison** — cannot treat dates as ordered values | Extract components; compare in code |
| 4 | **Indirection** — struggles with multi-hop reasoning, double negatives | Reduce hops; point directly to relevant state by name |
| 5 | **Large irrelevant state** — accuracy degrades with noise | Filter first; send only what the question needs |
| 6 | **Adversarial content** — can be steered by malicious text in state | Precise prompts; test edge cases; **not a security boundary** — defense-in-depth required |
| 7 | **Cross-question consistency** — answers may conflict across questions in same call | Design questions independently; validate post-hoc |
| 8 | **Choice option order bias** — answers vary with option ordering | Reorder options and verify consistency |
| 9 | **Generation** — cannot produce free-form text, code, summaries, explanations | Use a generative model for output creation |

---

## 2. IndyDevDan's Ten Levels of Jev (disler/ten-levels-of-jev)

The repository **disler/ten-levels-of-jev** arranges **30 concrete uses** (3 per level) into a progression from **code-called Jev (Levels 1–5)** to **agent-embedded Jev (Levels 6–10)**. Each level is a runnable TypeScript file with questions and thresholds.

### Levels 1–5: Jev Called from Code (Gate/Middleware Patterns)

| Level | Theme | Option A | Option B | Option C | Question Type(s) | Workflow Position |
|-------|-------|----------|----------|----------|------------------|-------------------|
| **1** | Single Decisions | Prompt injection gate | Urgency gate | Ticket classifier (4 depts) | Noul, Choice | Pre-processing / ingress gate |
| **2** | Composite Scoring | PR risk score (security, complexity, drift, msg quality) | Support ticket priority | Bug severity triage | Score | Pre-action scoring |
| **3** | Confidence Gating | Bash command gate (0.5 human, 0.9 auto) | Deploy gate | Data mutation gate | Noul + thresholds | Pre-execution gate |
| **4** | Multi-Question Batches | Code review batch (risk, convention, tests) | Alert triage batch (page/slack/ticket/suppress) | Content moderation batch | Noul, Choice, Score | Parallel decision batch |
| **5** | Policy as Code | RBAC policy evaluator | Rate limit policy | Data retention policy | Choice, Noul | Policy enforcement layer |

### Levels 6–10: Jev Inside the Agent (Tool/Autonomous Patterns)

| Level | Theme | Pattern | Question Type(s) | Workflow Position |
|-------|-------|---------|------------------|-------------------|
| **6** | Agent Tool Call + Bash Gate | Agent calls Jev directly; bash gate validates proposed actions before execution | Noul (gate) | Inside agent loop; pre-tool-use |
| **7** | *(Not explicitly documented in available sources)* | — | — | — |
| **8** | Ask-Jev-File | Agent asks Jev about a file **without putting the file in agent context**; Jev retrieves & processes | Choice, Score | Agent tool; context offload |
| **9** | Ask-Jev-Files (Recursive Globs) | Multi-file queries at scale via recursive globs; Jev as "agentic engineer" | Choice, Score | Agent tool; large-context offload |
| **10** | Autonomous Question Generation | Agent decides which Jev questions to ask to classify test failures & verify fixes | Noul, Choice, Score (agent-chosen) | Agent loop; self-directed verification |

**Key Architectural Shift**: Levels 1–5 treat Jev as **middleware/gate** (code calls Jev). Levels 6–10 treat Jev as a **tool the agent chooses** (agent calls Jev). Level 10 makes Jev **autonomous** (agent writes the questions).

---

## 3. Agent Harness Hooks (Pre/Post Tool-Use Gates)

Jev integrates with major agent harnesses as **pre-tool-use gates** (blocking) or **post-tool-use verifiers** (non-blocking). The critical distinction is **fail-open vs. fail-closed** behavior.

### 3.1 Per-Harness Hook Behavior

| Harness | Hook Type | Default Behavior | Fail-Closed Mechanism | Version Requirement |
|---------|-----------|------------------|----------------------|---------------------|
| **Claude Code** | Command, HTTP hooks | **Fail-open** | Add `onFailure: block` + timeout | v2.1.295+ (Oct 8, 2026) |
| **Cursor** | Security, permission hooks | **Fail-open** (crashes/timeouts) | `failClosed: true` in `hooks.json` | Current |
| **Codex** | Approval hooks | **Fail-open** | Not natively supported; wrapper required | — |
| **Grok** | Subagent-tier gates | **Fail-open** | Custom implementation needed | — |
| **LangChain** | Middleware callbacks | **Fail-open** | Custom middleware | — |
| **Pydantic AI** | Tool validators | **Fail-open** | Custom validator | — |
| **Pi Extensions** | Agent skills | **Fail-open** | Built-in `hyper-jev` skill | — |
| **Hermes / n8n / MCP** | Custom nodes | **Fail-open** | Custom node logic | — |

### 3.2 Gate vs. Tool vs. Middleware Placement

| Placement | Description | Example | Failure Mode |
|-----------|-------------|---------|--------------|
| **Gate (Blocking)** | Jev decision **must pass** before action executes; fail-closed = hard stop | Claude Code pre-tool hook with `onFailure: block` | Jev downtime = workflow halt (mitigate with fallback_route) |
| **Tool (Agent-Called)** | Agent **chooses** to call Jev; result informs but doesn't block | Level 6–10 patterns; `ask-jev-file` | Agent may skip call; no enforcement |
| **Middleware** | Jev runs **transparently** on all events; logs/flags but doesn't block | LangChain callback; Alertmanager webhook | Silent failures if not monitored |

### 3.3 Fallback Routing (Critical Safeguard)
When Jev is unreachable, **fail toward humans, never toward silence**:

```python
def fallback_route(alert: dict) -> str:
 severity = alert.get('labels', {}).get('severity', '')
 return 'page' if severity in {'critical', 'warning'} else 'slack'
```

This pattern **must** be implemented for every gate deployment.

---

## 4. Routers and Intent Classification

Jev's three question types map directly to routing patterns:

| Pattern | Question Type | Role | Output |
|---------|---------------|------|--------|
| **Agent Router** | Choice | Which specialist agent handles this? | `choice: "coding"|"research"|"writing"`, per-agent probabilities, confidence |
| **Intent Router** | Choice | What is the user's intent? | `choice: "refund"|"technical"|"billing"`, probabilities, confidence |
| **Model Router** | Choice | Which LLM should generate the answer? | `choice: "gpt-luna"|"gpt-astra"`, probabilities, confidence |
| **Gate** | Noul | Should this request proceed? | `noul: 0.0–1.0` (values near 0.5 = uncertainty) |
| **Prioritizer** | Score | How urgent/important is this? | `score: 0–4`, per-level probabilities, confidence |

### 4.1 Routing Criteria & Confidence Thresholds
- **Criteria** defined in question's `criteria` object (e.g., `{ "billing": "Payment issues", "technical": "Bug reports" }`)
- **Confidence thresholds are task-dependent** — calibrate on real inputs:
 - **Low confidence / flat distribution** → clarify, safer default, additional verification, or human review
 - **Noul near 0.5** → treat as uncertain (no separate confidence field)
- **No universal thresholds** — probe before trusting cookbook defaults

### 4.2 Multi-Agent Orchestrator (LangGraph Integration)
**Architecture**: Three specialist agents (coding, research, writing) supervised by Jev in a LangGraph state machine implementing **route → execute → verify** loops.

| Stage | Jev Role | Question Type | Action on Failure |
|-------|----------|---------------|-------------------|
| **Route** | Which agent? | Choice (3 options) | Retry with next-best agent |
| **Execute** | Agent works | — | — |
| **Verify** | Did answer satisfy request? | Noul (yes/no) | Retry with next agent (max 2 retries) |

**Differs from standard LangGraph**: Supervisor is **not an LLM** — Jev replaces routing/verification with structured, probability-scored decisions.

---

## 5. Retrieval/RAG Filtering and File Triage

Jev replaces multiple LLM decision calls in RAG pipelines with a **uniform pattern**: describe input, ask question(s), provide permissible answers.

### 5.1 Ingestion-Time Patterns
| Decision | Question Type | Workflow Position | Why Jev Beats LLM/Rules |
|----------|---------------|-------------------|-------------------------|
| **Sensitive data detection (PII)** | Noul | Document ingestion | 100x cheaper than LLM; calibrated probability vs. regex false positives |
| **Document classification** | Choice | Ingestion pipeline | Structured output; no parsing needed |
| **Metadata enrichment** | Choice/Score | Ingestion pipeline | Single pass for multiple tags |

### 5.2 Retrieval-Time Patterns
| Decision | Question Type | Workflow Position | Why Jev Beats LLM/Rules |
|----------|---------------|-------------------|-------------------------|
| **Passage reranking** | Score | Post-retrieval, pre-generation | Parallel scoring; probability-weighted mean; confidence for thresholding |
| **Context sufficiency check** | Choice | Pre-generation | "Is context sufficient?" → `sufficient|insufficient|ambiguous` with confidence |
| **Claim verification** | Choice | Post-generation | "Does answer follow from context?" → `supported|contradicted|unverifiable` |

### 5.3 File Triage (Agent-Offload Pattern)
- **ask-jev-file** (Level 8): Agent asks Jev about a file **without putting file in agent context** — Jev retrieves & processes
- **ask-jev-files** (Level 9): Recursive globs for multi-file queries at scale
- **Why Jev**: Offloads large-context reading from agent; ~32k token limit handled by Jev; agent stays focused on reasoning

### 5.4 Metadata-Driven Filtering (RBAC/ABAC)
- Jev tags documents at ingestion (Choice: department, sensitivity, classification)
- Downstream retrieval filters by metadata **without re-classification**
- Postgres `redact` function enforces role-based clearance using Jev-generated tags

---

## 6. Eval and QA Gates

### 6.1 Confidence-Gating Thresholds (Three-Tier System)
From ten-levels-of-jev Level 4 documentation:

| Confidence Range | Action | Use Case |
|------------------|--------|----------|
| **< 0.5** | Mandatory human review | High-risk decisions |
| **0.5 – 0.9** | Prompt for confirmation | Medium-risk; destructive actions require explicit OK |
| **> 0.9** | Auto-approve (destructive actions run) | Low-risk; high-confidence routine ops |

**Code review risk scoring** uses **0.5 threshold** combining security risk, complexity, convention drift, commit message quality.

### 6.2 Ecosystem Tools

| Tool | Type | Integration | Jev Role | Status |
|------|------|-------------|----------|--------|
| **jev-harness** | CLI / SDK | Agent hooks | Gate/verification | Documented |
| **jev-eval-agent** | Agent | Evaluation loops | Verifier | Documented |
| **jev-commit** | Git hook | Pre-commit/CI | Gate | Documented |
| **jev-secret-detection** | Scanner | CI/pre-commit | Noul (PII detection) | Documented |
| **Jev Review** | Dashboard + CLI | Local/staged review | Score (risk dimensions) | **Local reference impl.** |
| **jev-sec-bench** | Benchmark | Security eval | Score (vulnerability severity) | Documented |
| **jev-align** | Benchmark | Alignment eval | Score (alignment criteria) | Documented |
| **patdown** | CLI / GH Action / Agent hooks | Markdown rule evaluation | Choice/Noul | **Not found in Jev docs** |
| **perch** | Code scanner | CI (--since scoping) | Choice/Score | **Not found in Jev docs** |

> **Note**: `patdown` and `perch` do not appear in any authoritative Jev documentation. They may be from a different project or internal terminology.

### 6.3 Jev Review (Staged Code-Review Workflow)
- **Local-first reference implementation** (not a production-deployed service)
- **Entry points**: `review:changes` (diff), `review:codebase` (full scan)
- **Dashboard**: `npm run dashboard` → local UI at `127.0.0.1`
- **Dimensions**: Correctness, Security, Reliability, Compatibility, Test Coverage
- **Thresholds & policy applied in code** (not in model prompt)
- **Selects concrete diff hunks/regions before scoring** — avoids large irrelevant state

---

## 7. CI/CD and Code Review

### 7.1 Continuous Evaluation Pipelines
| Pattern | Tool | Scoping | Cost Control | Jev Role |
|---------|------|---------|--------------|----------|
| **Staged review** | Jev Review | `--since` (diff only) | Cost review before gating | Score (multi-dim risk) |
| **PR gate** | jev-commit / jev-harness | Changed files only | Skip if no relevant changes | Noul/Choice (gate) |
| **Nightly full scan** | Jev Review | Full codebase | Scheduled; budgeted | Score (trend tracking) |

### 7.2 Cost Review Before Gating
- **Rule**: Estimate Jev call cost for PR scope; if > threshold, require manual approval
- **Typical cost**: ~$0.00003 per call; 40k decisions/month = **$1.34/month**
- **Comparison**: Budget LLM ~$90/month; Frontier LLM ~$900/month for same volume

### 7.3 CI Failure Classification (Tutorial Pattern)
- **GitHub Actions integration**: Classifies failures as `flaky`, `runner_problem`, `real_regression`
- **Action**: Auto-rerun flaky/runner; page author for real regressions
- **Status**: Tutorial code / pattern — **no confirmed production deployment found**

---

## 8. Security and Data-Egress Policy

### 8.1 Command Classification (Jev-Assisted Shell / kamchatka)
- **Built with** `--assisted-shell`, **run with** `--advise`
- **Classifies** shell/kubectl commands with **color-coded safety ratings**
- **Danger probabilities** (demo): `rm -rf` ~96%, `cat password` ~70%, `echo hello` ~1%
- **Categories covered**: State changes, remote connections, container breakouts, sensitive file reads, security enumeration tools
- **Privilege escalation**: Not a distinct class; subsumed under dangerous command categories

### 8.2 PII Detection & Redaction
| Layer | Mechanism | Jev Role |
|-------|-----------|----------|
| **Candidate generation** | Regex (emails, digit runs, capitalized-word runs, address patterns) | — |
| **Contextual review** | Jev Noul/Choice on candidates | Confirms/denies PII with probability |
| **Enforcement** | Postgres `redact` function | Replaces longest snippets first; role-based clearance without re-classification |

### 8.3 Data-Egress Policy Enforcement
- **Gravitee AI Gateway**: PII Filtering Policy inspects prompts/responses in real time; **redaction** (placeholders) or **blocking** (reject)
- **Jev integration**: Not explicitly documented; Gravitee is separate product
- **Native Jev capability**: Unclear — relies on integrations (Postgres redact, Gravitee)

### 8.4 Security Alert Triage (Torq Case Study)
- **Task**: Classify alerts (e.g., encoded PowerShell from winword.exe) as malicious/benign
- **Finding**: Jev **sensitive to prompt framing** — small prompt changes swing classification from "almost all malicious" to "almost none"
- **Result**: **Not reliable for production security alert triage** without extensive prompt hardening
- **Lesson**: Zero-shot Jev on narrow, unforgiving tasks fails; requires calibration + fallback

---

## 9. Content Moderation

### 9.1 Real-Time Comment Classification (OpenRouter Cookbook)
**Pipeline**: ScrapeCreators API → Jev (2 questions/comment) → Threshold-based triage

| Question | Type | Output |
|----------|------|--------|
| **Relevance** | Noul | `noul: 0.0–1.0` |
| **Sentiment** | Choice | `choice: negative|neutral|positive`, `confidence: 0.0–1.0` |

### 9.2 Calibrated Thresholds for Triage
| Action | Condition | Purpose |
|--------|-----------|---------|
| **Ignore** | `relevance ≤ 0.2` | Drop noise |
| **Record** | `relevance ≥ 0.8` **AND** `sentiment_confidence ≥ 0.7` | High-value, clear signal |
| **Review** | Everything else | Human-in-the-loop for edge cases |

**Reason field** indicates which threshold was missed (relevance unclear / sentiment confidence too low).

### 9.3 Real-World Scale
- **384 news stories × 15 brands** scored in **24.9 seconds** at **$0.19**
- **~390x cheaper per headline** vs. Claude Opus 5 (4/384 stories at $0.77)
- Open-sourced with 30+ skills for PR team automation

### 9.4 Calibration Guidance (OpenRouter Decisions Skill)
> "Probe before you trust. Run real questions over representative inputs. Cover clear cases, ambiguous cases, no-match, empty/off-topic, negated statements, adversarial text. Set thresholds from those numbers, not cookbook defaults. Repeat when model changes."

---

## 10. Cost Control (Replacing LLM Calls)

### 10.1 Jev-Verified Cascade (OpenRouter Cookbook)
**Pattern**: Cheap draft model → Jev verification → Frontier model only on failure

| Component | Model | Role |
|-----------|-------|------|
| **Draft** | `~openai/gpt-luna-latest` | Generates answer from context |
| **Verify** | **Jev (jev-1.13)** | Noul: "Does context support draft?" |
| **Escalate** | `~openai/gpt-astra-latest` | Rewrites only when Jev says no |

**System prompt must require answers from excerpts only.**

### 10.2 Cost/Quality Tradeoff (Confidence Threshold τ)
| τ (Threshold) | Quality (rel.) | Cost (rel.) | Escalation Rate |
|---------------|----------------|-------------|-----------------|
| 0.50 | 0.767 | 0.244 | 16% |
| 0.65 | 0.830 | 0.419 | 36.8% |
| 0.75 | 0.873 | 0.569 | 56% |
| 0.85 | 0.901 | 0.677 | 74.4% |
| 0.95 | 0.915 | 0.746 | 86.5% |
| **Always-large** | 0.924 | 0.740 | 100% |
| **Rule-based (token≤80)** | 0.826 | 0.475 | 60.5% to small |

### 10.3 Published Cost Models
| Volume | Jev Cost | Budget LLM | Frontier LLM |
|--------|----------|------------|--------------|
| 40,000 decisions/month | **$1.34/month** | ~$90/month | ~$900/month |
| 1,700 emails triaged | **$0.18** | — | — |
| Website AI-slop scan (243 ms) | **$0.00015/check** | — | — |
| WebMCP browser benchmark | **112x lower model cost** vs. GPT-6 Astra + computer use | — | — |

> **Note**: The specific figure **$1.26/day for 50k alerts** was not found in verified sources. Closest verified: $1.34/month for 40k decisions (~$0.04/day).

### 10.4 Rule-Based Model Routing (Alternative to Cascade)
- **Token threshold 80**: Routes 60.5% to small model
- **Total cost**: 0.475 (rel.) vs. 0.740 for always-large
- **Quality**: 0.826 vs. 0.924

---

## 11. Monitoring/Alerting Triage

### 11.1 Alert Routing Engine
**Decision**: Route alert to **page**, **Slack**, **ticket**, or **suppress**
**Basis**: Semantic description (not just severity label)
**Question Type**: Choice (4 options) or Noul per route
**Latency**: 70–500 ms per alert

### 11.2 CI Failure Classification
| Category | Action |
|----------|--------|
| **Flaky test** | Auto-rerun (with retry cap) |
| **Runner problem** | Auto-rerun / infra ticket |
| **Real regression** | Page author directly |

### 11.3 Command Guardrails
- **Pre-execution classification**: `read-only` | `reversible` | `irreversible`
- **Applies to**: Shell commands, `kubectl`, any agent-proposed command
- **Integration**: Pre-tool-use hook (gate) or agent-called tool

### 11.4 Log Noise Filtering
- **One Noul per log cluster**: "Does this represent a user-facing failure?"
- **Result**: Expensive models/humans only review entries that matter

### 11.5 Fallback Routing (Mandatory)
```python
def fallback_route(alert):
 severity = alert.get('labels', {}).get('severity', '')
 return 'page' if severity in {'critical', 'warning'} else 'slack'
# "Fail toward humans, never toward silence"
```

### 11.6 5-Question Triage Pattern
**Not documented** in available TypeSafe/OpenRouter sources. The Kodekloud blog covers alert routing, CI failure handling, command guardrails, and log filtering — but no 5-question pattern. This may not exist in Jev's design or may be documented elsewhere.

---

## 12. News/Feed Scoring

### 12.1 Scoring Dimensions (Score-Type Questions)
Jev evaluates feed items across **four dimensions** using **Score questions with 5-band rubrics (0–4)**:

| Dimension | Rubric Bands (Example: Severity) |
|-----------|----------------------------------|
| **Relevance** | 0=Irrelevant … 4=Critical to workflow |
| **Urgency** | 0=No rush … 4=Immediate action needed |
| **Business Priority** | 0=Nice-to-have … 4=Strategic imperative |
| **Need for Deeper Analysis** | 0=Self-contained … 4=Requires LLM/expert |

### 12.2 Score Output Structure
```json
{
 "type": "score",
 "score": 2.35,
 "confidence": 0.7,
 "legend": { "0": "Cosmetic", "1": "Minor/Workaround", "2": "Major/Workflow Broken", "3": "Critical/Core Unusable", "4": "Catastrophic/Data Loss" },
 "probabilities": { "0": 0.0, "1": 0.0, "2": 0.77, "3": 0.10, "4": 0.13 }
}
```

### 12.3 Ranking Happens Outside Jev
Jev **does not rank** — it returns structured labels (Choice, Score, Noul). Downstream code/SQL joins labels to business data:

| Factor | Weight | Source |
|--------|--------|--------|
| Business Impact | 35% | Severity + affected revenue |
| Effort | 30% | Engineering estimate (inverted) |
| Strategic Fit | 20% | Product lead judgment |
| Request Frequency | 15% | Distinct accounts |

**TypeSafe advises**: Keep arithmetic in code, not in model prompts.

### 12.4 Confidence-Based Routing
- **Confident labels** (high confidence) → pass automatically
- **Uncertain labels** → escalate to named person
- **Exact confidence thresholds not specified** in sources

### 12.5 Real-World Performance
- **384 stories × 15 brands** → 24.9 sec, $0.19
- Open-sourced demo with 30+ PR automation skills

---

## 13. Human-in-the-Loop Escalation

### 13.1 Documented Thresholds (Community-Observed)
| Escalation Type | Threshold | Rationale |
|-----------------|-----------|-----------|
| **Privilege escalation** | **0.2** (20%) | Conservative; better safe than sorry for permission-sensitive ops |
| **PII redaction** | **0.5** (50%) | Balance false positives vs. privacy protection |
| **Middle-band (legal/financial/medical)** | **Regardless of confidence** | Risk-based routing; domain criticality overrides model confidence |
| **Attorney review** | Action classification tags + regulatory reqs | Specialized compliance path; not confidence-based |

> **Caveat**: These thresholds come from **community discussions** (jev.pro, gist.ai), not official TypeSafe documentation. They may vary by deployment and are likely configurable.

### 13.2 Escalation Architecture
- **Domain-specific routing**: Legal → attorney, Financial → compliance, Medical → clinician
- **Middle-band design**: Deliberate pattern ensuring expert oversight for high-stakes decisions even at high confidence
- **Configuration**: Likely supports enterprise overrides

---

## 14. Real-World Deployments vs. Proposed Patterns

| Pattern / Tool | Status | Evidence |
|----------------|--------|----------|
| **Ten-levels demos** | **Proposed patterns** (production-oriented templates) | Repo: "ways to replace costly model calls... and ship to production" — aspirational |
| **Alert triage toolkit (jev-ops-triage)** | **Tutorial / pattern** | Complete Python pkg + K8s shadow mode; Torq case study shows prompt sensitivity blocks production use for security alerts |
| **Jev Review dashboard** | **Local reference implementation** | "Local-first reference implementation... not a production deployment" |
| **CI failure classifier (GitHub Actions)** | **Tutorial code** | "In this tutorial we built..." — no confirmed production deployment |
| **Content moderation cookbook** | **Working demo / pattern** | 384 stories × 15 brands in 24.9s at $0.19; open-sourced |
| **Jev-verified cascade** | **Cookbook / pattern** | OpenRouter cookbook with configurable τ; cost model published |
| **kamchatka agent (assisted shell)** | **Demo / pattern** | Color-coded safety ratings; no production case study found |
| **PII detection + Postgres redact** | **Architectural pattern** | Neon blog describes architecture; no confirmed production deployment |
| **Multi-agent orchestrator (LangGraph)** | **Video demo / pattern** | YouTube demonstration; no production case study |
| **patdown / perch** | **Not found in Jev ecosystem** | No mention in any authoritative Jev documentation |

**No documented case studies of actual companies running Jev in production** were found in verified sources. All evidence points to **patterns, tutorials, demos, and reference implementations** — not confirmed customer deployments.

---

## 15. Where Jev Is a Poor Fit (Flagged Scenarios)

| Scenario | Why Jev Fails | Alternative |
|----------|---------------|-------------|
| **Free-form text generation** (replies, code, summaries, explanations) | Failure mode #9: not trained to generate | Generative LLM |
| **Arithmetic, counting, numeric interpolation** | Failure mode #2: unreliable math | Code / deterministic logic |
| **Date/time ordering & comparison** | Failure mode #3: cannot treat dates as ordered | Extract components; compare in code |
| **Multi-hop reasoning / double negatives** | Failure mode #4: indirection degrades accuracy | Reduce hops; flatten reasoning in code |
| **Large context with high irrelevant-to-relevant ratio** | Failure mode #5: accuracy loss | Filter/preprocess state before Jev |
| **Adversarial / security-boundary decisions** | Failure mode #6: can be steered; not a security boundary | Hard security controls (WAF, authz, sandboxing) |
| **Cross-question consistency required** | Failure mode #7: answers may conflict | Validate post-hoc; design independent questions |
| **Position-sensitive choice sets** | Failure mode #8: option order bias | Test with reordered options |
| **Tasks requiring explanation of reasoning** | Failure mode #9: no explanations | LLM judge / generative model |
| **High-stakes security alert triage (zero-shot)** | Torq case study: prompt sensitivity causes class collapse | Extensive calibration + fallback + human review |

---

## 16. Calibration & Threshold Guidance

### 16.1 General Principles
1. **Probe before you trust** — run real questions on representative inputs
2. **Cover**: clear cases, ambiguous, no-match, empty/off-topic, negated, adversarial
3. **Set thresholds from observed probabilities**, not cookbook defaults
4. **Repeat when model changes** (version pinning recommended: `jev-1.13.0`)

### 16.2 Threshold Patterns by Use Case
| Use Case | Threshold Pattern | Source |
|----------|-------------------|--------|
| **Destructive action gate** | <0.5 human, 0.5–0.9 confirm, >0.9 auto | Ten-levels Level 4 |
| **Code review risk** | 0.5 human review | Ten-levels Level 3 |
| **Content moderation (relevance)** | ≤0.2 ignore, ≥0.8 record, else review | OpenRouter cookbook |
| **Content moderation (sentiment)** | Confidence ≥0.7 for record | OpenRouter cookbook |
| **Cascade verification (τ)** | 0.50–0.95 (tradeoff table) | OpenRouter cookbook / mbrenndoerfer.com |
| **Feed filtering** | High confidence → auto; low → escalate | News/feed scoring sources |
| **Privilege escalation (HITL)** | 0.2 (community) | Community discussions |
| **PII redaction (HITL)** | 0.5 (community) | Community discussions |

### 16.3 Fail-Open vs. Fail-Closed Decision Matrix
| Risk Level | Preferred Default | Jev Role | Fallback |
|------------|-------------------|----------|----------|
| **Safety-critical** (prod deploy, data deletion) | **Fail-closed** | Gate (blocking) | Fallback_route → page human |
| **Security-sensitive** (command exec, data egress) | **Fail-closed** | Gate (blocking) | Fallback_route → block + alert |
| **Operational** (alert routing, triage) | **Fail-open** | Gate/middleware | Fallback_route → page on critical/warning |
| **Cost-optimization** (model routing, cascade) | **Fail-open** | Tool/middleware | Fallback → cheaper model / human |
| **Content moderation** | **Fail-open** | Tool (async) | Queue for human review |

---

## 17. Cookbooks & Tutorials Reference Index

| Source | Title | Key Patterns |
|--------|-------|--------------|
| **OpenRouter** | Classify Reddit/YouTube Comments with Jev | Content moderation pipeline, calibrated thresholds |
| **OpenRouter** | Cut LLM Cost with a Jev-Verified Cascade | Model routing, τ tradeoff table |
| **OpenRouter** | Decisions Skill | Calibration methodology, threshold probing |
| **TypeSafe (GitHub)** | ten-levels-of-jev | 30 runnable examples, Levels 1–10, hyper-jev skill |
| **TypeSafe (docs)** | Jev 1.13 Jaggedness | 9 failure modes with mitigations |
| **TypeSafe (docs)** | API Reference | Request/response schemas, all 3 question types |
| **Kodekloud** | What Is Jev? A DevOps Guide | Alert triage, CI failure classification, command guardrails, fallback_route |
| **Thoughtworks** | How Jev Improves RAG Pipeline Efficiency | Ingestion/retrieval/generation decision replacement |
| **Neon** | pg_redact: PII Detection with Jev | Regex candidates + Jev review + Postgres redact |
| **Gravitee** | AI Gateway PII Filtering Policy | Real-time redaction/blocking (separate product) |
| **Flowtivity** | Jev Cost Models & Benchmarks | 40k decisions/$1.34, cascade economics, WebMCP 112x |
| **Wavect** | Jev Review Architecture Review | Local dashboard, staged review, not production |
| **YouTube (IndyDevDan)** | 10 Levels of Jev For Agentic Engineers | Levels 6–10 agent-embedded patterns |
| **YouTube (TypeSafe)** | Multi-Agent Orchestrator with Jev, LangGraph | Route→execute→verify supervisor pattern |

---

## 18. Summary: Decision Framework for Jev Integration

| Question | If Yes → Use Jev | If No → Avoid Jev |
|----------|------------------|-------------------|
| Is the task a **decision** (route, gate, classify, score, verify)? | ✅ | ❌ Use generative LLM |
| Can the decision be expressed as **Noul/Choice/Score**? | ✅ | ❌ Use rules or LLM |
| Is **latency < 500ms** and **cost < $0.001/call** critical? | ✅ | ❌ Consider cached rules |
| Can you **calibrate thresholds on real data** before deploying? | ✅ | ❌ Risk of miscalibration |
| Do you have a **fallback_route** for Jev unavailability? | ✅ | ❌ Don't deploy as gate |
| Is the task **adversarial or a security boundary**? | ❌ | ✅ Use hard controls |
| Does the task require **math, dates, counting, or generation**? | ❌ | ✅ Use code/LLM |
| Is the input state **large with low signal-to-noise**? | ❌ (filter first) | ✅ Pre-filter or use RAG |

---

## Sources

[1] Jev 1.13 - API Pricing & Providers | OpenRouter: https://openrouter.ai/typesafe/jev-1.13  
[2] What Is Jev? Inside TypeSafe's Decision-Only AI Model and Its Developer Use Cases: https://www.firecrawl.dev/blog/what-is-jev  
[3] GitHub - disler/ten-levels-of-jev: Ten levels of Jev, from one smart if statement to a coding agent that reaches for Jev on its own · GitHub: https://github.com/disler/ten-levels-of-jev  
[4] 10 Levels of Jev For Agentic Engineers: https://www.youtube.com/watch?v=_U-O5lYhJ7Q  
[5] Multi-Agent Orchestrator with Jev, LangGraph & OpenAI: https://www.youtube.com/watch?v=Ugj5GjWA-ww  
[6] How Jev can help improve the efficiency of RAG pipelines | Thoughtworks United States: https://www.thoughtworks.com/en-us/insights/blog/generative-ai/how-jev-can-help-improve-the-efficiency-of-rag-pipelines  
[7] GitHub - AbdelStark/awesome-typesafe-jev: Awesome Jev: a source-backed field guide to TypeSafe's System One model, with SDKs, live demos, agent tools, and independent evaluations. · GitHub: https://github.com/AbdelStark/awesome-typesafe-jev  
[8] What Is Jev? A DevOps Guide to TypeSafe's AI Decision Models: https://kodekloud.com/blog/what-is-jev-and-how-devops-teams-can-use-typesafes-ai-model  
[9] Jev 1.13 jaggedness - TypeSafe AI: https://docs.typesafe.ai/model-jaggedness/jev-1.13  
[10] Do Your Agent Hooks Fail Open? Claude Code vs Codex vs Cursor vs Gemini CLI: https://www.developersdigest.tech/blog/coding-agent-hooks-fail-open-vs-fail-closed-2026  
[11] Classify Reddit and YouTube Comments with Jev and ScrapeCreators: https://openrouter.ai/docs/cookbook/evaluate-and-optimize/classify-reddit-comments-with-jev  
[12] Compare AI Models: Pricing, Context & Benchmarks | OpenRouter: https://openrouter.ai/models  
[13] Torq Blog - Jev Security Alert Triage: https://torq.io/blog/jev-security-alert-triage  
[14] Jev Review Repository: https://github.com/devagrawal09/jev-review

