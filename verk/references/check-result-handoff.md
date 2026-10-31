# Approved-check result handoff — 2026-10-31

Scope: vk-2534, shared source workflow only.

An implementation review rejected a stale checkpoint saying final checks were
pending, despite admitted passing producers at the reviewed revision. The shared
helper now records completed approved check names and exact HEAD after successful
producers and the unchanged/clean-tree check, before reconcile opens review.
It retains the qualification declaration and does not overwrite open/decided items.

`python3 -m unittest discover -s verk/scripts -p 'test_*.py'`: sixteen passed.
The configured-check regression checks declaration → producers → results →
reconcile ordering, exact revision, check names and preservation of other fields.
Existing tests cover producer errors and the real isolated review-only route.
The installed plugin and actual desktop callback are separate gates in vk-2530.
