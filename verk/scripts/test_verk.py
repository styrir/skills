#!/usr/bin/env python3
"""Identity/approval-boundary checks plus a real CLI lifecycle in a temp store."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import verk
from verk import author_copy, invocation

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
        command, _, env = invocation(["add", title], {"CODEX_THREAD_ID": "test-session"})
        self.assertEqual(command, [str(BIN / "verk"), "add", title])
        self.assertEqual(env["VERK_ACTOR"], "codex:test-session")
        self.assertEqual(env["VERK_SESSION"], "test-session")
        self.assertNotIn("VERK_REVIEWER", env)

    def test_equal_claims_pass_and_the_thread_id_wins_over_the_session_id(self):
        _, _, env = invocation(["brief"], {"CODEX_THREAD_ID": "thread", "CODEX_SESSION_ID": "other",
                                           "VERK_ACTOR": "codex:thread", "VERK_SESSION": "thread", "VERK_REVIEWER": "0"})
        self.assertEqual((env["VERK_ACTOR"], env["VERK_SESSION"]), ("codex:thread", "thread"))
        _, _, env = invocation(["--harness", "claude-code", "brief"], {
            "CLAUDE_CODE_SESSION_ID": "claude-test", "VERK_ACTOR": "claude-code:claude-test", "VERK_SESSION": "claude-test"})
        self.assertEqual(env["VERK_ACTOR"], "claude-code:claude-test")

    def refusals(self):
        codex, claude = {"CODEX_THREAD_ID": "codex-test"}, {"CLAUDE_CODE_SESSION_ID": "claude-test"}
        return [
            ([], dict(codex, CLAUDE_CODE_SESSION_ID="claude-test")), ([], dict(codex, CLAUDECODE="1")),
            ([], dict(codex, PI_CODING_AGENT="true")), ([], dict(codex, PI_SESSION_ID="pi-test")),
            ([], {"PI_CODING_AGENT": "true", "CODEX_THREAD_ID": "codex-test", "VERK_ACTOR": "pi:pi-test"}),
            (["--harness", "claude-code"], dict(claude, CODEX_THREAD_ID="codex-test")),
            (["--harness", "claude-code"], dict(claude, PI_CODING_AGENT="true")),
            ([], dict(codex, VERK_ACTOR="operator:test")), ([], dict(codex, VERK_ACTOR="codex:another")),
            ([], dict(codex, VERK_SESSION="another")),
            (["--harness", "claude-code"], dict(claude, VERK_ACTOR="codex:claude-test")),
            ([], dict(codex, VERK_REVIEWER="1")), (["--harness", "claude-code"], dict(claude, VERK_REVIEWER="1")),
        ]

    def test_each_refusal_happens_before_any_subprocess(self):
        for flags, environment in self.refusals():
            with self.subTest(flags=flags, environment=environment):
                with self.assertRaises(ValueError):
                    invocation([*flags, "brief"], environment)
                with patch.dict(os.environ, environment, clear=True), \
                        patch.object(verk.subprocess, "run", side_effect=AssertionError("ran Verk")), \
                        patch.object(verk.shutil, "which", side_effect=AssertionError("looked up Verk")), \
                        patch("sys.stderr"):
                    self.assertEqual(verk.main([*flags, "brief"]), 2)

    def test_a_refusal_names_the_fix_for_the_agent(self):
        with self.assertRaisesRegex(ValueError, "Run `verk` directly"):
            invocation(["brief"], {"CODEX_THREAD_ID": "codex-test", "PI_CODING_AGENT": "true"})

    def test_a_scrubbed_copy_carries_no_other_principal(self):
        dirty = {"CODEX_THREAD_ID": "old", "PI_CODING_AGENT": "true", "CLAUDE_CODE_SESSION_ID": "c", "VERK_ACTOR": "pi:x",
                 "VERK_SESSION": "x", "VERK_REVIEWER": "1", "HOME": "/h"}
        clean = author_copy("codex", dirty, "payload-session")
        self.assertEqual(clean, {"CODEX_THREAD_ID": "payload-session", "HOME": "/h"})
        invocation(["brief"], clean)

    def test_claude_identity_is_explicit_and_author_only(self):
        environment = {"CLAUDE_CODE_SESSION_ID": "claude-test"}
        _, _, env = invocation(["--harness", "claude-code", "brief"], environment)
        self.assertEqual(env["VERK_ACTOR"], "claude-code:claude-test")
        self.assertEqual(env["VERK_SESSION"], "claude-test")
        with self.assertRaisesRegex(ValueError, "another harness|identity"):
            invocation(["--harness", "claude-code", "brief"], {"CODEX_THREAD_ID": "wrong-harness"})
        with self.assertRaises(ValueError):
            invocation(["--harness", "claude-code", "answer", "vk-d1", "approved"], environment)

    def test_check_uses_the_installed_producer_with_the_same_identity(self):
        command, _, env = invocation(["check", "test", "--id", "vk-1"], {"CODEX_SESSION_ID": "fallback-session"})
        self.assertEqual(command, [str(BIN / "verk-check"), "test", "--id", "vk-1"])
        self.assertEqual(env["VERK_ACTOR"], "codex:fallback-session")

    def test_missing_binary_does_not_fall_back_to_path(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "executable"):
            invocation(["brief"], {"CODEX_THREAD_ID": "test-session"}, Path(directory))

    def test_the_binary_comes_from_the_folder_given_then_the_install_setting_then_path(self):
        with tempfile.TemporaryDirectory() as given, tempfile.TemporaryDirectory() as setting, tempfile.TemporaryDirectory() as on_path:
            for folder in (given, setting, on_path):
                binary = Path(folder) / "verk"
                binary.write_text("#!/bin/sh\n")
                binary.chmod(0o755)
            environment = {"CODEX_THREAD_ID": "test-session", "VERK_BIN_DIR": setting, "PATH": on_path}
            run = lambda env, folder=None: invocation(["brief"], env, folder)[0][0]
            self.assertEqual(run(environment, Path(given)), str(Path(given) / "verk"))
            self.assertEqual(run(environment), str(Path(setting) / "verk"))
            self.assertEqual(run({k: v for k, v in environment.items() if k != "VERK_BIN_DIR"}), str(Path(on_path) / "verk"))
            # A setting that names an empty folder is refused rather than quietly using another install.
            with tempfile.TemporaryDirectory() as empty, self.assertRaisesRegex(ValueError, "executable"):
                invocation(["brief"], dict(environment, VERK_BIN_DIR=empty))

    def test_real_cli_lifecycle_in_isolated_store(self):
        with tempfile.TemporaryDirectory(prefix="verk-skill-test-") as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            env = dict(author_copy("codex", os.environ, "skill-test-session"), VERK_HOME=str(root / "store"))
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
