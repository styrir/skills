# Shared closeout validation — 2026-10-31

Scope: source workflow for vk-2531. Desktop hook installation and actual host
Stop dispatch belong to vk-2530 and are not established by these checks.

## Diagnosis

Minni initially lacked a reviewable committed diagnosis/live qualification
record, although observations existed in chat and checkpoints. An empty approved
check list was also incorrectly treated by the author as preventing a receipt.
The workflow now requires an explicit committed qualification record or an
explicit source-only declaration before requesting review. Public reconcile
and independent review remain responsible for receipts.

## Source checks

`python3 -m unittest discover -s verk/scripts -p 'test_*.py'`: 14 passed.
Includes real CLI review-only submission in an isolated scratch store, with
no reviewer answer or fabricated receipt; a resumed session and corrected HEAD;
approved-check routing/deadline; duplicate, dirty and stale Stop requests;
wrong-session refusal; current-HEAD receipt matching and rejection visibility.
The bundled plugin copy passed the same 14 checks separately.
Skill Creator's quick_validate.py also passed. The skill entry contract and
its linked desktop/qualification guides own the updated workflow; no parent
ownership or routing contract changes.

## Live foreground observation and limits

The packaged foreground helper read Minni's actual independently issued receipt
vk-r64 at revision 57a3ba160e45883d1ce39c5fbc4a1dc00325a9e6. This verifies the
receipt observation route, not automatic desktop Stop dispatch. The scratch
fixtures never approve a live review. No permanent service is introduced.
