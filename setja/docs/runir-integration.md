# Setja ↔ Rúnir Integration Boundary

This document explains the intended integration model between Setja and Rúnir.

The most important point is simple:

- **Setja is not Rúnir**
- **Rúnir is not Setja**

The integration exists because they complement each other, not because one should absorb the other.

## The responsibility split

### Setja owns

- local project workspace organization
- build-time context construction
- task-time injection packaging
- Hexis-framed summarization of current raw artifacts

### Rúnir owns

- persistence across sessions
- retrieval and recall policy
- memory ranking / usefulness over time
- continuity beyond the current local workspace state

If this split blurs, both systems become harder to reason about.

## Current technical boundary in the repo

**File:** `src/adapters/runir.ts`

That file exposes two operations:

1. `captureBuiltContext(...)`
2. `recallForInjection(...)`

This is exactly the right size for the first integration.

It gives Setja two memory-adjacent capabilities without forcing memory policy into the core runtime.

## Build-side integration

After Setja has constructed summaries from the current workspace, it can optionally capture them to Rúnir.

Conceptually:

```text
workspace -> Setja build -> context summaries -> optional Rúnir capture
```

The payload includes:

- source = `setja`
- memory type = `context_build`
- Hexis metadata
- built summary items with kind and source path

This is a good first contract because it reflects what Setja actually knows:

- what it built
- what Hexis framed it
- where the summaries came from

It does **not** pretend Setja knows memory ranking policy or recall strategy.

## Inject-side integration

Before Setja prints the final injected context envelope, it can optionally ask Rúnir for relevant recall.

Conceptually:

```text
current task query + current built summaries + Hexis -> Rúnir recall -> injected envelope enrichment
```

This is intentionally task-conditioned. The question is not “what has ever been stored?” The question is “what prior memory is useful *for this task*, under this frame, given the current context package?”

## Why the adapter should stay narrow

The narrow adapter matters for several reasons.

### 1. It protects Setja from memory policy creep

Once Setja starts deciding ranking strategy, retention rules, or cross-session significance, it is no longer a context construction layer. It is becoming a second memory system.

### 2. It protects Rúnir from UI/workspace coupling

Rúnir should not need to understand how a local project stores screenshots, HTML prototypes, or scratch files. Setja already owns that local-reality problem.

### 3. It keeps failure modes sane

If Rúnir is unavailable, Setja should still be able to build and inject local context. That only works if the integration is optional and shallow.

## Practical contract guidance

If you evolve the hook contract later, keep these principles:

### Good payload fields

- source system identifier
- memory type
- Hexis name and stance metadata
- concise summary text
- source path / kind metadata
- current task query on recall

### Bad payload fields

- full raw workspace dumps
- hidden agent state
- memory ranking logic embedded in Setja
- environment-specific adapter behavior leaking into the contract

## The healthy future model

The clean long-term relationship looks like this:

```text
local artifacts
  -> Setja build
  -> curated current-context package
  -> optional Rúnir capture
  -> optional Rúnir recall
  -> Setja injection envelope
  -> agent
```

That keeps the systems orthogonal:

- Setja constructs the current package
- Rúnir contributes continuity when helpful

## What to resist

These are the main integration mistakes to avoid:

- renaming Setja in a way that implies it *is* Rúnir
- moving recall policy into Setja
- making Setja depend on Rúnir for basic operation
- letting environment-specific adapters bypass Setja and talk to Rúnir directly for task context

The whole point of Setja is to give you a stable, local, project-facing context layer. Rúnir should enrich that layer, not replace it.
