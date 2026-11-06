# Desktop closeout status: Claude Code and Codex

State at 2026-11-06T17:38Z. This summarizes the two host records and adds the Codex foreground outcome, which Codex's own record does not contain. Neither host is broadly qualified: each route below is shown only as far as its evidence goes.

- [Codex qualification](codex-desktop-closeout/qualification.md), in this repository
- Claude qualification: `docs/evidence/claude-code-desktop-closeout/qualification.md` in `plg-crk`, commit `03d2a7b`

## Outcome by host

| Case | Claude Code desktop | Codex desktop |
|---|---|---|
| Installed identity and hook dispatch | PASS: `verk-adapter claude-code stop`, plugin 0.1.1 | PASS: `closeout.py hook-stop`, plugin 0.2.6 |
| Stop with no request | PASS (narrow): dispatch recorded, nonblocking, no output | INCOMPLETE: host completion recorded, handler dispatch and output unobserved |
| Stop while a review is pending | PASS (narrow): four silent, nonblocking Stops | PASS: counter reached 11 at 17:29:07Z, with the request retained |
| Foreground closeout | PASS: `vk-2624`, one submission | PASS: `vk-2628`, one submission from the installed helper |
| Python marker follow-up | Unavailable: no consumer loaded | Consumed by the loaded hook, as recorded in the limit probe |
| Interruption | NOT RUN: needs the operator to press Stop during a pending closeout | PASS: stopped after four callbacks; the one-to-two-callback target was missed |
| Positive reconciliation at Stop | Not observed | Not observed: both reviews answered outside a Stop |
| Notice visibility in the app | UNOBSERVED | INCOMPLETE |

## Foreground stages

These are separate facts. The policy on both contracts is agent review with no approved checks, so there is no check admission to report.

| Stage | `vk-2624` (Claude) | `vk-2628` (Codex) |
|---|---|---|
| Reviewed revision | `010ee5d` | `826ac1e` |
| Independent review | `vk-d276` approved, after three refused tries | `vk-d281` approved |
| Automated gate | Approve, lowest clause 0.90 | **Reject**, lowest clause 0.42 |
| Check admission | None | None |
| Receipt | `vk-r145`, 15:49:17Z | `vk-r149`, 17:37:48Z |

**Gate disagreement on `vk-d281`:** the gate scored "A fresh actual desktop no-request baseline is recorded" at 0.42, the same gap Codex's record marks INCOMPLETE. The reviewer read that clause as requiring a truthful record of the event and its limits, not proof that the handler ran, and said a stricter reading would change the result. Under this policy the reviewer decides, so the receipt stands, and it should not be read as evidence that the baseline handler ran.

The `vk-2624` refusal is recorded in the Claude qualification. Why the same revision passed on retry is not established.

## Other receipts

| Contract | Purpose | Receipt | Revision |
|---|---|---|---|
| `vk-2625` | Claude qualification result | `vk-r147` | `03d2a7b` in `plg-crk` |
| `vk-2626` | Codex limit probe record | `vk-r148` | `5d5eee3` |
| `vk-2627` | Stop telling readers to wait when no verdict is coming | `vk-r146` | `5d5eee3` |

`vk-2626` was submitted from a Claude session at the operator's instruction. All of its host evidence is Codex's own, and its record was not edited.

## Remaining

1. **Installed Codex plugin lacks the `vk-2627` fix.** Plugin 0.2.6 still has `closeout.py` starting `ec21b3bc`, so its Stop can still say to wait on a review that has no verdict coming. The session's permission system blocked the install. A side-effect-free build from current source differs in five files, all from `vk-2627`, and `hooks/closeout.json` is byte-identical. The Claude path reads the source through a symlink, so it already has the fix. The fix has not been observed in a Codex host.
2. **Codex marker for session `01a1b1e6-b113-74d3-a6ea-33f0de73bf87`.** At this writing it remains on disk, after the review it was waiting on already reached a receipt. That session's next Stop is expected to settle it, which would also be the first Codex Stop observed reporting a receipt.
3. **Claude interruption.** It stays NOT RUN until the operator stops a turn during a fresh pending closeout.
4. **Limits with no agent-side test.** These are app display of notices on both hosts, Codex's baseline handler output, and the two Claude Stop handlers recorded only as `callback`. The Claude adapter's hash is also not tied to a source commit.
5. **Positive Stop reconciliation.** Neither host has shown one. On Claude, `stopReconcile` skips contracts with an open review, and checkpoints with proof already reconcile at once, so ordinary work leaves it little to do.
6. **Publication.** Commits in `skills` and `plg-crk` are local. Codex's original captures in `plg-crk/docs/evidence/codex-desktop-closeout/` remain untracked; the archive in this repository is the committed copy.
