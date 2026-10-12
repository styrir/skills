# Evaluating text-transformation and “humanizer” tools

Use this checklist for paraphrasers, style rewriters, detector-evasion tools, translation chains, and agent writing skills.

## 1. Establish the real execution path

- Trace the CLI entry point into the implementation; do not infer behavior from the README.
- Enumerate every external recipient of the text. A locally executed program may still send full or transformed copies to several LLM and translation providers.
- Inspect prompts for explicit simplification, conversationalization, vocabulary replacement, or register changes.
- Distinguish a standalone executable from an agent skill. A repository without a `SKILL.md` is not activated merely by copying it into a skills directory; install the tool separately and create a skill wrapper only if orchestration is useful.

## 2. Verify installation without polluting the host

- Clone unfamiliar projects into a quarantine or temporary directory.
- Prefer an isolated environment and a supported interpreter version; install the project itself so the declared console entry point is exercised.
- Run the CLI help, focused tests, and the full test suite. Separate failures in optional/legacy paths from the recommended path, but report both.
- Compare advertised Docker/API commands with declared dependencies and actual imports.
- Inspect network endpoints, subprocess execution, file writes, model downloads, and unpinned remote artifacts.
- Treat vulnerability-database findings carefully: verify the advisory range and note disputed or malformed advisories rather than declaring a current package malicious from one scanner result.

## 3. Audit evidence behind quality claims

- Locate the published evaluation corpus, scoring code, detector identity/version, and reproducible command.
- A showcase Markdown file containing a detector verdict is not a reproducible benchmark.
- Check whether tests actually call the detector or merely assert that expected labels exist in fixture text.
- Separate vendor claims from independently reproduced results.

## 4. Measure preservation, not only detector scores

Inspect representative source/final pairs for:

- named entities, numbers, citations, technical terms, claims, modality, and uncertainty;
- lexical diversity, average word length, sentence-length distribution, and paragraph shape;
- semantic drift, mistranslation, invented specificity, weakened qualifications, and awkward back-translation;
- loss of rhetorical devices, unusual diction, authorial cadence, and deliberate complexity.

Simple lexical metrics are diagnostic signals, not literary verdicts. Quote concrete source-to-output degradations when possible.

For Brooks, treat high-register diction as protected content. Do not assume that “human” means casual, colloquial, simplified, or stripped of sophisticated vocabulary. Distinguish precise erudition from generic AI pomposity.

### Voice-calibration claim audit

A prompt that accepts writing samples is not, by itself, evidence of voice retention. Verify:

- **Precedence:** does the author corpus override generic bans and house-style rules, or do universal rules still delete the author's punctuation, rhetoric, and register?
- **Fidelity:** compare every worked example for invented biography, anecdotes, locations, dates, experiences, opinions, and sensory detail. Engaging invented personality is voice fabrication, not retention.
- **Evaluation target:** detector-score lift, lexical overlap, and semantic similarity do not measure authorship fidelity. Look for held-out author samples, stylometric comparison, blind attribution, or human judgments against the target author.
- **Implementation depth:** distinguish genuine profile extraction and comparison from a prompt that merely says “match this sample.” Check for placeholders, hard-coded metrics, unused profile fields, and marketing labels such as “BERTScore-inspired” that do not implement the named metric.
- **Editing scope:** review-first or surgical editing usually preserves voice better than wholesale regeneration. Prefer systems where corpus-observed patterns exempt the author from generic AI-tell rules.

Do not rank tools from repository claims plus popularity alone. Community anecdotes and GitHub adoption are discovery signals, not comparative evidence.

## 5. Preferred design for voice-preserving rewriting

Prefer constrained direct editing over blind multi-hop translation:

1. Extract protected claims, entities, terminology, citations, hedges, and register.
2. Calibrate from a representative author sample when available.
3. Identify concrete AI-pattern candidates; leave already distinctive prose untouched.
4. Rewrite only implicated passages while preserving protected elements.
5. Run an independent semantic/register audit and reject candidates that become more generic.
6. Expose aggressive translation or detector-oriented modes only as explicit opt-ins with privacy and drift warnings.

Useful modes: conservative, high-register, technical, and aggressive. Avoid universal house-style rules such as banning every em dash; those can erase the author while claiming to preserve voice.

## 6. Recommendation format

Report:

- what actually runs and where text goes;
- verified installation/test results;
- privacy and supply-chain implications;
- evidence quality and reproducibility gaps;
- observed style/meaning drift;
- whether to install as a tool, wrap as a skill, adapt/fork, or reject;
- a minimal safe installation path and a preferred architecture for the user’s objective.
