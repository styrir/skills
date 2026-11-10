# code-memory-check: run record

Recorded 2026-11-10. This file is the evidence for claims no automated check
in this repo covers: that the skill is linked, that the script runs against
real functions with a live Rúnir, and that the judging and reporting steps
were carried out. Fact text is left out on purpose: Rúnir memory is private.
Facts are named by the first eight characters of their id.

## Link check

Run from the main checkout of this repo:

```
python3 scripts/link-harness-skills.py --check    # exit 0, every line "ok"
readlink ~/.claude/skills/code-memory-check       # -> <this repo>/code-memory-check
readlink ~/.codex/skills/code-memory-check        # -> <this repo>/code-memory-check
```

## Script tests

```
python3 -m unittest discover -s code-memory-check/scripts    # Ran 9 tests, OK
```

`scripts/test_check.py` builds a throwaway git repo and a stub Rúnir on
localhost. It covers the by-name lookup, `--lines`, both whole-file fallbacks,
a function that did not change in a file that did, the OK / RE-CHECK dates,
a timestamp with no zone, the split at the 220-character preview (a name
ending at character 220 is listed, one ending at 221 is counted), `--passing`,
no partial notice when a search returns its limit, the file-only tally,
`--file-facts`, the `mention:` line, `--full` with a good and a bad id, a
search that fails, and missing credentials. Python 3.14.6.

## Live runs

Against the Rúnir repository at `591fc1f`, with the local Rúnir service.

| Function | File | Target found by | Last changed | Facts naming it | Re-check | OK | Named only past the preview | File-only | Time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `arbitrateWrite` | `src/storage/writes/write-arbitrator.ts` | `--lines 1259,2062` from `gitnexus context` | 2026-09-25 `9672709` | 34 | 21 | 13 | 20 | 42 | 1.2 s |
| `annotateSelectedFacts` | `src/recall/source-excerpts.ts` | name | 2026-09-27 `6b1328c` | 7 | 5 | 2 | 5 | 4 | 2.2 s |
| `extractMemories` | `src/capture/extraction/capture.ts` | name | 2026-11-09 `3a18143` | 32 | 31 | 1 | 24 | 7 | 1.8 s |

Re-run after passing mentions were split out (vk-2712), against Rúnir at
`98784c1` (no change to these functions since `591fc1f`). The counts differ
from the table above because Rúnir's memory changed in between. Run the same
day, the previous script (`2f1b379`) found the same totals (34, 9, 33) and
printed a `mention:` line for the same number of facts (17, 5, 24) as the new
script counts as named only later.

| Function | Named in first 220 chars | Named only later | File-only | Time |
| --- | --- | --- | --- | --- |
| `arbitrateWrite` | 17 | 17 (10 re-check, 7 ok) | 41 | 1.3 s |
| `annotateSelectedFacts` | 4 | 5 (5 re-check) | 4 | 1.9 s |
| `extractMemories` | 9 | 24 (24 re-check) | 7 | 1.1 s |

No run printed a partial-list notice.

Also run: `--full dabf29d4 zzzz` (prints one fact whole, then
`no listed fact has an id starting with zzzz`), and `neutralize` in
`source-excerpts.ts`, which matched four facts that use the ordinary word
rather than the function: the common-name limit in SKILL.md.

## Judging and reporting trial (steps 3 and 4)

A sample: 11 of the 57 facts flagged RE-CHECK across the three functions,
chosen because they make a claim that code can settle.

| Fact | Function | Verdict | Current code |
| --- | --- | --- | --- |
| `746911d2` | `arbitrateWrite` | Still true | The clock is read once at `write-arbitrator.ts:1358`; the zero default is passed only when the temporal guard is off, and the one reader sits inside that guard (`:596`, `:613`). |
| `968c0c12` | `arbitrateWrite` | Still true | Optional `nowMs` on the input (`:187`), `withinHours` (`:212`), and on `pruneRecentWrites` / `rememberWrite` in `recent-writes.ts`. |
| `5bfc5c96` | `arbitrateWrite` | True, details drifted | The resolve-and-clamp block is at `:1273-1292`, not `:1150-1169`; the floor test is at `:276`, not `:820`. A shell script it cites is not in this checkout. |
| `cfa69a52` | `arbitrateWrite` | True, details drifted | The guard exists and is read in `arbitrateWrite` (`:1340`) as designed; the predicate was built as `mergeKeepBothReason` (`write-signals.ts:455`), not under the name in the design note. |
| `e070746f` | `arbitrateWrite` | Outdated | Says a fixed 0.85 floor at `:819-824`. The floor is now `supersedeCandidateFloor ?? mergeThreshold` at `:276`. |
| `dabf29d4` | `arbitrateWrite` | Outdated (fixed) | Reported two of four `targetTable` sites without the fallback. All four have it: `:1323`, `:1886`, `:1953`, `:2022`. |
| `16391aa5` | `arbitrateWrite` | Not about this function | The claim is about a replay harness that calls the function. |
| `4c72f853` | `annotateSelectedFacts` | Not about this function; its claim is outdated (fixed) | The passing mention still holds (`source-excerpts.ts:66` returns before any read when the flag is off). The finding itself, in `enrichLinkedExactQaHits`, is fixed: it now returns unless the mode is `on` (`memory-query.ts:62`) and has its own timeout. |
| `a3240d09` | `extractMemories` | Outdated | Names an older model, provider and line `:378`. The default is now set at `capture.ts:529` and the function starts at `:771`. |
| `999a6366` | `extractMemories` | Outdated (fixed) | Reported the session timestamp not reaching the function. The route reads it (`routes/hooks/index.ts:1195`) and passes it (`:1734`); the function takes it as its fourth parameter. |
| `cb7e13d5` | `extractMemories` | Outdated (fixed) | Reported the timeout being cleared before the response body was read. It is now cleared after `response.json()`. A later fact (`1a8be05b`) records the fix. |

Totals: 2 still true, 2 true with drifted details, 5 outdated (3 of them
because the reported problem was fixed), 2 not about the function.

### What the trial changed in the skill

- The listing cut each fact at 220 characters, which is not enough to judge
  it. Added `--full [ID ...]`.
- Most function-named facts name the function only in a list attached to a
  claim about something else (20 of 34, 5 of 7, 24 of 32). Added the
  `mention:` line and a "not about this function" verdict.
- Step 3 offered three verdicts. It now has five, including "true, details
  drifted" and "can't tell from code".
- Step 1 said `gitnexus context` counts lines from zero. It does not; only
  the Cypher route does. Following the old text gave an out-of-range line
  span and a silent fall back to whole-file dates. The text is corrected and
  the output now says `whole file (line range not valid)`.
- A timestamp without a zone would have raised an error. It is read as UTC.
- Passing mentions crowded out the facts about the function. Facts that name
  it only past the 220-character preview are now counted on one line, like
  file-only facts, and `--passing` lists them (vk-2712).
- The "search hit its limit, so this list may be partial" notice printed on
  every live run, so it said nothing. It is gone; the 50-fact caveat stays
  in SKILL.md under Limits (vk-2712).
