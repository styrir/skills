import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import closeout


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verk-closeout-test-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.env = dict(os.environ, CODEX_THREAD_ID="closeout-test", VERK_HOME=str(Path(self.tmp.name) / "store"))
        self.env.pop("VERK_REVIEWER", None)
        self.env.pop("VERK_ACTOR", None)
        self.env.pop("VERK_SESSION", None)
        for args in [("init", "-q"), ("config", "user.name", "Synthetic test"),
                     ("config", "user.email", "test@example.invalid")]:
            self.git(*args)
        (self.repo / "proof.txt").write_text("Synthetic proof only")
        self.git("add", "proof.txt")
        self.git("commit", "-qm", "fixture")
        self.head = closeout.git(self.repo, "rev-parse", "HEAD")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def test_real_review_only_route_waits_for_an_independent_verdict(self):
        binary = Path.home() / ".local/bin/verk"
        # Operator fixture setup is isolated; author commands retain their own identity.
        subprocess.run([str(binary), "bind", "synthetic", "--approve-policy", "--json"], cwd=self.repo, env=self.env,
                       check=True, capture_output=True)
        added = closeout.call(self.repo, self.env, "add", "Synthetic code", "--kind", "code", "--start", "--json")
        contract = added["id"]
        result = closeout.closeout(self.repo, self.env, contract, "proof.txt", 0, source_only=True)
        self.assertEqual(result["status"], "review_pending")
        view = closeout.call(self.repo, self.env, "view", contract, "--json")
        self.assertEqual(view["receipts"], [])
        self.assertEqual(view["reviews"][0]["lifecycle"], "open")
        self.assertEqual(view["attempts"][0]["actor"], "codex:closeout-test")
        old_review = view["reviews"][0]["decision"]
        (self.repo / "proof.txt").write_text("Corrected synthetic proof")
        self.git("commit", "-qam", "corrected proof")
        self.head = closeout.git(self.repo, "rev-parse", "HEAD")
        resumed = dict(self.env, CODEX_THREAD_ID="resumed-session")
        closeout.call(self.repo, resumed, "start", contract, "--json")
        result = closeout.closeout(self.repo, resumed, contract, "proof.txt", 0, source_only=True)
        self.assertEqual(result["status"], "review_pending")
        self.assertNotEqual(result["reviews"], [old_review])
        decision = closeout.call(self.repo, resumed, "view", result["reviews"][0], "--json")
        self.assertEqual(decision["target"]["revision"], self.head)
        self.env = resumed
        payload = {"hook_event_name": "Stop", "session_id": "resumed-session", "cwd": str(Path(self.tmp.name))}
        self.assertIn("review_pending", closeout.hook(payload, self.env)["systemMessage"])
        with patch.object(closeout, "call", side_effect=AssertionError("duplicate hook called Verk")):
            self.assertEqual(closeout.hook(payload, self.env), {})

    def test_dirty_work_is_never_submitted(self):
        (self.repo / "proof.txt").write_text("uncommitted")
        with patch.object(closeout, "call", side_effect=AssertionError("dirty submission")):
            with self.assertRaisesRegex(ValueError, "clean"):
                closeout.closeout(self.repo, self.env, "vk-1", "proof.txt", 0, source_only=True)

    def test_no_request_and_other_session_perform_no_verk_calls(self):
        payload = {"hook_event_name": "Stop", "session_id": "other", "cwd": str(self.repo)}
        with patch.object(closeout, "call", side_effect=AssertionError("unexpected Verk call")):
            self.assertEqual(closeout.hook(payload, dict(self.env, CODEX_THREAD_ID="other")), {})
            with self.assertRaisesRegex(ValueError, "differs"):
                closeout.hook(payload, self.env)

    def test_changed_ready_work_is_consumed_without_mutation(self):
        path = closeout.state_path(self.repo, self.env)
        closeout.save(path, {"repo": str(self.repo), "contract": "vk-1", "head": self.head,
                             "common_dir": closeout.git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")})
        (self.repo / "proof.txt").write_text("new work")
        payload = {"hook_event_name": "Stop", "session_id": "closeout-test", "cwd": str(self.repo)}
        with patch.object(closeout, "call", side_effect=AssertionError("stale request submitted")):
            result = closeout.hook(payload, self.env)
            self.assertIn("changed", result["systemMessage"])
        self.assertFalse(path.exists())
        self.assertEqual(json.loads(path.with_suffix(".result.json").read_text())["status"], "needs_action")

    def test_required_checks_use_only_the_approved_producer(self):
        view = {"contract": {"id": "vk-1"}, "state": "active", "attempts": [{"actor": "codex:closeout-test"}],
                "policy": {"checks": [{"name": "unit", "status": "none"}, {"name": "lint", "status": "passed"}]}}
        with patch.object(closeout, "call", return_value=view) as invoke, patch.object(closeout, "observe", return_value={"status": "receipt"}):
            closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        args = [c.args[2:] for c in invoke.call_args_list]
        check = next(a for a in args if a[0] == "check")
        self.assertEqual(check[:4], ("check", "unit", "--id", "vk-1"))
        self.assertEqual(check[4], "--until")
        self.assertGreater(int(check[5]), 0)
        self.assertEqual([a[1] for a in args if a[0] == "check"], ["unit", "lint"])
        self.assertFalse(any("checkpoint" in a or "answer" in a for a in args))

    def test_observing_another_receipt_preserves_pending_work(self):
        path = closeout.state_path(self.repo, self.env)
        pending = {"repo": str(self.repo), "contract": "vk-pending"}
        closeout.save(path, pending)
        view = {"contract": {"id": "vk-done"}, "state": "satisfied"}
        with patch.object(closeout, "call", return_value=view), patch.object(closeout, "observe", return_value={"status": "receipt"}):
            closeout.closeout(self.repo, self.env, "vk-done", "proof.txt", 0, source_only=True)
        self.assertEqual(json.loads(path.read_text()), pending)

    def test_receipt_must_cover_head_and_rejections_are_visible(self):
        for view, reason in [
            ({"state": "satisfied", "receipts": [{"id": "vk-r1", "revision": "old"}]}, "HEAD"),
            ({"state": "available", "reviews": [{"lifecycle": "answered", "verdict": "rejected"}]}, "rejected")]:
            with patch.object(closeout, "call", return_value=view):
                result = closeout.observe(self.repo, self.env, "vk-1", self.head, 0)
            self.assertEqual(result["status"], "needs_action")
            self.assertIn(reason, result["reason"])

    def test_new_review_is_not_mistaken_for_an_older_rejection(self):
        view = {"state": "available", "reviews": [
            {"lifecycle": "answered", "verdict": "rejected"},
            {"lifecycle": "open", "verdict": None, "decision": "vk-d2"}]}
        with patch.object(closeout, "call", return_value=view):
            result = closeout.observe(self.repo, self.env, "vk-1", self.head, 0)
        self.assertEqual(result["status"], "review_pending")

    def test_qualification_choice_is_required_before_verk_mutations(self):
        # Plain CLI startup must not create untracked bytecode in its own repository.
        for name in ["closeout.py", "verk.py"]:
            (self.repo / name).write_bytes(Path(__file__).with_name(name).read_bytes())
        self.git("add", "closeout.py", "verk.py")
        self.git("commit", "-qm", "helper fixture")
        run_env = dict(self.env)
        run_env.pop("PYTHONDONTWRITEBYTECODE", None)
        subprocess.run([sys.executable, str(self.repo / "closeout.py"), "--help"], env=run_env,
                       check=True, capture_output=True)
        self.assertEqual(closeout.git(self.repo, "status", "--porcelain"), "")
        with patch.object(closeout, "call", side_effect=AssertionError("premature submission")):
            with self.assertRaisesRegex(ValueError, "qualification"):
                closeout.closeout(self.repo, self.env, "vk-1", "proof.txt", 0)
            outside = Path(self.tmp.name) / "outside.md"
            outside.write_text("not a committed record")
            with self.assertRaises(ValueError):
                closeout.closeout(self.repo, self.env, "vk-1", None, 0, qualification=str(outside))


if __name__ == "__main__":
    unittest.main()
