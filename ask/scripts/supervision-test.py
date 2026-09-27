#!/usr/bin/env python3
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent


class SupervisionTests(unittest.TestCase):
    def run_case(self, code, *, first=3, wall=5, adapter='grok-stream-surface.ts'):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        (out / 'prompt.md').write_text('synthetic test')
        command = [sys.executable, str(ROOT / 'supervise.py'), '--outdir', str(out), '--adapter', str(ROOT / adapter),
                   '--transport', 'fixture', '--first-output-seconds', str(first), '--wall-seconds', str(wall),
                   '--heartbeat-seconds', '0.1', '--', sys.executable, '-c', code]
        result = subprocess.run(command, capture_output=True, timeout=15)
        self.assertTrue((out / 'result.json').exists(), (result.returncode, result.stderr.decode()))
        return result, json.loads((out / 'result.json').read_text()), out

    def test_complete_modern_grok(self):
        proc, result, out = self.run_case('import json; print(json.dumps({"type":"tool_call","toolName":"read_file","status":"completed"})); print(json.dumps({"type":"text","data":"VERDICT: CONCUR\\n\\n1. café"})); print(json.dumps({"type":"end","stopReason":"EndTurn"}))')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result['status'], 'complete')
        self.assertIn('café', (out / 'artifact.md').read_text())
        self.assertGreater((out/'trace.jsonl').stat().st_size,0)
        records = [json.loads(x) for x in (out / 'status.jsonl').read_text().splitlines()]
        self.assertEqual(records[0]['event'], 'watcher_attached')
        self.assertEqual([x['seq'] for x in records], list(range(1,len(records)+1)))

    def test_partial_eof(self):
        proc, result, out = self.run_case('print(\'{"type":"text","data":"partial answer"}\')')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(result['reason'], 'missing_completion')
        self.assertIn('partial answer', (out / 'partial.md').read_text())

    def test_length_and_error_cannot_pass(self):
        for ending in ['{"type":"end","stopReason":"Length"}', '{"type":"error","message":"max_tokens_truncation"}\n{"type":"end","stopReason":"EndTurn"}']:
            proc, result, _ = self.run_case('print(\'{"type":"text","data":"partial"}\'); print('+repr(ending)+')')
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(result['status'], 'failed')

    def test_empty_and_malformed(self):
        for prefix in ['', 'not json\n']:
            proc, result, _ = self.run_case('print('+repr(prefix+'{"type":"end","stopReason":"EndTurn"}')+')')
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(result['reason'], ['empty_answer', 'malformed_stream'])

    def test_first_output_timeout_and_heartbeat(self):
        proc, result, out = self.run_case('import time; print(\'{"type":"available_commands"}\',flush=True); time.sleep(10)', first=.5)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(result['reason'], 'first_model_output_budget')
        self.assertIn('heartbeat', (out / 'status.jsonl').read_text())

    def test_wall_timeout_after_progress(self):
        _, result, _ = self.run_case('import time; print(\'{"type":"text","data":"working"}\',flush=True); time.sleep(10)', wall=.5)
        self.assertEqual(result['reason'], 'total_wall_budget')

    def test_split_chunks_and_redacted_stderr(self):
        _, result, out = self.run_case('import os,time; b=\'{"type":"text","data":"café"}\\n{"type":"end","stopReason":"EndTurn"}\\n\'.encode(); [os.write(1,bytes([x])) for x in b]; print("Bearer secretvalue api_key=sk-secretabcdefghi",file=__import__("sys").stderr)')
        self.assertEqual(result['status'], 'complete')
        self.assertIn('café', (out / 'trace.jsonl').read_text())
        self.assertNotIn('secretvalue', (out / 'stderr.log').read_text())

    def test_native_claude_and_codex_completion(self):
        for adapter, event in [('claude-stream-surface.ts',{'type':'result','subtype':'success','result':'review'}),
                               ('codex-stream-surface.ts',{'type':'item.completed','item':{'type':'agent_message','text':'review'}})]:
            code='print('+repr(json.dumps(event))+')'
            if adapter.startswith('codex'): code += '; print(\'{"type":"turn.completed"}\')'
            _, result, _ = self.run_case(code,adapter=adapter)
            self.assertEqual(result['status'],'complete')

    def test_codex_config_warning_does_not_mask_failures(self):
        warning = {"type": "error", "message": "Codex is ignoring 6 unrecognized configuration settings. Check for typos or deprecated settings.\n  user (/example/config.toml): `network_access` is ignored.\n  ... and 5 more ignored settings."}
        answer = {"type": "item.completed", "item": {"type": "agent_message", "text": "source-anchored review"}}
        terminal = {"type": "turn.completed"}
        cases = [
            ([warning, answer, terminal], "complete"),
            ([warning, answer], "failed"),
            ([warning, terminal], "failed"),
            ([warning, answer, {"type": "error", "message": "authentication failed"}, terminal], "failed"),
            ([warning, answer, {"type": "turn.failed"}, terminal], "failed"),
            ([dict(warning, message=warning["message"] + "\nProvider request failed"), answer, terminal], "failed"),
            ([{"type": "error", "message": "unknown warning"}, answer, terminal], "failed"),
        ]
        for events, expected in cases:
            with self.subTest(events=events):
                code = "print(" + repr("\n".join(json.dumps(e) for e in events)) + ")"
                proc, result, out = self.run_case(code, adapter="codex-stream-surface.ts")
                self.assertEqual(result["status"], expected, proc.stderr)
                if warning in events:
                    self.assertIn("unrecognized configuration", (out / "trace.jsonl").read_text())
        item_warning = {"type": "item.completed", "item": {"type": "error", "message": warning["message"]}}
        code = "print(" + repr("\n".join(json.dumps(e) for e in [item_warning, answer, terminal])) + ")"
        _, result, _ = self.run_case(code, adapter="codex-stream-surface.ts")
        self.assertEqual(result["status"], "complete")

    def test_signal_cancellation_and_child_drain(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); (out/'prompt.md').write_text('test')
            proc=subprocess.Popen([sys.executable,str(ROOT/'supervise.py'),'--outdir',d,'--adapter',str(ROOT/'grok-stream-surface.ts'),'--transport','fixture','--',sys.executable,'-c','import time; time.sleep(30)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.addCleanup(lambda: proc.poll() is None and proc.kill())
            deadline=time.monotonic()+3
            while not (out/'status.jsonl').exists() or 'started' not in (out/'status.jsonl').read_text():
                self.assertLess(time.monotonic(),deadline); time.sleep(.02)
            proc.terminate(); proc.wait(timeout=8)
            result=json.loads((out/'result.json').read_text())
            self.assertEqual(result['status'],'cancelled')

    def test_watcher_loss_guard(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); (out/'prompt.md').write_text('test')
            proc=subprocess.Popen([sys.executable,str(ROOT/'supervise.py'),'--outdir',d,'--adapter',str(ROOT/'grok-stream-surface.ts'),'--transport','fixture','--',sys.executable,'-c','import time; time.sleep(30)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.addCleanup(lambda: proc.poll() is None and proc.kill())
            deadline=time.monotonic()+4
            while not (out/'status.jsonl').exists() or 'started' not in (out/'status.jsonl').read_text():
                self.assertLess(time.monotonic(),deadline); time.sleep(.02)
            # Give the guard time to start its child before removing the watcher.
            time.sleep(.2); proc.kill(); proc.wait(timeout=3)
            while not (out/'watcher-loss.json').exists():
                self.assertLess(time.monotonic(),deadline); time.sleep(.02)
            self.assertEqual(json.loads((out/'watcher-loss.json').read_text())['reason'],'watcher_lost')

    def test_runner_freezes_source_before_child_launch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source'; shutil.copytree(ROOT.parent,source)
            tools=root/'bin'; tools.mkdir(); stub=tools/'grok'
            stub.write_text('#!/bin/bash\nif [ "$1" = models ]; then echo "You are logged in"; exit 0; fi\nprintf \'{"type":"text","data":"frozen"}\\n\'\nsleep 1\nprintf \'{"type":"end","stopReason":"EndTurn"}\\n\'\n')
            stub.chmod(0o755); config=root/'config.toml';config.write_text('')
            out=root/'output'
            env=dict(os.environ,PATH=str(tools)+os.pathsep+os.environ['PATH'],ASK_GROK_CONFIG=str(config))
            proc=subprocess.Popen(['bash',str(source/'scripts/ask.sh'),'grok','-o',str(out),'synthetic'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.addCleanup(lambda: proc.poll() is None and proc.kill())
            deadline=time.monotonic()+6
            while not (out/'status.jsonl').exists() or 'started' not in (out/'status.jsonl').read_text():
                self.assertLess(time.monotonic(),deadline);time.sleep(.02)
            (source/'scripts/ask.sh').write_text('#!/bin/bash\nexit 99\n')
            (source/'scripts/grok-stream-surface.ts').write_text('throw new Error("changed source");')
            proc.wait(timeout=8)
            self.assertEqual(proc.returncode,0)
            self.assertEqual(json.loads((out/'result.json').read_text())['status'],'complete')

    def test_empty_replay_cannot_overwrite_answer(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); trace=out/'trace.jsonl';trace.write_text('')
            artifact=out/'artifact.md';artifact.write_text('preserved review')
            result=subprocess.run(['node','--experimental-strip-types',str(ROOT/'grok-stream-surface.ts'),'--from-file',str(trace),str(artifact)],capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(artifact.read_text(),'preserved review')


if __name__=='__main__': unittest.main()
