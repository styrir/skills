#!/usr/bin/env python3
"""Attached watcher: own one consultation, persist JSONL, enforce budgets, drain."""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time
import uuid


def scrub(text):
    text = re.sub(r'(?i)(bearer\s+|api[_-]?key[\s:=]+|password[\s:=]+)\S+', r'\1[redacted]', text)
    return re.sub(r'\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,})\b', '[redacted]', text)


def group_members(group):
    # ps is read-only; group identity is the session we created for this run.
    output = subprocess.check_output(['ps', '-axo', 'pid=,pgid=,stat='], text=True)
    rows = [line.split() for line in output.splitlines()]
    return [int(row[0]) for row in rows if len(row) >= 3 and row[1] == str(group) and not row[2].startswith('Z')]


def drain(proc):
    if proc is None:
        return
    for sig, grace in [(signal.SIGTERM, 0.5), (signal.SIGKILL, 1.0)]:
        members = group_members(proc.pid)
        if not members:
            break
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            break
        except PermissionError:
            # macOS sandbox can refuse group signals after a leader exits.
            # Signal only independently verified members of our own group.
            for pid in members:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    pass
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline and group_members(proc.pid):
            time.sleep(0.05)
    proc.poll()
    return group_members(proc.pid)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--outdir', required=True)
    p.add_argument('--adapter', required=True)
    p.add_argument('--model', default='')
    p.add_argument('--transport', required=True)
    p.add_argument('--first-output-seconds', type=float, default=180)
    p.add_argument('--wall-seconds', type=float, default=600)
    p.add_argument('--heartbeat-seconds', type=float, default=15)
    p.add_argument('command', nargs=argparse.REMAINDER)
    args = p.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or not all(math.isfinite(x) and x > 0 for x in [args.first_output_seconds, args.wall_seconds, args.heartbeat_seconds]):
        p.error('command and positive budgets required')
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    import fcntl
    lock = open(out / '.watcher.lock', 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('watcher: output directory already owned by another run', file=sys.stderr)
        return 2
    run_id = str(uuid.uuid4())
    parent = os.getppid()
    started = time.monotonic()
    seq = 0
    provider = adapter = None
    status = 'failed'
    reason = 'watcher_initialization_failed'
    cancelled = False
    first = None
    last = None
    stderr_tail = ''
    pending = b''
    stream_result = {}
    route_metadata = {}
    files = {}

    def emit(event, **fields):
        nonlocal seq
        seq += 1
        record = dict(schemaVersion=1, run_id=run_id, parent_id=os.environ.get('ASK_PARENT_RUN_ID'),
                      agent_id=run_id, seq=seq, at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      event=event, **fields)
        files['status'].write(json.dumps(record) + '\n')
        files['status'].flush()

    def cancel(signum, frame):
        nonlocal cancelled
        cancelled = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, cancel)
    try:
        for name, filename in [('status', 'status.jsonl'), ('trace', 'trace.jsonl'), ('stderr', 'stderr.log')]:
            files[name] = open(out / filename, 'wb') if name == 'trace' else open(out / filename, 'w', encoding='utf-8')
            os.chmod(out / filename, 0o600)
        # This watcher exists before either child is admitted.
        emit('watcher_attached', model=args.model, transport=args.transport,
             first_output_seconds=args.first_output_seconds, wall_seconds=args.wall_seconds)
        group_members(0)  # capability probe before launching any provider
        env = dict(os.environ, ASK_TRACE_CAPTURED='true')
        adapter = subprocess.Popen(['node', '--experimental-strip-types', args.adapter,
                                    str(out / 'trace.jsonl'), str(out / 'artifact.md'), str(out / 'prompt.md')],
                                   stdin=subprocess.PIPE, start_new_session=True, env=env)
        provider = subprocess.Popen([sys.executable, str(Path(__file__).with_name('child-guard.py')), str(out)] + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        emit('started', provider_pid=provider.pid, adapter_pid=adapter.pid)
        selector = selectors.DefaultSelector()
        selector.register(provider.stdout, selectors.EVENT_READ, 'stdout')
        selector.register(provider.stderr, selectors.EVENT_READ, 'stderr')
        beat = started
        while selector.get_map():
            now = time.monotonic()
            if cancelled or os.getppid() != parent:
                status, reason = 'cancelled', 'signal' if cancelled else 'parent_lost'
                break
            if now - started >= args.wall_seconds:
                status, reason = 'timed_out', 'total_wall_budget'
                break
            if first is None and now - started >= args.first_output_seconds:
                status, reason = 'timed_out', 'first_model_output_budget'
                break
            if adapter.poll() is not None:
                status, reason = 'failed', 'adapter_exited_before_provider'
                break
            if now - beat >= args.heartbeat_seconds:
                emit('heartbeat', state='receiving' if first else 'waiting_for_model',
                     elapsed_seconds=round(now - started, 2), last_provider_event=last,
                     provider_alive=provider.poll() is None)
                print('watcher: ' + ('receiving' if first else 'waiting for model') +
                      ' (' + str(round(now - started)) + 's)', file=sys.stderr, flush=True)
                beat = now
            for key, _ in selector.select(timeout=0.2):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == 'stderr':
                    text = scrub(chunk.decode('utf-8', errors='replace'))
                    files['stderr'].write(text)
                    files['stderr'].flush()
                    stderr_tail = (stderr_tail + text)[-8000:]
                    continue
                # Raw trace is captured independently of adapter health.
                files['trace'].write(chunk)
                files['trace'].flush()
                adapter.stdin.write(chunk)
                adapter.stdin.flush()
                pending += chunk
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    try:
                        event = json.loads(line)
                        kind = event.get('type', 'unknown')
                        if kind == 'route':
                            route_metadata.update({k:event[k] for k in ['requestedModel','resolvedModel','endpoint'] if k in event})
                        if kind == 'model_reported':
                            route_metadata['reportedModel'] = event.get('model')
                        last = dict(type=kind, elapsed_seconds=round(now - started, 2))
                        emit('provider_event', type=kind)
                        if kind in ('text', 'thought', 'assistant', 'reasoning_progress') or kind.startswith('item.'):
                            if first is None:
                                first = now - started
                                emit('first_model_output', elapsed_seconds=round(first, 2))
                    except (ValueError, AttributeError):
                        emit('provider_event', type='malformed')
        selector.close()
        if reason in ('watcher_initialization_failed',):
            reason = 'provider_exited'
        if reason == 'provider_exited':
            try:
                provider.wait(timeout=2)
            except subprocess.TimeoutExpired:
                reason = 'provider_not_quiescent'
        drain(provider)
        adapter.stdin.close()
        try:
            adapter.wait(timeout=10)
        except subprocess.TimeoutExpired:
            drain(adapter)
        stream_path = out / 'stream-result.json'
        if stream_path.exists():
            stream_result = json.loads(stream_path.read_text())
        if reason == 'provider_exited':
            if provider.returncode == 0 and adapter.returncode == 0 and stream_result.get('complete') and (out/'trace.jsonl').stat().st_size > 0:
                status, reason = 'complete', 'completed'
            else:
                status = 'failed'
                reason = ('missing_trace' if (out/'trace.jsonl').stat().st_size == 0 else stream_result.get('reason')) or 'provider_exit_' + str(provider.returncode)
                if 'max_tokens_truncation' in stderr_tail:
                    reason = 'max_tokens_truncation'
    except Exception as error:
        reason = 'watcher_error_' + type(error).__name__
    finally:
        remaining = (drain(provider) or []) + (drain(adapter) or [])
        if remaining:
            status, reason = 'failed', 'owned_children_not_drained'
        if status != 'complete':
            artifact = out / 'artifact.md'
            if artifact.exists():
                artifact.replace(out / 'partial.md')
            artifact.write_text('# Consultation incomplete\n\nStatus: ' + status + '\n\nReason: ' + reason + '\n\nSee result.json, partial.md (if present), trace.jsonl, and stderr.log.\n')
            (out / 'summary.md').write_text('INCOMPLETE: ' + status + ' — ' + reason + '\n')
        import hashlib
        hashes = {n: hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ['trace.jsonl','artifact.md','summary.md'] if (out/n).is_file()}
        runtime_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).resolve().parent.iterdir() if p.suffix in ('.py','.ts','.sh')}
        result = dict(runtime_sha256=runtime_hashes, artifact_sha256=hashes, schemaVersion=1, run_id=run_id, status=status, reason=reason,
                      requested_model=args.model, transport=args.transport, route=route_metadata,
                      skill_root=os.environ.get('ASK_CANONICAL_SKILL_ROOT',str(Path(__file__).resolve().parent.parent)),
                      provider_exit=provider.returncode if provider else None,
                      adapter_exit=adapter.returncode if adapter else None,
                      stream=stream_result, elapsed_seconds=round(time.monotonic() - started, 2),
                      first_model_output_seconds=first, last_provider_event=last,
                      artifacts={name: str(out / name) for name in ['trace.jsonl', 'status.jsonl', 'stderr.log', 'artifact.md', 'summary.md']})
        tmp = out / 'result.json.tmp'
        tmp.write_text(json.dumps(result, indent=2) + '\n')
        os.chmod(tmp, 0o600)
        tmp.replace(out / 'result.json')
        if files.get('status'):
            emit('terminal', status=status, reason=reason)
        for f in files.values():
            f.close()
        print('watcher: ' + status + ' — ' + reason, file=sys.stderr, flush=True)
    return 0 if status == 'complete' else 2


if __name__ == '__main__':
    sys.exit(main())
