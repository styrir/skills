# Codex review adapter validation — 2 November 2026

The operator requested automatic review completion in each individual harness
adapter, explicitly leaving standard Verk code unchanged. Codex's completion
logic is in `codex_closeout.py` and `codex_review.py`. The shared script's only
production changes dispatch the Codex entrypoint and parse its explicit delegation
flag. Shared functions, `verk.py` author identity, Claude behavior and Verk
core/store/policy/reviewer code are unchanged.

`python3 -m unittest discover -s verk/scripts -p 'test_*.py'`: **26 passed**.
Skill Creator `quick_validate.py verk`: passed. Coverage includes missing,
failed, rejected, altered and stale approval; wrong project/acceptance/harness;
unfinished or changed child receipts; dirty/moved work; untrusted report paths;
operator-delegation audit reason; repeated native Stop continuation and marker
persistence; receipt/duplicate completion; all existing author/Claude tests.
The existing real-CLI resume fixture omitted acceptance; it now supplies its
synthetic acceptance because current Verk correctly refuses absent acceptance.
No core behavior was changed to make that test pass.

A real isolated temporary Verk store produced a goal receipt through the new
Codex route using a **synthetic independent-report fixture**. This is a boundary
integration test, not a real model review. Operator fixture setup is confined to
that store. The before/after policy is identical and author attempts retain their
Codex session. No live goal is approved by that test.

The native Stop JSON contract was checked against official OpenAI documentation:
https://learn.chatgpt.com/docs/hooks#stop . Pending review returns a continuation
(`decision: block`), not `continue: false`. No independent verdict is synthesized,
no tests run at Stop, and no daemon is created. Real installed host dispatch and
live Orakel completion will be recorded after observation; synthetic handler
output alone does not prove desktop enforcement.
