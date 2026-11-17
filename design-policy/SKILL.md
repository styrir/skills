---
name: design-policy
description: Coordinate UI design work using the shared design skills. Use for building, redesigning, or reviewing interfaces, or when asked for the combined UI skill setup; selects one design lead and relevant specialist skills.
---

# Shared UI design workflow

Use this as the entry point for the consolidated UI skills. Carry the user's
actual UI task through implementation and verification; loading a skill is not
the deliverable. User instructions and the project's design system take priority.

## Choose only what the task needs

| Need | Skill |
| --- | --- |
| Product UI, settings, dashboards, general design or refinement | `impeccable` (default lead) |
| Landing pages, portfolios, deliberate visual art direction | `design-taste-frontend` (alternate lead, only when enabled) |
| Realistic worst-case data, overflow, empty and missing states | Emil `break-ui` |
| Motion review requested by the user | Emil `review-animations` |
| Component-library selection requested by the user | Emil `pick-ui-library` |
| References from real products | Connected Mobbin skills/tools, when useful and available |

Read the chosen lead's SKILL.md, then only the applicable references. Use one
visual lead per task; do not stack Taste and Impeccable instructions. Reuse the
project's existing components, installed dependencies and native controls before
adding a library. Library picks are advice, not authority to replace the stack.
Check current official library documentation before implementation.

Find skills in the current harness catalog first. Respect disabled skills; use
Impeccable when Taste is disabled, and do not bypass that setting by reading its
files directly. This installation exposes the
plain skills in `~/.agents/skills/<name>/SKILL.md`. Impeccable has official
provider-specific builds: prefer the current harness's registered build; do not
substitute another harness's build. If a dependency is missing, state that limit
and continue the authorized work using available guidance.

Use `break-ui` when edge-case testing is relevant, passing the real target and
whether fixes are already authorized. Preserve upstream explicit-invocation
metadata for `review-animations` and `pick-ui-library`; do not auto-run them for
every UI task. Resolve upstream file links from the **real skill directory**
after following symlinks, so sibling references stay inside the pinned checkout.

Mobbin uses the connected plugin and its own guidance/authentication. Discover
its tools before use; this skill does not install or grant connector access.
Cook contributes the bounded reference → render → critique approach, but the
full Cook workflow is only for an explicit request with an agreed budget.

## Deliver and check

Preserve the existing identity during refinement; honor an explicit redesign
brief. Render the result and check the affected interaction, keyboard/focus,
narrow layouts, text zoom, and reduced motion where applicable. Make a bounded
fix-and-recheck pass; distinguish observed results from inferred behavior.

Keep local lessons in project guidance. Never edit upstream skill files to
store preferences or let an updater write through shared links. For installation,
pins and rollback, see [installation.json](installation.json); use the repository's
existing `harness-links.json` and linker. Stage updates at a new revision before
repointing links. Do not update a live pin in place.
