# Jev question design and known weak spots

Condensed from TypeSafe's Jev 1.13 docs and jaggedness page, the `hyper-jev` cookbook in
disler/ten-levels-of-jev, and our own live calibration (`research/jev/`).

## Pick the smallest judgment

| Need | Use | Avoid |
|---|---|---|
| Is the customer blocked? | Noul | Generating prose and parsing yes/no |
| Which approved handler owns this? | Choice | Free-form handler names |
| How severe? | Score with observable levels | Bare low/medium/high |
| Is the invoice overdue? | Date comparison in code | Asking Jev |
| How many items match? | One Noul per item, sum in code | Asking Jev to count |
| Draft a reply | An LLM (then verify it with Jev) | Asking Jev to write |

## Writing criteria

- **Literal reading.** Jev answers the words you wrote, not what you meant. Put boundary cases into the
  criteria text. If you catch yourself explaining what you really meant, that explanation is the missing
  criterion.
- **Situations, not degrees.** "The author is blocked, losing money or customers, or very angry" beats "high".
- **No indirection or double negatives.** Refer to parts of the state by name (`` `command` ``,
  `` `files["src/a.ts"]` ``, `` `output` ``).
- **Instructions and criteria must agree.** A Noul whose `true` describes "no" performs worse.
- **Question IDs are never sent to the model.** All meaning lives in `instructions` and `criteria`.
- **Choices need an exit.** Add `other` (or `none_of_the_above`) and route it to review even at high confidence.

## State

- Filter first. Unrelated content lowers accuracy. Send the hunk, not the repo, and the summary, not the log.
- Keep state plus the longest question under about 32k tokens. `jev.py` refuses more than ~110k characters.
- Adversarial state (text that argues for its own classification) can move answers. For content an attacker
  controls, ask about hostility directly and treat the answer as one signal.

## Thresholds and policy (in code)

- A Noul floor and bar: accept above the bar, reject below the floor, and send the middle to review.
- For Choice and Score, `confidence` gates whether the pick is reliable enough for the action.
- **Thresholds do not transfer** across question types or wordings. A Noul and the equivalent yes/no Choice give
  different numbers, and Q and not-Q don't sum to 1.
- Measured jitter: identical calls moved by up to 0.12 on one question and never flipped a decision across 4
  runs of 20 commands. Keep at least 0.1 of margin around every threshold you act on.
- Weights for composite scores belong in code (`{severity: 0.6, frustration: 0.3, quality: 0.1}`). Tuning is
  then a number change, not a prompt change.

## Lessons from our own gates (2026-09-28)

1. **Ask every risk class.** "What does this do to the machine?" rated `cat ~/.codex/auth.json`,
   `env | grep KEY`, and `security find-generic-password -w` as read-only at 0.99–1.00. Adding
   `secret_exposure`, `outward`, and `weakens_safety` Nouls took unsafe auto-approvals from 4 to 0 on train,
   held-out, and adversarial sets.
2. **"Addressed to an AI" is not "hostile".** Our SKILL.md, AGENTS.md, and CLAUDE.md legitimately instruct
   agents, and the naive injection question flagged them at 0.93. Ask whether the content tries to make the agent
   act *against its user*: leak, exfiltrate, destroy, bypass checks, hide actions, or claim approvals. That
   question scored 11/11.
3. **Obfuscated payloads belong to the static list.** `printf '…' | rev | sh` read as ambiguous (0.41
   read-only, 0.63 destructive). Any pipe into a shell or interpreter, `eval`, or `base64 -d |` is held by rule
   before Jev is asked.
4. **Tests look ~0.7 read-only** because they write artifacts. Set the read-only bar for auto-approval at 0.65,
   and only when every risk Noul is low.

## Cost and latency (measured through Requesty)

- About 400–600 ms end-to-end per call from this machine, and about 2 s wall-clock for 17 files in parallel.
- A typical 450-token call costs about $0.00002–0.00003. Output is free, and input is $0.042/MTok.
- Per token, Jev is about 238x cheaper than uncached Fable 5.1 input and about 6x cheaper than cached input.
  The bigger saving is that judged content never enters, and is never re-billed in, a long agent context.
