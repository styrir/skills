#!/usr/bin/env python3
"""Run the portable ingest CLI against synthetic five-harness acceptance cases.

This is an executable smoke scenario, not a replacement for downstream checks
or report tests.  It creates all inputs in a temporary directory, invokes the
actual ``ingest.py`` command, and prints a machine-readable result.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).with_name("ingest.py")
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
        assert one_run(first, "pi", "pi-1")["lifecycle"]["state"] == "unknown"
        assert one_run(first, "pi", "pi-1")["tokens"]["total"] == "unknown"
        ended = one_run(first, "omp", "omp-ended")
        unpaired = one_run(first, "omp", "omp-unpaired")
        live = one_run(first, "omp", "omp-live")
        assert ended["lifecycle"]["state"] == "terminal"
        ended_calls = [call for turn in ended["turns"] for call in turn["tool_calls"]]
        assert len(ended_calls) == 1 and ended_calls[0]["id"] == "omp-call" and ended_calls[0]["status"] == "ok"
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

        retained = Path(__file__).resolve().parents[2] / ".styrir" / "runs" / "session-eval-implementation" / "skills-2ol.2" / "round2-fixtures"
        assert retained.is_dir()
        _, stale_after = invoke(root / "round2-after-stale", [retained / "stale-sidecars"], ["grok"])
        stale_run = one_run(stale_after, "grok", "primary-A")
        assert stale_run["lifecycle"]["state"] == "unknown"
        assert stale_run["tokens"]["total"] == "unknown"
        assert len(stale_after["coverage"]["coverage_gaps"]) >= 2
        _, overlap_after = invoke(root / "round2-after-overlap", [retained / "overlap"], ["grok"])
        overlap_run = one_run(overlap_after, "grok", "primary-A")
        overlap_calls = [call for turn in overlap_run["turns"] for call in turn["tool_calls"]]
        assert len(overlap_calls) == 1 and overlap_calls[0]["id"] == "X" and overlap_calls[0]["status"] == "ok"
        assert len(overlap_calls[0]["evidence"]) >= 4 and not overlap_run["checks"]
        _, order_after = invoke(root / "round2-after-order", [retained / "result-before-call"], ["grok"])
        order_run = one_run(order_after, "grok", "primary-A")
        order_calls = [call for turn in order_run["turns"] for call in turn["tool_calls"]]
        assert len(order_calls) == 1 and order_calls[0]["id"] == "X" and order_calls[0]["status"] == "ok"
        assert not order_run["checks"] and not any(turn["errors"] for turn in order_run["turns"])
        summary_cohort = retained / "summary-cohort-conflict"
        _, summary_cohort_after = invoke(root / "round3-after-summary-cohort", [summary_cohort], ["grok"])
        summary_cohort_run = one_run(summary_cohort_after, "grok", "summary-A")
        assert summary_cohort_run["tokens"]["total"] == "unknown"
        assert not summary_cohort_run["usage_provenance"]
        assert any(
            gap.get("observed_identity") == ["usage-B"]
            and gap.get("reason") == "grok sidecar identity mismatch; sidecar ignored"
            for gap in summary_cohort_after["coverage"]["coverage_gaps"]
        )

        primary_cohort = retained / "primary-cohort-conflict"
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

        no_summary_conflict = retained / "no-summary-sidecar-conflict"
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

        no_summary_consistent = retained / "no-summary-sidecar-consistent"
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
            ],
            "runs": len(first["runs"]),
            "malformed": first["coverage"]["malformed_count"],
        }
        print(json.dumps(result, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
