---
name: code-memory-check
description: >
  Check what Rúnir remembers about a specific function or file against the
  code as it is now, and flag remembered facts written before the code last
  changed. Use on request ("what do we remember about X", "are the memories
  about this function still true") or before editing unfamiliar code that
  memory mentions. Reads only; stores nothing. Do NOT use on every turn, for
  non-code questions, or as a replacement for the ambient Rúnir hooks.
---

# Code memory check

Rúnir facts do not know when the code they describe changes. This skill does
the comparison at the moment you need it: facts about one function, the date
that function last changed, and which facts predate the change.

Nothing is stored. Each run is two Rúnir searches and one `git log`.

## 1. Name the target

You need a symbol name and its file path, relative to the repo root.

If a code index is available, use it to confirm where the symbol lives now and
to get its line range. Any index works:

- GitNexus: `gitnexus context <symbol> -r <repo>` (its line numbers are
  zero-based; add 1 to both).
- CodeGraph: `codegraph explore "<symbol>"`.
- Neither: grep for the definition.

Pass the line range when you have it. Without it the script finds the function
by name, which takes the first line at column 0 that contains the name; that
can be a re-export or a type instead of the definition. The output says which
method was used.

## 2. Run the check

```bash
python3 <this skill's folder>/scripts/check.py --symbol <name> --file <path> \
  [--lines START,END] [--repo <repo root>] [--file-facts]
```

`--file` is relative to the repo root. `--repo` defaults to the current
folder, so pass it unless you are already at the repo root.

Needs `RUNIR_API_KEY` and `RUNIR_USER_ID` in the environment, the same as the
`runir-search` skill. If the search fails, say so; do not guess.

Output comes in two parts:

1. Facts that name the function, one block each. Read these.
2. One line counting facts that name only the file, with how many are
   re-check and ok. These are usually about other code in the same file. Add
   `--file-facts` to list them when the function-named list is empty or you
   need the wider picture.

Each fact is marked:

- `OK` — written after the function's last change.
- `RE-CHECK` — the function has changed since the fact was written, with the
  number of commits.
- A `note:` when the fact names a file that is absent from this checkout. That
  can mean a rename, or a path from another repository.

If the output says the search hit its limit, the list may be partial. Older
facts can drop out as newer ones about the same function are stored,
including facts captured from earlier runs of this skill.

## 3. Judge the flagged facts

`RE-CHECK` means "the code moved on", not "the fact is wrong". For each one,
read the current function and decide: still true, outdated, or can't tell.
For what depends on the function, use the code index's impact query.

## 4. Report

Tell the user which facts still hold and which are outdated, quoting the fact
and the code that contradicts it. Then stop.

- Do not forget, edit or supersede a fact on your own.
- If the user asks you to correct one, store the corrected statement with
  `runir_store`; Rúnir's normal write arbitration handles the old one.

## Limits

- Matching is by name. Facts that describe the function without naming it or
  its file are missed; common names over-match.
- A large, frequently edited function is flagged almost every time. The flag
  is a prompt to read, not a verdict.
- A function that was moved shows its move as the last change.
- Only committed changes count. Uncommitted edits are invisible.
- If the repo's history starts at an import, every fact older than the import
  is flagged. The output notes when a fact predates the function's history.
- Rúnir memory spans projects, so a same-named symbol or file in another
  project can match.
- Each search returns at most 50 facts.
- Dates come from the checkout you run in. Run it where the code you are
  about to edit lives.
