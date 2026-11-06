import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
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
        record = json.loads(closeout.state_path(resumed).read_text())
        self.assertEqual({k: record[k] for k in ("harness", "session", "store", "contract", "project", "head")},
                         {"harness": "codex", "session": "resumed-session", "store": self.env["VERK_HOME"], "contract": contract, "project": "synthetic", "head": self.head})
        self.assertRegex(record["request_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(sorted(record["bindings"]), ["acceptanceVersion", "policyVersion", "subjectsVersion"])
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
                ran = []
                def delayed(repo, scoped, *args, **kwargs):
                    if args[0] == "check":
                        ran.append(args[1])
                        time.sleep(3)  # A's lease lapses during a long check
                        if rival.startswith("same"):
                            real_call(repo, scoped, "start", b, "--json")
                        else:
                            real_call(repo, rival_env, "start", a, "--json")
                        return None
                    data = real_call(repo, scoped, *args, **kwargs)
                    if args[0] == "view" and data.get("contract", {}).get("id") == a:
                        data["policy"]["checks"] = [{"name": "unit", "status": "none", "evidence": [self.evidence()] if ran else []}]
                    return data
                with patch.object(closeout, "call", side_effect=delayed):
                    with self.assertRaisesRegex(ValueError, "working on" if rival.startswith("same") else "reacquired"):
                        closeout.closeout(self.repo, env, a, "proof.txt", 0, source_only=True)
                self.assertEqual(ran, ["unit"])
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
        path = closeout.state_path(env)
        self.assertNotEqual(path, closeout.state_path(self.env))
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

    def pending(self, **fields):
        path = closeout.state_path(self.env)
        request = dict({"request_id": "one", "repo": str(self.repo), "contract": "vk-1", "head": self.head,
                        "common_dir": closeout.git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")}, **fields)
        closeout.save(path, request)
        return path, request, {"hook_event_name": "Stop", "session_id": "closeout-test", "cwd": str(self.repo)}

    def test_lock_excludes_a_second_writer_until_released(self):
        path, _, _ = self.pending()
        order = []
        def writer():
            with closeout.request_lock(path):
                order.append("second")
        with closeout.request_lock(path):
            thread = threading.Thread(target=writer)
            thread.start()
            thread.join(0.3)
            self.assertTrue(thread.is_alive())
            order.append("first")
        thread.join(5)
        self.assertEqual(order, ["first", "second"])

    def test_stop_holds_no_lock_during_child_calls(self):
        path, _, payload = self.pending()
        def free(*args, **kwargs):
            descriptor = os.open(path.with_suffix(".lock"), os.O_RDWR)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises if the hook still held it
            finally:
                os.close(descriptor)
            return {"state": "available", "reviews": [{"decision": "vk-d1", "lifecycle": "open", "verdict": None}]}
        with patch.object(closeout, "call", side_effect=free) as invoke:
            self.assertIn("review_pending", closeout.hook(payload, self.env)["systemMessage"])
        self.assertTrue(invoke.called)

    def test_foreground_replacement_during_stop_keeps_the_new_request(self):
        path, _, payload = self.pending()
        newer = {"request_id": "two", "repo": str(self.repo), "contract": "vk-2", "head": self.head, "common_dir": "x"}
        def replaced(*args, **kwargs):
            with closeout.request_lock(path):
                closeout.save(path, newer)
            return {"state": "satisfied", "receipts": [{"id": "vk-r1", "revision": self.head}]}
        with patch.object(closeout, "call", side_effect=replaced):
            self.assertIn("newer request", closeout.hook(payload, self.env)["systemMessage"])
        self.assertEqual(json.loads(path.read_text()), newer)
        self.assertFalse(path.with_suffix(".result.json").exists())

    def test_duplicate_stop_during_a_stop_replays_nothing(self):
        _, _, payload = self.pending()
        inner = []
        def overlapping(*args, **kwargs):
            if not inner:
                inner.append(closeout.hook(payload, self.env))
            return {"state": "available", "reviews": [{"decision": "vk-d1", "lifecycle": "open", "verdict": None}]}
        with patch.object(closeout, "call", side_effect=overlapping) as invoke:
            self.assertIn("review_pending", closeout.hook(payload, self.env)["systemMessage"])
        self.assertEqual(inner, [{}])
        self.assertEqual(invoke.call_count, 2)  # reconcile and view, once each

    def test_failed_stop_keeps_the_request_and_retries_on_the_next_stop(self):
        path, request, payload = self.pending()
        with patch.object(closeout, "call", side_effect=subprocess.TimeoutExpired("verk", 5)):
            result = json.loads(closeout.hook(payload, self.env)["systemMessage"].removeprefix("Verk closeout: "))
        self.assertEqual((result["status"], result["retained"]), ("needs_action", True))
        self.assertEqual(json.loads(path.read_text()), request)
        receipt = {"state": "satisfied", "receipts": [{"id": "vk-r1", "revision": self.head}]}
        with patch.object(closeout, "call", return_value=receipt):
            self.assertIn("receipt", closeout.hook(payload, self.env)["systemMessage"])
        self.assertFalse(path.exists())

    def test_hard_exit_keeps_the_request_and_its_claim_expires(self):
        path, request, payload = self.pending()
        script = """
import json,os,sys
from unittest.mock import patch
import closeout
with patch.object(closeout,'call',side_effect=lambda *a,**k:os._exit(17)):
    closeout.hook(json.loads(sys.argv[1]),os.environ)
"""
        env = dict(self.env, VERK_CLOSEOUT_HARNESS="codex")
        done = subprocess.run([sys.executable, "-c", script, json.dumps(payload)], cwd=Path(__file__).parent, env=env)
        self.assertEqual(done.returncode, 17)
        kept = json.loads(path.read_text())
        self.assertEqual(kept["request_id"], request["request_id"])
        with patch.object(closeout, "call", side_effect=AssertionError("replayed inside the claim")):
            self.assertEqual(closeout.hook(payload, self.env), {})
        closeout.save(path, dict(kept, stop_claim=kept["stop_claim"] - closeout.CLAIM_SECONDS - 1))
        receipt = {"state": "satisfied", "receipts": [{"id": "vk-r1", "revision": self.head}]}
        with patch.object(closeout, "call", return_value=receipt):
            self.assertIn("receipt", closeout.hook(payload, self.env)["systemMessage"])

    def test_another_repository_at_the_recorded_path_keeps_the_request(self):
        path, request, payload = self.pending(common_dir="/somewhere/else/.git")
        with patch.object(closeout, "call", side_effect=AssertionError("wrong repository, no Verk write")):
            self.assertIn("no longer holds this repository", closeout.hook(payload, self.env)["systemMessage"])
        self.assertEqual(json.loads(path.read_text()), request)

    def test_missing_checkout_keeps_the_request_without_verk_calls(self):
        path, request, payload = self.pending(repo=str(Path(self.tmp.name) / "deleted"))
        with patch.object(closeout, "call", side_effect=AssertionError("no checkout, no Verk write")):
            self.assertIn("retained", closeout.hook(dict(payload, cwd=str(Path(self.tmp.name) / "gone")), self.env)["systemMessage"])
        self.assertEqual(json.loads(path.read_text()), request)

    def overlapped(self, during, status):
        """A closeout whose observation sees `during` happen first, as an overlapping closeout finishing mid-run."""
        view = {"contract": {"id": "vk-1"}, "state": "satisfied", "receipts": []}
        result = {"status": status, "contract": "vk-1", "reviews": ["vk-d1"]}
        def observed(*args, **kwargs):
            during()
            return result
        with patch.object(closeout, "call", return_value=view), patch.object(closeout, "observe", side_effect=observed):
            return closeout.closeout(self.repo, self.env, "vk-1", "proof.txt", 0, source_only=True)

    def test_an_older_closeout_neither_deletes_nor_overwrites_a_newer_request(self):
        path, _, _ = self.pending()
        for status in ("needs_action", "review_pending"):
            with self.subTest(status):
                newer = {}
                def later_closeout():
                    newer.update(json.loads(path.read_text()), request_id="newer", began=time.time_ns() + 10**12, contract="vk-1", repo=str(self.repo))
                    closeout.save(path, newer)
                result = self.overlapped(later_closeout, status)
                self.assertTrue(result["superseded"])
                self.assertEqual(json.loads(path.read_text()), newer)

    def test_a_later_closeout_replaces_an_earlier_one_and_cleans_up_after_itself(self):
        path, _, _ = self.pending(began=1, repo=str(self.repo.resolve()))
        self.assertEqual(self.overlapped(lambda: None, "needs_action")["status"], "needs_action")
        self.assertFalse(path.exists())
        path, _, _ = self.pending(began=1)
        result = self.overlapped(lambda: None, "review_pending")
        self.assertEqual(json.loads(path.read_text())["request_id"], result["request_id"])

    def test_foreground_result_is_written_inside_the_lock(self):
        path, _, _ = self.pending(began=1)
        real_save = closeout.save
        def checked(target, data):
            descriptor = os.open(path.with_suffix(".lock"), os.O_RDWR)
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(descriptor)
            real_save(target, data)
        with patch.object(closeout, "save", side_effect=checked) as saved:
            self.overlapped(lambda: None, "needs_action")
        self.assertTrue(saved.called)

    def test_a_verk_fault_during_stop_is_retained_and_a_settled_request_stays_quiet(self):
        path, request, payload = self.pending()
        with patch.object(closeout, "call", return_value={}):  # no state: Verk's answer, not the request, is malformed
            self.assertIn("retained", closeout.hook(payload, self.env)["systemMessage"])
        self.assertEqual(json.loads(path.read_text()), request)
        def settled_elsewhere(*args, **kwargs):
            path.unlink(missing_ok=True)
            return {"state": "available", "reviews": [{"decision": "vk-d1", "lifecycle": "open", "verdict": None}]}
        with patch.object(closeout, "call", side_effect=settled_elsewhere):
            self.assertEqual(closeout.hook(payload, self.env), {})

    def test_an_older_closeout_cannot_revive_a_request_a_newer_one_settled(self):
        path, _, _ = self.pending()
        def newer_settled():
            closeout.mark_settled(path, {"began": time.time_ns() + 10**12})
            path.unlink(missing_ok=True)
        result = self.overlapped(newer_settled, "review_pending")
        self.assertTrue(result["superseded"])
        self.assertFalse(path.exists())

    def test_a_stop_that_consumes_a_request_also_blocks_older_closeouts(self):
        path, _, payload = self.pending(began=time.time_ns() + 10**12)
        receipt = {"state": "satisfied", "receipts": [{"id": "vk-r1", "revision": self.head}]}
        with patch.object(closeout, "call", return_value=receipt):
            self.assertIn("receipt", closeout.hook(payload, self.env)["systemMessage"])
        self.assertTrue(self.overlapped(lambda: None, "review_pending")["superseded"])
        self.assertFalse(path.exists())

    def test_moved_checkout_request_clears_when_closeout_observes_its_receipt(self):
        path, _, _ = self.pending(began=1, repo="/moved/from/here")
        self.overlapped(lambda: None, "receipt")
        self.assertFalse(path.exists())

    def test_interruption_during_stop_keeps_the_request_and_claims_nothing_forever(self):
        path, request, payload = self.pending()
        with patch.object(closeout, "call", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                closeout.hook(payload, self.env)
        kept = json.loads(path.read_text())
        self.assertEqual(kept["request_id"], request["request_id"])
        self.assertFalse(path.with_suffix(".result.json").exists())
        closeout.save(path, dict(kept, stop_claim=kept["stop_claim"] - closeout.CLAIM_SECONDS - 1))
        with patch.object(closeout, "call", return_value={"state": "satisfied", "receipts": [{"id": "vk-r1", "revision": self.head}]}):
            self.assertIn("receipt", closeout.hook(payload, self.env)["systemMessage"])

    def test_interruption_during_foreground_closeout_writes_no_request(self):
        path, request, _ = self.pending()
        with patch.object(closeout, "call", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                closeout.closeout(self.repo, self.env, "vk-1", "proof.txt", 0, source_only=True)
        self.assertEqual(json.loads(path.read_text()), request)

    def test_nonnumeric_times_do_not_crash_stop(self):
        _, _, payload = self.pending(stop_claim="soon", began="later")
        with patch.object(closeout, "call", return_value={"state": "satisfied", "receipts": [{"id": "vk-r1", "revision": self.head}]}):
            self.assertIn("receipt", closeout.hook(payload, self.env)["systemMessage"])

    def test_pending_request_records_the_reviewed_artifact_and_checkout_identity(self):
        artifact = {"path": "a.bin", "revision": self.head}
        view = {"contract": {"id": "vk-1", "project": "p", "acceptance_version": 1, "subjects_version": 0}, "state": "satisfied", "receipts": [],
                "policy": {"kind_version": 2, "checks": []}}
        def invoke(repo, env, *args, **kwargs):
            return {"target": {"artifact": artifact}} if args[1] == "vk-d1" else view
        with patch.object(closeout, "call", side_effect=invoke), patch.object(closeout, "observe", return_value={"status": "review_pending", "reviews": ["vk-d1"]}):
            closeout.closeout(self.repo, self.env, "vk-1", "proof.txt", 0, source_only=True)
        record = json.loads(closeout.state_path(self.env).read_text())
        self.assertEqual(record["artifact"], artifact)
        self.assertEqual(record["repo"], str(self.repo.resolve()))
        self.assertTrue(record["common_dir"].endswith(".git"))
        self.assertEqual(record["bindings"], {"acceptanceVersion": 1, "subjectsVersion": 0, "policyVersion": 2})

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
        path = closeout.state_path(self.env)
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
        old_pass = self.evidence(revision="0" * 40)  # lint "passed" at another revision: must run again
        invoke = self.producing([{"name": "unit", "status": "none"}, {"name": "lint", "status": "passed", "evidence": [old_pass]}])
        with patch.object(closeout, "call", side_effect=invoke) as invoke, patch.object(closeout, "observe", return_value={"status": "receipt"}):
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
            return self.producing([{"name": "unit", "status": "none"}])(repo, env, *args, **kwargs)
        with patch.object(closeout, "call", side_effect=fail_check) as failed:
            with self.assertRaisesRegex(ValueError, "producer failed"):
                closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        self.assertFalse(any("Approved checks passed" in str(c.args) for c in failed.call_args_list))

    def test_qualification_and_additional_proof_reach_the_checkpoint_before_checks(self):
        invoke = self.producing([{"name": "unit", "status": "none"}])
        with patch.object(closeout, "call", side_effect=invoke) as invoke, patch.object(closeout, "observe", return_value={"status": "receipt"}):
            closeout.closeout(self.repo, self.env, "vk-1", "extra.txt", 0, qualification="proof.txt")
        args = [c.args[2:] for c in invoke.call_args_list]
        checkpoint = next(a for a in args if a[0] == "checkpoint")
        self.assertIn("Qualification record: proof.txt", checkpoint[3])
        self.assertEqual([checkpoint[i + 1] for i, a in enumerate(checkpoint) if a == "--proof"], ["extra.txt", "proof.txt"])
        self.assertLess(args.index(checkpoint), next(i for i, a in enumerate(args) if a[0] == "check"))

    def producing(self, checks):
        """Verk as seen by closeout: each check it runs then shows as admitted at HEAD in later views."""
        ran = set()
        def invoke(repo, env, *args, **kwargs):
            if args[0] == "check":
                ran.add(args[1])
            shown = [dict(c, evidence=c.get("evidence", []) + ([self.evidence()] if c["name"] in ran else [])) for c in checks]
            return {"contract": {"id": "vk-1"}, "state": "active", "attempt": {"id": "vk-1.1"},
                    "attempts": [{"id": "vk-1.1", "state": "active"}], "policy": {"checks": shown}}
        return invoke

    def views(self, *evidence_by_view):
        """Closeout's successive views of one check, the last repeating."""
        seen = iter(evidence_by_view)
        latest = []
        calls = []
        def invoke(repo, env, *args, **kwargs):
            nonlocal latest
            calls.append(args)
            if args[0] == "view":
                latest = next(seen, latest)
            return {"contract": {"id": "vk-1"}, "state": "active", "attempt": {"id": "vk-1.1"}, "attempts": [{"id": "vk-1.1", "state": "active"}],
                    "policy": {"checks": [{"name": "unit", "status": "passed", "evidence": latest}]}}
        return invoke, calls

    def test_evidence_invalidated_during_an_earlier_check_is_not_skipped(self):
        # First view admitted; the next, read after an earlier run could have moved terms, is not: the producer must run.
        good = self.evidence()
        invoke, calls = self.views([good], [self.evidence(bindings_current=False)], [self.evidence(bindings_current=False), good])
        with patch.object(closeout, "call", side_effect=invoke), patch.object(closeout, "observe", return_value={"status": "review_pending", "reviews": []}):
            closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        self.assertEqual([a[1] for a in calls if a[0] == "check"], ["unit"])

    def test_no_passed_note_when_admission_lapses_after_the_last_check(self):
        good = self.evidence()
        invoke, calls = self.views([good], [good], [self.evidence(bindings_current=False)])
        with patch.object(closeout, "call", side_effect=invoke), patch.object(closeout, "observe", side_effect=AssertionError("went on")):
            with self.assertRaisesRegex(ValueError, "no longer shows unit admitted"):
                closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        self.assertFalse(any("Approved checks passed" in str(a) for a in calls))

    def test_a_verk_without_evidence_lists_is_refused_before_any_check(self):
        view = {"contract": {"id": "vk-1"}, "state": "active", "attempt": {"id": "vk-1.1"}, "attempts": [{"id": "vk-1.1", "state": "active"}],
                "policy": {"checks": [{"name": "unit", "status": "passed"}]}}
        with patch.object(closeout, "call", return_value=view) as invoke:
            with self.assertRaisesRegex(ValueError, "no per-check evidence"):
                closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        self.assertFalse(any(c.args[2] == "check" for c in invoke.call_args_list))

    def test_a_check_that_left_the_policy_is_not_claimed(self):
        view = {"policy": {"checks": []}}
        with self.assertRaisesRegex(ValueError, "no longer in the policy"):
            closeout.check_named(view, "unit", self.head)

    def test_covering_review_starts_nothing_and_differing_policy_kind_refuses(self):
        view = {"contract": {"id": "vk-1", "acceptance_version": 1, "subjects_version": 0}, "state": "active",
                "reviews": [{"decision": "vk-d1", "lifecycle": "open"}], "policy": {"version": 9, "kind_version": 2, "checks": [{"name": "unit", "evidence": []}]}}
        decision = {"lifecycle": "open", "contracts": ["vk-1"], "target": {"revision": self.head},
                    "bindings": {"acceptanceVersion": 1, "subjectsVersion": 0, "policyVersion": 2}}
        def invoke(repo, env, *args, **kwargs):
            return decision if args[1] == "vk-d1" else view
        with patch.object(closeout, "call", side_effect=invoke) as called, patch.object(closeout, "observe", return_value={"status": "review_pending", "reviews": ["vk-d1"]}):
            closeout.closeout(self.repo, self.env, "vk-1", None, 0, source_only=True)
        self.assertEqual({c.args[2] for c in called.call_args_list}, {"view", "reconcile"})
        self.assertFalse(closeout.review_covers(view, dict(decision, bindings=dict(decision["bindings"], policyVersion=9)), self.head))

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
        view = {"contract": {"id": "vk-1", "acceptance_version": 2, "subjects_version": 1}, "policy": {"version": 9, "kind_version": 3}}
        good = {"lifecycle": "open", "contracts": ["vk-1"], "target": {"revision": self.head},
                "bindings": {"acceptanceVersion": 2, "subjectsVersion": 1, "policyVersion": 3}}
        self.assertTrue(closeout.review_covers(view, good, self.head))
        self.assertFalse(closeout.review_covers({"contract": view["contract"], "policy": {"version": 3}}, good, self.head))
        self.assertTrue(closeout.review_covers(view, dict(good, target={"artifact": {"revision": self.head}}), self.head))
        for name, changed in {"revision": {"target": {"revision": "0" * 40}},
                              "artifact revision": {"target": {"artifact": {"revision": "0" * 40}}},
                              "acceptance": {"bindings": dict(good["bindings"], acceptanceVersion=1)},
                              "subjects": {"bindings": dict(good["bindings"], subjectsVersion=0)},
                              "policy": {"bindings": dict(good["bindings"], policyVersion=2)},
                              "other contract": {"contracts": ["vk-2"]}, "answered": {"lifecycle": "answered"}}.items():
            with self.subTest(name):
                self.assertFalse(closeout.review_covers(view, dict(good, **changed), self.head))

    def outcome(self, review, row=None, checks=(), receipt=None):
        day = Path(self.env["VERK_HOME"]) / "reviews" / "2026-11-05"
        day.mkdir(parents=True, exist_ok=True)
        (day / "verdicts.jsonl").write_text(json.dumps(dict({"decision": "vk-d1", "at": 1, "exit": 0}, **row)) + "\ngarbage\n" if row else "")
        view = {"reviews": [dict({"decision": "vk-d1", "lifecycle": "open", "verdict": None}, **review)] if review is not None else [],
                "policy": {"checks": list(checks)}}
        return closeout.outcomes(self.env, view, self.head, receipt)

    def test_each_review_situation_has_its_own_outcome(self):
        approve, reject = {"verdict": "approve", "clauses": [{"clause": "c", "met": 0.9}]}, {"verdict": "reject", "clauses": [{"clause": "c", "met": 0.1}]}
        answered = lambda verdict: {"lifecycle": "answered", "verdict": verdict}
        current = self.evidence()
        cases = [
            ("disagreement_gate_rejected", {}, {"proposed": "approve", "decider": reject}, []),
            ("disagreement_gate_rejected", answered("approved"), {"proposed": "approve", "decider": reject}, []),
            ("disagreement_reviewer_rejected", {}, {"proposed": "reject", "decider": approve}, []),
            ("process_failure", {}, {"proposed": "retry", "exit": 143}, []),
            ("unavailable", {}, {"proposed": "unavailable", "decider": {"error": "no key"}}, []),
            ("review_withdrawn", {"lifecycle": "withdrawn"}, None, []),
            ("stale_bindings", None, None, [{"name": "unit", "evidence": [self.evidence(bindings_current=False)]}]),
            ("review_rejected", answered("rejected"), {"proposed": "reject", "decider": reject}, []),
            ("check_rejected", None, None, [{"name": "unit", "evidence": [self.evidence(status="rejected", reason="failed")]}]),
            ("approved_awaiting_answer", {}, {"proposed": "approve", "decider": approve}, [{"name": "unit", "evidence": [current]}]),
            ("answered_no_receipt", answered("approved"), {"proposed": "approve", "decider": approve}, [{"name": "unit", "evidence": [current]}]),
            ("stale_target", {}, {"proposed": "approve", "decider": approve, "revision": "0" * 40}, []),
            ("review_pending", {}, None, [{"name": "unit", "evidence": [current]}]),
        ]
        for expected, review, row, checks in cases:
            with self.subTest(expected, review=review):
                seen = self.outcome(review, row, checks)
                self.assertEqual(seen["outcome"], expected)
                self.assertEqual(seen["next_action"], closeout.NEXT_ACTION[expected])
        self.assertEqual(len({c[0] for c in cases}), 12)

    def test_a_review_no_verdict_is_coming_from_is_not_reported_as_waiting(self):
        for outcome in ("process_failure", "unavailable"):
            with self.subTest(outcome):
                result = {"status": "review_pending", "contract": "vk-1", "reviews": ["vk-d1"],
                          "outcomes": {"outcome": outcome, "next_action": closeout.NEXT_ACTION[outcome]}}
                seen = closeout.reported(result)
                self.assertEqual((seen["status"], seen["reason"], seen["reviews"]), ("needs_action", closeout.NEXT_ACTION[outcome], ["vk-d1"]))
                self.assertEqual(result["status"], "review_pending")  # Control flow still sees the open review, so its request survives.
        for unchanged in ({"status": "review_pending", "reviews": ["vk-d1"], "outcomes": {"outcome": "review_pending"}},
                          {"status": "review_pending", "reviews": ["vk-d1"]}, {"status": "receipt", "outcomes": {"outcome": "process_failure"}}):
            self.assertEqual(closeout.reported(unchanged), unchanged)

    def test_an_answer_against_the_reviewer_keeps_the_disagreement_visible(self):
        approve, reject = {"verdict": "approve", "clauses": []}, {"verdict": "reject", "clauses": []}
        overruled = self.outcome({"lifecycle": "answered", "verdict": "approved"}, {"proposed": "reject", "decider": approve})
        self.assertEqual((overruled["review"], overruled["answer"], overruled["gate"], overruled["disagreement"]),
                         ("reject", "approved", "approve", "disagreement_reviewer_rejected"))
        rejected = self.outcome({"lifecycle": "answered", "verdict": "rejected"}, {"proposed": "approve", "decider": reject})
        self.assertEqual((rejected["review"], rejected["answer"], rejected["disagreement"]), ("approve", "rejected", "disagreement_gate_rejected"))
        after_failure = self.outcome({"lifecycle": "answered", "verdict": "approved"}, {"proposed": "retry", "exit": 1})
        self.assertEqual((after_failure["review"], after_failure["answer"], after_failure["outcome"]), ("process_failure", "approved", "answered_no_receipt"))
        self.assertEqual(self.outcome({"lifecycle": "answered", "verdict": "approved"})["review"], "not_recorded")

    def test_outcome_fields_stay_separate_and_a_receipt_keeps_the_disagreement_visible(self):
        reject = {"verdict": "reject", "clauses": [{"clause": "c", "met": 0.1}]}
        seen = self.outcome({"lifecycle": "answered", "verdict": "approved"}, {"proposed": "approve", "decider": reject, "chars": 900, "revision": self.head},
                            [{"name": "unit", "evidence": [self.evidence(status="used")]}, {"name": "lint", "evidence": []}, {"name": "old"},
                             {"name": "moved", "evidence": [self.evidence(revision="0" * 40)]}], receipt="vk-r1")
        self.assertEqual((seen["outcome"], seen["review"], seen["gate"], seen["receipt"], seen["disagreement"]),
                         ("receipt", "approve", "reject", "vk-r1", "disagreement_gate_rejected"))
        self.assertEqual([a["state"] for a in seen["admission"]], ["admitted", "none", "unknown", "other_revision"])
        self.assertEqual(seen["coverage"], {"reviewed_revision": self.head, "requested_revision": self.head, "covers_requested_revision": True,
                                            "report_chars": 900, "gate_clauses": reject["clauses"], "checks_admitted": ["unit"],
                                            "checks_not_admitted": ["lint", "moved", "old"]})
        gate = {"verdict": "unsure", "clauses": []}
        self.assertEqual(self.outcome({}, {"proposed": "approve", "decider": gate})["gate"], "unsure")
        self.assertEqual(self.outcome({})["gate"], "not_run")

    def test_a_damaged_manifest_never_fails_observation(self):
        day = Path(self.env["VERK_HOME"]) / "reviews" / "2026-11-05"
        day.mkdir(parents=True, exist_ok=True)
        (day / "verdicts.jsonl").write_bytes(b"\xff\xfe not utf-8\n")
        (Path(self.env["VERK_HOME"]) / "reviews" / "2026-11-06").mkdir()
        (Path(self.env["VERK_HOME"]) / "reviews" / "2026-11-06" / "verdicts.jsonl").write_text(
            json.dumps({"decision": "vk-d1", "at": "soon", "exit": 0, "proposed": "approve"}) + "\n")
        self.assertEqual(closeout.verdict_row(self.env, "vk-d1")["proposed"], "approve")

    def test_observe_reports_outcomes_without_changing_its_status(self):
        view = {"state": "available", "reviews": [{"decision": "vk-d1", "lifecycle": "open", "verdict": None}], "policy": {"checks": []}}
        self.outcome({}, {"proposed": "approve", "decider": {"verdict": "reject", "clauses": []}})
        with patch.object(closeout, "call", return_value=view):
            result = closeout.observe(self.repo, self.env, "vk-1", self.head, 0)
        self.assertEqual(result["status"], "review_pending")
        self.assertEqual(result["outcomes"]["outcome"], "disagreement_gate_rejected")

    def test_observing_another_receipt_preserves_pending_work(self):
        path = closeout.state_path(self.env)
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
