#!/usr/bin/env python3
"""Run every skill's tests. This is the repo's recorded Verk check.

Suites are found from git-tracked files, never from a list of skill names:
  - a package.json with a "test" script runs `npm test` and claims the test
    files that script names, expanded the way npm's shell expands them
    (quoted globs the way Node's test runner does);
  - each Python test file runs on its own from its folder: under unittest
    when it imports the unittest module or a TestCase from it (as a script
    when its name is not importable), otherwise as a plain script;
  - a shell test file runs with bash.
Python files in a folder whose PEP 723 header lists dependencies run under
`uv run --with` those dependencies.

Suites run with no stdin and a time limit. Fails when a suite fails, hangs,
or cannot be set up, when a unittest file or Node
suite reports zero tests, when a Node package with dependencies has no
node_modules (this check never installs), when a tracked test file is
missing from disk, or when a tracked test file is claimed by no suite. Plain
script and shell suites are judged by exit code alone.
"""
import ast, fnmatch, glob, json, os, re, signal, subprocess, sys, time, tomllib
from pathlib import Path

TEST_NAMES = ["test_*.py", "*_test.py", "*-test.py",
              *[f"{p}.{e}" for e in ("ts", "js", "mjs", "cjs")
                for p in ("*.test", "*_test", "*-test", "test_*")],
              "test-*.sh", "*-test.sh"]
TAIL = 40  # lines of output shown for a failing suite
# seconds; a suite that hangs fails instead of stalling the check
SUITE_TIMEOUT = float(os.environ.get("RUN_SKILL_TESTS_TIMEOUT", 600))
GLOB_CHARS = set("*?[")
NODE_TEST_RUNNERS = {"node", "tsx"}  # runners whose --test mode takes test files as arguments

root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                           text=True, check=True).stdout.strip())
tracked = [f for f in subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True,
                                     check=True).stdout.decode().split("\0") if f]
tests = sorted(f for f in tracked if any(fnmatch.fnmatch(Path(f).name, p) for p in TEST_NAMES))

suites = []  # dicts: name, cwd, cmd, count (regex or None), error (str or None)
claimed = set()

def suite(name, cwd=None, cmd=None, count=None, error=None):
    suites.append({"name": name, "cwd": cwd, "cmd": cmd, "count": count, "error": error})

def node_claims(folder, script):
    """Files the test script names, relative to the repo root."""
    found = set()
    # Only arguments of a test-runner command count; a file merely mentioned
    # elsewhere (an echo, a build step) is not run, so it stays unclaimed.
    runner_args = []
    for segment in re.split(r"&&|\|\||[;|]", script):
        tokens = re.findall(r"""'[^']*'|"[^"]*"|\S+""", segment)
        words = [t for t in tokens if not re.match(r"^\w+=", t)]  # drop VAR=value prefixes
        if words[:1] == ["npx"]:
            words = words[1:]
        if words and Path(words[0]).name in NODE_TEST_RUNNERS and "--test" in words:
            runner_args += words[1:]
    for raw in runner_args:
        quoted = raw[0] in "'\"" and raw[-1] == raw[0] and len(raw) > 1
        token = raw[1:-1] if quoted else raw
        if quoted and GLOB_CHARS & set(token):
            # passed through to the tool; Node's test runner globs it (** recursive, no dotfiles)
            hits = glob.glob(token, root_dir=root / folder, recursive=True)
        elif GLOB_CHARS & set(token):
            # npm runs scripts with sh, which expands the glob itself
            r = subprocess.run(["sh", "-c", f"for f in {token}; do printf '%s\\0' \"$f\"; done"],
                               cwd=root / folder, capture_output=True)
            hits = [h for h in r.stdout.decode().split("\0") if h and h != token]
            if not hits:  # sh leaves an unmatched glob as is, and the tool globs it itself
                hits = glob.glob(token, root_dir=root / folder, recursive=True)
        else:
            hits = [token]
        found.update((folder / h).as_posix() for h in hits if (root / folder / h).is_file())
    return found

# Node packages.
for f in tracked:
    if Path(f).name != "package.json" or not (root / f).is_file():
        continue
    folder = Path(f).parent
    try:
        pkg = json.loads((root / f).read_text())
        script = pkg.get("scripts", {}).get("test")
        if not script:
            continue
        mine = node_claims(folder, script)
    except Exception as e:
        suite(str(folder), error=f"cannot read {f}: {e}")
        claimed.update(t for t in tests if Path(t).is_relative_to(folder) and not t.endswith((".py", ".sh")))
        continue
    claimed.update(t for t in tests if t in mine)
    if (pkg.get("dependencies") or pkg.get("devDependencies")) and not (root / folder / "node_modules").is_dir():
        suite(str(folder), error="declares dependencies but has no node_modules; run npm ci there first")
    else:
        suite(str(folder), root / folder, ["npm", "test"], r"^(?:ℹ|#) tests (\d+)")

def imports_unittest(path):
    """True when the file imports unittest itself, or from unittest or one of its
    submodules (under any alias). Importing only unittest.mock does not count."""
    def counts(module):
        return module == "unittest" or (module.startswith("unittest.") and not module.startswith("unittest.mock"))
    for n in ast.walk(ast.parse(path.read_text(), str(path))):
        if isinstance(n, ast.Import) and any(counts(a.name) for a in n.names):
            return True
        if isinstance(n, ast.ImportFrom) and counts(n.module or ""):
            return True
    return False

def inline_deps(folder):
    """Dependencies from PEP 723 headers of tracked .py files in this folder."""
    deps = set()
    for f in tracked:
        if Path(f).parent == folder and f.endswith(".py") and (root / f).is_file():
            m = re.search(r"^# /// script\s*$\n((?:^#.*$\n)*?)^# ///\s*$", (root / f).read_text(), re.M)
            if m:
                block = "\n".join(l[2:] if l.startswith("# ") else l[1:] for l in m.group(1).splitlines())
                deps.update(tomllib.loads(block).get("dependencies", []))
    return sorted(deps)

# Python test files, each on its own from its own folder.
for t in tests:
    if not t.endswith(".py"):
        continue
    claimed.add(t)
    path, folder = Path(t), Path(t).parent
    if not (root / path).is_file():
        suite(t, error="tracked but missing from disk")
        continue
    try:
        deps = inline_deps(folder)
        py = ["uv", "run", "--no-project", *[a for d in deps for a in ("--with", d)], "python"] if deps else [sys.executable]
        unit = imports_unittest(root / path)
    except Exception as e:
        suite(t, error=f"cannot set up: {e}")
        continue
    if not unit:
        suite(t, root / folder, [*py, path.name])
    elif path.stem.isidentifier():
        suite(t, root / folder, [*py, "-m", "unittest", path.stem], r"^Ran (\d+) tests?\b")
    else:  # not importable (e.g. proxy-test.py): the file must run unittest.main() itself
        suite(t, root / folder, [*py, path.name], r"^Ran (\d+) tests?\b")

# Shell test files.
for t in tests:
    if t.endswith(".sh"):
        claimed.add(t)
        if (root / t).is_file():
            suite(t, root / Path(t).parent, ["bash", Path(t).name])
        else:
            suite(t, error="tracked but missing from disk")

failed = []
for s in suites:
    start, out, ok, count = time.monotonic(), s["error"] or "", s["error"] is None, ""
    if ok:
        try:
            # own process group, so a timeout also stops what npm or bash started
            p = subprocess.Popen(s["cmd"], cwd=s["cwd"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, start_new_session=True)
            try:
                out, _ = p.communicate(timeout=SUITE_TIMEOUT)
                ok = p.returncode == 0
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                out, _ = p.communicate()
                out, ok = f"{out}\ntimed out after {SUITE_TIMEOUT} s", False
        except OSError as e:
            out, ok = f"cannot run {s['cmd'][0]}: {e}", False
        if ok and s["count"]:
            found = re.findall(s["count"], out, re.M)
            n = int(found[-1]) if found else 0
            count = f"{n} tests, "
            if n == 0:
                ok, out = False, out + "\nreported zero tests\n"
    cmd = s["cmd"] or []
    via = " via " + " ".join(cmd[:cmd.index("python")]) if "uv" in cmd else ""
    print(f"{'PASS' if ok else 'FAIL'}  {s['name']}  ({count}{time.monotonic() - start:.1f}s){via}", flush=True)
    if not ok:
        failed.append(s["name"])
        print("\n".join("    " + l for l in out.rstrip().splitlines()[-TAIL:]), flush=True)

orphans = sorted(set(tests) - claimed)
for o in orphans:
    print(f"FAIL  {o}  (test file no suite runs)")
print(f"\n{len(suites) - len(failed)} of {len(suites)} suites passed"
      + (f"; {len(orphans)} unclaimed test file(s)" if orphans else ""))
sys.exit(1 if failed or orphans else 0)
