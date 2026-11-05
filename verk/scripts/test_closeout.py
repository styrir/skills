import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
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
        added = closeout.call(self.repo, self.env, "add", "Synthetic code", "--kind", "code", "--accept", "Synthetic proof exists", "--start", "--json")
        contract = added["id"]
        result = closeout.closeout(self.repo, self.env, contract, "proof.txt", 0, source_only=True)
        self.assertEqual(result["status"], "review_pending")
        view = closeout.call(self.repo, self.env, "view", contract, "--json")
        self.assertEqual(view["receipts"], [])
        self.assertEqual(view["reviews"][0]["lifecycle"], "open")
        self.assertEqual(view["attempts"][0]["actor"], "codex:closeout-test")
        self.assertIn("Source-only acceptance explicitly declared", view["checkpoint"]["next"])
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

    def test_lapsed_attempt_cannot_checkpoint_or_prove_later_work(self):
        binary = Path.home() / ".local/bin/verk"
        env = dict(self.env, VERK_LEASE_TTL_MS="2500")
        subprocess.run([str(binary), "bind", "synthetic", "--approve-policy", "--json"], cwd=self.repo, env=env,
                       check=True, capture_output=True)
        rival_env = dict(env, CODEX_THREAD_ID="rival-session")
        real_call = closeout.call
        for rival in ("same session, other contract", "other session, same contract"):
            with self.subTest(rival=rival):
                a = real_call(self.repo, env, "add", "Synthetic A", "--kind", "code", "--accept", "A", "--start", "--json")["id"]
                b = real_call(self.repo, env, "add", "Synthetic B", "--kind", "code", "--accept", "B", "--json")["id"]
                def delayed(repo, scoped, *args, **kwargs):
                    if args[0] == "check":
                        time.sleep(3)  # A's lease lapses during a long check
                        if rival.startswith("same"):
                            real_call(repo, scoped, "start", b, "--json")
                        else:
                            real_call(repo, rival_env, "start", a, "--json")
                        return None
                    data = real_call(repo, scoped, *args, **kwargs)
                    if args[0] == "view" and data.get("contract", {}).get("id") == a:
                        data["policy"]["checks"] = [{"name": "unit", "status": "none"}]
                    return data
                with patch.object(closeout, "call", side_effect=delayed):
                    with self.assertRaises(ValueError):
                        closeout.closeout(self.repo, env, a, "proof.txt", 0, source_only=True)
                later = real_call(self.repo, env, "view", b, "--json")
                self.assertIsNone(later["checkpoint"])
                self.assertEqual(later["receipts"], [])
                self.assertFalse(later["proof"] and later["proof"].get("evidence"))
                notes = [c["next"] for c in [real_call(self.repo, env, "view", a, "--json")["checkpoint"]] if c]
                self.assertFalse(any("Approved checks passed" in n for n in notes))
                if rival.startswith("same"):
                    real_call(self.repo, env, "checkpoint", b, "--next", "fixture reset", "--json")

    def test_claude_pending_request_is_separate_and_stop_uses_claude_actor(self):
        env = dict(self.env, VERK_CLOSEOUT_HARNESS="claude-code", CLAUDE_CODE_SESSION_ID="closeout-test")
        path = closeout.state_path(self.repo, env)
        self.assertNotEqual(path, closeout.state_path(self.repo, self.env))
        closeout.save(path, {"repo": str(self.repo), "contract": "vk-1", "head": self.head,
                             "common_dir": closeout.git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")})
        payload = {"hook_event_name": "Stop", "session_id": "closeout-test", "cwd": str(self.repo)}
        def invoke(repo, scoped, *args, **kwargs):
            command, _, author = closeout.invocation(["--harness", scoped["VERK_CLOSEOUT_HARNESS"], "brief"], scoped)
            self.assertEqual(author["VERK_ACTOR"], "claude-code:closeout-test")
            return {}
        with patch.object(closeout, "call", side_effect=invoke), patch.object(closeout, "observe", return_value={"status": "review_pending"}):
            self.assertIn("review_pending", closeout.hook(payload, env)["systemMessage"])
        self.assertFalse(path.exists())
        with self.assertRaisesRegex(ValueError, "differs"):
            closeout.hook(dict(payload, session_id="different"), env)

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
        view = {"contract": {"id": "vk-1"}, "state": "active", "attempt": {"id": "vk-1.1"},
                "attempts": [{"id": "vk-1.1", "state": "active", "actor": "codex:closeout-test"}],
                "policy": {"checks": [{"name": "unit", "status": "none"}, {"name": "lint", "status": "passed"}]}}
        with patch.object(closeout, "call", return_value=view) as invoke, patch.object(closeout, "observe", return_value={"status": "receipt"}):
            closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        args = [c.args[2:] for c in invoke.call_args_list]
        check = next(a for a in args if a[0] == "check")
        self.assertEqual(check[:4], ("check", "unit", "--id", "vk-1"))
        self.assertEqual(check[4], "--until")
        self.assertGreater(int(check[5]), 0)
        self.assertEqual([a[1] for a in args if a[0] == "check"], ["unit", "lint"])
        checkpoint = next(a for a in args if a[0] == "checkpoint")
        self.assertTrue(all(a[1] == "vk-1.1" for a in args if a[0] == "checkpoint"))
        self.assertIn("Source-only acceptance explicitly declared", checkpoint[3])
        self.assertIn("--keep", checkpoint)
        self.assertLess(args.index(checkpoint), args.index(check))
        result = [a for a in args if a[0] == "checkpoint"][-1]
        message = result[result.index("--next") + 1]
        self.assertIn(f"Approved checks passed at {self.head}: unit, lint", message)
        self.assertIn("Source-only acceptance explicitly declared", message)
        self.assertFalse(any(a in result for a in ["--open", "--open=", "--decided"]))
        self.assertLess(max(i for i, a in enumerate(args) if a[0] == "check"), args.index(result))
        self.assertLess(args.index(result), next(i for i, a in enumerate(args) if a[0] == "reconcile"))
        self.assertFalse(any("answer" in a for a in args))
        def fail_check(repo, env, *args, **kwargs):
            if args[0] == "check":
                raise ValueError("producer failed")
            return view
        with patch.object(closeout, "call", side_effect=fail_check) as failed:
            with self.assertRaisesRegex(ValueError, "producer failed"):
                closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        self.assertFalse(any("Approved checks passed" in str(c.args) for c in failed.call_args_list))

    def evidence(self, **changes):
        return dict({"id": "vk-e1", "revision": self.head, "status": "accepted", "reason": None, "bindings_current": True}, **changes)

    def submit_with(self, evidence):
        view = {"contract": {"id": "vk-1"}, "state": "active", "attempt": {"id": "vk-1.1"},
                "attempts": [{"id": "vk-1.1", "state": "active"}],
                "policy": {"checks": [{"name": "unit", "status": "passed", "evidence": evidence}]}}
        with patch.object(closeout, "call", return_value=view) as invoke, patch.object(closeout, "observe", return_value={"status": "review_pending", "reviews": []}):
            closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        return [c.args[2:] for c in invoke.call_args_list if c.args[2] == "check"]

    def test_admitted_evidence_for_this_revision_starts_no_check(self):
        for status in ("accepted", "used"):
            self.assertEqual(self.submit_with([self.evidence(status=status)]), [])
        # An older failure or stale run beside the admitted one doesn't force another.
        self.assertEqual(self.submit_with([self.evidence(status="rejected"), self.evidence()]), [])

    def test_anything_short_of_current_admission_is_not_reused(self):
        cases = {"old revision": self.evidence(revision="0" * 40), "changed bindings": self.evidence(bindings_current=False),
                 "rejected, despite exit 0": self.evidence(status="rejected", reason="dirty"), "pending": self.evidence(status="pending"),
                 "withdrawn": self.evidence(status="withdrawn"), "no bindings verdict": {"revision": self.head, "status": "accepted"}}
        for name, row in cases.items():
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, "did not admit"):
                    self.submit_with([row])  # the check runs, and the unchanged view still shows no admission
        self.assertFalse(closeout.admitted_at({"status": "passed"}, self.head))

    def test_a_check_that_exits_zero_without_admission_stops_closeout(self):
        with self.assertRaisesRegex(ValueError, "exited 0 but Verk did not admit it .*dirty"):
            self.submit_with([self.evidence(status="rejected", reason="dirty")])

    def test_a_review_is_reused_only_for_exactly_this_target(self):
        view = {"contract": {"id": "vk-1", "acceptance_version": 2, "subjects_version": 1}, "policy": {"version": 3}}
        good = {"lifecycle": "open", "contracts": ["vk-1"], "target": {"revision": self.head},
                "bindings": {"acceptanceVersion": 2, "subjectsVersion": 1, "policyVersion": 3}}
        self.assertTrue(closeout.review_covers(view, good, self.head))
        self.assertTrue(closeout.review_covers(view, dict(good, target={"artifact": {"revision": self.head}}), self.head))
        for name, changed in {"revision": {"target": {"revision": "0" * 40}},
                              "artifact revision": {"target": {"artifact": {"revision": "0" * 40}}},
                              "acceptance": {"bindings": dict(good["bindings"], acceptanceVersion=1)},
                              "subjects": {"bindings": dict(good["bindings"], subjectsVersion=0)},
                              "policy": {"bindings": dict(good["bindings"], policyVersion=2)},
                              "other contract": {"contracts": ["vk-2"]}, "answered": {"lifecycle": "answered"}}.items():
            with self.subTest(name):
                self.assertFalse(closeout.review_covers(view, dict(good, **changed), self.head))

    def test_qualification_and_additional_proof_reach_the_checkpoint_before_checks(self):
        view = {"contract": {"id": "vk-1"}, "state": "active", "attempt": {"id": "vk-1.1"},
                "attempts": [{"id": "vk-1.1", "state": "active"}],
                "policy": {"checks": [{"name": "unit", "status": "none"}]}}
        with patch.object(closeout, "call", return_value=view) as invoke, patch.object(closeout, "observe", return_value={"status": "receipt"}):
            closeout.closeout(self.repo, self.env, "vk-1", "extra.txt", 0, qualification="proof.txt")
        args = [c.args[2:] for c in invoke.call_args_list]
        checkpoint = next(a for a in args if a[0] == "checkpoint")
        self.assertIn("Qualification record: proof.txt", checkpoint[3])
        self.assertEqual([checkpoint[i + 1] for i, a in enumerate(checkpoint) if a == "--proof"], ["extra.txt", "proof.txt"])
        self.assertLess(args.index(checkpoint), next(i for i, a in enumerate(args) if a[0] == "check"))

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
