# Final shared closeout artifact qualification

Tested source: `36947c879bba87f46384634a8bb15d2b7ffd9a77`.
Observed at: 2026-10-31T07:25:27.800304+00:00.
Contract: vk-2536. Source artifact qualification only; desktop dispatch is vk-2530.

## Final source check

Command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s verk/scripts -p 'test_*.py'`.
Result: sixteen tests passed, exit 0, with the source checkout clean before this
record was written. This run followed both final regression-test corrections.
The earlier note was written before an assertion-index correction and must not
be read as evidence that the earlier test version passed.

The configured-check regression covers declaration before producers, completed
check names and exact revision after successful producers, result checkpoint
before the helper's reconcile, preservation of other fields, and refusal to
report failed producers as passed. The real isolated review-only route also
reads its persisted declaration back. Tests use synthetic scratch stores.

This qualification commit adds this document only; runtime and test files remain
identical to tested source `36947c879bba87f46384634a8bb15d2b7ffd9a77`. Review may open inside verk-check before
the helper returns, so the owner reviewer separately reads admitted check evidence
for its exact revision and decision bindings. Installed plugin tests, actual
Stop dispatch and any operator confirmation remain separate evidence.
