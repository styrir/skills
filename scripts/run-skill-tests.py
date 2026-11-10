#!/usr/bin/env python3
"""Run every skill's tests. This is the repo's recorded Verk check.

Suites are found from git-tracked files, never from a list of skill names:
  - a package.json with a "test" script runs `npm test` and claims the test
    files its script's globs match (anything else under it stays unclaimed);
  - each Python test file runs on its own from its folder: under unittest
    when it defines a TestCase (as a script when its name is not importable),
    otherwise as a plain script;
  - a shell test file runs with bash.
Python files in a folder whose PEP 723 header lists dependencies run under
`uv run --with` those dependencies.

Fails when a suite fails, when a unittest file or Node suite reports zero
tests, when a Node package with dependencies has no node_modules (this check
never installs), or when a tracked test file is claimed by no suite. Plain
script and shell suites are judged by exit code alone. Run from the repo root.
"""
import ast, fnmatch, json, re, shlex, subprocess, sys, time, tomllib
from collections import defaultdict
from pathlib import Path

TEST_NAMES = ["test_*.py", "*_test.py", "*-test.py",
              *[f"{p}.{e}" for e in ("ts", "js", "mjs", "cjs")
                for p in ("*.test", "*_test", "*-test", "test_*")],
              "test-*.sh", "*-test.sh"]
TAIL = 40  # lines of output shown for a failing suite

root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                           text=True, check=True).stdout.strip())
tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True,
                         check=True).stdout.decode().split("\0")
tracked = [f for f in tracked if f and (root / f).is_file()]
tests = sorted(f for f in tracked if any(fnmatch.fnmatch(Path(f).name, p) for p in TEST_NAMES))

def glob_re(pattern):
    """Shell glob to regex: ** spans folders, * and ? stay inside one."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")

def is_unittest(path):
    tree = ast.parse(path.read_text(), str(path))
    return any(isinstance(n, ast.ClassDef) and any(
        (isinstance(b, ast.Attribute) and b.attr == "TestCase")
        or (isinstance(b, ast.Name) and b.id == "TestCase") for b in n.bases)
        for n in ast.walk(tree))

def inline_deps(folder):
    """Dependencies from PEP 723 headers of tracked .py files in this folder."""
    deps = set()
    for f in tracked:
        if Path(f).parent == folder and f.endswith(".py"):
            m = re.search(r"^# /// script\s*$\n((?:^#.*$\n)*?)^# ///\s*$", (root / f).read_text(), re.M)
            if m:
                block = "\n".join(l[2:] if l.startswith("# ") else l[1:] for l in m.group(1).splitlines())
                deps.update(tomllib.loads(block).get("dependencies", []))
    return sorted(deps)

def python_cmd(folder):
    deps = inline_deps(folder)
    if not deps:
        return [sys.executable]
    return ["uv", "run", "--no-project", *[a for d in deps for a in ("--with", d)], "python"]

suites = []  # (name, cwd, command or None, count_regex or None, reason it cannot run or None)
claimed = set()

# Node: claims only the test files the test script's globs match.
for f in tracked:
    if Path(f).name != "package.json":
        continue
    pkg = json.loads((root / f).read_text())
    script = pkg.get("scripts", {}).get("test")
    if not script:
        continue
    folder = Path(f).parent
    globs = [glob_re(t) for t in shlex.split(script) if "*" in t]
    for t in tests:
        if Path(t).is_relative_to(folder) and not t.endswith((".py", ".sh")):
            rel = Path(t).relative_to(folder).as_posix()
            if any(g.match(rel) for g in globs):
                claimed.add(t)
    blocked = None
    if (pkg.get("dependencies") or pkg.get("devDependencies")) and not (root / folder / "node_modules").is_dir():
        blocked = "declares dependencies but has no node_modules; run npm ci there first"
    suites.append((str(folder), root / folder, ["npm", "test"], r"^(?:ℹ|#) tests (\d+)", blocked))

# Python: each test file on its own, from its own folder.
for t in tests:
    if not t.endswith(".py"):
        continue
    claimed.add(t)
    path, folder = Path(t), Path(t).parent
    py = python_cmd(folder)
    if not is_unittest(root / path):
        suites.append((t, root / folder, [*py, path.name], None, None))
    elif path.stem.isidentifier():
        suites.append((t, root / folder, [*py, "-m", "unittest", path.stem], r"^Ran (\d+) tests?\b", None))
    else:  # not importable (e.g. proxy-test.py): the file must run unittest.main() itself
        suites.append((t, root / folder, [*py, path.name], r"^Ran (\d+) tests?\b", None))

# Shell test files.
for t in tests:
    if t.endswith(".sh"):
        claimed.add(t)
        suites.append((t, root / Path(t).parent, ["bash", Path(t).name], None, None))

failed = []
for name, cwd, cmd, count_re, blocked in suites:
    start = time.monotonic()
    if blocked:
        ok, out, count = False, blocked, ""
    else:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        out, ok, count = r.stdout + r.stderr, r.returncode == 0, ""
        if ok and count_re:
            found = re.findall(count_re, out, re.M)
            n = int(found[-1]) if found else 0
            count = f"{n} tests, "
            if n == 0:
                ok, out = False, out + "\nreported zero tests\n"
    via = " via " + " ".join(cmd[cmd.index("uv"):cmd.index("python")]) if cmd and "uv" in cmd else ""
    print(f"{'PASS' if ok else 'FAIL'}  {name}  ({count}{time.monotonic() - start:.1f}s){via}", flush=True)
    if not ok:
        failed.append(name)
        print("\n".join("    " + l for l in out.rstrip().splitlines()[-TAIL:]), flush=True)

orphans = sorted(set(tests) - claimed)
for o in orphans:
    print(f"FAIL  {o}  (test file no suite runs)")
print(f"\n{len(suites) - len(failed)} of {len(suites)} suites passed"
      + (f"; {len(orphans)} unclaimed test file(s)" if orphans else ""))
sys.exit(1 if failed or orphans else 0)
