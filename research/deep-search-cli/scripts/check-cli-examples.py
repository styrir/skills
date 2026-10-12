#!/usr/bin/env python3
"""Check deep-search skill docs against the installed deep-search-mcp command registry.

Fails on flag-form examples (rejected since deep-search e8555ee) and on --json payloads
with unknown commands, unknown fields, missing required fields, or wrong types.
Payloads containing "..." are illustrative and only checked for their command name.

Usage: .venv/bin/python -I check-cli-examples.py [deep-search repo] [skills research dir]
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = Path(sys.argv[1] if len(sys.argv) > 1 else "/Users/brooks/Code/refs/deep-search")
DOCS = Path(sys.argv[2] if len(sys.argv) > 2 else HERE.parents[2])
sys.path.insert(0, str(REPO / "src"))

from deep_search_mcp.commands.registry import COMMAND_BY_NAME  # noqa: E402
from deep_search_mcp.errors import DeepSearchError  # noqa: E402

CALL = re.compile(r"deep-search-mcp ([a-z][a-z-]+)((?:[ \t]+\S.*)?)")
JSON_ARG = re.compile(r"^\s*--json '([^']*)'")
FLAG = re.compile(r"(?<![\w-])--[a-z][a-z-]*")


def check(path: Path) -> list[str]:
    problems = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        for m in CALL.finditer(line):
            name, rest = m.group(1), m.group(2)
            where = f"{path.relative_to(DOCS)}:{lineno}"
            if name not in COMMAND_BY_NAME:
                if rest.lstrip().startswith("--"):  # "deep-search-mcp as a CLI" is prose
                    problems.append(f"{where}: unknown command {name!r}")
                continue
            arg = JSON_ARG.match(rest)
            if not arg:
                stale = FLAG.findall(rest.split("`")[0])
                if stale:
                    problems.append(f"{where}: {name} uses flag form {stale}; use --json")
                continue
            payload = arg.group(1)
            if "..." in payload:
                continue
            try:
                COMMAND_BY_NAME[name].validate(json.loads(payload))
            except (json.JSONDecodeError, DeepSearchError) as exc:
                problems.append(f"{where}: {name} payload invalid: {exc}")
    return problems


def main() -> int:
    files = sorted(DOCS.glob("deep-search-*/**/*.md"))
    problems = [p for f in files for p in check(f)]
    for p in problems:
        print(p)
    print(f"checked {len(files)} files: {'FAIL' if problems else 'ok'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
