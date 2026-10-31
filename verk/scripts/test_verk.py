#!/usr/bin/env python3
"""Identity/approval-boundary checks plus a real CLI lifecycle in a temp store."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from verk import invocation

SCRIPT = Path(__file__).with_name("verk.py")
BIN = Path.home() / ".local" / "bin"


class SessionWrapperTests(unittest.TestCase):
    def test_missing_identity_fails_before_a_command_can_run(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            invocation(["brief"], {})

    def test_operator_actions_are_not_available(self):
        for args in [["answer", "vk-d1", "approved"], ["bind", "project"],
                     ["snapshot", "--final"], ["migrate", "--from", "beads"],
                     ["setup", "--apply", "plan"], ["setup", "--apply=plan"]]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                invocation(args, {"CODEX_THREAD_ID": "test-session"})

    def test_identity_is_session_scoped_and_arguments_remain_literal(self):
        title = "Keep spaces; literal $(text) and 'quotes'"
        command, _, env = invocation(["add", title], {
            "CODEX_THREAD_ID": "test-session", "VERK_ACTOR": "operator:test",
            "VERK_SESSION": "other-session", "VERK_REVIEWER": "1"
        })
        self.assertEqual(command, [str(BIN / "verk"), "add", title])
        self.assertEqual(env["VERK_ACTOR"], "codex:test-session")
        self.assertEqual(env["VERK_SESSION"], "test-session")
        self.assertNotIn("VERK_REVIEWER", env)

    def test_check_uses_the_installed_producer_with_the_same_identity(self):
        command, _, env = invocation(["check", "test", "--id", "vk-1"], {"CODEX_SESSION_ID": "fallback-session"})
        self.assertEqual(command, [str(BIN / "verk-check"), "test", "--id", "vk-1"])
        self.assertEqual(env["VERK_ACTOR"], "codex:fallback-session")

    def test_missing_binary_does_not_fall_back_to_path(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "executable"):
            invocation(["brief"], {"CODEX_THREAD_ID": "test-session"}, Path(directory))

    def test_real_cli_lifecycle_in_isolated_store(self):
        with tempfile.TemporaryDirectory(prefix="verk-skill-test-") as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            env = dict(os.environ, VERK_HOME=str(root / "store"), CODEX_THREAD_ID="skill-test-session",
                       VERK_ACTOR="operator:must-not-carry", VERK_SESSION="must-not-carry")
            env.pop("VERK_REVIEWER", None)
            def run(command):
                result = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result
            run(["git", "init", "-q"])
            run(["git", "-c", "user.name=Verk test", "-c", "user.email=verk-test@example.invalid",
                 "commit", "--allow-empty", "-qm", "fixture"])
            # Fixture-only binding in the temporary store. No live policy is approved.
            run([str(BIN / "verk"), "bind", "skill-test", "--json"])
            def wrapped(*args):
                return json.loads(run([sys.executable, str(SCRIPT), "--repo", str(repo), *args]).stdout)
            title = "A quoted task with spaces; literal punctuation"
            added = wrapped("add", title, "--kind", "ops", "--start", "--json")
            self.assertEqual(added["data"]["title"], title)
            attempt = added["data"]["start"]["attempt"]
            self.assertEqual(attempt["actor"], "codex:skill-test-session")
            self.assertEqual(attempt["session"], "skill-test-session")
            (repo / "verification.txt").write_text("Fixture evidence only.\n")
            run(["git", "add", "verification.txt"])
            run(["git", "-c", "user.name=Verk test", "-c", "user.email=verk-test@example.invalid", "commit", "-qm", "fixture proof"])
            note = "Review the exact files and remaining verification"
            checkpoint = wrapped("checkpoint", "--next", note, "--decided", "Keep the existing policy", "--proof", "verification.txt", "--json")
            self.assertEqual(checkpoint["data"]["checkpoint"]["next"], note)
            view = wrapped("view", added["data"]["id"], "--json")
            self.assertEqual(view["data"]["checkpoint"]["next"], note)
            brief = wrapped("brief", "--json")
            self.assertTrue(brief["ok"])
            self.assertEqual(brief["data"]["project"], "skill-test")


if __name__ == "__main__":
    unittest.main()
