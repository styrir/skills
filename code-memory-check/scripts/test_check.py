#!/usr/bin/env python3
"""Tests for check.py against a throwaway git repo and a stub Rúnir on localhost.

No network and no real memory. Run: python3 -m unittest discover -s code-memory-check/scripts
"""
import json, os, subprocess, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CHECK = Path(__file__).with_name("check.py")
FACTS = []  # what the stub returns for every search

class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"results": FACTS}).encode())

    def log_message(self, *_):
        pass

def fact(id, text, created):
    return {"id": id, "memory": text, "created_at": created}

OLD, NEW = "2026-02-01T00:00:00Z", "2026-04-01T00:00:00Z"  # either side of the 2026-03-01 change to charge()

class CheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = cls.tmp.name

        def git(*args, date="2026-01-01T00:00:00+00:00"):
            env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
                   "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
            subprocess.run(["git", "-C", cls.repo, *args], check=True, capture_output=True, env=env)

        pay = Path(cls.repo, "src", "pay.py")
        pay.parent.mkdir()
        git("init", "-q")
        pay.write_text("def charge(x):\n    return x\n\n\ndef refund(x):\n    return -x\n")
        git("add", ".")
        git("commit", "-qm", "first")
        pay.write_text("def charge(x):\n    return x * 2\n\n\ndef refund(x):\n    return -x\n")
        git("commit", "-qam", "double charge", date="2026-03-01T00:00:00+00:00")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def check(self, *args, facts=(), symbol="charge", env=None):
        FACTS[:] = facts
        e = {**os.environ, "RUNIR_API_KEY": "test", "RUNIR_USER_ID": "test",
             "RUNIR_BASE": f"http://127.0.0.1:{self.server.server_port}", **(env or {})}
        return subprocess.run([sys.executable, str(CHECK), "--repo", self.repo, "--symbol", symbol,
                               "--file", "src/pay.py", *args], capture_output=True, text=True, env=e)

    def test_dates_facts_against_the_function(self):
        out = self.check(facts=[
            fact("a1", "charge doubles nothing", OLD),
            fact("a2", "charge doubles the amount", NEW),
            fact("a3", "charge existed before the repo", "2025-12-01T00:00:00Z"),
            fact("b1", "pay.py is the billing module", OLD),
            fact("c1", "unrelated", OLD),
        ]).stdout
        self.assertIn("scope: function, found by name", out)
        self.assertIn("last changed 2026-03-01", out)
        self.assertIn("3 fact(s) name the function in their first 220 characters", out)
        self.assertIn("RE-CHECK  2026-02-01  1 commit(s) to the function since\n          a1", out)
        self.assertIn("OK        2026-04-01  written after the last change\n          a2", out)
        self.assertIn("2 commit(s) to the function since; note: older than this checkout's history", out)
        self.assertIn("1 more name only pay.py: 1 re-check, 0 ok  (--file-facts lists them)", out)
        self.assertNotIn("b1", out)
        self.assertNotIn("c1", out)

    def test_file_facts_lists_file_only_matches(self):
        out = self.check("--file-facts", facts=[fact("b1", "pay.py is the billing module", OLD)]).stdout
        self.assertIn("0 fact(s) name the function", out)
        self.assertIn("b1", out)

    def test_unchanged_function_in_a_changed_file_is_ok(self):
        out = self.check(symbol="refund", facts=[fact("r1", "refund negates", OLD)]).stdout
        self.assertIn("last changed 2026-01-01", out)
        self.assertIn("OK        2026-02-01", out)

    def test_line_range_and_whole_file_fallbacks(self):
        self.assertIn("scope: function, by line range", self.check("--lines", "1,2").stdout)
        self.assertIn("scope: whole file (line range not valid)", self.check("--lines", "90,99").stdout)
        out = self.check(symbol="missing", facts=[fact("m1", "missing was here", OLD)]).stdout
        self.assertIn("scope: whole file (function not found; pass --lines)", out)
        self.assertIn("1 commit(s) to the whole file since", out)

    def test_timestamp_without_a_zone_is_read_as_utc(self):
        run = self.check(facts=[fact("n1", "charge naive", "2026-02-01T00:00:00")])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("RE-CHECK  2026-02-01", run.stdout)

    def test_names_past_the_preview_are_tallied_by_position(self):
        # The name ends at character 220 in one fact and at 221 in the other; no other difference.
        at_edge = fact("e1", "x" * 214 + "charge", OLD)
        past_edge = fact("e2", "x" * 215 + "charge", NEW)
        out = self.check(facts=[at_edge, past_edge]).stdout
        self.assertIn("1 fact(s) name the function in their first 220 characters", out)
        self.assertIn("\n          e1\n", out)
        self.assertNotIn("e2", out)
        self.assertIn("1 more name it only later in the text: 0 re-check, 1 ok  (--passing lists them)", out)
        listed = self.check("--passing", facts=[at_edge, past_edge]).stdout
        self.assertIn("\n          e2\n", listed)
        self.assertNotIn("--passing lists them", listed)

    def test_no_partial_notice_when_the_search_is_full(self):
        out = self.check("--limit", "2", facts=[fact("a1", "charge one", OLD), fact("a2", "charge two", NEW)]).stdout
        self.assertIn("2 fact(s) name the function", out)
        self.assertNotIn("limit", out)
        self.assertNotIn("partial", out)

    def test_mention_line_and_full_text(self):
        long = fact("f1", "Lead claim about something else. " + "pad " * 80 + "see charge in the list. TAIL", OLD)
        self.assertNotIn("mention:", self.check(facts=[long]).stdout)
        out = self.check("--passing", facts=[long]).stdout
        self.assertIn("mention: …", out)
        self.assertIn("see charge in the list", out)
        self.assertNotIn("Lead claim about something else. " + "pad " * 60, out)
        run = self.check("--full", "f", "zz", facts=[long, fact("a1", "charge short", OLD)])
        self.assertEqual(run.returncode, 1)
        self.assertIn("TAIL", run.stdout)
        self.assertNotIn("mention:", run.stdout)
        self.assertNotIn("a1", run.stdout)
        self.assertIn("no listed fact has an id starting with zz", run.stdout)

    def test_search_failure_and_missing_credentials_exit_with_a_reason(self):
        down = self.check(env={"RUNIR_BASE": "http://127.0.0.1:1"})
        self.assertNotEqual(down.returncode, 0)
        self.assertIn("Rúnir search failed", down.stderr)
        unset = self.check(env={"RUNIR_API_KEY": ""})
        self.assertNotEqual(unset.returncode, 0)
        self.assertIn("must be set", unset.stderr)

if __name__ == "__main__":
    unittest.main()
