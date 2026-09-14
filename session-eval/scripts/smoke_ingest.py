#!/usr/bin/env python3
"""Run the portable ingest CLI against synthetic five-harness acceptance cases.

This is an executable smoke scenario, not a replacement for downstream checks
or report tests.  It creates all inputs in a temporary directory, invokes the
actual ``ingest.py`` command, and prints a machine-readable result.
"""

from __future__ import annotations

import json
import os
import hashlib
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).with_name("ingest.py")
EVALUATE = Path(__file__).with_name("evaluate.py")
SECRET = "SMOKE_SECRET_7f4c9e"
MARKUP = "<script>alert('smoke')</script>"


def write_jsonl(path: Path, rows: list[Any], malformed: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if isinstance(row, str):
                handle.write(row + "\n")
            else:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        if malformed:
            handle.write("{not-json\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_grok_dir(path: Path, files: dict[str, Any]) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        target = path / name
        if payload is None:
            write_text(target, "")
        elif isinstance(payload, list):
            write_jsonl(target, payload)
        elif isinstance(payload, (dict, list)):
            write_text(target, json.dumps(payload))
        else:
            write_text(target, str(payload))
    return path


def invoke(
    out: Path,
    paths: list[Path],
    harnesses: list[str],
    skill_roots: list[Path] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    command = [sys.executable, str(SCRIPT), "--since", "all", "--out", str(out)]
    for harness in harnesses:
        command.extend(["--harness", harness])
    for path in paths:
        command.extend(["--path", str(path)])
    for skill_root in skill_roots or []:
        command.extend(["--skill-root", str(skill_root)])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"CLI failed ({result.returncode}): {result.stderr.strip()}")
    try:
        summary = json.loads(result.stdout)
        receipt = json.loads(Path(summary["receipt"]).read_text(encoding="utf-8"))
    except (ValueError, OSError, KeyError) as exc:
        raise AssertionError(f"CLI did not emit a readable receipt: {result.stdout!r}") from exc
    return summary, receipt


def runs_by_harness(receipt: dict[str, Any], harness: str) -> list[dict[str, Any]]:
    return [run for run in receipt.get("runs", []) if run.get("harness") == harness]


def one_run(receipt: dict[str, Any], harness: str, native_id: str | None = None) -> dict[str, Any]:
    candidates = runs_by_harness(receipt, harness)
    if native_id is not None:
        candidates = [run for run in candidates if run.get("native_identity", {}).get("id") == native_id]
    if len(candidates) != 1:
        raise AssertionError(f"expected one {harness} run {native_id!r}, got {len(candidates)}")
    return candidates[0]


def omp_rows(session_id: str) -> list[Any]:
    return [
        {"type": "session", "version": 3, "id": session_id, "timestamp": "2026-09-13T10:03:00Z"},
        {
            "type": "message",
            "id": f"{session_id}-message",
            "message": {
                "role": "assistant",
                "content": [{"type": "toolCall", "id": f"{session_id}-call", "name": "shell", "arguments": {"cmd": "true"}}],
            },
        },
        {
            "type": "message",
            "id": f"{session_id}-result",
            "message": {"role": "toolResult", "toolCallId": f"{session_id}-call", "isError": False, "content": "ok"},
        },
        {"type": "custom", "customType": "session_end", "timestamp": "2026-09-13T10:03:02Z"},
    ]


def snapshot_path(out: Path, index: int, item: dict[str, Any]) -> Path:
    path = str(item.get("path") or "")
    role = str(item.get("role") or "primary")
    digest = str(item.get("sha256") or "")
    basename = Path(path).name or "source"
    token = hashlib.sha256(f"{path}:{role}".encode("utf-8")).hexdigest()[:12]
    return out / ".private" / "snapshots" / digest / f"{index:03d}-{token}-{basename}"


def invoke_evaluate(receipt_path: Path, out: Path) -> dict[str, Any]:
    command = [sys.executable, str(EVALUATE), "--receipt", str(receipt_path), "--out", str(out)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"evaluate failed ({result.returncode}): {result.stderr.strip()}")
    exported = out / "receipt.json"
    if not exported.is_file():
        raise AssertionError(f"evaluate did not write receipt: {result.stdout!r} {result.stderr!r}")
    return json.loads(exported.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="session-eval-smoke-") as temporary:
        root = Path(temporary)
        claude = root / "claude" / "session.jsonl"
        codex = root / "codex" / "rollout-001.jsonl"
        pi = root / "pi" / "session.jsonl"
        omp_dir = root / "omp"
        omp_ended = omp_dir / "ended.jsonl"
        omp_unpaired = omp_dir / "unpaired.jsonl"
        omp_live = omp_dir / "live.jsonl"
        grok = root / "grok" / "session-1"

        write_jsonl(
            claude,
            [
                {
                    "sessionId": "claude-1",
                    "timestamp": "2026-09-13T10:00:00Z",
                    "cwd": str(root),
                    "type": "assistant",
                    "future_schema": {"secret": SECRET},
                    "message": {
                        "id": "claude-message-1",
                        "role": "assistant",
                        "model": "claude-test",
                        "usage": {"input_tokens": 2, "output_tokens": 3},
                        "content": [{"type": "tool_use", "id": "claude-call-1", "name": "Bash", "input": {"secret": SECRET}}],
                    },
                },
                {
                    "sessionId": "claude-1",
                    "timestamp": "2026-09-13T10:00:01Z",
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": "claude-call-1", "is_error": False, "content": MARKUP}],
                    },
                },
                {
                    "sessionId": "claude-1",
                    "timestamp": "2026-09-13T10:00:02Z",
                    "type": "result",
                    "result": MARKUP,
                    "total_cost_usd": 0.12,
                },
                "{malformed-claude",
            ],
        )
        write_jsonl(
            codex,
            [
                {
                    "timestamp": "2026-09-13T10:01:00Z",
                    "ordinal": 1,
                    "type": "session_meta",
                    "payload": {
                        "session_id": "codex-1",
                        "cwd": str(root),
                        "parent_thread_id": "parent-thread",
                        "children": ["codex-child"],
                        "attempt": {"id": "attempt-1", "number": 2},
                        "continuation_of": "codex-previous",
                    },
                },
                {
                    "timestamp": "2026-09-13T10:01:01Z",
                    "ordinal": 2,
                    "type": "response_item",
                    "payload": {"type": "message", "id": "codex-message", "role": "assistant", "content": []},
                },
                {
                    "timestamp": "2026-09-13T10:01:02Z",
                    "ordinal": 3,
                    "type": "response_item",
                    "payload": {"type": "custom_tool_call", "id": "codex-item", "call_id": "codex-call", "name": "shell", "parentId": "parent-turn", "input": {"secret": SECRET}},
                },
                {
                    "timestamp": "2026-09-13T10:01:03Z",
                    "ordinal": 4,
                    "type": "response_item",
                    "payload": {"type": "custom_tool_call_output", "call_id": "codex-call", "is_error": False, "output": MARKUP},
                },
                {
                    "timestamp": "2026-09-13T10:01:04Z",
                    "ordinal": 5,
                    "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 10, "output_tokens": 4}}},
                },
                {
                    "timestamp": "2026-09-13T10:01:05Z",
                    "ordinal": 6,
                    "type": "event_msg",
                    "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 10, "output_tokens": 4}}},
                },
                {
                    "timestamp": "2026-09-13T10:01:06Z",
                    "ordinal": 7,
                    "type": "event_msg",
                    "payload": {"type": "task_complete"},
                },
                "{malformed-codex",
            ],
        )
        write_jsonl(
            pi,
            [
                {"type": "session", "version": 3, "id": "pi-1", "timestamp": "2026-09-13T10:02:00Z", "cwd": str(root)},
                {"type": "model_change", "provider": "test", "modelId": "pi-model"},
                {
                    "type": "message",
                    "id": "pi-message",
                    "timestamp": "2026-09-13T10:02:01Z",
                    "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "pi-call", "name": "read", "arguments": {"secret": SECRET}}]},
                },
                {"type": "turn_completed", "timestamp": "2026-09-13T10:02:02Z"},
            ],
        )
        write_jsonl(
            omp_ended,
            [
                {"type": "session", "version": 3, "id": "omp-ended", "timestamp": "2026-09-13T10:03:00Z", "cwd": str(root)},
                {"type": "custom", "customType": "tool_execution_start", "data": {"toolCallId": "omp-call", "toolName": "shell", "startedAt": "2026-09-13T10:03:00Z", "args": {"secret": SECRET}}},
                {"type": "message", "id": "omp-message", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "omp-call", "name": "shell", "arguments": {"secret": SECRET}}]}},
                {"type": "message", "id": "omp-result", "message": {"role": "toolResult", "toolCallId": "omp-call", "isError": False, "content": MARKUP}},
                {"type": "custom", "customType": "session_end", "timestamp": "2026-09-13T10:03:02Z"},
            ],
        )
        write_jsonl(
            omp_unpaired,
            [
                {"type": "session", "version": 3, "id": "omp-unpaired", "timestamp": "2026-09-13T10:03:00Z", "cwd": str(root)},
                {"type": "message", "id": "omp-unpaired-message", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "omp-unpaired-call", "name": "shell", "arguments": {"secret": SECRET}}]}},
                {"type": "custom", "customType": "session_end", "timestamp": "2026-09-13T10:03:02Z"},
            ],
        )
        write_jsonl(
            omp_live,
            [
                {"type": "session", "version": 3, "id": "omp-live", "timestamp": "2026-09-13T10:04:00Z", "cwd": str(root)},
                {"type": "message", "id": "omp-live-message", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "omp-live-call", "name": "shell", "arguments": {"secret": SECRET}}]}},
                {"type": "custom", "customType": "live", "timestamp": "2026-09-13T10:04:01Z"},
            ],
        )
        grok.mkdir(parents=True)
        write_jsonl(
            grok / "chat_history.jsonl",
            [
                {"type": "assistant", "id": "grok-message", "content": MARKUP, "tool_calls": [{"id": "grok-call", "name": "shell", "arguments": {"secret": SECRET}}]},
                {"type": "tool_result", "tool_call_id": "grok-call", "is_error": False, "content": SECRET},
            ],
        )
        write_jsonl(
            grok / "events.jsonl",
            [
                {"type": "turn_started", "ts": "2026-09-13T10:05:00Z", "params": {"sessionId": "grok-primary", "turnId": "grok-turn", "modelId": "grok-model"}},
                {"type": "heartbeat", "ts": 1726221900},
            ],
        )
        write_jsonl(
            grok / "updates.jsonl",
            [
                {"timestamp": 1726221901, "method": "session/update", "params": {"sessionId": "grok-primary", "update": {"sessionUpdate": {"type": "tool_call", "toolCallId": "grok-update-call", "title": "shell", "turnId": "grok-turn"}}}},
                {"timestamp": 1726221902, "method": "session/update", "params": {"sessionId": "grok-primary", "update": {"sessionUpdate": {"type": "tool_call_update", "toolCallId": "grok-update-call", "status": "completed", "turnId": "grok-turn"}}}},
                {"timestamp": 1726221903, "method": "session/update", "params": {"sessionId": "grok-primary", "update": {"sessionUpdate": {"type": "turn_completed", "inputTokens": 5, "outputTokens": 2, "totalTokens": 7, "turnId": "grok-turn"}}}, "_meta": {"totalTokens": 30}},
            ],
        )
        skill_root = root / "skills"
        skill_file = skill_root / "demo" / "SKILL.md"
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text("name: demo\nversion: current\n", encoding="utf-8")
        (grok / "summary.json").write_text(
            json.dumps({"info": {"id": "grok-stale", "cwd": str(root), "current_model_id": "grok-stale-model", "created_at": "2026-09-13T10:05:00Z", "ended_at": "2026-09-13T10:05:03Z"}, "session_summary": MARKUP}),
            encoding="utf-8",
        )
        (grok / "usage.json").write_text(
            json.dumps({"sessionId": "grok-stale", "session": {"inputTokens": 999, "outputTokens": 999, "totalTokens": 999}, "turns": [{"inputTokens": 999, "outputTokens": 999}]}),
            encoding="utf-8",
        )
        (grok / "prompt_context.json").write_text(
            json.dumps({"skills": [{"path": "demo/SKILL.md", "digest": "sha256:historical"}]}),
            encoding="utf-8",
        )

        output = root / "out"
        _, first = invoke(
            output,
            [root / "claude", root / "codex", root / "pi", omp_dir, grok],
            list(("claude", "codex", "pi", "omp", "grok")),
            [skill_root],
        )
        _, repeated = invoke(
            output,
            [root / "claude", root / "codex", root / "pi", omp_dir, grok],
            list(("claude", "codex", "pi", "omp", "grok")),
            [skill_root],
        )


        assert first["schema"] == "styrir-session-eval/v0"
        assert first["harnesses_found"] == ["claude", "codex", "pi", "omp", "grok"]
        assert first["coverage"]["malformed_count"] >= 2
        assert first["coverage"]["sessions_ingested"] == 7
        assert one_run(first, "claude", "claude-1")["lifecycle"]["state"] == "terminal"
        assert one_run(first, "claude", "claude-1")["cost_usd"] == 0.12
        assert one_run(first, "codex", "codex-1")["tokens"]["input"] == 10
        assert one_run(first, "codex", "codex-1")["tokens"]["output"] == 4
        assert one_run(first, "codex", "codex-1")["tokens"]["total"] == 14
        assert one_run(first, "codex", "codex-1")["lineage"]["children"] == ["codex-child"]
        assert one_run(first, "codex", "codex-1")["lineage"]["attempt"] == {"id": "attempt-1", "number": 2}
        assert one_run(first, "codex", "codex-1")["lineage"]["continuation_of"] == "codex-previous"
        codex_run = one_run(first, "codex", "codex-1")
        codex_kinds = [item["kind"] for item in codex_run["lifecycle"]["evidence"]]
        assert "type:task_complete" in codex_kinds
        assert not any("[REDACTED]" in str(kind) for kind in codex_kinds)
        assert one_run(first, "pi", "pi-1")["lifecycle"]["state"] == "unknown"
        assert one_run(first, "pi", "pi-1")["tokens"]["total"] == "unknown"
        ended = one_run(first, "omp", "omp-ended")
        unpaired = one_run(first, "omp", "omp-unpaired")
        live = one_run(first, "omp", "omp-live")
        assert ended["lifecycle"]["state"] == "terminal"
        ended_calls = [call for turn in ended["turns"] for call in turn["tool_calls"]]
        assert len(ended_calls) == 1 and ended_calls[0]["id"] == "omp-call" and ended_calls[0]["status"] == "ok"
        assert ended["source_path"] == str(omp_ended.resolve())
        assert ended["source_snapshot"]["files"][0]["path"] == str(omp_ended.resolve())
        assert not ended["checks"]
        assert unpaired["lifecycle"]["state"] == "terminal"
        pairing = next(check for check in unpaired["checks"] if check["id"] == "tool.unpaired")
        assert pairing["kind"] == "code" and pairing["class"] == "hard_fail" and pairing["channel"] == "behavior"
        assert pairing["observed"] == "unpaired_after_explicit_end"
        assert pairing["error"] is None
        assert pairing["evidence"][0]["event_range"]["start_line"] == 2
        assert live["lifecycle"]["state"] == "live"
        assert not live["checks"]
        grok_run = one_run(first, "grok", "grok-primary")
        assert grok_run["source_path"] == str((grok / "chat_history.jsonl").resolve())
        assert grok_run["model"] == "grok-model"
        assert grok_run["tokens"]["total"] == 30
        grok_calls = [call for turn in grok_run["turns"] for call in turn["tool_calls"]]
        assert any(call["id"] == "grok-update-call" and call["status"] == "ok" for call in grok_calls)
        assert grok_run["lifecycle"]["state"] == "live"
        assert len(first["coverage"]["coverage_gaps"]) >= 2
        skill = next(item for item in first["skills"] if item["name"] == "demo")
        assert skill["digest"] == "sha256:historical"
        assert skill["current_on_disk_digest"] != skill["digest"]
        assert skill["digest_relation"] == "historical_differs_from_current"

        grok_cases = root / "grok-cases"
        stale_dir = write_grok_dir(
            grok_cases / "stale-sidecars",
            {
                "chat_history.jsonl": None,
                "events.jsonl": [{"type": "turn_started", "params": {"sessionId": "primary-A"}}],
                "updates.jsonl": None,
                "summary.json": {"info": {"id": "stale-B", "ended_at": "2026-09-13T10:00:00Z"}},
                "usage.json": {"sessionId": "stale-B", "session": {"totalTokens": 999}},
            },
        )
        _, stale_after = invoke(root / "round2-after-stale", [stale_dir], ["grok"])
        stale_run = one_run(stale_after, "grok", "primary-A")
        assert stale_run["lifecycle"]["state"] == "unknown"
        assert stale_run["tokens"]["total"] == "unknown"
        assert len(stale_after["coverage"]["coverage_gaps"]) >= 2
        overlap_dir = write_grok_dir(
            grok_cases / "overlap",
            {
                "chat_history.jsonl": [
                    {"type": "assistant", "tool_calls": [{"id": "X", "name": "read", "arguments": {}}]},
                    {"type": "tool_result", "tool_call_id": "X", "is_error": False},
                ],
                "events.jsonl": [{"type": "turn_started", "params": {"sessionId": "primary-A"}}],
                "updates.jsonl": [
                    {"method": "session/update", "params": {"sessionId": "primary-A", "update": {"sessionUpdate": {"type": "tool_call", "toolCallId": "X", "title": "read"}}}},
                    {"method": "session/update", "params": {"sessionId": "primary-A", "update": {"sessionUpdate": {"type": "tool_call_update", "toolCallId": "X", "status": "completed"}}}},
                ],
            },
        )
        _, overlap_after = invoke(root / "round2-after-overlap", [overlap_dir], ["grok"])
        overlap_run = one_run(overlap_after, "grok", "primary-A")
        overlap_calls = [call for turn in overlap_run["turns"] for call in turn["tool_calls"]]
        assert len(overlap_calls) == 1 and overlap_calls[0]["id"] == "X" and overlap_calls[0]["status"] == "ok"
        assert len(overlap_calls[0]["evidence"]) >= 4 and not overlap_run["checks"]
        order_dir = write_grok_dir(
            grok_cases / "result-before-call",
            {
                "chat_history.jsonl": [{"type": "tool_result", "tool_call_id": "X", "is_error": False}],
                "events.jsonl": [{"type": "turn_started", "params": {"sessionId": "primary-A"}}],
                "updates.jsonl": [{"method": "session/update", "params": {"sessionId": "primary-A", "update": {"sessionUpdate": {"type": "tool_call", "toolCallId": "X", "title": "read"}}}}],
                "summary.json": {"info": {"id": "primary-A", "ended_at": "2026-09-13T10:00:00Z"}},
            },
        )
        _, order_after = invoke(root / "round2-after-order", [order_dir], ["grok"])
        order_run = one_run(order_after, "grok", "primary-A")
        order_calls = [call for turn in order_run["turns"] for call in turn["tool_calls"]]
        assert len(order_calls) == 1 and order_calls[0]["id"] == "X" and order_calls[0]["status"] == "ok"
        assert not order_run["checks"] and not any(turn["errors"] for turn in order_run["turns"])
        summary_cohort = write_grok_dir(
            grok_cases / "summary-cohort-conflict",
            {
                "chat_history.jsonl": [{"type": "user", "content": "Synthetic request"}],
                "events.jsonl": None,
                "updates.jsonl": None,
                "summary.json": {"info": {"id": "summary-A"}},
                "usage.json": {"sessionId": "usage-B", "session": {"totalTokens": 888}},
            },
        )
        _, summary_cohort_after = invoke(root / "round3-after-summary-cohort", [summary_cohort], ["grok"])
        summary_cohort_run = one_run(summary_cohort_after, "grok", "summary-A")
        assert summary_cohort_run["tokens"]["total"] == "unknown"
        assert not summary_cohort_run["usage_provenance"]
        assert any(
            gap.get("observed_identity") == ["usage-B"]
            and gap.get("reason") == "grok sidecar identity mismatch; sidecar ignored"
            for gap in summary_cohort_after["coverage"]["coverage_gaps"]
        )
        primary_cohort = write_grok_dir(
            grok_cases / "primary-cohort-conflict",
            {
                "chat_history.jsonl": None,
                "events.jsonl": [{"type": "turn_started", "params": {"sessionId": "primary-A"}}],
                "updates.jsonl": [{"method": "session/update", "params": {"sessionId": "primary-B", "update": {"sessionUpdate": {"type": "tool_call", "toolCallId": "B-call", "title": "read"}}}}],
            },
        )
        _, primary_cohort_after = invoke(root / "round3-after-primary-cohort", [primary_cohort], ["grok"])
        primary_cohort_runs = runs_by_harness(primary_cohort_after, "grok")
        assert len(primary_cohort_runs) == 1
        primary_cohort_run = primary_cohort_runs[0]
        assert primary_cohort_run["native_identity"] == "unknown"
        assert not primary_cohort_run["turns"]
        assert any(
            gap.get("observed_identity") == ["primary-A", "primary-B"]
            and "primary identity conflict" in gap.get("reason", "")
            for gap in primary_cohort_after["coverage"]["coverage_gaps"]
        )
        no_summary_conflict = write_grok_dir(
            grok_cases / "no-summary-sidecar-conflict",
            {
                "chat_history.jsonl": [{"type": "user", "content": "Synthetic no-summary conflict"}],
                "signals.json": {"sessionId": "sidecar-B", "status": "terminal"},
                "usage.json": {"sessionId": "sidecar-A", "session": {"inputTokens": 100, "totalTokens": 111}},
            },
        )
        _, no_summary_conflict_after = invoke(root / "round3-after-no-summary-conflict", [no_summary_conflict], ["grok"])
        no_summary_conflict_run = runs_by_harness(no_summary_conflict_after, "grok")[0]
        assert no_summary_conflict_run["native_identity"] == "unknown"
        assert no_summary_conflict_run["tokens"]["total"] == "unknown"
        assert not no_summary_conflict_run["usage_provenance"]
        assert no_summary_conflict_run["lifecycle"]["state"] == "unknown"
        assert any(
            gap.get("observed_identity") == ["sidecar-A", "sidecar-B"]
            and "sidecar identity conflict" in gap.get("reason", "")
            for gap in no_summary_conflict_after["coverage"]["coverage_gaps"]
        )
        no_summary_consistent = write_grok_dir(
            grok_cases / "no-summary-sidecar-consistent",
            {
                "chat_history.jsonl": [{"type": "user", "content": "Synthetic no-summary consistent"}],
                "signals.json": {"sessionId": "sidecar-A", "status": "live"},
                "usage.json": {"sessionId": "sidecar-A", "session": {"inputTokens": 100, "totalTokens": 111}},
            },
        )
        _, no_summary_consistent_after = invoke(root / "round3-after-no-summary-consistent", [no_summary_consistent], ["grok"])
        no_summary_consistent_run = one_run(no_summary_consistent_after, "grok", "sidecar-A")
        assert no_summary_consistent_run["tokens"]["input"] == 100
        assert no_summary_consistent_run["tokens"]["total"] == 111
        assert no_summary_consistent_run["lifecycle"]["state"] == "live"
        assert not no_summary_consistent_after["coverage"]["coverage_gaps"]


        snapshots_first = {run["id"]: run["source_snapshot"]["sha256"] for run in first["runs"]}
        snapshots_repeated = {run["id"]: run["source_snapshot"]["sha256"] for run in repeated["runs"]}
        assert snapshots_first == snapshots_repeated

        exported = (output / "receipt.json").read_text(encoding="utf-8")
        assert SECRET not in exported
        assert MARKUP not in exported
        receipt_before_change = exported
        private = output / ".private" / "unknown-fields.json"
        assert private.exists() and stat.S_IMODE(private.stat().st_mode) & 0o077 == 0
        private_data = json.loads(private.read_text(encoding="utf-8"))
        assert private_data["runs"] and any(run["unknown_fields"] for run in private_data["runs"])
        snapshot_dir = output / ".private" / "snapshots" / first["runs"][0]["source_snapshot"]["files"][0]["sha256"]
        assert any(path.is_file() and path.read_bytes() == claude.read_bytes() for path in snapshot_dir.rglob("*"))

        changed = claude.read_text(encoding="utf-8") + json.dumps({"sessionId": "claude-1", "type": "assistant", "message": {"role": "assistant", "content": []}}) + "\n"
        claude.write_text(changed, encoding="utf-8")
        _, changed_receipt = invoke(output, [claude], ["claude"])
        changed_run = one_run(changed_receipt, "claude", "claude-1")
        _, changed_repeat = invoke(output, [claude], ["claude"])
        repeated_changed_run = one_run(changed_repeat, "claude", "claude-1")
        assert repeated_changed_run["source_snapshot"]["sha256"] == changed_run["source_snapshot"]["sha256"]
        assert changed_run["source_snapshot"]["sha256"] != snapshots_first["claude:claude-1"]
        assert changed_run["id"] == "claude:claude-1"
        assert (output / "receipt.json").read_text(encoding="utf-8") == receipt_before_change
        run_receipts = list((output / "run_receipts").glob("claude_*.json"))
        assert len(run_receipts) >= 2

        _, missing = invoke(output / "missing", [claude], ["omp"])
        assert missing["coverage"]["missing_requested_inputs"]
        assert missing["coverage"]["missing_requested_inputs"][0]["harness"] == "omp"
        escape = root / "escape"
        escape.mkdir()
        unsafe_out = root / "unsafe-out"
        unsafe_out.symlink_to(escape, target_is_directory=True)
        blocked = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--since",
                "all",
                "--harness",
                "claude",
                "--path",
                str(claude),
                "--out",
                str(unsafe_out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert blocked.returncode != 0
        assert not (escape / ".private").exists()
        nested_escape = root / "nested-escape"
        nested_escape.mkdir()
        nested_out = root / "nested-out"
        nested_out.mkdir()
        (nested_out / ".private").symlink_to(nested_escape, target_is_directory=True)
        blocked_nested = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--since",
                "all",
                "--harness",
                "claude",
                "--path",
                str(claude),
                "--out",
                str(nested_out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert blocked_nested.returncode != 0
        assert not any(nested_escape.iterdir())

        key_order = omp_dir / "loop-key-order.jsonl"
        write_jsonl(
            key_order,
            [
                {"type": "session", "version": 3, "id": "terminal-reset", "timestamp": "2026-09-14T03:00:00Z"},
                {"type": "message", "id": "msg-0", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "call-0", "name": "read", "arguments": {"path": "synthetic.txt"}}]}},
                {"type": "message", "id": "res-0", "message": {"role": "toolResult", "toolCallId": "call-0", "isError": True, "content": "synthetic missing file"}},
                {"type": "message", "id": "msg-1", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "call-1", "name": "read", "arguments": {"path": "synthetic.txt"}}]}},
                {"type": "message", "id": "res-1", "message": {"role": "toolResult", "toolCallId": "call-1", "isError": True, "content": "synthetic missing file"}},
                {"type": "message", "id": "msg-2", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "call-2", "name": "read", "arguments": {"path": "synthetic.txt"}}]}},
                {"type": "message", "id": "res-2", "message": {"role": "toolResult", "toolCallId": "call-2", "isError": True, "content": "synthetic missing file"}},
                {"type": "custom", "customType": "session_end", "timestamp": "2026-09-14T03:01:00Z"},
                {"type": "message", "id": "msg-3", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "call-3", "name": "read", "arguments": {"path": "synthetic.txt"}}]}},
                {"type": "message", "id": "res-3", "message": {"role": "toolResult", "toolCallId": "call-3", "isError": True, "content": "synthetic missing file"}},
            ],
        )
        key_out = root / "key-order-out"
        key_summary, key_receipt = invoke(key_out, [key_order], ["omp"])
        key_run = one_run(key_receipt, "omp", "terminal-reset")
        key_public = (key_out / "receipt.json").read_text(encoding="utf-8")
        assert "key-order" not in key_public
        assert "[REDACTED]" in key_run["source_path"]
        assert key_run["source_path"] != str(key_order.resolve())
        key_files = key_run["source_snapshot"]["files"]
        assert len(key_files) == 1 and key_files[0]["role"] == "primary"
        key_snap = snapshot_path(key_out, 0, key_files[0])
        assert key_snap.is_file() and key_snap.read_bytes() == key_order.read_bytes()
        for turn in key_run["turns"]:
            assert turn["source_path"] == key_run["source_path"]
            for call in turn["tool_calls"]:
                assert call["source_path"] == key_run["source_path"]
                if call.get("result_source_path"):
                    assert call["result_source_path"] == key_run["source_path"]
        for item in key_run["lifecycle"]["evidence"]:
            assert item["source_path"] == key_run["source_path"]
        key_eval = invoke_evaluate(Path(key_summary["receipt"]), root / "key-order-eval")
        key_eval_run = one_run(key_eval, "omp", "terminal-reset")
        parse_check = next(check for check in key_eval_run["checks"] if check["id"] == "ingest.parse_error")
        assert parse_check["status"] == "pass"
        assert not any(
            "unreadable frozen snapshot" in str(err)
            for err in (key_eval.get("coverage") or {}).get("evaluation_errors") or []
        )

        collision_dir = root / "collision" / "omp"
        collision_a = collision_dir / "loop-key-order.jsonl"
        collision_b = collision_dir / "loop-key-other.jsonl"
        write_jsonl(collision_a, omp_rows("collision-a"))
        write_jsonl(collision_b, omp_rows("collision-b"))
        collision_out = root / "collision-out"
        _, collision_receipt = invoke(collision_out, [collision_dir], ["omp"])
        collision_runs = runs_by_harness(collision_receipt, "omp")
        assert len(collision_runs) == 2
        collision_paths = {run["id"]: run["source_path"] for run in collision_runs}
        assert len(set(collision_paths.values())) == 2
        collision_public = (collision_out / "receipt.json").read_text(encoding="utf-8")
        assert "key-order" not in collision_public and "key-other" not in collision_public
        for run in collision_runs:
            item = run["source_snapshot"]["files"][0]
            snap = snapshot_path(collision_out, 0, item)
            native = run["native_identity"]["id"]
            source = collision_a if native == "collision-a" else collision_b
            assert snap.is_file() and snap.read_bytes() == source.read_bytes()
            assert item["role"] == "primary"

        long_dir = root / "long" / "omp"
        long_prefix = "N" * 240
        long_a = long_dir / f"{long_prefix}ONE.jsonl"
        long_b = long_dir / f"{long_prefix}TWO.jsonl"
        write_jsonl(long_a, omp_rows("long-a"))
        write_jsonl(long_b, omp_rows("long-b"))
        long_out = root / "long-out"
        _, long_receipt = invoke(long_out, [long_dir], ["omp"])
        long_runs = runs_by_harness(long_receipt, "omp")
        assert len(long_runs) == 2
        long_paths = [run["source_path"] for run in long_runs]
        assert len(set(long_paths)) == 2
        for run in long_runs:
            item = run["source_snapshot"]["files"][0]
            snap = snapshot_path(long_out, 0, item)
            native = run["native_identity"]["id"]
            source = long_a if native == "long-a" else long_b
            assert snap.is_file() and snap.read_bytes() == source.read_bytes()

        sidecar_dir = root / "loop-key-order-session"
        sidecar_dir.mkdir(parents=True)
        write_jsonl(
            sidecar_dir / "chat_history.jsonl",
            [
                {"type": "assistant", "id": "grok-redact-message", "content": "ok", "tool_calls": [{"id": "grok-redact-call", "name": "shell", "arguments": {"cmd": "true"}}]},
                {"type": "tool_result", "tool_call_id": "grok-redact-call", "is_error": False, "content": "ok"},
            ],
        )
        write_jsonl(
            sidecar_dir / "events.jsonl",
            [{"type": "turn_started", "ts": "2026-09-13T10:05:00Z", "params": {"sessionId": "grok-redact", "turnId": "t1", "modelId": "grok-model"}}],
        )
        write_jsonl(
            sidecar_dir / "updates.jsonl",
            [{"timestamp": 1726221903, "method": "session/update", "params": {"sessionId": "grok-redact", "update": {"sessionUpdate": {"type": "turn_completed", "inputTokens": 5, "outputTokens": 2, "totalTokens": 7, "turnId": "t1"}}}, "_meta": {"totalTokens": 7}}],
        )
        (sidecar_dir / "summary.json").write_text(json.dumps({"info": {"id": "grok-redact", "cwd": str(root), "current_model_id": "grok-model", "created_at": "2026-09-13T10:05:00Z"}}), encoding="utf-8")
        (sidecar_dir / "usage.json").write_text(json.dumps({"sessionId": "grok-redact", "session": {"inputTokens": 5, "outputTokens": 2, "totalTokens": 7}}), encoding="utf-8")
        sidecar_out = root / "sidecar-out"
        sidecar_summary, sidecar_receipt = invoke(sidecar_out, [sidecar_dir], ["grok"])
        sidecar_run = one_run(sidecar_receipt, "grok", "grok-redact")
        sidecar_public = (sidecar_out / "receipt.json").read_text(encoding="utf-8")
        assert "key-order" not in sidecar_public
        roles = {item["role"] for item in sidecar_run["source_snapshot"]["files"]}
        assert "primary" in roles and "sidecar" in roles
        exported_paths = [item["path"] for item in sidecar_run["source_snapshot"]["files"]]
        assert len(exported_paths) == len(set(exported_paths))
        raw_by_digest = {
            hashlib.sha256((sidecar_dir / name).read_bytes()).hexdigest(): sidecar_dir / name
            for name in ("chat_history.jsonl", "events.jsonl", "updates.jsonl", "summary.json", "usage.json")
        }
        for index, item in enumerate(sidecar_run["source_snapshot"]["files"]):
            snap = snapshot_path(sidecar_out, index, item)
            assert snap.is_file()
            assert snap.read_bytes() == raw_by_digest[item["sha256"]].read_bytes()
            assert item["path"].endswith(raw_by_digest[item["sha256"]].suffix)
        sidecar_eval = invoke_evaluate(Path(sidecar_summary["receipt"]), root / "sidecar-eval")
        sidecar_eval_run = one_run(sidecar_eval, "grok", "grok-redact")
        sidecar_parse = next(check for check in sidecar_eval_run["checks"] if check["id"] == "ingest.parse_error")
        assert sidecar_parse["status"] == "pass"
        assert not any(
            "unreadable frozen snapshot" in str(err)
            for err in (sidecar_eval.get("coverage") or {}).get("evaluation_errors") or []
        )

        assert "key-order" not in blocked.stderr and "key-order" not in blocked_nested.stderr

        secret_title = "sk_completeABCDEF"
        secret_claude = root / "secret-label" / "session.jsonl"
        write_jsonl(
            secret_claude,
            [
                {
                    "sessionId": "claude-secret-label",
                    "timestamp": "2026-09-13T10:00:00Z",
                    "type": "assistant",
                    "title": secret_title,
                    "message": {"id": "secret-message", "role": "assistant", "content": []},
                },
                {
                    "sessionId": "claude-secret-label",
                    "timestamp": "2026-09-13T10:00:01Z",
                    "type": "result",
                    "result": "ok",
                },
            ],
        )
        secret_out = root / "secret-label-out"
        _, secret_receipt = invoke(secret_out, [secret_claude], ["claude"])
        secret_run = one_run(secret_receipt, "claude", "claude-secret-label")
        secret_public = (secret_out / "receipt.json").read_text(encoding="utf-8")
        assert secret_title not in secret_public
        assert "[REDACTED]" in secret_run["display_name"]
        secret_kinds = [item["kind"] for item in secret_run["lifecycle"]["evidence"]]
        assert "type:result" in secret_kinds
        assert not any("[REDACTED]" in str(kind) for kind in secret_kinds)

        def canonical(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        raw_manifest = [
            {
                "path": str(key_order.resolve()),
                "role": "primary",
                "sha256": hashlib.sha256(key_order.read_bytes()).hexdigest(),
            }
        ]
        raw_hash = hashlib.sha256(canonical(raw_manifest).encode("utf-8")).hexdigest()
        assert key_run["source_snapshot"]["sha256"] == raw_hash
        public_hash = hashlib.sha256(canonical(key_run["source_snapshot"]["files"]).encode("utf-8")).hexdigest()
        assert public_hash != raw_hash

        look_dir = root / "alias-omp" / "omp"
        ordinary_alias = look_dir / "plain.jsonl"
        lookalike = look_dir / "plain#0123456789ab.jsonl"
        write_jsonl(ordinary_alias, omp_rows("alias-plain"))
        write_jsonl(lookalike, omp_rows("alias-lookalike"))
        _, alias_receipt = invoke(root / "alias-out", [look_dir], ["omp"])
        alias_runs = runs_by_harness(alias_receipt, "omp")
        assert len(alias_runs) == 2
        by_native = {run["native_identity"]["id"]: run for run in alias_runs}
        assert by_native["alias-plain"]["source_path"] == str(ordinary_alias.resolve())
        assert by_native["alias-lookalike"]["source_path"] != str(lookalike.resolve())
        assert len({run["source_path"] for run in alias_runs}) == 2

        def claude_anonymous(text: str) -> list[Any]:
            return [
                {"timestamp": "2026-09-13T10:00:00Z", "type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}},
                {"timestamp": "2026-09-13T10:00:01Z", "type": "result", "result": "ok"},
            ]

        missing_a = root / "missing-native-a" / "session.jsonl"
        missing_b = root / "missing-native-b" / "session.jsonl"
        write_jsonl(missing_a, claude_anonymous("aaa"))
        write_jsonl(missing_b, claude_anonymous("bbb"))
        _, missing_native = invoke(root / "missing-native-out", [missing_a, missing_b], ["claude"])
        missing_runs = runs_by_harness(missing_native, "claude")
        assert len(missing_runs) == 2
        missing_ids = {run["id"] for run in missing_runs}
        assert len(missing_ids) == 2
        assert all(":path:" in run["id"] for run in missing_runs)
        assert all(run["native_identity"] == "unknown" for run in missing_runs)
        _, missing_again = invoke(root / "missing-native-out2", [missing_a], ["claude"])
        again_run = runs_by_harness(missing_again, "claude")[0]
        assert again_run["id"] in missing_ids
        snap_a = again_run["source_snapshot"]["sha256"]

        write_jsonl(missing_a, claude_anonymous("aaa-changed"))
        _, missing_changed = invoke(root / "missing-native-out3", [missing_a], ["claude"])
        changed_anon = runs_by_harness(missing_changed, "claude")[0]
        assert changed_anon["id"] == again_run["id"]
        assert changed_anon["source_snapshot"]["sha256"] != snap_a

        _, wrong_claude_as_omp = invoke(root / "wrong-claude-as-omp", [missing_a, missing_b], ["omp"])
        assert wrong_claude_as_omp["coverage"]["missing_requested_inputs"]
        assert wrong_claude_as_omp["coverage"]["missing_requested_inputs"][0]["harness"] == "omp"
        assert not runs_by_harness(wrong_claude_as_omp, "omp")
        assert not runs_by_harness(wrong_claude_as_omp, "claude")

        def omp_anonymous(text: str) -> list[Any]:
            return [
                {
                    "type": "message",
                    "version": 3,
                    "timestamp": "2026-09-13T10:03:00Z",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
                },
                {"type": "custom", "customType": "session_end", "timestamp": "2026-09-13T10:03:02Z"},
            ]

        anon_omp_a = root / "anon-cred" / "sk_live_aaa.jsonl"
        anon_omp_b = root / "anon-cred" / "sk_live_bbb.jsonl"
        write_jsonl(anon_omp_a, omp_anonymous("aaa"))
        write_jsonl(anon_omp_b, omp_anonymous("bbb"))
        _, anon_omp = invoke(root / "anon-omp-out", [anon_omp_a, anon_omp_b], ["omp"])
        anon_omp_runs = runs_by_harness(anon_omp, "omp")
        assert len(anon_omp_runs) == 2
        anon_omp_ids = {run["id"] for run in anon_omp_runs}
        assert len(anon_omp_ids) == 2
        assert all(run["id"].startswith("omp:path:") for run in anon_omp_runs)
        assert all(run["native_identity"] == "unknown" for run in anon_omp_runs)
        _, wrong_omp_as_claude = invoke(root / "wrong-omp-as-claude", [anon_omp_a, anon_omp_b], ["claude"])
        assert wrong_omp_as_claude["coverage"]["missing_requested_inputs"]
        assert wrong_omp_as_claude["coverage"]["missing_requested_inputs"][0]["harness"] == "claude"
        assert not runs_by_harness(wrong_omp_as_claude, "claude")
        assert not runs_by_harness(wrong_omp_as_claude, "omp")




        result = {
            "status": "pass",
            "cases": [
                "five primary harness adapters",
                "malformed rows and unknown fields",
                "nested parent lineage",
                "terminal/live/unknown lifecycle and unpaired tools",
                "adapter-scoped lifecycle markers",
                "real Grok events/updates envelopes and primary identity",
                "Grok sidecar identity mismatch is a coverage gap",
                "Grok cross-stream overlap deduplication",
                "Grok result-before-call correlation",
                "Grok summary-selected identity rejects stale usage",
                "Grok conflicting primary identities are not merged",
                "Grok no-summary sidecar identity conflict leaves evidence unmerged",
                "Grok no-summary agreeing sidecars select identity",
                "OMP duplicate call observation merge",
                "Claude top-level terminal cost",
                "byte-bound private snapshots",
                "symlink-safe owner-only output",
                "repeat and changed-byte snapshots including B-to-B",
                "absent harness coverage gap",
                "usage deduplication and provenance",
                "historical/current skill digest separation",
                "redacted export with owner-only private state",
                "credential-like-path loop-key-order.jsonl ingest and evaluate",
                "path-redaction-collision distinct frozen bytes",
                "long-path truncated identities stay distinct",
                "ordinary unredacted source paths unchanged",
                "downstream evaluate opens redacted primary and sidecar snapshots",
                "private-guard symlink errors omit credential-like names",
                "codex type:task_complete lifecycle kind preserved",
                "untrusted sk_complete label redacts without a task_complete exception",
                "raw snapshot hash independent of public path labels",
                "alias-lookalike raw path does not collide with generated alias",
                "missing-native path-hash ids stay distinct and survive byte change",
                "clean-worktree synthetic grok fixtures without .styrir",
                "wrong requested harness on Claude files is missing_requested_inputs",
                "anonymous OMP credential-stem path-hash ids stay distinct",
                "wrong requested harness on OMP files is missing_requested_inputs",
            ],
            "runs": len(first["runs"]),
            "malformed": first["coverage"]["malformed_count"],
        }
        result["scenario_rows"] = [{"row": index + 1, "scenario": name} for index, name in enumerate(result["cases"])]
        result["original_ingest_rows"] = 37
        print(json.dumps(result, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
