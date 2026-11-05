---
name: styrir-init
description: Explain the retired Styrir repository bootstrap when a user requests initialization. Automatic bootstrap is disabled pending its Verk migration; do not run the legacy Beads initializer.
---

# Styrir initialization - pending migration

The former initializer and templates depended on Beads, which is decommissioned
for this operator. The script now refuses setup without changing the target.
Do not execute the legacy implementation, revive bd/Dolt, or use its templates
to create active tracking instructions. Migration is tracked as `vk-2589`.

Use the installed Verk skill for current tracking. On an unbound repository,
its `setup --json` is a read-only plan; applying bindings or approving policy
remains the operator's action. Git remote creation and publication retain the
repository's existing authorization boundaries.

The legacy templates remain historical migration inputs. This skill does not
claim a replacement bootstrap exists. Verify retirement with:

```sh
bash scripts/test-styrir-init.sh
```
