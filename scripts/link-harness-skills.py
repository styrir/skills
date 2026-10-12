#!/usr/bin/env python3
"""Link harness skill dirs (Codex, Grok, Hermes, ...) to this repo, per harness-links.json.

Default is a dry run that prints the plan. --apply makes changes; --check exits 1 if
anything is not linked correctly. A real directory in the way is moved to
~/.skill-link-backups/<timestamp>/ (never deleted). A copy whose files differ from the
repo is refused unless --replace-diverged, so drifted edits get merged first.
"""
import argparse
import filecmp
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IGNORE = {".DS_Store", "node_modules", "__pycache__", ".git", ".venv"}


def same_tree(a: Path, b: Path) -> bool:
    cmp = filecmp.dircmp(a, b, ignore=list(IGNORE))
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    return not (mismatch or errors) and all(same_tree(a / d, b / d) for d in cmp.common_dirs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="make the changes")
    ap.add_argument("--check", action="store_true", help="exit 1 unless every link is correct")
    ap.add_argument("--replace-diverged", action="store_true", help="also back up and replace copies that differ from the repo")
    ap.add_argument("--harness", action="append", help="limit to these harnesses")
    args = ap.parse_args()

    manifest = json.loads((REPO / "harness-links.json").read_text())
    backup = Path.home() / ".skill-link-backups" / time.strftime("%Y%m%d-%H%M%S")
    bad = 0
    for harness, spec in manifest.items():
        if harness.startswith("_") or (args.harness and harness not in args.harness):
            continue
        base = Path(os.path.expanduser(spec["dir"]))
        for rel, src_rel in spec["links"].items():
            link, src = base / rel, REPO / src_rel
            label = f"{harness}: {rel}"
            if not (src / "SKILL.md").is_file():
                print(f"ERROR   {label}: repo path {src_rel} has no SKILL.md")
                bad += 1
                continue
            if link.is_symlink() and Path(os.path.realpath(link)) == src.resolve():
                print(f"ok      {label}")
                continue
            bad += 1
            if link.is_symlink():
                action = f"repoint (was -> {os.readlink(link)})"
            elif link.is_dir():
                if not same_tree(link, src) and not args.replace_diverged:
                    print(f"DIVERGED {label}: copy differs from repo; merge it first or pass --replace-diverged")
                    continue
                action = "replace copy (backed up)"
            elif link.exists():
                print(f"ERROR   {label}: {link} is a file, not a skill dir")
                continue
            else:
                action = "create"
            print(f"{'apply' if args.apply else 'plan'}   {label}: {action}")
            if not args.apply:
                continue
            if link.is_symlink():
                link.unlink()
            elif link.is_dir():
                dest = backup / harness / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(link), str(dest))
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(src)
            bad -= 1
    if args.apply and backup.exists():
        print(f"backups: {backup}")
    return 1 if (args.check and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
