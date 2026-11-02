import json
import os
from pathlib import Path
import subprocess
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
        self.report.chmod(0o644)
        target = self.report.with_suffix('.copy')
        self.report.rename(target)
        self.report.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'owner-controlled'):
            self.invoke()

    def test_real_cli_goal_receipt_without_changing_policy_or_reviewer(self):
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
        policy = closeout.call(repo, self.env, 'view', goal, '--json')['policy']
        done = codex_closeout.closeout(repo, self.env, goal, 'proof.txt', 0, source_only=True, delegate_approved_goals=True)
        self.assertEqual(done['status'], 'receipt')
        view = closeout.call(repo, self.env, 'view', goal, '--json')
        self.assertEqual(view['policy'], policy)
        self.assertTrue(all(a['actor'] == 'codex:codex-delegation-test' for a in view['attempts']))

class CodexStopTests(unittest.TestCase):
    def test_pending_survives_repeated_stops_and_receipt_ends_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, CODEX_THREAD_ID='codex-stop-test', VERK_HOME=str(root / 'store'))
            path = closeout.state_path(root, env)
            request = {'repo': str(root), 'contract': 'vk-1', 'head': 'head', 'common_dir': 'git',
                       'delegate_approved_goals': True}
            closeout.save(path, request)
            payload = {'hook_event_name': 'Stop', 'session_id': 'codex-stop-test', 'cwd': str(root)}
            def git(repo, *args):
                return '' if args[0] == 'status' else ('head' if args[-1] == 'HEAD' else 'git')
            with patch.object(closeout, 'git', side_effect=git), patch.object(closeout, 'call', return_value={}), \
                 patch.object(codex_closeout, 'observe', return_value={'status': 'review_pending'}) as observe:
                for active in [False, True]:
                    result = codex_closeout.hook(dict(payload, stop_hook_active=active), env)
                    self.assertEqual(result['decision'], 'block')
                    self.assertEqual(json.loads(path.read_text()), request)
                    self.assertTrue(observe.call_args.args[2]['delegate_approved_goals'])
                observe.return_value = {'status': 'receipt', 'receipt': 'vk-r1'}
                self.assertNotIn('decision', codex_closeout.hook(payload, env))
                self.assertFalse(path.exists())
                observe.side_effect = AssertionError('duplicate completion')
                self.assertEqual(codex_closeout.hook(payload, env), {})

    def test_changed_work_blocks_completion_without_verk_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, CODEX_THREAD_ID='codex-stale-test', VERK_HOME=str(root / 'store'))
            path = closeout.state_path(root, env)
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
