# Qualification evidence before review

Use a short committed record when acceptance includes installation, live
interaction or operator confirmation. Start collecting it while doing the work;
do not reconstruct a success story at closeout. Keep raw content and secrets out.

Record only what applies:

- Diagnosis: the actual failure, observed inputs, root cause evidence and
  remaining uncertainty. Distinguish a demonstrated defect from a causal hypothesis.
- Source checks: source revision, exact commands, results and any failed normal
  path. A fallback result does not replace the normal path's result.
- Installed artifact: version/revision, signed hash or other reproducible identity,
  permission/signature checks and rollback location when applicable.
- Live observations: action taken, timestamp, actual result and tool/source that
  observed it. Explain what the test does not establish.
- Operator confirmations: attribute them explicitly; do not label them
  independently observed or copy unrelated conversation.
- Remaining gates: pending, failed and intentionally out-of-scope checks,
  including long-duration or release qualification limits.

The reviewer reads this at the exact reviewed revision and decides whether it
supports acceptance. The author does not issue the review verdict or receipt.
For source-only acceptance, `--source-only` makes the narrower scope explicit
without inventing installation or operator evidence.
