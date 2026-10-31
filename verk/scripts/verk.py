#!/usr/bin/env python3
"""Run Verk as the current Codex session, preserving normal CLI arguments."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

AUTHOR_VERBS = {"brief", "view", "add", "set", "need", "drop", "start", "checkpoint", "ask", "reconcile", "setup", "help"}


def invocation(arguments, environment, bin_dir=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args(arguments)
    args = options.arguments
    if not args:
        parser.error("supply a Verk verb, such as brief --json")
    verb = args[0]
    if verb not in AUTHOR_VERBS and verb != "check":
        raise ValueError(f"{verb!r} is outside this author-session wrapper; use the operator's own interface if required.")
    if verb == "setup" and any(a == "--apply" or a.startswith("--apply=") for a in args[1:]):
        raise ValueError("Applying setup is the operator's action; this wrapper can show setup plans only.")
    session = environment.get("CODEX_THREAD_ID") or environment.get("CODEX_SESSION_ID")
    if not session or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", session):
        raise ValueError("Codex session identity is unavailable; no Verk command was run.")
    repo = options.repo.expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f"Repository directory does not exist: {repo}")
    binary = (bin_dir or Path.home() / ".local" / "bin") / ("verk-check" if verb == "check" else "verk")
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError(f"Installed executable is unavailable: {binary}")
    env = dict(environment)
    env["VERK_ACTOR"] = f"codex:{session}"
    env["VERK_SESSION"] = session
    env.pop("VERK_REVIEWER", None)
    command = [str(binary), *(args[1:] if verb == "check" else args)]
    return command, repo, env


def main(arguments=None):
    try:
        command, repo, env = invocation(sys.argv[1:] if arguments is None else arguments, os.environ)
        return subprocess.run(command, cwd=repo, env=env, check=False).returncode
    except (ValueError, OSError) as error:
        print(f"verk skill: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
