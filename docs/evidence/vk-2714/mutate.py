"""Apply one break of each kind in the current (throwaway) worktree."""
import json, os, subprocess
from pathlib import Path

def edit(p, old, new):
    s = Path(p).read_text(); assert old in s, p; Path(p).write_text(s.replace(old, new, 1))

# one break per style
edit("code-memory-check/scripts/test_check.py", 'self.assertIn("2 fact(s) name the function", out)', 'self.assertIn("BROKEN", out)')
edit("jev-guard/tests/test_policy.py", "\nimport ", "\nimport sys; sys.exit(1)\nimport ")
Path("styrir-search/scripts/styrir-route.test.ts").write_text(Path("styrir-search/scripts/styrir-route.test.ts").read_text()
    + '\nimport brokenTest from "node:test"; import brokenAssert from "node:assert"; brokenTest("broken", () => brokenAssert.equal(1, 2));\n')
edit("rea-report/scripts/test_package_report.py", "import unittest", "import unittest\nassert False, 'broken'")
edit("styrir-init/scripts/test-styrir-init.sh", "set -euo pipefail", "set -euo pipefail\nexit 1")
# zero tests, orphan by new name pattern
Path("zero").mkdir(); Path("zero/test_zero.py").write_text("import unittest\nclass Empty(unittest.TestCase):\n    pass\n")
Path("lonely").mkdir(); Path("lonely/foo_test.ts").write_text('import test from "node:test";\n')
# Codex findings
Path("styrir-search/scripts/.regression.test.ts").write_text('import test from "node:test";\n')        # 1: dotfile sh skips
Path("setja/test/unit").mkdir(); Path("setja/test/unit/new.test.ts").write_text('import test from "node:test";\n')  # 1: sh ** = *
Path("aliased").mkdir(); Path("aliased/test_aliased.py").write_text(
    "from unittest import TestCase as Base\nclass T(Base):\n    def test_fails(self):\n        self.assertEqual(1, 2)\n")  # 2
Path("syntax").mkdir(); Path("syntax/test_syntax.py").write_text("def broken(:\n")                  # 3
Path("litpkg").mkdir(); Path("litpkg/example.test.js").write_text(
    'import test from "node:test"; test("ok", () => {});\n')
Path("litpkg/package.json").write_text(json.dumps({"type": "module", "scripts": {"test": "node --test example.test.js"}}))  # 5
subprocess.run(["git", "add", "-A"], check=True)
# follow-up review cases
Path("echopkg").mkdir()
Path("echopkg/good.test.js").write_text('import test from "node:test"; test("ok", () => {});\n')
Path("echopkg/broken.test.js").write_text('import test from "node:test"; import a from "node:assert"; test("bad", () => a.equal(1, 2));\n')
Path("echopkg/package.json").write_text(json.dumps({"type": "module", "scripts": {"test": "node --test good.test.js && echo broken.test.js"}}))
Path("mockonly").mkdir(); Path("mockonly/test_mockonly.py").write_text(
    "from unittest.mock import patch\nimport os\nif __name__ == '__main__':\n    with patch('os.getcwd', return_value='x'):\n        assert os.getcwd() == 'x'\n    print('mock script ok')\n")
Path("hang").mkdir(); Path("hang/test-hang.sh").write_text("sleep 4242 &\nwait\n")
subprocess.run(["git", "add", "-A"], check=True)
os.remove("session-eval/scripts/test_history.py")                                                  # 4: unstaged deletion
