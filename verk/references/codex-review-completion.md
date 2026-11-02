# Codex review completion

Codex owns this workflow in `scripts/codex_closeout.py` and
`scripts/codex_review.py`. The shared helper dispatches only the Codex entrypoint;
its common functions and the Claude route are unchanged. Verk core/store/policy
and independent-reviewer code are not modified. Each other harness must own its
own enforcement using its own events.

## Ready work and Stop

Use the normal closeout command with committed qualification or source-only
scope. Codex retains an explicitly pending request until a receipt. Its native
Stop response is `decision: "block"` with `reason` asking the model to continue
review/repair. It does not merely warn and then discard the reminder. Repeated
continued Stop events retain the request; a receipt removes it. No request means
no Verk call. Stale/dirty work is not submitted: the continuation asks the agent
to re-qualify at current HEAD. No tests run at Stop and no new daemon is created.
User interruption is a host event and remains effective; this is completion
workflow enforcement, not protection against a malicious same-user process.

The native Stop command/timeout need not change. Refresh the installed package
from this source using the existing packager and plugin add route. Preserve hook
trust; do not edit trust hashes. Handler tests and real host dispatch are separate
observations. [Official Codex hooks documentation](https://learn.chatgpt.com/docs/hooks#stop)
describes the native continuation response.

## Explicit operator delegation

When the operator asks Codex to finish reviews automatically, use
`--delegate-approved-goals` with foreground closeout. That authorization is copied
into this session's pending request for Stop follow-through. It is not inferred
from a passing test or generic permission to edit code.

This route handles goal-completion reviews only. The independent reviewer still
judges the exact target. Codex reads only the installed reviewer's existing
owner-controlled report and verdict manifest, never an arbitrary author report.
It requires matching decision/contract/revision, a successful final approval,
matching report length and Reviewed marker, current acceptance/subjects/project,
satisfied children/prerequisites and the reviewed child receipts. Missing or
failed review stays pending; rejected, stale or altered review cannot approve.

After rechecking the decision and clean HEAD, the adapter uses the existing
public `answer --report` CLI as the OS operator **under the user's explicit
delegation**. The resolution records the actual Codex session, delegation and
independent report SHA-256. This is an operator-delegated completion, not an author
review or impersonation of the independent reviewer. Core still validates the
answer and issues the receipt through normal reconciliation. No policy/review
mode, bindings, stores, checks or receipt rules are changed. Normal `verk.py`
commands remain author-only; this route exposes no arbitrary answer/setup/policy
operation and refuses another operator or harness.

For this operator, the 2 November 2026 instruction explicitly authorizes automatic
review completion in the Codex adapter. Apply this route to completed independent
goal reviews without sending terminal chores back to the operator. Other kinds
continue through Verk's existing independent reviewer.
