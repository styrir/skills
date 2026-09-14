#!/usr/bin/env python3
"""CLI smoke for session-eval/scripts/evaluate.py.

Creates synthetic native sessions, runs the real ingest CLI, then the real
evaluate CLI.  Checks consume frozen snapshots rather than preclassified
fixtures.  WorkGraph scoring is prepared against the existing red-baseline
fixture and is not executed here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

INGEST = Path(__file__).with_name("ingest.py")
EVALUATE = Path(__file__).with_name("evaluate.py")
WORKGRAPH_BIN = Path("/Users/brooks/Code/agent-ops/bin/workgraph-eval-score")
WORKGRAPH_EVIDENCE = Path("/Users/brooks/Code/agent-ops/tests/workgraph-eval/fixtures/red-baseline")
WORKGRAPH_MANIFEST = Path("/Users/brooks/Code/agent-ops/tests/workgraph-eval/fixtures/acceptance-manifest.json")
WORKGRAPH_ALLOWLIST = Path("/Users/brooks/Code/agent-ops/tests/workgraph-eval/fixtures/mutation-allowlist.json")


def write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if isinstance(row, str):
                handle.write(row.rstrip("\n") + "\n")
            else:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_cli(script: Path, args: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def ingest(out: Path, paths: list[Path], harnesses: list[str]) -> dict[str, Any]:
    args = ["--since", "all", "--out", str(out)]
    for harness in harnesses:
        args.extend(["--harness", harness])
    for path in paths:
        args.extend(["--path", str(path)])
    code, stdout, stderr = run_cli(INGEST, args)
    if code != 0:
        raise AssertionError(f"ingest failed ({code}): {stderr or stdout}")
    receipt_path = out / "receipt.json"
    return json.loads(receipt_path.read_text(encoding="utf-8"))


def evaluate(receipt_path: Path, out: Path, snapshot_root: Path | None = None) -> dict[str, Any]:
    args = ["--receipt", str(receipt_path), "--out", str(out)]
    if snapshot_root is not None:
        args.extend(["--snapshot-root", str(snapshot_root)])
    code, stdout, stderr = run_cli(EVALUATE, args)
    if code != 0:
        raise AssertionError(f"evaluate failed ({code}): {stderr or stdout}")
    evaluated = out / "receipt.json"
    if not evaluated.is_file():
        raise AssertionError(f"evaluate did not write {evaluated}: {stdout}")
    return json.loads(evaluated.read_text(encoding="utf-8"))


def ingest_and_evaluate(root: Path, name: str, path: Path, harness: str) -> dict[str, Any]:
    ingested = ingest(root / f"{name}-ingest", [path], [harness])
    receipt_path = root / f"{name}-ingest" / "receipt.json"
    return evaluate(receipt_path, root / f"{name}-evaluate")


def one_run(receipt: dict[str, Any]) -> dict[str, Any]:
    runs = receipt.get("runs") or []
    assert runs, f"expected runs, coverage={receipt.get('coverage')}"
    return runs[0]


def check(run: dict[str, Any], check_id: str) -> dict[str, Any]:
    matches = [item for item in run.get("checks") or [] if item.get("id") == check_id]
    assert matches, f"missing check {check_id}"
    return matches[0]


def rollup(receipt: dict[str, Any], check_id: str) -> dict[str, Any]:
    matches = [item for item in receipt.get("checks") or [] if item.get("id") == check_id]
    assert matches, f"missing rollup {check_id}"
    return matches[0]


def omp_session(session_id: str, rows: list[Any]) -> list[Any]:
    return [
        {"type": "session", "version": 3, "id": session_id, "timestamp": "2026-09-13T10:00:00Z"},
        *rows,
    ]


def tool_call(
    call_id: str,
    name: str,
    arguments: Any,
    attempt: dict[str, Any] | None = None,
    parent_id: str | None = None,
    child_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "type": "message",
        "id": f"msg-{call_id}",
        "message": {
            "role": "assistant",
            "content": [{"type": "toolCall", "id": call_id, "name": name, "arguments": arguments}],
        },
    }
    if attempt is not None:
        row["attempt"] = attempt
    if parent_id is not None:
        row["parentId"] = parent_id
    if child_id is not None:
        row["childId"] = child_id
    if timestamp is not None:
        row["timestamp"] = timestamp
    return row


def tool_result(
    call_id: str,
    is_error: bool,
    content: Any,
    attempt: dict[str, Any] | None = None,
    parent_id: str | None = None,
    child_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "type": "message",
        "id": f"res-{call_id}",
        "message": {"role": "toolResult", "toolCallId": call_id, "isError": is_error, "content": content},
    }
    if attempt is not None:
        row["attempt"] = attempt
    if parent_id is not None:
        row["parentId"] = parent_id
    if child_id is not None:
        row["childId"] = child_id
    if timestamp is not None:
        row["timestamp"] = timestamp
    return row


def assistant_text(turn_id: str, text: str, attempt: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "type": "message",
        "id": turn_id,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }
    if attempt is not None:
        row["attempt"] = attempt
    return row


def user_text(turn_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": turn_id,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def session_end() -> dict[str, Any]:
    return {"type": "custom", "customType": "session_end", "timestamp": "2026-09-13T10:09:00Z"}


def session_summary_non_marker() -> dict[str, Any]:
    return {"type": "custom", "customType": "session_summary", "timestamp": "2026-09-13T10:08:00Z"}


def session_live() -> dict[str, Any]:
    return {"type": "custom", "customType": "live", "timestamp": "2026-09-13T10:09:00Z"}


def codex_session(session_id: str, rows: list[Any]) -> list[Any]:
    return [
        {"type": "session_meta", "payload": {"id": session_id, "timestamp": "2026-09-14T02:00:00Z"}},
        *rows,
    ]


def codex_tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {"type": "custom_tool_call", "id": call_id, "call_id": call_id, "name": name, "input": arguments},
    }


def codex_tool_result(call_id: str, is_error: bool, output: Any) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {"type": "custom_tool_call_output", "call_id": call_id, "is_error": is_error, "output": output},
    }


def codex_assistant(text: str) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]},
    }


def codex_user(text: str) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]},
    }


def grok_session_dir(
    root: Path,
    name: str,
    session_id: str,
    chat: list[Any],
    events: list[Any],
    updates: list[Any],
) -> Path:
    path = root / name
    path.mkdir()
    write_jsonl(path / "chat_history.jsonl", chat)
    write_jsonl(path / "events.jsonl", events)
    write_jsonl(path / "updates.jsonl", updates)
    (path / "summary.json").write_text(
        json.dumps(
            {
                "info": {
                    "id": session_id,
                    "cwd": str(root),
                    "current_model_id": "grok-model",
                    "created_at": "2026-09-13T10:05:00Z",
                    "ended_at": "2026-09-13T10:09:00Z",
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def grok_update(session_id: str, inner: dict[str, Any], timestamp: int) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "method": "session/update",
        "params": {"sessionId": session_id, "update": {"sessionUpdate": inner}},
    }


def grok_turn_started(session_id: str, turn_id: str) -> dict[str, Any]:
    return {
        "type": "turn_started",
        "ts": "2026-09-13T10:05:00Z",
        "params": {"sessionId": session_id, "turnId": turn_id, "modelId": "grok-model"},
    }


def grok_failed_reads(session_id: str, count: int, start: int = 1726221900) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(count):
        stamp = start + index
        rows.append(
            grok_update(
                session_id,
                {"type": "tool_call", "toolCallId": f"a{index}", "title": "read", "arguments": {"path": "x"}},
                stamp,
            )
        )
        rows.append(
            grok_update(
                session_id,
                {
                    "type": "tool_call_update",
                    "toolCallId": f"a{index}",
                    "status": "failed",
                    "content": [{"type": "text", "text": "same recorded failure"}],
                },
                stamp,
            )
        )
    return rows



def workgraph_parent_command(receipt_path: Path, out: Path) -> list[str]:
    return [
        sys.executable,
        str(EVALUATE),
        "--receipt",
        str(receipt_path),
        "--out",
        str(out),
        "--workgraph",
        str(WORKGRAPH_EVIDENCE),
        "--workgraph-manifest",
        str(WORKGRAPH_MANIFEST),
        "--workgraph-allowlist",
        str(WORKGRAPH_ALLOWLIST),
        "--workgraph-bin",
        str(WORKGRAPH_BIN),
    ]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="session-eval-evaluate-smoke-") as temporary:
        root = Path(temporary)
        cases: list[str] = []

        ended = root / "ended.jsonl"
        write_jsonl(
            ended,
            omp_session(
                "ended-unpaired",
                [
                    tool_call("ended-call", "shell", {"command": "ls"}),
                    session_end(),
                ],
            ),
        )
        ended_receipt = ingest_and_evaluate(root, "ended", ended, "omp")
        ended_run = one_run(ended_receipt)
        assert ended_run["lifecycle"]["state"] == "terminal"
        unpaired = check(ended_run, "tool.unpaired")
        assert unpaired["status"] == "fail"
        assert unpaired["class"] == "hard_fail"
        assert unpaired["channel"] == "behavior"
        cases.append("ended unpaired tool.unpaired fail")

        live = root / "live.jsonl"
        write_jsonl(
            live,
            omp_session(
                "live-unpaired",
                [
                    tool_call("live-call", "shell", {"command": "ls"}),
                    session_live(),
                ],
            ),
        )
        live_receipt = ingest_and_evaluate(root, "live", live, "omp")
        live_run = one_run(live_receipt)
        assert live_run["lifecycle"]["state"] == "live"
        assert check(live_run, "tool.unpaired")["status"] == "not_applicable"
        assert check(live_run, "session.incomplete")["status"] == "not_applicable"
        cases.append("live unpaired tool.unpaired not_applicable")

        malformed = root / "malformed.jsonl"
        write_jsonl(
            malformed,
            omp_session(
                "malformed-1",
                [
                    assistant_text("malformed-ok", "hello"),
                    "{not-json",
                    session_end(),
                ],
            ),
        )
        malformed_receipt = ingest_and_evaluate(root, "malformed", malformed, "omp")
        malformed_run = one_run(malformed_receipt)
        parse = check(malformed_run, "ingest.parse_error")
        assert parse["status"] == "fail"
        assert parse["channel"] == "infra"
        assert malformed_receipt["infra_ok"] is False
        cases.append("malformed ingest.parse_error fail infra_ok false")

        empty_dir = root / "empty-inputs"
        empty_dir.mkdir()
        empty_ingest_out = root / "empty-ingest"
        empty_doc = ingest(empty_ingest_out, [empty_dir], ["omp"])
        empty_receipt = evaluate(empty_ingest_out / "receipt.json", root / "empty-evaluate")
        assert empty_receipt["coverage"]["sessions_ingested"] == 0
        assert empty_receipt["coverage"]["empty"] is True
        assert empty_receipt["hard_pass"] is False
        assert empty_doc["coverage"]["empty"] is True
        cases.append("empty coverage hard_pass false")

        missing_ingest = ingest(root / "missing-ingest", [ended], ["claude"])
        missing_receipt = evaluate(root / "missing-ingest" / "receipt.json", root / "missing-evaluate")
        assert missing_receipt["coverage"]["missing_requested_inputs"]
        assert missing_receipt["hard_pass"] is False
        assert missing_ingest["coverage"]["missing_requested_inputs"]
        cases.append("missing requested input prevents success")

        loop_fail = root / "loop-fail.jsonl"
        loop_rows: list[Any] = []
        for index in range(4):
            call_id = f"loop-{index}"
            loop_rows.append(tool_call(call_id, "shell", {"command": "ls /tmp", "nonce": "same"}))
            loop_rows.append(tool_result(call_id, True, {"exit_code": 1, "output": "retry"}))
        loop_rows.append(session_end())
        write_jsonl(loop_fail, omp_session("loop-fail", loop_rows))
        loop_receipt = ingest_and_evaluate(root, "loop-fail", loop_fail, "omp")
        loop_run = one_run(loop_receipt)
        assert check(loop_run, "tool.repeat_loop")["status"] == "fail"
        assert check(loop_run, "tool.result_error")["status"] == "fail"
        assert check(loop_run, "tool.result_error")["class"] == "expected_behavior"
        cases.append("four-call same-args loop fail")

        loop_reset = root / "loop-reset.jsonl"
        reset_rows: list[Any] = []
        for index in range(3):
            call_id = f"reset-a-{index}"
            reset_rows.append(tool_call(call_id, "shell", {"command": "ls /tmp", "nonce": "same"}))
            reset_rows.append(tool_result(call_id, True, {"exit_code": 1, "output": "retry"}))
        reset_rows.append(user_text("user-reset", "try a different path"))
        for index in range(2):
            call_id = f"reset-b-{index}"
            reset_rows.append(tool_call(call_id, "shell", {"command": "ls /tmp", "nonce": "same"}))
            reset_rows.append(tool_result(call_id, True, {"exit_code": 1, "output": "retry"}))
        reset_rows.append(session_end())
        write_jsonl(loop_reset, omp_session("loop-reset", reset_rows))
        reset_receipt = ingest_and_evaluate(root, "loop-reset", loop_reset, "omp")
        reset_run = one_run(reset_receipt)
        assert check(reset_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("user-turn progress reset keeps loop under 4")

        args_id = root / "args-identity.jsonl"
        identity_rows = [
            tool_call("id-1", "shell", {"command": "ls /tmp", "nonce": "1"}),
            tool_result("id-1", True, {"exit_code": 1}),
            tool_call("id-2", "shell", {"command": "ls /tmp", "nonce": "1"}),
            tool_result("id-2", True, {"exit_code": 1}),
            tool_call("id-3", "shell", {"command": "ls /tmp", "nonce": "2"}),
            tool_result("id-3", True, {"exit_code": 1}),
            tool_call("id-4", "shell", {"command": "ls /tmp "}),
            tool_result("id-4", True, {"exit_code": 1}),
            session_end(),
        ]
        write_jsonl(args_id, omp_session("args-identity", identity_rows))
        identity_receipt = ingest_and_evaluate(root, "args-identity", args_id, "omp")
        identity_run = one_run(identity_receipt)
        assert check(identity_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("argument identity preserves keys/strings and does not false-loop")

        ordinary = root / "ordinary-error.jsonl"
        write_jsonl(
            ordinary,
            omp_session(
                "ordinary-error",
                [
                    tool_call("err-1", "shell", {"command": "ls /missing"}),
                    tool_result("err-1", True, {"exit_code": 1, "output": "missing"}),
                    session_end(),
                ],
            ),
        )
        ordinary_receipt = ingest_and_evaluate(root, "ordinary-error", ordinary, "omp")
        ordinary_run = one_run(ordinary_receipt)
        assert check(ordinary_run, "tool.result_error")["status"] == "fail"
        assert check(ordinary_run, "tool.repeat_loop")["status"] == "pass"
        assert check(ordinary_run, "tool.result_error")["class"] == "expected_behavior"
        cases.append("ordinary single tool error does not fail repeat_loop")

        unknown_gate = root / "unknown-gate.jsonl"
        write_jsonl(
            unknown_gate,
            omp_session(
                "unknown-gate",
                [
                    assistant_text("done-1", "The implementation is complete."),
                    session_end(),
                ],
            ),
        )
        unknown_receipt = ingest_and_evaluate(root, "unknown-gate", unknown_gate, "omp")
        unknown_run = one_run(unknown_receipt)
        completion = check(unknown_run, "claim.completion")
        assert completion["status"] == "unknown"
        assert completion["class"] == "hard_fail"
        identity = check(unknown_run, "session.identity_missing")
        assert identity["status"] == "pass"
        assert unknown_receipt["hard_pass"] is False
        assert unknown_receipt["coverage"]["applicable_hard_fail_decided"] >= 1
        assert unknown_receipt["coverage"]["applicable_hard_fail_unknown"] >= 1
        cases.append("passed plus unknown hard gates => hard_pass false")

        contradict = root / "contradict.jsonl"
        write_jsonl(
            contradict,
            omp_session(
                "contradict",
                [
                    tool_call("pytest-1", "shell", {"command": "pytest -q"}),
                    tool_result("pytest-1", True, {"exit_code": 1, "output": "failed"}),
                    assistant_text("claim-fail", "pytest passed"),
                    session_end(),
                ],
            ),
        )
        contradict_receipt = ingest_and_evaluate(root, "contradict", contradict, "omp")
        contradict_run = one_run(contradict_receipt)
        assert check(contradict_run, "claim.command_outcome")["status"] == "fail"
        cases.append("command claim contradicted by final nonzero exit")

        retry = root / "retry.jsonl"
        write_jsonl(
            retry,
            omp_session(
                "retry",
                [
                    tool_call("pytest-a", "shell", {"command": "pytest -q"}),
                    tool_result("pytest-a", True, {"exit_code": 1, "output": "failed"}),
                    tool_call("pytest-b", "shell", {"command": "pytest -q"}),
                    tool_result("pytest-b", False, {"exit_code": 0, "output": "passed"}),
                    assistant_text("claim-ok", "pytest passed"),
                    session_end(),
                ],
            ),
        )
        retry_receipt = ingest_and_evaluate(root, "retry", retry, "omp")
        retry_run = one_run(retry_receipt)
        assert check(retry_run, "claim.command_outcome")["status"] == "pass"
        cases.append("successful retry supports later success claim")

        missing_set = root / "missing-set.jsonl"
        write_jsonl(
            missing_set,
            omp_session(
                "missing-set",
                [
                    assistant_text("done-2", "The task is complete."),
                    session_end(),
                ],
            ),
        )
        missing_set_receipt = ingest_and_evaluate(root, "missing-set", missing_set, "omp")
        missing_set_run = one_run(missing_set_receipt)
        missing_completion = check(missing_set_run, "claim.completion")
        assert missing_completion["status"] == "unknown"
        assert missing_completion["class"] == "hard_fail"
        assert missing_set_receipt["hard_pass"] is False
        assert any(
            gap.get("id") == "claim.historical_policy_unavailable"
            for gap in missing_set_receipt.get("proof_gaps") or []
        )
        cases.append("unambiguous completion with no acceptance set is unknown")

        recovered = root / "recovered-fourth.jsonl"
        recovered_rows: list[Any] = []
        error_payload = {"exit_code": 1, "output": "same-error"}
        for index in range(3):
            call_id = f"rec-{index}"
            recovered_rows.append(tool_call(call_id, "shell", {"command": "ls /tmp", "nonce": "same"}))
            recovered_rows.append(tool_result(call_id, True, error_payload))
        recovered_rows.append(tool_call("rec-3", "shell", {"command": "ls /tmp", "nonce": "same"}))
        recovered_rows.append(tool_result("rec-3", False, {"exit_code": 0, "output": "different-success"}))
        recovered_rows.append(session_end())
        write_jsonl(recovered, omp_session("recovered-fourth", recovered_rows))
        recovered_receipt = ingest_and_evaluate(root, "recovered-fourth", recovered, "omp")
        recovered_run = one_run(recovered_receipt)
        assert check(recovered_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("fourth-call success vs prior error payload resets loop")

        nested_args = {"command": "ls /tmp", "nonce": "same"}
        nested_error = {"exit_code": 1, "output": "same-error"}
        nested_rows: list[Any] = []
        for index in range(3):
            call_id = f"nested-a-{index}"
            nested_rows.append(tool_call(call_id, "shell", nested_args, parent_id="agent-a"))
            nested_rows.append(tool_result(call_id, True, nested_error, parent_id="agent-a"))
        nested_rows.append(tool_call("nested-b-0", "shell", nested_args, parent_id="agent-b"))
        nested_rows.append(tool_result("nested-b-0", True, nested_error, parent_id="agent-b"))
        nested_rows.append(tool_call("nested-a-3", "shell", nested_args, parent_id="agent-a"))
        nested_rows.append(tool_result("nested-a-3", True, nested_error, parent_id="agent-a"))
        nested_rows.append(session_end())
        nested_path = root / "loop-nested-agent.jsonl"
        write_jsonl(nested_path, omp_session("loop-nested-agent", nested_rows))
        nested_receipt = ingest_and_evaluate(root, "loop-nested-agent", nested_path, "omp")
        nested_run = one_run(nested_receipt)
        assert check(nested_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("A×3 B×1 A×1 nested-agent parent switch does not loop")

        consecutive_rows: list[Any] = []
        for index in range(4):
            call_id = f"consec-a-{index}"
            consecutive_rows.append(tool_call(call_id, "shell", nested_args, parent_id="agent-a"))
            consecutive_rows.append(tool_result(call_id, True, nested_error, parent_id="agent-a"))
        consecutive_rows.append(session_end())
        consecutive_path = root / "loop-consecutive-a4.jsonl"
        write_jsonl(consecutive_path, omp_session("loop-consecutive-a4", consecutive_rows))
        consecutive_receipt = ingest_and_evaluate(root, "loop-consecutive-a4", consecutive_path, "omp")
        consecutive_run = one_run(consecutive_receipt)
        assert check(consecutive_run, "tool.repeat_loop")["status"] == "fail"
        cases.append("true consecutive A×4 same parent identity loops")

        attempt_loop_a = {"id": "attempt-1", "number": 1}
        attempt_loop_b = {"id": "attempt-2", "number": 2}
        attempt_loop_rows: list[Any] = []
        for index in range(3):
            call_id = f"attloop-a-{index}"
            attempt_loop_rows.append(tool_call(call_id, "shell", nested_args, attempt_loop_a))
            attempt_loop_rows.append(tool_result(call_id, True, nested_error, attempt_loop_a))
        attempt_loop_rows.append(tool_call("attloop-b-0", "shell", nested_args, attempt_loop_b))
        attempt_loop_rows.append(tool_result("attloop-b-0", True, nested_error, attempt_loop_b))
        attempt_loop_rows.append(tool_call("attloop-a-3", "shell", nested_args, attempt_loop_a))
        attempt_loop_rows.append(tool_result("attloop-a-3", True, nested_error, attempt_loop_a))
        attempt_loop_rows.append(session_end())
        attempt_loop_path = root / "loop-attempt-switch.jsonl"
        write_jsonl(attempt_loop_path, omp_session("loop-attempt-switch", attempt_loop_rows))
        attempt_loop_receipt = ingest_and_evaluate(root, "loop-attempt-switch", attempt_loop_path, "omp")
        attempt_loop_run = one_run(attempt_loop_receipt)
        assert check(attempt_loop_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("A×3 B×1 A×1 attempt switch does not loop")

        three_rows: list[Any] = []
        for index in range(3):
            call_id = f"three-{index}"
            three_rows.append(tool_call(call_id, "shell", {"command": "ls /tmp", "nonce": "same"}))
            three_rows.append(tool_result(call_id, True, {"exit_code": 1, "output": "retry"}))
        three_rows.append(session_end())
        three_path = root / "loop-three.jsonl"
        write_jsonl(three_path, omp_session("loop-three", three_rows))
        three_run = one_run(ingest_and_evaluate(root, "loop-three", three_path, "omp"))
        assert check(three_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("three-call same-args under threshold pass")

        tool_bound_rows: list[Any] = []
        for index in range(3):
            call_id = f"read-x-{index}"
            tool_bound_rows.append(tool_call(call_id, "read", {"path": "synthetic.txt"}))
            tool_bound_rows.append(tool_result(call_id, True, "missing"))
        tool_bound_rows.append(tool_call("bash-y", "shell", {"command": "ls"}))
        tool_bound_rows.append(tool_result("bash-y", True, "missing"))
        tool_bound_rows.append(tool_call("read-x-3", "read", {"path": "synthetic.txt"}))
        tool_bound_rows.append(tool_result("read-x-3", True, "missing"))
        tool_bound_rows.append(session_end())
        tool_bound_path = root / "loop-tool-boundary.jsonl"
        write_jsonl(tool_bound_path, omp_session("loop-tool-boundary", tool_bound_rows))
        tool_bound_run = one_run(ingest_and_evaluate(root, "loop-tool-boundary", tool_bound_path, "omp"))
        assert check(tool_bound_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("read×3 bash×1 read×1 tool-name switch does not loop")

        args_bound_rows: list[Any] = []
        args_x = {"command": "ls /tmp", "nonce": "x"}
        args_y = {"command": "ls /tmp", "nonce": "y"}
        for index in range(3):
            call_id = f"args-x-{index}"
            args_bound_rows.append(tool_call(call_id, "shell", args_x))
            args_bound_rows.append(tool_result(call_id, True, {"exit_code": 1, "output": "retry"}))
        args_bound_rows.append(tool_call("args-y-0", "shell", args_y))
        args_bound_rows.append(tool_result("args-y-0", True, {"exit_code": 1, "output": "retry"}))
        args_bound_rows.append(tool_call("args-x-3", "shell", args_x))
        args_bound_rows.append(tool_result("args-x-3", True, {"exit_code": 1, "output": "retry"}))
        args_bound_rows.append(session_end())
        args_bound_path = root / "loop-args-boundary.jsonl"
        write_jsonl(args_bound_path, omp_session("loop-args-boundary", args_bound_rows))
        args_bound_run = one_run(ingest_and_evaluate(root, "loop-args-boundary", args_bound_path, "omp"))
        assert check(args_bound_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("args X×3 Y×1 X×1 digest switch does not loop")

        child_rows: list[Any] = []
        for index in range(3):
            call_id = f"child-a-{index}"
            child_rows.append(tool_call(call_id, "shell", nested_args, child_id="agent-a"))
            child_rows.append(tool_result(call_id, True, nested_error, child_id="agent-a"))
        child_rows.append(tool_call("child-b-0", "shell", nested_args, child_id="agent-b"))
        child_rows.append(tool_result("child-b-0", True, nested_error, child_id="agent-b"))
        child_rows.append(tool_call("child-a-3", "shell", nested_args, child_id="agent-a"))
        child_rows.append(tool_result("child-a-3", True, nested_error, child_id="agent-a"))
        child_rows.append(session_end())
        child_path = root / "loop-child-agent.jsonl"
        write_jsonl(child_path, omp_session("loop-child-agent", child_rows))
        child_run = one_run(ingest_and_evaluate(root, "loop-child-agent", child_path, "omp"))
        assert check(child_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("A×3 B×1 A×1 child-id agent switch does not loop")

        terminal_rows: list[Any] = []
        for index in range(3):
            call_id = f"term-{index}"
            terminal_rows.append(tool_call(call_id, "read", {"path": "synthetic.txt"}))
            terminal_rows.append(tool_result(call_id, True, "synthetic missing file"))
        terminal_rows.append(session_end())
        terminal_rows.append(tool_call("term-3", "read", {"path": "synthetic.txt"}))
        terminal_rows.append(tool_result("term-3", True, "synthetic missing file"))
        terminal_path = root / "loop-terminal-reset.jsonl"
        write_jsonl(terminal_path, omp_session("terminal-reset", terminal_rows))
        terminal_run = one_run(ingest_and_evaluate(root, "loop-terminal-reset", terminal_path, "omp"))
        assert check(terminal_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("A×3 session_end A×1 explicit terminal resets loop")

        eof_rows: list[Any] = []
        for index in range(4):
            call_id = f"eof-{index}"
            eof_rows.append(
                tool_call(
                    call_id,
                    "shell",
                    {"command": "ls /tmp", "nonce": "same"},
                    timestamp=f"2026-09-13T10:0{index}:00Z",
                )
            )
            eof_rows.append(
                tool_result(
                    call_id,
                    True,
                    {"exit_code": 1, "output": "retry"},
                    timestamp=f"2026-09-13T10:0{index}:01Z",
                )
            )
        eof_path = root / "omp" / "loop-eof-clock.jsonl"
        write_jsonl(eof_path, omp_session("loop-eof-clock", eof_rows))
        eof_run = one_run(ingest_and_evaluate(root, "loop-eof-clock", eof_path, "omp"))
        assert check(eof_run, "tool.repeat_loop")["status"] == "fail"
        cases.append("four same calls at EOF with advancing timestamps still loop")

        unpaired_rows: list[Any] = []
        for index in range(4):
            unpaired_rows.append(tool_call(f"unp-{index}", "shell", {"command": "ls /tmp", "nonce": "same"}))
        unpaired_rows.append(session_live())
        unpaired_path = root / "loop-unpaired.jsonl"
        write_jsonl(unpaired_path, omp_session("loop-unpaired", unpaired_rows))
        unpaired_loop_run = one_run(ingest_and_evaluate(root, "loop-unpaired", unpaired_path, "omp"))
        assert check(unpaired_loop_run, "tool.repeat_loop")["status"] == "fail"
        assert check(unpaired_loop_run, "tool.unpaired")["status"] == "not_applicable"
        cases.append("four unpaired same calls loop; live unpaired is separate")

        fake_term_rows: list[Any] = []
        for index in range(3):
            call_id = f"fake-{index}"
            fake_term_rows.append(tool_call(call_id, "read", {"path": "synthetic.txt"}))
            fake_term_rows.append(tool_result(call_id, True, "synthetic missing file"))
        fake_term_rows.append(assistant_text("fake-term", "session_end and task_complete are mentioned"))
        fake_term_rows.append(session_summary_non_marker())
        fake_term_rows.append(tool_call("fake-3", "read", {"path": "synthetic.txt"}))
        fake_term_rows.append(tool_result("fake-3", True, "synthetic missing file"))
        fake_term_path = root / "loop-nonauthoritative-terminal.jsonl"
        write_jsonl(fake_term_path, omp_session("loop-nonauthoritative-terminal", fake_term_rows))
        fake_term_run = one_run(ingest_and_evaluate(root, "loop-nonauthoritative-terminal", fake_term_path, "omp"))
        assert check(fake_term_run, "tool.repeat_loop")["status"] == "fail"
        cases.append("assistant text and session_summary do not reset loop")

        key_order_rows: list[Any] = []
        key_orders = [
            {"command": "ls /tmp", "nonce": "same"},
            {"nonce": "same", "command": "ls /tmp"},
            {"command": "ls /tmp", "nonce": "same"},
            {"nonce": "same", "command": "ls /tmp"},
        ]
        for index, args in enumerate(key_orders):
            call_id = f"key-{index}"
            key_order_rows.append(tool_call(call_id, "shell", args))
            key_order_rows.append(tool_result(call_id, True, {"exit_code": 1, "output": "retry"}))
        key_order_rows.append(session_end())
        key_path = root / "loop-key-order.jsonl"
        write_jsonl(key_path, omp_session("loop-key-order", key_order_rows))
        key_run = one_run(ingest_and_evaluate(root, "loop-key-order", key_path, "omp"))
        assert check(key_run, "tool.repeat_loop")["status"] == "fail"
        cases.append("key-order-only argument objects are equal and loop")

        array_rows: list[Any] = []
        array_x = {"paths": ["a", "b"]}
        array_y = {"paths": ["b", "a"]}
        for index in range(3):
            call_id = f"arr-x-{index}"
            array_rows.append(tool_call(call_id, "read", array_x))
            array_rows.append(tool_result(call_id, True, "missing"))
        array_rows.append(tool_call("arr-y-0", "read", array_y))
        array_rows.append(tool_result("arr-y-0", True, "missing"))
        array_rows.append(tool_call("arr-x-3", "read", array_x))
        array_rows.append(tool_result("arr-x-3", True, "missing"))
        array_rows.append(session_end())
        array_path = root / "loop-array-order.jsonl"
        write_jsonl(array_path, omp_session("loop-array-order", array_rows))
        array_run = one_run(ingest_and_evaluate(root, "loop-array-order", array_path, "omp"))
        assert check(array_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("reordered argument arrays are unequal and reset")

        success_rows: list[Any] = []
        success_payload = {"exit_code": 0, "output": "ok"}
        for index in range(4):
            call_id = f"ok-{index}"
            success_rows.append(tool_call(call_id, "shell", {"command": "true", "nonce": "same"}))
            success_rows.append(tool_result(call_id, False, success_payload))
        success_rows.append(session_end())
        success_path = root / "loop-same-success.jsonl"
        write_jsonl(success_path, omp_session("loop-same-success", success_rows))
        success_run = one_run(ingest_and_evaluate(root, "loop-same-success", success_path, "omp"))
        assert check(success_run, "tool.repeat_loop")["status"] == "fail"
        cases.append("four identical success payloads still loop")

        codex_term_rows = []
        for index in range(3):
            call_id = f"codex-term-{index}"
            codex_term_rows.append(codex_tool_call(call_id, "shell", {"command": "ls /tmp", "nonce": "same"}))
            codex_term_rows.append(codex_tool_result(call_id, True, {"exit_code": 1, "output": "retry"}))
        codex_term_rows.append({"type": "event_msg", "payload": {"type": "task_complete"}})
        codex_term_rows.append(codex_tool_call("codex-term-3", "shell", {"command": "ls /tmp", "nonce": "same"}))
        codex_term_rows.append(codex_tool_result("codex-term-3", True, {"exit_code": 1, "output": "retry"}))
        codex_term_path = root / "loop-codex-terminal.jsonl"
        write_jsonl(codex_term_path, codex_session("loop-codex-terminal", codex_term_rows))
        codex_term_run = one_run(ingest_and_evaluate(root, "loop-codex-terminal", codex_term_path, "codex"))
        assert check(codex_term_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("A×3 Codex task_complete A×1 explicit terminal resets loop")

        attempt_a = {"id": "attempt-1", "number": 1}
        attempt_b = {"id": "attempt-2", "number": 2}
        attempt_bind = root / "attempt-bind.jsonl"
        write_jsonl(
            attempt_bind,
            omp_session(
                "attempt-bind",
                [
                    tool_call("att-1", "shell", {"command": "pytest -q"}, attempt_a),
                    tool_result("att-1", True, {"exit_code": 1, "output": "failed"}, attempt_a),
                    tool_call("att-2", "shell", {"command": "pytest -q"}, attempt_b),
                    tool_result("att-2", False, {"exit_code": 0, "output": "passed"}, attempt_b),
                    assistant_text("claim-att-1", "pytest passed", attempt_a),
                    session_end(),
                ],
            ),
        )
        attempt_receipt = ingest_and_evaluate(root, "attempt-bind", attempt_bind, "omp")
        attempt_run = one_run(attempt_receipt)
        assert check(attempt_run, "claim.command_outcome")["status"] == "fail"
        cases.append("claim bound to attempt 1 ignores later attempt 2 success")

        grok_dir = root / "grok-cross"
        grok_dir.mkdir()
        write_jsonl(
            grok_dir / "chat_history.jsonl",
            [
                {"type": "user", "id": "u1", "content": "run tests"},
                {"type": "user", "id": "u2", "content": "again"},
                {"type": "user", "id": "u3", "content": "again"},
                {"type": "user", "id": "u4", "content": "again"},
                {"type": "assistant", "id": "claim-cross", "content": "pytest passed"},
            ],
        )
        write_jsonl(
            grok_dir / "events.jsonl",
            [
                {"type": "turn_started", "ts": "2026-09-13T10:05:00Z", "params": {"sessionId": "grok-cross", "turnId": "t1", "modelId": "grok-model"}},
            ],
        )
        write_jsonl(
            grok_dir / "updates.jsonl",
            [
                {
                    "timestamp": 1726221901,
                    "method": "session/update",
                    "params": {
                        "sessionId": "grok-cross",
                        "update": {
                            "sessionUpdate": {
                                "type": "tool_call",
                                "toolCallId": "py-cross",
                                "title": "shell",
                                "turnId": "t1",
                                "arguments": {"command": "pytest -q"},
                            }
                        },
                    },
                },
                {
                    "timestamp": 1726221902,
                    "method": "session/update",
                    "params": {
                        "sessionId": "grok-cross",
                        "update": {
                            "sessionUpdate": {
                                "type": "tool_call_update",
                                "toolCallId": "py-cross",
                                "status": "completed",
                                "turnId": "t1",
                                "result": {"exit_code": 0, "output": "passed"},
                            }
                        },
                    },
                },
            ],
        )
        (grok_dir / "summary.json").write_text(
            json.dumps(
                {
                    "info": {
                        "id": "grok-cross",
                        "cwd": str(root),
                        "current_model_id": "grok-model",
                        "created_at": "2026-09-13T10:05:00Z",
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        grok_ingest = ingest(root / "grok-cross-ingest", [grok_dir], ["grok"])
        grok_receipt = evaluate(root / "grok-cross-ingest" / "receipt.json", root / "grok-cross-evaluate")
        grok_run = one_run(grok_receipt)
        assert grok_ingest["coverage"]["malformed_count"] == 0
        assert check(grok_run, "ingest.parse_error")["status"] == "pass"
        assert grok_receipt["infra_ok"] is True
        assert check(grok_run, "claim.command_outcome")["status"] == "unknown"
        cases.append("multiline JSON sidecar is not JSONL; cross-stream line numbers do not bind claims")

        codex_contradict = root / "codex-claim-contradict.jsonl"
        write_jsonl(
            codex_contradict,
            codex_session(
                "codex-claim-contradict",
                [
                    codex_tool_call("codex-py", "shell", {"command": "pytest -q"}),
                    codex_tool_result("codex-py", True, {"exit_code": 1, "output": "failed"}),
                    codex_assistant("pytest passed"),
                    {"type": "event_msg", "payload": {"type": "task_complete"}},
                ],
            ),
        )
        codex_contradict_receipt = ingest_and_evaluate(root, "codex-claim-contradict", codex_contradict, "codex")
        codex_contradict_run = one_run(codex_contradict_receipt)
        assert check(codex_contradict_run, "claim.command_outcome")["status"] == "fail"
        cases.append("Codex response_item.payload assistant claim contradicted by failed pytest")

        codex_missing = root / "codex-claim-missing.jsonl"
        write_jsonl(
            codex_missing,
            [
                {"type": "session_meta", "payload": {"id": "codex-claim-repro", "timestamp": "2026-09-14T02:00:00Z"}},
                {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "pytest passed"}]}},
                {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "The task is complete."}]}},
            ],
        )
        codex_missing_receipt = ingest_and_evaluate(root, "codex-claim-missing", codex_missing, "codex")
        codex_missing_run = one_run(codex_missing_receipt)
        assert check(codex_missing_run, "claim.command_outcome")["status"] == "not_applicable"
        missing_completion = check(codex_missing_run, "claim.completion")
        assert missing_completion["status"] == "unknown"
        assert missing_completion["class"] == "hard_fail"
        assert codex_missing_receipt["hard_pass"] is False
        cases.append("Codex response_item.payload completion with no evidence is unknown")

        grok_fail_id = "grok-claim-contradict"
        grok_fail_dir = grok_session_dir(
            root,
            "grok-claim-contradict",
            grok_fail_id,
            [{"type": "user", "id": "u1", "content": "run tests"}],
            [grok_turn_started(grok_fail_id, "t1")],
            [
                grok_update(
                    grok_fail_id,
                    {
                        "type": "tool_call",
                        "toolCallId": "py-fail",
                        "title": "shell",
                        "turnId": "t1",
                        "arguments": {"command": "pytest -q"},
                    },
                    1726221901,
                ),
                grok_update(
                    grok_fail_id,
                    {
                        "type": "tool_call_update",
                        "toolCallId": "py-fail",
                        "status": "failed",
                        "turnId": "t1",
                        "result": {"exit_code": 1, "output": "failed"},
                        "isError": True,
                    },
                    1726221902,
                ),
                grok_update(
                    grok_fail_id,
                    {"type": "agent_message_chunk", "turnId": "t1", "content": "pytest passed"},
                    1726221903,
                ),
            ],
        )
        grok_fail_ingest = ingest(root / "grok-claim-contradict-ingest", [grok_fail_dir], ["grok"])
        grok_fail_receipt = evaluate(
            root / "grok-claim-contradict-ingest" / "receipt.json",
            root / "grok-claim-contradict-evaluate",
        )
        grok_fail_run = one_run(grok_fail_receipt)
        assert grok_fail_ingest["coverage"]["sessions_ingested"] == 1
        assert check(grok_fail_run, "claim.command_outcome")["status"] == "fail"
        cases.append("Grok agent_message_chunk claim contradicted by failed pytest")

        grok_miss_id = "grok-claim-missing"
        grok_miss_dir = grok_session_dir(
            root,
            "grok-claim-missing",
            grok_miss_id,
            [{"type": "user", "id": "u1", "content": "finish the task"}],
            [grok_turn_started(grok_miss_id, "t1")],
            [
                grok_update(
                    grok_miss_id,
                    {"type": "user_message_chunk", "turnId": "t1", "content": "pytest passed"},
                    1726221901,
                ),
                grok_update(
                    grok_miss_id,
                    {"type": "agent_thought_chunk", "turnId": "t1", "content": "pytest passed"},
                    1726221902,
                ),
                grok_update(
                    grok_miss_id,
                    {"type": "agent_message_chunk", "turnId": "t1", "content": "The task is complete."},
                    1726221903,
                ),
            ],
        )
        ingest(root / "grok-claim-missing-ingest", [grok_miss_dir], ["grok"])
        grok_miss_receipt = evaluate(
            root / "grok-claim-missing-ingest" / "receipt.json",
            root / "grok-claim-missing-evaluate",
        )
        grok_miss_run = one_run(grok_miss_receipt)
        assert check(grok_miss_run, "claim.command_outcome")["status"] == "not_applicable"
        grok_miss_completion = check(grok_miss_run, "claim.completion")
        assert grok_miss_completion["status"] == "unknown"
        assert grok_miss_completion["class"] == "hard_fail"
        assert grok_miss_receipt["hard_pass"] is False
        def four_omp(name: str, arg_list: list[Any], error: bool = True) -> dict[str, Any]:
            rows: list[Any] = []
            for index, args in enumerate(arg_list):
                call_id = f"{name}-{index}"
                rows.append(tool_call(call_id, "read", args))
                rows.append(tool_result(call_id, error, {"exit_code": 1 if error else 0, "output": "retry" if error else "ok"}))
            rows.append(session_end())
            path = root / f"{name}.jsonl"
            write_jsonl(path, omp_session(name, rows))
            return one_run(ingest_and_evaluate(root, name, path, "omp"))

        id_run = four_omp(
            "args-real-id",
            [{"type": "record", "id": str(index), "path": "same"} for index in range(4)],
        )
        assert check(id_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("argument id values remain semantic and do not loop")

        ts_run = four_omp(
            "args-real-timestamp",
            [{"name": "item", "timestamp": f"t{index}", "path": "same"} for index in range(4)],
        )
        assert check(ts_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("argument timestamp values remain semantic and do not loop")

        env_rows: list[Any] = []
        same_args = {"path": "synthetic.txt"}
        for index in range(4):
            call_id = f"env-{index}"
            env_rows.append(tool_call(call_id, "read", same_args, timestamp=f"2026-09-13T10:0{index}:00Z"))
            env_rows.append(tool_result(call_id, True, "missing", timestamp=f"2026-09-13T10:0{index}:01Z"))
        env_rows.append(session_end())
        env_path = root / "args-envelope-only.jsonl"
        write_jsonl(env_path, omp_session("args-envelope-only", env_rows))
        env_run = one_run(ingest_and_evaluate(root, "args-envelope-only", env_path, "omp"))
        assert check(env_run, "tool.repeat_loop")["status"] == "fail"
        cases.append("envelope-only id/timestamp differences still loop")

        ws_run = four_omp(
            "args-scalar-ws",
            [
                {"path": "a", "n": 1},
                {"path": "a", "n": 1},
                {"path": "a", "n": 1},
                {"path": "a ", "n": 1},
            ],
        )
        assert check(ws_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("string whitespace and scalar identity change arguments")

        null_run = four_omp("args-json-null", [None, None, None, None])
        # explicit null inside object is recorded; four identical → fail
        assert check(null_run, "tool.repeat_loop")["status"] == "fail"
        cases.append("explicit JSON null argument values are recorded and can loop")

        missing_src = root / "omp" / "missing-frozen.jsonl"
        missing_rows: list[Any] = []
        for index in range(4):
            call_id = f"miss-{index}"
            missing_rows.append(tool_call(call_id, "read", {"path": f"file-{index}"}))
            missing_rows.append(tool_result(call_id, True, "missing"))
        missing_rows.append(session_end())
        write_jsonl(missing_src, omp_session("missing-frozen", missing_rows))
        ingest(root / "missing-frozen-ingest", [missing_src], ["omp"])
        empty_snaps = root / "empty-snapshots"
        empty_snaps.mkdir()
        missing_eval = evaluate(
            root / "missing-frozen-ingest" / "receipt.json",
            root / "missing-frozen-evaluate",
            snapshot_root=empty_snaps,
        )
        missing_run = one_run(missing_eval)
        assert check(missing_run, "tool.repeat_loop")["status"] == "unknown"
        cases.append("unreadable frozen arguments yield repeat_loop unknown")

        ok_miss_rows: list[Any] = []
        for index in range(3):
            call_id = f"okmiss-{index}"
            ok_miss_rows.append(tool_call(call_id, "read", {"path": "synthetic.txt"}))
            ok_miss_rows.append(tool_result(call_id, True, "missing"))
        ok_miss_rows.append(tool_call("okmiss-3", "read", {"path": "synthetic.txt"}))
        ok_miss_rows.append(
            {
                "type": "message",
                "id": "res-okmiss-3",
                "message": {"role": "toolResult", "toolCallId": "okmiss-3", "isError": False},
            }
        )
        ok_miss_rows.append(session_end())
        ok_miss_path = root / "ok-missing-result.jsonl"
        write_jsonl(ok_miss_path, omp_session("ok-missing-result", ok_miss_rows))
        ok_miss_run = one_run(ingest_and_evaluate(root, "ok-missing-result", ok_miss_path, "omp"))
        assert check(ok_miss_run, "tool.repeat_loop")["status"] == "unknown"
        cases.append("fourth ok with unavailable result hash is unknown not fail")
        assert check(loop_run, "tool.repeat_loop")["status"] == "fail"
        cases.append("independent proven four-call fail is retained")

        def missing_success_run(name: str, length: int, holes: set[int]) -> dict[str, Any]:
            rows: list[Any] = []
            for index in range(length):
                call_id = f"{name}-{index}"
                rows.append(tool_call(call_id, "read", {"path": "x"}))
                if index in holes:
                    rows.append(
                        {
                            "type": "message",
                            "id": f"res-{call_id}",
                            "message": {"role": "toolResult", "toolCallId": call_id, "isError": False},
                        }
                    )
                else:
                    rows.append(tool_result(call_id, True, {"recorded": "R"}))
            path = root / "omp" / f"{name}.jsonl"
            write_jsonl(path, omp_session(name, rows))
            return one_run(ingest_and_evaluate(root, name, path, "omp"))

        miss_pos1 = missing_success_run("missing-success-pos1", 4, {1})
        assert check(miss_pos1, "tool.repeat_loop")["status"] == "unknown"
        cases.append("missing success in second position is unknown not fail")
        miss_pos2 = missing_success_run("missing-success-pos2", 4, {2})
        assert check(miss_pos2, "tool.repeat_loop")["status"] == "unknown"
        cases.append("missing success in third position is unknown not fail")
        miss_later = missing_success_run("missing-success-later-fail", 7, {3})
        assert check(miss_later, "tool.repeat_loop")["status"] == "fail"
        cases.append("four later proven errors after missing success still fail")



        grok_user_id = "grok-user-reset"
        grok_user_dir = root / "grok-user-reset"
        grok_user_dir.mkdir()
        write_jsonl(
            grok_user_dir / "chat_history.jsonl",
            [{"type": "user", "id": "u-mid", "content": "retry", "timestamp": 1726221905}],
        )
        write_jsonl(grok_user_dir / "events.jsonl", [grok_turn_started(grok_user_id, "t1")])
        user_updates = []
        for index in range(3):
            user_updates.append(grok_update(grok_user_id, {"type": "tool_call", "toolCallId": f"gu-{index}", "title": "read", "arguments": {"path": "x"}}, 1726221900 + index))
            user_updates.append(grok_update(grok_user_id, {"type": "tool_call_update", "toolCallId": f"gu-{index}", "status": "completed"}, 1726221900 + index))
        user_updates.append(grok_update(grok_user_id, {"type": "tool_call", "toolCallId": "gu-3", "title": "read", "arguments": {"path": "x"}}, 1726221910))
        user_updates.append(grok_update(grok_user_id, {"type": "tool_call_update", "toolCallId": "gu-3", "status": "completed"}, 1726221910))
        write_jsonl(grok_user_dir / "updates.jsonl", user_updates)
        (grok_user_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_user_id, "current_model_id": "grok-model"}}), encoding="utf-8")
        grok_user_run = one_run(ingest_and_evaluate(root, "grok-user-reset", grok_user_dir, "grok"))
        assert check(grok_user_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("Grok timestamped user turn resets cross-stream streak")

        grok_term_id = "grok-term-reset"
        grok_term_dir = root / "grok-term-reset"
        grok_term_dir.mkdir()
        write_jsonl(grok_term_dir / "chat_history.jsonl", [{"type": "assistant", "content": "working"}])
        write_jsonl(
            grok_term_dir / "events.jsonl",
            [
                grok_turn_started(grok_term_id, "t1"),
                {"type": "session_end", "ts": 1726221905, "params": {"sessionId": grok_term_id}},
            ],
        )
        term_updates = []
        for index in range(3):
            term_updates.append(grok_update(grok_term_id, {"type": "tool_call", "toolCallId": f"gt-{index}", "title": "read", "arguments": {"path": "x"}}, 1726221900 + index))
            term_updates.append(grok_update(grok_term_id, {"type": "tool_call_update", "toolCallId": f"gt-{index}", "status": "completed"}, 1726221900 + index))
        term_updates.append(grok_update(grok_term_id, {"type": "tool_call", "toolCallId": "gt-3", "title": "read", "arguments": {"path": "x"}}, 1726221910))
        term_updates.append(grok_update(grok_term_id, {"type": "tool_call_update", "toolCallId": "gt-3", "status": "completed"}, 1726221910))
        write_jsonl(grok_term_dir / "updates.jsonl", term_updates)
        (grok_term_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_term_id}}), encoding="utf-8")
        grok_term_run = one_run(ingest_and_evaluate(root, "grok-term-reset", grok_term_dir, "grok"))
        assert check(grok_term_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("Grok timestamped terminal resets cross-stream streak")

        grok_fail_id = "grok-cross-fail"
        grok_fail_dir = root / "grok-cross-fail"
        grok_fail_dir.mkdir()
        write_jsonl(grok_fail_dir / "chat_history.jsonl", [{"type": "assistant", "content": "go"}])
        write_jsonl(grok_fail_dir / "events.jsonl", [grok_turn_started(grok_fail_id, "t1")])
        fail_updates = []
        for index in range(4):
            fail_updates.append(grok_update(grok_fail_id, {"type": "tool_call", "toolCallId": f"gf-{index}", "title": "read", "arguments": {"path": "x"}}, 1726221900 + index))
            fail_updates.append(grok_update(grok_fail_id, {"type": "tool_call_update", "toolCallId": f"gf-{index}", "status": "completed"}, 1726221900 + index))
        write_jsonl(grok_fail_dir / "updates.jsonl", fail_updates)
        (grok_fail_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_fail_id}}), encoding="utf-8")
        grok_fail_run = one_run(ingest_and_evaluate(root, "grok-cross-fail", grok_fail_dir, "grok"))
        assert check(grok_fail_run, "tool.repeat_loop")["status"] == "unknown"
        cases.append("completed Grok updates without result payload stay unknown")

        grok_err_id = "grok-known-errors"
        grok_err_dir = root / "grok-known-errors"
        grok_err_dir.mkdir()
        write_jsonl(grok_err_dir / "chat_history.jsonl", [{"type": "assistant", "content": "go"}])
        write_jsonl(grok_err_dir / "events.jsonl", [grok_turn_started(grok_err_id, "t1")])
        err_updates = []
        for index in range(4):
            err_updates.append(grok_update(grok_err_id, {"type": "tool_call", "toolCallId": f"ge-{index}", "title": "read", "arguments": {"path": "x"}}, 1726221900 + index))
            err_updates.append(
                grok_update(
                    grok_err_id,
                    {
                        "type": "tool_call_update",
                        "toolCallId": f"ge-{index}",
                        "status": "failed",
                        "content": [{"type": "text", "text": "same recorded failure"}],
                    },
                    1726221900 + index,
                )
            )
        write_jsonl(grok_err_dir / "updates.jsonl", err_updates)
        (grok_err_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_err_id}}), encoding="utf-8")
        grok_err_run = one_run(ingest_and_evaluate(root, "grok-known-errors", grok_err_dir, "grok"))
        grok_err_loop = check(grok_err_run, "tool.repeat_loop")
        assert grok_err_loop["status"] == "fail"
        file_digest = {
            item["path"]: item["sha256"]
            for item in grok_err_run["source_snapshot"]["files"]
            if isinstance(item, dict)
        }
        aggregate = grok_err_run["source_snapshot"]["sha256"]
        assert grok_err_loop["evidence"]
        for pointer in grok_err_loop["evidence"]:
            assert pointer["parser_version"] == grok_err_run["parser_version"]
            assert pointer["evidence_hash"] not in (None, "", "unknown")
            assert pointer["snapshot_hash"] not in (None, "", "unknown")
            assert pointer["snapshot_hash"] == aggregate
            assert pointer["source_path"] in file_digest
            assert pointer["event_range"]["start_line"]
            assert pointer["event_range"]["end_line"]
        cases.append("recorded identical Grok failures loop with span evidence hashes")

        grok_amb_id = "grok-ambiguous"
        grok_amb_dir = root / "grok-ambiguous"
        grok_amb_dir.mkdir()
        write_jsonl(grok_amb_dir / "chat_history.jsonl", [{"type": "user", "id": "u-untimed", "content": "retry"}])
        write_jsonl(grok_amb_dir / "events.jsonl", [grok_turn_started(grok_amb_id, "t1")])
        amb_updates = []
        for index in range(4):
            amb_updates.append(grok_update(grok_amb_id, {"type": "tool_call", "toolCallId": f"ga-{index}", "title": "read", "arguments": {"path": "x"}}, 1726221900 + index))
            amb_updates.append(grok_update(grok_amb_id, {"type": "tool_call_update", "toolCallId": f"ga-{index}", "status": "completed"}, 1726221900 + index))
        write_jsonl(grok_amb_dir / "updates.jsonl", amb_updates)
        (grok_amb_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_amb_id}}), encoding="utf-8")
        grok_amb_run = one_run(ingest_and_evaluate(root, "grok-ambiguous", grok_amb_dir, "grok"))
        assert check(grok_amb_run, "tool.repeat_loop")["status"] == "unknown"
        cases.append("untermined Grok user vs tools chronology is unknown")

        grok_eq_user_id = "grok-equal-user"
        grok_eq_user_dir = root / "grok-equal-user"
        grok_eq_user_dir.mkdir()
        write_jsonl(grok_eq_user_dir / "chat_history.jsonl", [{"type": "user", "content": "Continue.", "timestamp": 1726221901}])
        write_jsonl(grok_eq_user_dir / "events.jsonl", [grok_turn_started(grok_eq_user_id, "t1")])
        write_jsonl(grok_eq_user_dir / "updates.jsonl", grok_failed_reads(grok_eq_user_id, 4))
        (grok_eq_user_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_eq_user_id}}), encoding="utf-8")
        grok_eq_user_run = one_run(ingest_and_evaluate(root, "grok-equal-user", grok_eq_user_dir, "grok"))
        assert check(grok_eq_user_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("equal-time user at second of four calls is unanimous pass")

        grok_eq_term_id = "grok-equal-terminal"
        grok_eq_term_dir = root / "grok-equal-terminal"
        grok_eq_term_dir.mkdir()
        write_jsonl(grok_eq_term_dir / "chat_history.jsonl", [{"type": "assistant", "content": "go"}])
        write_jsonl(
            grok_eq_term_dir / "events.jsonl",
            [
                grok_turn_started(grok_eq_term_id, "t1"),
                {"type": "session_end", "params": {"sessionId": grok_eq_term_id}, "ts": 1726221901},
            ],
        )
        write_jsonl(grok_eq_term_dir / "updates.jsonl", grok_failed_reads(grok_eq_term_id, 4))
        (grok_eq_term_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_eq_term_id}}), encoding="utf-8")
        grok_eq_term_run = one_run(ingest_and_evaluate(root, "grok-equal-terminal", grok_eq_term_dir, "grok"))
        assert check(grok_eq_term_run, "tool.repeat_loop")["status"] == "pass"
        cases.append("equal-time terminal at second of four calls is unanimous pass")

        grok_tool_untimed_id = "grok-tool-untimed"
        grok_tool_untimed_dir = root / "grok-tool-untimed"
        grok_tool_untimed_dir.mkdir()
        write_jsonl(
            grok_tool_untimed_dir / "chat_history.jsonl",
            [{"type": "assistant", "content": "", "tool_calls": [{"id": "foreign", "name": "other", "arguments": {"path": "x"}}]}],
        )
        write_jsonl(grok_tool_untimed_dir / "events.jsonl", [grok_turn_started(grok_tool_untimed_id, "t1")])
        write_jsonl(grok_tool_untimed_dir / "updates.jsonl", grok_failed_reads(grok_tool_untimed_id, 4))
        (grok_tool_untimed_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_tool_untimed_id}}), encoding="utf-8")
        grok_tool_untimed_run = one_run(ingest_and_evaluate(root, "grok-tool-untimed", grok_tool_untimed_dir, "grok"))
        assert check(grok_tool_untimed_run, "tool.repeat_loop")["status"] == "unknown"
        cases.append("untimed foreign other-tool is possible reset unknown")

        grok_args_untimed_id = "grok-args-untimed"
        grok_args_untimed_dir = root / "grok-args-untimed"
        grok_args_untimed_dir.mkdir()
        write_jsonl(
            grok_args_untimed_dir / "chat_history.jsonl",
            [{"type": "assistant", "content": "", "tool_calls": [{"id": "foreign", "name": "read", "arguments": {"path": "y"}}]}],
        )
        write_jsonl(grok_args_untimed_dir / "events.jsonl", [grok_turn_started(grok_args_untimed_id, "t1")])
        write_jsonl(grok_args_untimed_dir / "updates.jsonl", grok_failed_reads(grok_args_untimed_id, 4))
        (grok_args_untimed_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_args_untimed_id}}), encoding="utf-8")
        grok_args_untimed_run = one_run(ingest_and_evaluate(root, "grok-args-untimed", grok_args_untimed_dir, "grok"))
        assert check(grok_args_untimed_run, "tool.repeat_loop")["status"] == "unknown"
        cases.append("untimed foreign other-args is possible reset unknown")

        grok_tool_eq5_id = "grok-tool-equal-5"
        grok_tool_eq5_dir = root / "grok-tool-equal-5"
        grok_tool_eq5_dir.mkdir()
        write_jsonl(
            grok_tool_eq5_dir / "chat_history.jsonl",
            [{"type": "assistant", "content": "", "tool_calls": [{"id": "foreign", "name": "other", "arguments": {"path": "x"}}], "timestamp": 1726221901}],
        )
        write_jsonl(grok_tool_eq5_dir / "events.jsonl", [grok_turn_started(grok_tool_eq5_id, "t1")])
        write_jsonl(grok_tool_eq5_dir / "updates.jsonl", grok_failed_reads(grok_tool_eq5_id, 5))
        (grok_tool_eq5_dir / "summary.json").write_text(json.dumps({"info": {"id": grok_tool_eq5_id}}), encoding="utf-8")
        grok_tool_eq5_run = one_run(ingest_and_evaluate(root, "grok-tool-equal-5", grok_tool_eq5_dir, "grok"))
        assert check(grok_tool_eq5_run, "tool.repeat_loop")["status"] == "unknown"
        cases.append("equal-time foreign other-tool on five calls is unknown")


        renamed = root / "zz-renamed-grok"
        shutil.copytree(grok_fail_dir, renamed)
        renamed_run = one_run(ingest_and_evaluate(root, "grok-renamed", renamed, "grok"))
        assert check(renamed_run, "tool.repeat_loop")["status"] == "unknown"
        cases.append("renamed Grok completed-without-payload keeps unknown")

        cases.append("Grok agent_message_chunk completion with no evidence is unknown")


        secret_fail = root / "secret-field.jsonl"
        write_jsonl(
            secret_fail,
            omp_session(
                "secret-field",
                [
                    tool_call("sec-1", "env", {"api_key": "sk-livegga3REALSECRET99abcd"}),
                    session_end(),
                ],
            ),
        )
        secret_fail_receipt = ingest_and_evaluate(root, "secret-field", secret_fail, "omp")
        secret_fail_run = one_run(secret_fail_receipt)
        secret_check = check(secret_fail_run, "tool.secret_pattern")
        assert secret_check["status"] == "fail"
        dumped = json.dumps(secret_fail_receipt)
        assert "sk-livegga3REALSECRET99abcd" not in dumped
        assert secret_check["evidence"][0]["evidence_hash"]
        assert secret_check["evidence"][0]["event_range"]
        cases.append("credential-field secret fails with redacted evidence")

        secret_payload = root / "secret-payload.jsonl"
        write_jsonl(
            secret_payload,
            [
                {
                    "timestamp": "2026-09-13T10:00:00Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "see demo/SKILL.md and sk-abcdefghijklmnopqrstuvwxyz012345 in the transcript",
                    },
                },
                {"timestamp": "2026-09-13T10:00:01Z", "type": "event_msg", "payload": {"type": "task_complete"}},
            ],
        )
        secret_payload_receipt = ingest_and_evaluate(root, "secret-payload", secret_payload, "codex")
        assert check(one_run(secret_payload_receipt), "tool.secret_pattern")["status"] == "not_applicable"
        cases.append("non-credential Codex payload does not fail secret_pattern")

        secret_allow = root / "secret-allow.jsonl"
        write_jsonl(
            secret_allow,
            omp_session(
                "secret-allow",
                [
                    tool_call("sec-ex", "env", {"api_key": "sk-examplePLACEHOLDERtokenxx"}),
                    session_end(),
                ],
            ),
        )
        assert check(one_run(ingest_and_evaluate(root, "secret-allow", secret_allow, "omp")), "tool.secret_pattern")["status"] == "pass"
        cases.append("allowlisted example token does not fail secret_pattern")

        missing_skill = root / "missing-skill.jsonl"
        write_jsonl(
            missing_skill,
            omp_session(
                "missing-skill",
                [
                    tool_call("sk-miss", "read", {"path": "/tmp/gga4-missing-skill/SKILL.md"}),
                    session_end(),
                ],
            ),
        )
        missing_skill_run = one_run(ingest_and_evaluate(root, "missing-skill", missing_skill, "omp"))
        assert any(item.get("path", "").endswith("gga4-missing-skill/SKILL.md") for item in missing_skill_run.get("skills") or [])
        assert check(missing_skill_run, "skill.registry_unreadable")["status"] == "fail"
        cases.append("missing real SKILL.md still fails registry_unreadable")

        junk_skill = root / "junk-skill.jsonl"
        write_jsonl(
            junk_skill,
            omp_session(
                "junk-skill",
                [
                    {
                        "type": "message",
                        "message": {
                            "role": "assistant",
                            "content": "mentions 7|SKILL.md ./SKILL.md ~/Code/x/SKILL.md ../other/SKILL.md",
                        },
                    },
                    session_end(),
                ],
            ),
        )
        junk_skill_run = one_run(ingest_and_evaluate(root, "junk-skill", junk_skill, "omp"))
        junk_paths = [str(item.get("path") or "") for item in junk_skill_run.get("skills") or []]
        assert not any("7|" in path or path.endswith("/SKILL.md") and (".." in path or path.startswith("./")) for path in junk_paths)
        assert all("7|" not in path and not path.endswith("./SKILL.md") for path in junk_paths)
        assert check(junk_skill_run, "skill.registry_unreadable")["status"] == "not_applicable"
        cases.append("junk SKILL.md mention tokens do not join the registry")

        unrequested = unknown_receipt.get("provenance", {}).get("workgraph") or {}
        assert unrequested.get("invoked") is False
        assert not unrequested.get("argv")
        cases.append("unrequested workgraph binary is not invoked")

        parent_cmd = workgraph_parent_command(
            root / "unknown-gate-ingest" / "receipt.json",
            root / "workgraph-evaluate",
        )
        result = {
            "status": "pass",
            "catalog_id": unknown_receipt.get("catalog_id"),
            "claim_language_version": unknown_receipt.get("provenance", {}).get("claim_language_version"),
            "cases": cases,
            "scenario_rows": [{"row": index + 1, "scenario": name} for index, name in enumerate(cases)],
            "original_eval_rows": 50,
            "added_unknown_and_order_rows": [
                "missing success in second position is unknown not fail",
                "missing success in third position is unknown not fail",
                "four later proven errors after missing success still fail",
                "equal-time user at second of four calls is unanimous pass",
                "equal-time terminal at second of four calls is unanimous pass",
                "untimed foreign other-tool is possible reset unknown",
                "untimed foreign other-args is possible reset unknown",
                "equal-time foreign other-tool on five calls is unknown",
            ],
            "workgraph_invocation": {
                "executed": False,
                "reason": "parent runs validation after concurrent builders stop",
                "binary": str(WORKGRAPH_BIN),
                "evidence": str(WORKGRAPH_EVIDENCE),
                "command": parent_cmd,
                "expected_closeout": "closeout.eval_score_fail fail because red-baseline hard_pass is false",
            },
            "api": {
                "function": "evaluate_receipt",
                "returns": "(enriched styrir-session-eval/v0 receipt, immutable Path)",
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
