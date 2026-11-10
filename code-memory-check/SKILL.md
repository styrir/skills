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

- GitNexus: `gitnexus context <symbol> -r <repo>` gives `startLine` and
  `endLine`; pass them as they are. Add `--file <path>` when the name matches
  more than one symbol. (Its Cypher queries count the same lines from zero;
  add 1 to both if you take them from there.)
- CodeGraph: `codegraph explore "<symbol>"`.
- Neither: grep for the definition.

Pass the line range when you have it. Without it the script finds the function
by name, which takes the first line at column 0 that contains the name; that
can be a re-export or a type instead of the definition. The output's `scope:`
line says which method was used. If it says `whole file`, the function was
not found or the line range was wrong, and every date is for the file, not
the function: fix the target before reading on.

## 2. Run the check

```bash
python3 <this skill's folder>/scripts/check.py --symbol <name> --file <path> \
  [--lines START,END] [--repo <repo root>] [--passing] [--file-facts] \
  [--full [ID ...]]
```

`--file` is relative to the repo root. `--repo` defaults to the current
folder, so pass it unless you are already at the repo root.

Needs `RUNIR_API_KEY` and `RUNIR_USER_ID` in the environment, the same as the
`runir-search` skill. If the search fails, say so; do not guess.

Output comes in three parts:

1. Facts that name the function in their first 220 characters, one block
   each, showing those 220 characters. Read these.
2. One line counting facts that name the function only later in the text,
   with how many are re-check and ok. Most name it in passing, in a list of
   files attached to a claim about something else. Add `--passing` to list
   them; each block then has a `mention:` line with the text around the name.
3. One line counting facts that name only the file. These are usually about
   other code in the same file. Add `--file-facts` to list them when the
   lists above are empty or you need the wider picture.

Each fact is marked:

- `OK` — written after the function's last change.
- `RE-CHECK` — the function has changed since the fact was written, with the
  number of commits.
- A `note:` when the fact names a file that is absent from this checkout. That
  can mean a rename, or a path from another repository.

## 3. Judge the flagged facts

`RE-CHECK` means "the code moved on", not "the fact is wrong". To read the
facts you are judging in full, rerun with `--full <id> [<id> ...]` (id
prefixes work; `--full` alone prints every listed fact whole). Then read the
current function and put each fact in one of these:

- **Still true** — the code does what the fact says.
- **True, details drifted** — the claim holds but a line number, path or name
  in it is out of date. Old line numbers almost always are.
- **Outdated** — the code contradicts it. A bug report or review finding is
  usually outdated because it was fixed: check whether the fix landed.
- **Not about this function** — the fact names the function in passing and
  its claim is about other code. Check that code if it matters; otherwise say
  so and move on.
- **Can't tell from code** — status and history, such as "the task is done"
  or "two scouts are running". Do not force a verdict.

On a long list, judge the facts that make a claim about the code first. For
what depends on the function, use the code index's impact query.

## 4. Report

Tell the user which facts still hold and which are outdated, quoting the fact
and the code that contradicts it, with its file and line. Say how many facts
you judged out of how many were listed. Then stop.

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
- Each search returns at most 50 facts, and the output does not say when a
  search was cut off. Older facts can drop out as newer ones about the same
  function are stored, including facts captured from earlier runs of this
  skill.
- The split between parts 1 and 2 goes by where the name falls in the text,
  nothing else. A fact about the function that names it late is counted in
  part 2; a passing mention near the start is listed in part 1.
- Dates come from the checkout you run in. Run it where the code you are
  about to edit lives.
