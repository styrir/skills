import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import closeout
import codex_review
import codex_closeout


class DelegatedGoalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, VERK_HOME=str(self.root / 'store'), CODEX_THREAD_ID='codex-delegation-test')
        self.head = 'a' * 40
        self.view = {'contract': {'id': 'vk-1', 'project': 'fixture', 'kind': 'goal', 'acceptance_version': 1, 'subjects_version': 0},
                     'children': [], 'prerequisites': []}
        self.decision = {'id': 'vk-d1', 'kind': 'review', 'contract': 'vk-1', 'contracts': ['vk-1'], 'lifecycle': 'open',
                         'responsible': 'operator:' + Path.home().owner(), 'created_at': 1,
                         'target': {'revision': self.head}, 'bindings': {'acceptanceVersion': 1, 'subjectsVersion': 0}}
        self.folder = self.root / 'store/reviews/2026-11-02'
        self.folder.mkdir(parents=True)
        self.report = self.folder / 'vk-d1.md'
        self.report.write_text(f'Reviewed: {self.head}\nIndependent fixture report.\nVERDICT: approve\n')
        self.row = {'decision': 'vk-d1', 'contract': 'vk-1', 'revision': self.head, 'exit': 0, 'proposed': 'approve',
                    'answered': False, 'at': 2, 'chars': len(self.report.read_text())}
        self.manifest = self.folder / 'verdicts.jsonl'
        self.manifest.write_text(json.dumps(self.row) + '\n')

    def invoke(self, **kwargs):
        def call(repo, env, *args, **kw):
            return {'project': 'fixture'} if args[0] == 'brief' else self.decision
        def git(repo, *args):
            return self.head if args[0] == 'rev-parse' else ''
        return codex_review.complete_goal(self.root, kwargs.get('env', self.env), self.view, self.decision,
                                          self.head, kwargs.get('call', call), kwargs.get('git', git))

    def test_explicit_delegation_uses_operator_only_for_approved_goal_answer(self):
        with patch.object(codex_review.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"ok":true}', '')) as run:
            self.assertTrue(self.invoke())
        args = run.call_args.args[0]
        self.assertEqual(args[1:3], ['answer', 'vk-d1'])
        self.assertIn('operator-delegated', args[3])
        self.assertIn('codex:codex-delegation-test', args[3])
        self.assertEqual(run.call_args.kwargs['env']['VERK_ACTOR'], self.decision['responsible'])
        self.assertEqual(run.call_args.kwargs['env']['VERK_SESSION'], 'codex-delegation-test')
        self.assertNotIn('VERK_REVIEWER', run.call_args.kwargs['env'])

    def test_missing_failed_rejected_stale_and_tampered_approvals_never_answer(self):
        for change in [{'exit': 1}, {'proposed': 'reject'}, {'revision': 'b' * 40}, {'chars': 1}, {'at': 0}]:
            with self.subTest(change=change), patch.object(codex_review.subprocess, 'run', side_effect=AssertionError('unexpected answer')):
                self.manifest.write_text(json.dumps(dict(self.row, **change)) + '\n')
                try:
                    self.assertFalse(self.invoke())
                except ValueError:
                    pass
        self.manifest.unlink()
        self.assertIsNone(codex_review.approved_report(self.env, self.decision, 'vk-1', self.head))

    def test_wrong_harness_non_goal_dirty_moved_or_unfinished_children_never_answer(self):
        with patch.object(codex_review.subprocess, 'run', side_effect=AssertionError('unexpected answer')):
            with self.assertRaisesRegex(ValueError, 'Codex-only'):
                self.invoke(env=dict(self.env, VERK_CLOSEOUT_HARNESS='claude-code'))
            self.view['contract']['kind'] = 'code'
            self.assertFalse(self.invoke())
            self.view['contract']['kind'] = 'goal'
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.invoke(git=lambda *args: 'changed')
            self.view['children'] = [{'id': 'vk-2', 'state': 'available'}]
            with self.assertRaisesRegex(ValueError, 'children'):
                self.invoke()

    def test_symlink_and_shared_writable_reports_are_not_admitted(self):
        self.report.chmod(0o666)
        with self.assertRaisesRegex(ValueError, 'owner-controlled'):
            self.invoke()

        self.report.chmod(0o644)
        target = self.report.with_suffix('.copy')
        self.report.rename(target)
        self.report.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'owner-controlled'):
            self.invoke()

    def test_project_acceptance_and_bound_children_must_still_match(self):
        with patch.object(codex_review.subprocess, 'run', side_effect=AssertionError('unexpected answer')):
            self.view['contract']['project'] = 'other'
            with self.assertRaisesRegex(ValueError, 'another repository'):
                self.invoke()
            self.view['contract']['project'] = 'fixture'
            self.view['contract']['acceptance_version'] = 2
            with self.assertRaisesRegex(ValueError, 'current goal review'):
                self.invoke()
            self.view['contract']['acceptance_version'] = 1
            self.view['children'] = [{'id': 'vk-2', 'state': 'satisfied'}]
            with self.assertRaisesRegex(ValueError, 'children changed'):
                self.invoke()
            self.decision['bindings']['children'] = [{'id': 'vk-2', 'source': 'receipt', 'receipt': 'vk-r1'}]
            def call(repo, env, *args, **kwargs):
                if args[0] == 'brief': return {'project': 'fixture'}
                if args[1] == 'vk-2': return {'state': 'satisfied', 'receipts': [{'id': 'vk-r2'}]}
                return self.decision
            with self.assertRaisesRegex(ValueError, 'current child receipts'):
                self.invoke(call=call)

    def test_installed_reviewer_markdown_target_heading_is_accepted(self):
        for heading in [f'1. **Reviewed: {self.head[:8]}**', f'## Reviewed: `{self.head}`']:
            body = heading + '\nIndependent fixture report.\nVERDICT: approve\n'
            self.report.write_text(body)
            self.manifest.write_text(json.dumps(dict(self.row, chars=len(body), decider=None)) + '\n')
            self.assertIsNotNone(codex_review.approved_report(self.env, self.decision, 'vk-1', self.head))

    def approved_goal(self):
        """A real goal with an open review whose approved report would let delegated completion answer it."""
        repo = self.root / 'repo'
        repo.mkdir()
        def run(*args, env=None):
            r = subprocess.run(args, cwd=repo, env=env or self.env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return r
        for args in [('init', '-q'), ('config', 'user.name', 'Test'), ('config', 'user.email', 'test@example.invalid')]:
            run('git', *args)
        (repo / 'proof.txt').write_text('Synthetic goal evidence only')
        run('git', 'add', 'proof.txt')
        run('git', 'commit', '-qm', 'fixture')
        binary = str(Path.home() / '.local/bin/verk')
        run(binary, 'bind', 'fixture', '--approve-policy', '--json')
        goal = closeout.call(repo, self.env, 'add', 'Synthetic goal', '--kind', 'goal', '--accept', 'Synthetic proof exists', '--json')['id']
        pending = closeout.closeout(repo, self.env, goal, 'proof.txt', 0, source_only=True)
        decision = closeout.call(repo, self.env, 'view', pending['reviews'][0], '--json')
        head = closeout.git(repo, 'rev-parse', 'HEAD')
        body = f'Reviewed: {head}\nAcceptance: Synthetic proof exists.\n' + ('Synthetic independent fixture review. ' * 30) + '\n## Missing coverage\nNo live data used.\n## Assumptions\nIsolated synthetic fixture only.\nVERDICT: approve\n'
        (self.folder / (decision['id'] + '.md')).write_text(body)
        row = dict(self.row, decision=decision['id'], contract=goal, revision=head,
                   chars=len(body), at=decision['created_at'] + 1)
        self.manifest.write_text(json.dumps(row) + '\n')
        return repo, goal, head

    def snapshot(self, repo):
        """Everything observing could change: store rows, every other store file with its mtime, and the checkout."""
        rows, files = {}, {}
        for item in sorted(Path(self.env['VERK_HOME']).rglob('*')):
            if not item.is_file() or item.name.endswith(('-wal', '-shm')):
                continue
            head = item.read_bytes()[:16]
            if head == b'SQLite format 3\x00':
                db = sqlite3.connect(f'file:{item}?mode=ro', uri=True)
                rows[str(item)] = list(db.iterdump())
                db.close()
            else:
                files[str(item)] = (item.stat().st_mtime_ns, item.read_bytes())
        self.assertTrue(rows, 'the fixture store should hold a database')
        return rows, files, closeout.git(repo, 'status', '--porcelain'), closeout.git(repo, 'rev-parse', 'HEAD')

    def operate(self, repo, *args):
        script = Path(__file__).with_name('closeout.py')
        result = subprocess.run([sys.executable, str(script), *args, '--repo', str(repo)], env=self.env,
                                capture_output=True, text=True, timeout=60)
        return result.returncode, json.loads(result.stdout) if result.stdout.strip() else result.stderr

    def test_observing_a_delegated_request_twice_changes_and_completes_nothing(self):
        repo, goal, head = self.approved_goal()
        path = closeout.state_path(self.env)
        closeout.save(path, dict(json.loads(path.read_text()), delegate_approved_goals=True))
        before = self.snapshot(repo)
        for _ in range(2):
            code, result = self.operate(repo, 'observe', '--id', goal)
            self.assertEqual(code, 3, result)
            self.assertEqual((result['status'], result['operation']), ('review_pending', 'observe'))
            self.assertEqual(self.snapshot(repo), before)
        # In process too, so the only Verk verb and the absence of completion are seen directly, not just their effects.
        verbs = []
        real = closeout.call
        def spy(*args, **kwargs):
            verbs.append(args[2])
            return real(*args, **kwargs)
        with patch.object(closeout, 'call', side_effect=spy), patch.object(codex_closeout, 'complete_goal', side_effect=AssertionError('completed')):
            self.assertEqual(closeout.observe(repo, self.env, goal, head, 0)['status'], 'review_pending')
        self.assertEqual(set(verbs), {'view'})
        self.assertEqual(self.snapshot(repo), before)
        # The same request really is completable, so the reads above held back something that could happen.
        code, done = self.operate(repo, 'complete', '--id', goal)
        self.assertEqual((code, done['status'], done['operation']), (0, 'receipt', 'complete'), done)
        self.assertFalse(path.exists())

    def test_delegation_is_never_applied_to_a_request_this_closeout_did_not_write(self):
        path = closeout.state_path(self.env)
        other = {'request_id': 'other', 'contract': 'vk-other', 'repo': str(self.root), 'head': 'h', 'common_dir': 'g', 'delegate_approved_goals': False}
        def replaced(*args, **kwargs):
            closeout.save(path, other)
            return {'status': 'review_pending', 'contract': 'vk-1', 'reviews': ['vk-d1'], 'request_id': 'mine'}
        with patch.object(closeout, 'closeout', side_effect=replaced), \
             patch.object(codex_closeout, 'complete', side_effect=AssertionError('completed under another request')):
            result = codex_closeout.closeout(self.root, self.env, 'vk-1', None, 0, source_only=True, delegate_approved_goals=True)
        self.assertTrue(result['superseded'])
        self.assertEqual(json.loads(path.read_text()), other)

    def test_a_replacement_before_the_delegated_answer_stops_it(self):
        repo, goal, _ = self.approved_goal()
        path = closeout.state_path(self.env)
        request = dict(json.loads(path.read_text()), delegate_approved_goals=True)
        closeout.save(path, request)
        real = codex_review.invocation
        def replaced_then_invocation(*args, **kwargs):
            closeout.save(path, dict(request, request_id='newer', delegate_approved_goals=False))  # arrives while the goal is being checked
            return real(*args, **kwargs)
        with patch.object(codex_review, 'invocation', side_effect=replaced_then_invocation):
            result = codex_closeout.complete(repo, self.env, request)
        self.assertEqual(result['status'], 'review_pending')
        self.assertEqual(closeout.call(repo, self.env, 'view', goal, '--json')['receipts'], [])

    def test_complete_needs_the_recorded_delegation_and_reconcile_is_labelled(self):
        repo, goal, _ = self.approved_goal()
        path = closeout.state_path(self.env)
        before = path.read_text()
        code, result = self.operate(repo, 'complete', '--id', goal)
        self.assertEqual((code, result['status'], result['operation']), (3, 'review_pending', 'complete'))
        self.assertEqual(path.read_text(), before)
        self.assertEqual(closeout.call(repo, self.env, 'view', goal, '--json')['receipts'], [])
        code, result = self.operate(repo, 'reconcile', '--id', goal)
        self.assertEqual((code, result['status'], result['operation']), (3, 'review_pending', 'reconcile'))
        self.assertEqual(self.operate(repo, '--harness', 'claude-code', 'complete', '--id', goal)[0], 2)
        path.unlink()
        code, message = self.operate(repo, 'complete', '--id', goal)
        self.assertEqual(code, 2)
        self.assertIn('No pending closeout request', message)

    def test_real_cli_goal_receipt_without_changing_policy_or_reviewer(self):
        repo, goal, _ = self.approved_goal()
        policy = closeout.call(repo, self.env, 'view', goal, '--json')['policy']
        done = codex_closeout.closeout(repo, self.env, goal, 'proof.txt', 0, source_only=True, delegate_approved_goals=True)
        self.assertEqual(done['status'], 'receipt')
        view = closeout.call(repo, self.env, 'view', goal, '--json')
        self.assertEqual(view['policy'], policy)
        self.assertTrue(all(a['actor'] == 'codex:codex-delegation-test' for a in view['attempts']))

class CodexStopTests(unittest.TestCase):
    def test_foreground_replacement_during_stop_keeps_the_new_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, CODEX_THREAD_ID='codex-race-test', VERK_HOME=str(root / 'store'))
            path = closeout.state_path(env)
            first = {'request_id': 'one', 'repo': str(root), 'contract': 'vk-1', 'head': 'head', 'common_dir': 'git'}
            newer = dict(first, request_id='two', head='newer')
            closeout.save(path, first)
            def replaced(*args, **kwargs):
                with closeout.request_lock(path):
                    closeout.save(path, newer)
                return {'status': 'receipt', 'receipt': 'vk-r1'}
            def git(repo, *args):
                return '' if args[0] == 'status' else ('head' if args[-1] == 'HEAD' else 'git')
            payload = {'hook_event_name': 'Stop', 'session_id': 'codex-race-test', 'cwd': str(root)}
            with patch.object(closeout, 'git', side_effect=git), patch.object(closeout, 'call', return_value={}), \
                 patch.object(codex_closeout, 'complete', side_effect=replaced):
                result = codex_closeout.hook(payload, env)
            self.assertEqual(result['decision'], 'block')
            self.assertIn('newer closeout request', result['reason'])
            self.assertEqual(json.loads(path.read_text()), newer)
            self.assertFalse(path.with_suffix('.result.json').exists())

    def test_request_is_found_after_checkout_and_payload_cwd_are_gone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, CODEX_THREAD_ID='codex-gone-test', VERK_HOME=str(root / 'store'))
            path = closeout.state_path(env)
            request = {'request_id': 'one', 'repo': str(root / 'deleted'), 'contract': 'vk-1', 'head': 'head', 'common_dir': 'git'}
            closeout.save(path, request)
            payload = {'hook_event_name': 'Stop', 'session_id': 'codex-gone-test', 'cwd': str(root / 'also-deleted')}
            with patch.object(closeout, 'call', side_effect=AssertionError('no Verk write without a checkout')):
                result = codex_closeout.hook(payload, env)
            self.assertEqual(result['decision'], 'block')
            self.assertEqual(json.loads(path.read_text()), request)

    def test_hard_exit_during_stop_never_consumes_pending_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, CODEX_THREAD_ID='codex-crash-test', VERK_HOME=str(root / 'store'))
            path = closeout.state_path(env)
            request = {'repo': str(root), 'contract': 'vk-1', 'head': 'head', 'common_dir': 'git'}
            closeout.save(path, request)
            script = """
import os,sys
from pathlib import Path
from unittest.mock import patch
import closeout,codex_closeout
def git(repo,*args):
    return '' if args[0]=='status' else ('head' if args[-1]=='HEAD' else 'git')
with patch.object(closeout,'git',side_effect=git), patch.object(closeout,'call',side_effect=lambda *a,**k:os._exit(17)):
    codex_closeout.hook({'hook_event_name':'Stop','session_id':'codex-crash-test','cwd':sys.argv[1]},os.environ)
"""
            result = subprocess.run([sys.executable, '-c', script, str(root)], cwd=Path(__file__).parent, env=env)
            self.assertEqual(result.returncode, 17)
            self.assertEqual(json.loads(path.read_text()), request)

    def test_pending_survives_repeated_stops_and_receipt_ends_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, CODEX_THREAD_ID='codex-stop-test', VERK_HOME=str(root / 'store'))
            path = closeout.state_path(env)
            request = {'repo': str(root), 'contract': 'vk-1', 'head': 'head', 'common_dir': 'git',
                       'delegate_approved_goals': True}
            closeout.save(path, request)
            payload = {'hook_event_name': 'Stop', 'session_id': 'codex-stop-test', 'cwd': str(root)}
            def git(repo, *args):
                return '' if args[0] == 'status' else ('head' if args[-1] == 'HEAD' else 'git')
            with patch.object(closeout, 'git', side_effect=git), patch.object(closeout, 'call', return_value={}), \
                 patch.object(codex_closeout, 'complete', return_value={'status': 'review_pending'}) as complete:
                for active in [False, True]:
                    result = codex_closeout.hook(dict(payload, stop_hook_active=active), env)
                    self.assertEqual(result['decision'], 'block')
                    self.assertEqual(json.loads(path.read_text()), request)
                    self.assertTrue(complete.call_args.args[2]['delegate_approved_goals'])
                complete.return_value = {'status': 'receipt', 'receipt': 'vk-r1'}
                self.assertNotIn('decision', codex_closeout.hook(payload, env))
                self.assertFalse(path.exists())
                complete.side_effect = AssertionError('duplicate completion')
                self.assertEqual(codex_closeout.hook(payload, env), {})

    def test_changed_work_blocks_completion_without_verk_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, CODEX_THREAD_ID='codex-stale-test', VERK_HOME=str(root / 'store'))
            path = closeout.state_path(env)
            closeout.save(path, {'repo': str(root), 'contract': 'vk-1', 'head': 'old', 'common_dir': 'git'})
            payload = {'hook_event_name': 'Stop', 'session_id': 'codex-stale-test', 'cwd': str(root)}
            with patch.object(closeout, 'git', return_value='changed'), \
                 patch.object(closeout, 'call', side_effect=AssertionError('stale write')):
                result = codex_closeout.hook(payload, env)
                self.assertEqual(result['decision'], 'block')
                self.assertIn('changed', result['reason'])
                self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
