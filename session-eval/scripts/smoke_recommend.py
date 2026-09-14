#!/usr/bin/env python3
"""CLI smoke for session-eval/scripts/recommend.py.

Creates synthetic native sessions, skills, and adapters; runs the real ingest
CLI, evaluate CLI, and recommend CLI.  Recommendations consume evaluated
check rows.  No provider calls.  This file is the executable matrix; it does
not assert that a parent has already run it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

INGEST = Path(__file__).with_name("ingest.py")
EVALUATE = Path(__file__).with_name("evaluate.py")
RECOMMEND = Path(__file__).with_name("recommend.py")
SECRET = "sk-secretTEST123456789"
MARKUP = "<script>alert(1)</script>"
HISTORICAL_A = "sha256:" + hashlib.sha256(b"session-eval-recommend-historical-A").hexdigest()
HISTORICAL_C = "sha256:" + hashlib.sha256(b"session-eval-recommend-historical-C").hexdigest()
STALE_HASH = hashlib.sha256(b"session-eval-unrelated-snapshot").hexdigest()
HASH_SHAPE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if isinstance(row, str):
                handle.write(row.rstrip("\n") + "\n")
            else:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    return json.loads((out / "receipt.json").read_text(encoding="utf-8"))


def evaluate(receipt_path: Path, out: Path, first_party: Path | None = None) -> dict[str, Any]:
    args = ["--receipt", str(receipt_path), "--out", str(out)]
    if first_party is not None:
        args.extend(["--first-party-root", str(first_party)])
    code, stdout, stderr = run_cli(EVALUATE, args)
    if code != 0:
        raise AssertionError(f"evaluate failed ({code}): {stderr or stdout}")
    evaluated = out / "receipt.json"
    if not evaluated.is_file():
        raise AssertionError(f"evaluate did not write {evaluated}: {stdout}")
    return json.loads(evaluated.read_text(encoding="utf-8"))


def recommend(
    receipt_path: Path,
    out: Path,
    first_party: Path,
    adapter_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    args = [
        "--receipt",
        str(receipt_path),
        "--out",
        str(out),
        "--first-party-root",
        str(first_party),
    ]
    if adapter_root is not None:
        args.extend(["--adapter-root", str(adapter_root)])
    command = [sys.executable, str(RECOMMEND), *args]
    code, stdout, stderr = run_cli(RECOMMEND, args)
    if code != 0:
        raise AssertionError(f"recommend failed ({code}): {stderr or stdout}")
    summary = json.loads(stdout)
    written = Path(summary["receipt"])
    return json.loads(written.read_text(encoding="utf-8")), summary, command


def one_run(receipt: dict[str, Any]) -> dict[str, Any]:
    runs = [item for item in (receipt.get("runs") or []) if isinstance(item, dict)]
    assert runs, f"expected runs, coverage={receipt.get('coverage')}"
    return runs[0]


def check(run: dict[str, Any], check_id: str) -> dict[str, Any]:
    matches = [item for item in run.get("checks") or [] if item.get("id") == check_id]
    assert matches, f"missing check {check_id}"
    return matches[0]


def recs(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    rows = receipt.get("recommendations")
    assert isinstance(rows, list), "recommendations must be an array"
    return rows


def actions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("limitation") is None]


def limitations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("limitation") is not None]


def omp_session(session_id: str, rows: list[Any]) -> list[Any]:
    return [
        {"type": "session", "version": 3, "id": session_id, "timestamp": "2026-09-13T10:00:00Z"},
        *rows,
    ]


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "message",
        "id": f"msg-{call_id}",
        "message": {
            "role": "assistant",
            "content": [{"type": "toolCall", "id": call_id, "name": name, "arguments": arguments}],
        },
    }


def assistant_text(turn_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": turn_id,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def session_end() -> dict[str, Any]:
    return {"type": "custom", "customType": "session_end", "timestamp": "2026-09-13T10:09:00Z"}


def grok_session(
    root: Path,
    name: str,
    session_id: str,
    *,
    skill_entries: list[dict[str, Any]] | None = None,
    mention_paths: list[str] | None = None,
    unpaired: bool = True,
    title: str | None = None,
    ended: bool = True,
) -> Path:
    path = root / name
    path.mkdir(parents=True)
    chat: list[Any] = [{"type": "user", "id": "u1", "content": "do the work"}]
    if mention_paths:
        mentioned = " ".join(mention_paths)
        chat.append({"type": "assistant", "id": "a-mention", "content": f"consider {mentioned}"})
    if unpaired:
        chat.append(
            {
                "type": "assistant",
                "id": "a-tool",
                "content": "working",
                "tool_calls": [{"id": f"{session_id}-call", "name": "shell", "arguments": {"command": "status"}}],
            }
        )
    write_jsonl(path / "chat_history.jsonl", chat)
    write_jsonl(
        path / "events.jsonl",
        [
            {
                "type": "turn_started",
                "ts": "2026-09-13T10:05:00Z",
                "params": {"sessionId": session_id, "turnId": "t1", "modelId": "grok-model"},
            }
        ],
    )
    write_jsonl(path / "updates.jsonl", [])
    info: dict[str, Any] = {
        "id": session_id,
        "cwd": str(root),
        "current_model_id": "grok-model",
        "created_at": "2026-09-13T10:05:00Z",
    }
    if ended:
        info["ended_at"] = "2026-09-13T10:09:00Z"
    if title is not None:
        info["title"] = title
    write_json(path / "summary.json", {"info": info})
    if skill_entries:
        write_json(path / "prompt_context.json", {"skills": skill_entries})
    return path


def tree_hashes(paths: list[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        result[str(path)] = sha256_file(path)
    return result


def assert_limitation(row: dict[str, Any], token: str | None = None) -> None:
    assert row["target"] is None
    assert row["action"] is None
    assert row["rationale"] is None
    assert row["verification"] is None
    assert row["confidence"] == "none"
    assert row["limitation"]
    if token is not None:
        assert row["limitation"] == token, row["limitation"]


def assert_action(row: dict[str, Any], *, check_id: str, kind: str) -> None:
    assert row["limitation"] is None
    assert isinstance(row["target"], dict)
    assert row["target"]["kind"] == kind
    assert row["target"]["path"]
    assert HASH_SHAPE.fullmatch(str(row["target"]["digest"] or ""))
    assert row["action"]
    assert row["rationale"]
    assert "Recurring" in row["rationale"] if row["confidence"] == "high" else "Recurring" not in row["rationale"]
    assert row["verification"]
    assert row["confidence"] in {"high", "medium"}
    assert row["evidence"], "actionable row requires evidence"
    for item in row["evidence"]:
        assert item.get("check_id") == check_id
        assert item.get("source_path")
        assert HASH_SHAPE.fullmatch(str(item.get("snapshot_hash") or ""))
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,31}", str(item.get("parser_version") or ""))
        assert isinstance(item.get("event_range"), dict)
        assert isinstance(item["event_range"].get("start_line"), int)
        assert isinstance(item["event_range"].get("end_line"), int)
        assert item["event_range"]["start_line"] >= 1
        assert item["event_range"]["end_line"] >= item["event_range"]["start_line"]
        evidence_hash = item.get("evidence_hash")
        assert evidence_hash == "unknown" or HASH_SHAPE.fullmatch(str(evidence_hash or ""))


def ingest_evaluate_recommend(
    root: Path,
    name: str,
    paths: list[Path],
    harnesses: list[str],
    first_party: Path,
    adapter_root: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    ingested = ingest(root / f"{name}-ingest", paths, harnesses)
    evaluated = evaluate(root / f"{name}-ingest" / "receipt.json", root / f"{name}-evaluate", first_party)
    recommended, summary, command = recommend(
        root / f"{name}-evaluate" / "receipt.json",
        root / f"{name}-recommend",
        first_party,
        adapter_root,
    )
    assert ingested["schema"] == "styrir-session-eval/v0"
    assert evaluated["schema"] == "styrir-session-eval/v0"
    assert recommended["schema"] == "styrir-session-eval/v0"
    assert summary.get("provider_calls") == 0
    return recommended, evaluated, command


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="session-eval-recommend-smoke-") as temporary:
        root = Path(temporary)
        first_party = root / "first-party"
        host = root / "host-skills"
        external = root / "external"
        adapters = first_party / "adapters"
        (first_party / "demo").mkdir(parents=True)
        (host / "demo").mkdir(parents=True)
        (host / "vendor").mkdir(parents=True)
        (external / "vendor").mkdir(parents=True)
        adapters.mkdir(parents=True)
        demo = first_party / "demo" / "SKILL.md"
        demo.write_text("---\nname: demo\nversion: 2.0.0\n---\ncurrent-bytes-B\n", encoding="utf-8")
        current_b = "sha256:" + sha256_file(demo)
        os.symlink(demo, host / "demo" / "SKILL.md")
        (first_party / "other").mkdir(parents=True)
        other = first_party / "other" / "SKILL.md"
        other.write_text("---\nname: other\nversion: 1.0.0\n---\nother-bytes\n", encoding="utf-8")
        vendor = external / "vendor" / "SKILL.md"
        vendor.write_text("---\nname: vendor\n---\nthird-party\n", encoding="utf-8")
        os.symlink(vendor, host / "vendor" / "SKILL.md")
        adapter_file = adapters / "omp-v3-adapter.py"
        adapter_file.write_text("# first-party omp adapter stand-in\nprint('adapter')\n", encoding="utf-8")
        missing_skill = host / "gone" / "SKILL.md"

        tracked = [
            demo,
            other,
            vendor,
            adapter_file,
            host / "demo" / "SKILL.md",
            host / "vendor" / "SKILL.md",
        ]
        before = tree_hashes(tracked)

        matrix: list[dict[str, Any]] = []
        commands: list[list[str]] = []

        first_a = grok_session(
            root,
            "fp-a",
            "fp-unpaired-a",
            skill_entries=[{"path": str(host / "demo" / "SKILL.md"), "digest": HISTORICAL_A}],
            unpaired=True,
            title="first-party A",
        )
        first_b = grok_session(
            root,
            "fp-b",
            "fp-unpaired-b",
            skill_entries=[{"path": str(host / "demo" / "SKILL.md"), "digest": HISTORICAL_A}],
            unpaired=True,
            title="first-party B",
        )
        tracked.extend(
            [
                first_a / "chat_history.jsonl",
                first_a / "events.jsonl",
                first_a / "updates.jsonl",
                first_a / "summary.json",
                first_a / "prompt_context.json",
                first_b / "chat_history.jsonl",
                first_b / "events.jsonl",
                first_b / "updates.jsonl",
                first_b / "summary.json",
                first_b / "prompt_context.json",
            ]
        )
        before = tree_hashes(tracked)
        actionable, actionable_eval, cmd = ingest_evaluate_recommend(
            root, "actionable-firstparty", [first_a, first_b], ["grok"], first_party, adapters
        )
        commands.append(cmd)
        unpaired_fail = 0
        for run in actionable_eval.get("runs") or []:
            row = check(run, "tool.unpaired")
            if row["status"] == "fail":
                unpaired_fail += 1
        assert unpaired_fail >= 2, f"expected repeated tool.unpaired fail, got {unpaired_fail}"
        actionable_rows = recs(actionable)
        skill_actions = [
            row
            for row in actions(actionable_rows)
            if row["target"]["kind"] == "skill" and any(item.get("check_id") == "tool.unpaired" for item in row["evidence"])
        ]
        assert skill_actions, actionable_rows
        skill_row = skill_actions[0]
        assert_action(skill_row, check_id="tool.unpaired", kind="skill")
        assert skill_row["confidence"] == "high"
        assert HISTORICAL_A in {skill_row["target"]["digest"], skill_row["rationale"]} or skill_row["target"]["digest"] == HISTORICAL_A
        assert skill_row["target"]["digest"] == HISTORICAL_A
        assert skill_row["target"]["digest"] != current_b
        assert str(demo.resolve()) in skill_row["target"]["path"] or Path(skill_row["target"]["path"]).resolve() == demo.resolve()
        matrix.append(
            {
                "id": "actionable-firstparty",
                "scenario": "repeated-firstparty-unpaired",
                "expected": "Non-null target/action/rationale/verification; evidence includes tool.unpaired and snapshot spans; high confidence; historical digest A",
                "observed": {
                    "id": skill_row["id"],
                    "target": skill_row["target"],
                    "confidence": skill_row["confidence"],
                    "check_ids": sorted({item["check_id"] for item in skill_row["evidence"]}),
                },
            }
        )

        empty_dir = root / "empty-inputs"
        empty_dir.mkdir()
        empty_rec, empty_eval, cmd = ingest_evaluate_recommend(
            root, "insufficient-empty", [empty_dir], ["omp"], first_party, adapters
        )
        commands.append(cmd)
        empty_rows = recs(empty_rec)
        assert empty_eval["coverage"]["empty"] is True
        assert limitations(empty_rows), empty_rows
        for row in limitations(empty_rows):
            assert_limitation(row)
        assert not actions(empty_rows)
        matrix.append(
            {
                "id": "insufficient-evidence",
                "scenario": "empty-evaluation",
                "expected": "Explicit limitation row; target/action/rationale/verification null and confidence none",
                "observed": {
                    "limitations": [row["limitation"] for row in limitations(empty_rows)],
                    "actionable": len(actions(empty_rows)),
                },
            }
        )

        complete = root / "completion-unknown.jsonl"
        write_jsonl(
            complete,
            omp_session(
                "completion-unknown",
                [
                    assistant_text("done-1", "The implementation is complete."),
                    session_end(),
                ],
            ),
        )
        tracked.append(complete)
        before = tree_hashes(tracked)
        unknown_rec, unknown_eval, cmd = ingest_evaluate_recommend(
            root, "insufficient-completion", [complete], ["omp"], first_party, adapters
        )
        commands.append(cmd)
        unknown_run = one_run(unknown_eval)
        assert check(unknown_run, "claim.completion")["status"] == "unknown"
        unknown_rows = recs(unknown_rec)
        completion_limits = [
            row
            for row in limitations(unknown_rows)
            if row["limitation"] in {"recommend.unknown_completion_outcome", "recommend.historical_policy_unavailable", "recommend.missing_target_attribution"}
        ]
        assert completion_limits, unknown_rows
        for row in completion_limits:
            assert_limitation(row)
        assert not [
            row
            for row in actions(unknown_rows)
            if any(item.get("check_id") == "claim.completion" for item in row.get("evidence") or [])
        ]
        matrix.append(
            {
                "id": "insufficient-evidence",
                "scenario": "completion-claim-no-outcomes",
                "expected": "Limitation for unknown completion; no invented patch",
                "observed": {
                    "claim.completion": check(unknown_run, "claim.completion")["status"],
                    "limitations": [row["limitation"] for row in completion_limits],
                    "proof_gaps_preserved": bool(unknown_rec.get("proof_gaps") is not None),
                },
            }
        )

        ext_session = grok_session(
            root,
            "external-only",
            "external-unpaired",
            skill_entries=[{"path": str(host / "vendor" / "SKILL.md"), "digest": "sha256:historical-vendor"}],
            unpaired=True,
        )
        missing_session = grok_session(
            root,
            "missing-only",
            "missing-unpaired",
            skill_entries=[{"path": str(missing_skill), "digest": "sha256:historical-gone"}],
            unpaired=True,
        )
        tracked.extend(
            [
                ext_session / "chat_history.jsonl",
                ext_session / "prompt_context.json",
                missing_session / "chat_history.jsonl",
                missing_session / "prompt_context.json",
            ]
        )
        before = tree_hashes(tracked)
        ownership_rec, ownership_eval, cmd = ingest_evaluate_recommend(
            root,
            "ownership",
            [first_a, ext_session, missing_session],
            ["grok"],
            first_party,
            adapters,
        )
        commands.append(cmd)
        ownership_rows = recs(ownership_rec)
        fp_actions = [
            row
            for row in actions(ownership_rows)
            if row["target"]["kind"] == "skill" and any(item.get("check_id") == "tool.unpaired" for item in row["evidence"])
        ]
        assert fp_actions
        assert all("vendor" not in str(row["target"]["path"]) for row in fp_actions)
        ext_limits = [row for row in limitations(ownership_rows) if row["limitation"] == "recommend.external_target"]
        unresolved_limits = [row for row in limitations(ownership_rows) if row["limitation"] == "recommend.unresolved_target"]
        assert ext_limits, ownership_rows
        assert unresolved_limits, ownership_rows
        for row in ext_limits + unresolved_limits:
            assert_limitation(row)
            assert row["action"] is None
        matrix.append(
            {
                "id": "ownership",
                "scenario": "symlink-firstparty-vs-external-vs-missing",
                "expected": "Only resolved configured-firstparty target actionable; external/unresolved limitation",
                "observed": {
                    "first_party_actions": [row["target"]["path"] for row in fp_actions],
                    "external_limitations": len(ext_limits),
                    "unresolved_limitations": len(unresolved_limits),
                    "evaluated_unpaired": [
                        check(run, "tool.unpaired")["status"] for run in ownership_eval.get("runs") or [] if isinstance(run, dict)
                    ],
                },
            }
        )

        mention = grok_session(
            root,
            "mention-only",
            "mention-unpaired",
            mention_paths=[str(host / "demo" / "SKILL.md")],
            unpaired=True,
        )
        tracked.extend([mention / "chat_history.jsonl", mention / "summary.json"])
        before = tree_hashes(tracked)
        hist_rec, hist_eval, cmd = ingest_evaluate_recommend(
            root, "historical-vs-current", [first_a, mention], ["grok"], first_party, adapters
        )
        commands.append(cmd)
        hist_rows = recs(hist_rec)
        hist_actions = [
            row
            for row in actions(hist_rows)
            if row["target"]["kind"] == "skill" and any(item.get("check_id") == "tool.unpaired" for item in row["evidence"])
        ]
        assert hist_actions
        for row in hist_actions:
            assert row["target"]["digest"] == HISTORICAL_A
            assert row["target"]["digest"] != current_b
        mention_limits = [row for row in limitations(hist_rows) if row["limitation"] == "recommend.mention_only"]
        assert mention_limits, hist_rows
        for row in mention_limits:
            assert_limitation(row)
        mention_run = None
        for run in hist_eval.get("runs") or []:
            skills = run.get("skills") or []
            if any(item.get("confidence") == "low" for item in skills if isinstance(item, dict)):
                mention_run = run
                break
        matrix.append(
            {
                "id": "historical-vs-current",
                "scenario": "historical-A-vs-current-B-and-mention-only",
                "expected": "No attribution to current digest B; mention-only insufficient; immutable A preserved",
                "observed": {
                    "action_digests": [row["target"]["digest"] for row in hist_actions],
                    "current_b": current_b,
                    "mention_limitations": [row["limitation"] for row in mention_limits],
                    "mention_run_present": mention_run is not None,
                },
            }
        )

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
        tracked.append(malformed)
        before = tree_hashes(tracked)
        adapter_rec, adapter_eval, cmd = ingest_evaluate_recommend(
            root, "adapter-target", [malformed], ["omp"], first_party, adapters
        )
        commands.append(cmd)
        adapter_run = one_run(adapter_eval)
        assert check(adapter_run, "ingest.parse_error")["status"] == "fail"
        adapter_rows = recs(adapter_rec)
        adapter_actions = [row for row in actions(adapter_rows) if row["target"]["kind"] == "adapter"]
        assert not adapter_actions, adapter_actions
        adapter_limits = [
            row
            for row in limitations(adapter_rows)
            if row["limitation"] == "recommend.unresolved_target"
            and any(item.get("check_id") == "ingest.parse_error" for item in row.get("evidence") or [])
        ]
        assert adapter_limits, adapter_rows
        for row in adapter_limits:
            assert_limitation(row)
            assert "remains fail" not in str(row.get("verification") or "")
        matrix.append(
            {
                "id": "adapter-target",
                "scenario": "no-explicit-adapter-association",
                "expected": "Concrete adapter action only when canonical provenance associates an existing first-party adapter path; filename/root guesses yield a null limitation",
                "observed": {
                    "adapter_actions": len(adapter_actions),
                    "limitations": [row["limitation"] for row in adapter_limits],
                    "guessed_standin_unused": True,
                },
            }
        )

        no_adapter_rec, _, cmd = ingest_evaluate_recommend(
            root, "adapter-unresolved", [malformed], ["omp"], first_party, first_party / "missing-adapters"
        )
        commands.append(cmd)
        no_adapter_limits = [
            row
            for row in limitations(recs(no_adapter_rec))
            if row["limitation"] in {"recommend.unresolved_target", "recommend.missing_target_attribution"}
            and any(item.get("check_id") == "ingest.parse_error" for item in row.get("evidence") or [])
        ]
        assert no_adapter_limits, recs(no_adapter_rec)
        for row in no_adapter_limits:
            assert_limitation(row)

        det_rec = actionable
        det_actions = [
            row
            for row in actions(recs(det_rec))
            if any(item.get("check_id") == "tool.unpaired" for item in row["evidence"])
        ]
        judged = copy.deepcopy(actionable_eval)
        judge_evidence = None
        for run in judged.get("runs") or []:
            for item in run.get("checks") or []:
                if item.get("id") == "tool.unpaired" and item.get("status") == "fail" and item.get("evidence"):
                    judge_evidence = copy.deepcopy(item["evidence"])
                    break
            if judge_evidence:
                break
        assert judge_evidence
        injected = False
        for run in judged.get("runs") or []:
            checks = run.get("checks") or []
            for item in checks:
                if item.get("id") == "judge.completeness":
                    item["status"] = "fail"
                    item["observed"] = "undisclosed_unmet_request"
                    item["evidence"] = judge_evidence
                    item["error"] = None
                    item["judge"] = {
                        "rubric_id": "judge.completeness",
                        "rubric_set": "session-eval-judge-rubrics/v1",
                        "model": "named-model",
                        "provider": "named-provider",
                        "approval_id": None,
                        "explanation": f"token {SECRET} must never be copied",
                    }
                    injected = True
        assert injected
        judged_path = root / "judge-optional" / "input.json"
        write_json(judged_path, judged)
        judged_out, judged_summary, cmd = recommend(judged_path, root / "judge-optional-out", first_party, adapters)
        commands.append(cmd)
        assert judged_summary.get("provider_calls") == 0
        judged_rows = recs(judged_out)
        judged_unpaired = [
            row
            for row in actions(judged_rows)
            if any(item.get("check_id") == "tool.unpaired" for item in row["evidence"])
        ]
        judged_judge = [
            row
            for row in actions(judged_rows)
            if any(item.get("check_id") == "judge.completeness" for item in row["evidence"])
        ]
        assert judged_unpaired, judged_rows
        assert judged_judge, judged_rows
        for row in judged_judge:
            assert_action(row, check_id="judge.completeness", kind="skill")
            dumped = json.dumps(row, ensure_ascii=False)
            assert SECRET not in dumped
            assert "token sk-" not in dumped
        matrix.append(
            {
                "id": "judge-optional",
                "scenario": "deterministic-without-and-with-judge-findings",
                "expected": "Deterministic recommendations work without judges; optional judge rows use same evidence schema and do not trigger provider calls",
                "observed": {
                    "deterministic_without_judges": [row["id"] for row in det_actions],
                    "deterministic_with_judges": [row["id"] for row in judged_unpaired],
                    "judge_rows": [row["id"] for row in judged_judge],
                    "provider_calls": judged_summary.get("provider_calls"),
                },
            }
        )

        private_session = grok_session(
            root,
            "privacy",
            "privacy-unpaired",
            skill_entries=[{"path": str(host / "demo" / "SKILL.md"), "digest": HISTORICAL_A}],
            unpaired=True,
            title=MARKUP,
        )
        tracked.extend([private_session / "summary.json", private_session / "chat_history.jsonl"])
        before = tree_hashes(tracked)
        private_eval_doc, private_eval, cmd = ingest_evaluate_recommend(
            root, "privacy-base", [private_session], ["grok"], first_party, adapters
        )
        commands.append(cmd)
        private_input = copy.deepcopy(private_eval)
        for run in private_input.get("runs") or []:
            run["display_name"] = MARKUP
            for skill in run.get("skills") or []:
                if isinstance(skill, dict):
                    skill["digest"] = "sha256:" + SECRET
                    skill["historical_loaded_digest"] = "sha256:" + SECRET
            for item in run.get("checks") or []:
                if item.get("id") == "tool.unpaired":
                    item["secret"] = SECRET
                    item["metadata"] = {"token": SECRET, "html": MARKUP}
                    rewritten = []
                    for pointer in item.get("evidence") or []:
                        if not isinstance(pointer, dict):
                            continue
                        cloned = copy.deepcopy(pointer)
                        cloned["snapshot_hash"] = "sha256:" + SECRET
                        cloned["parser_version"] = SECRET
                        cloned["evidence_hash"] = SECRET
                        rewritten.append(cloned)
                    item["evidence"] = rewritten
        private_path = root / "privacy-input.json"
        write_json(private_path, private_input)
        private_rec, _, cmd = recommend(private_path, root / "privacy-recommend", first_party, adapters)
        commands.append(cmd)
        dumped = json.dumps(private_rec.get("recommendations"), ensure_ascii=False)
        assert SECRET not in dumped
        assert MARKUP not in dumped
        assert "<script>" not in dumped
        assert not actions(recs(private_rec)) or all(
            SECRET not in json.dumps(row, ensure_ascii=False) for row in recs(private_rec)
        )
        matrix.append(
            {
                "id": "privacy",
                "scenario": "secrets-and-markup-redacted",
                "expected": "No raw payload/secret in exported recommendation; malformed structural hashes rejected without reexport",
                "observed": {
                    "secret_absent": SECRET not in dumped,
                    "markup_absent": MARKUP not in dumped,
                    "rows": [row["id"] for row in recs(private_rec)],
                    "limitations": [row["limitation"] for row in limitations(recs(private_rec))],
                },
            }
        )

        demo_skill = {
            "name": "demo",
            "path": str(demo.resolve()),
            "digest": HISTORICAL_A,
            "source": "grok.prompt_context",
            "confidence": "high",
        }
        other_skill = {
            "name": "other",
            "path": str(other.resolve()),
            "digest": HISTORICAL_C,
            "source": "grok.prompt_context",
            "confidence": "high",
        }
        base_one = copy.deepcopy(actionable_eval)
        base_one["runs"] = [copy.deepcopy(actionable_eval["runs"][0])]
        order_ab = copy.deepcopy(base_one)
        order_ab["runs"][0]["skills"] = [demo_skill, other_skill]
        order_ba = copy.deepcopy(base_one)
        order_ba["runs"][0]["skills"] = [other_skill, demo_skill]
        write_json(root / "ambiguous-ab.json", order_ab)
        write_json(root / "ambiguous-ba.json", order_ba)
        ab_rec, _, cmd = recommend(root / "ambiguous-ab.json", root / "ambiguous-ab-out", first_party, adapters)
        commands.append(cmd)
        ba_rec, _, cmd = recommend(root / "ambiguous-ba.json", root / "ambiguous-ba-out", first_party, adapters)
        commands.append(cmd)
        ab_unpaired = [
            row
            for row in actions(recs(ab_rec))
            if any(item.get("check_id") == "tool.unpaired" for item in row.get("evidence") or [])
        ]
        ba_unpaired = [
            row
            for row in actions(recs(ba_rec))
            if any(item.get("check_id") == "tool.unpaired" for item in row.get("evidence") or [])
        ]
        assert not ab_unpaired and not ba_unpaired
        ab_limits = [row for row in limitations(recs(ab_rec)) if row["limitation"] == "recommend.ambiguous_target"]
        ba_limits = [row for row in limitations(recs(ba_rec)) if row["limitation"] == "recommend.ambiguous_target"]
        assert ab_limits and ba_limits
        for row in ab_limits + ba_limits:
            assert_limitation(row)
        assert [row["limitation"] for row in recs(ab_rec) if row.get("limitation")] == [
            row["limitation"] for row in recs(ba_rec) if row.get("limitation")
        ]
        matrix.append(
            {
                "id": "ambiguous-target-order",
                "scenario": "two-authoritative-skills-list-order",
                "expected": "Multiple plausible first-party skills with no evidence binding yield the same null limitation regardless of list order",
                "observed": {
                    "ab_actions": len(ab_unpaired),
                    "ba_actions": len(ba_unpaired),
                    "limitation": ab_limits[0]["limitation"],
                },
            }
        )

        single = copy.deepcopy(base_one)
        for item in single["runs"][0].get("checks") or []:
            if item.get("id") == "tool.unpaired" and item.get("evidence"):
                item["evidence"] = list(item["evidence"]) + copy.deepcopy(item["evidence"])
        write_json(root / "pointer-count.json", single)
        pointer_rec, _, cmd = recommend(root / "pointer-count.json", root / "pointer-count-out", first_party, adapters)
        commands.append(cmd)
        pointer_actions = [
            row
            for row in actions(recs(pointer_rec))
            if any(item.get("check_id") == "tool.unpaired" for item in row["evidence"])
        ]
        assert pointer_actions
        for row in pointer_actions:
            assert_action(row, check_id="tool.unpaired", kind="skill")
            assert row["confidence"] == "medium"
            assert "Recurring" not in row["rationale"]
        matrix.append(
            {
                "id": "recurrence-runs-not-pointers",
                "scenario": "one-fail-two-spans",
                "expected": "Recurrence counts distinct failed runs, not pointer count; one check with two spans stays medium/non-recurring",
                "observed": {
                    "confidence": pointer_actions[0]["confidence"],
                    "rationale": pointer_actions[0]["rationale"],
                    "evidence_count": len(pointer_actions[0]["evidence"]),
                },
            }
        )

        incomplete = copy.deepcopy(base_one)
        for item in incomplete["runs"][0].get("checks") or []:
            if item.get("id") == "tool.unpaired":
                for pointer in item.get("evidence") or []:
                    if isinstance(pointer, dict):
                        pointer.pop("parser_version", None)
                        pointer.pop("evidence_hash", None)
        write_json(root / "incomplete-pointer.json", incomplete)
        inc_rec, _, cmd = recommend(root / "incomplete-pointer.json", root / "incomplete-pointer-out", first_party, adapters)
        commands.append(cmd)
        inc_actions = [
            row
            for row in actions(recs(inc_rec))
            if any(item.get("check_id") == "tool.unpaired" for item in row.get("evidence") or [])
        ]
        assert not inc_actions
        inc_limits = [row for row in limitations(recs(inc_rec)) if row["limitation"] == "recommend.insufficient_evidence"]
        assert inc_limits
        stale = copy.deepcopy(base_one)
        for item in stale["runs"][0].get("checks") or []:
            if item.get("id") == "tool.unpaired":
                for pointer in item.get("evidence") or []:
                    if isinstance(pointer, dict):
                        pointer["snapshot_hash"] = STALE_HASH
        write_json(root / "stale-pointer.json", stale)
        stale_rec, _, cmd = recommend(root / "stale-pointer.json", root / "stale-pointer-out", first_party, adapters)
        commands.append(cmd)
        stale_actions = [
            row
            for row in actions(recs(stale_rec))
            if any(item.get("check_id") == "tool.unpaired" for item in row.get("evidence") or [])
        ]
        assert not stale_actions
        stale_limits = [row for row in limitations(recs(stale_rec)) if row["limitation"] == "recommend.insufficient_evidence"]
        assert stale_limits
        matrix.append(
            {
                "id": "pointer-completeness",
                "scenario": "incomplete-and-stale-pointers",
                "expected": "Missing required pointer fields or unrelated snapshot hash yield insufficient-evidence limitations, not actions",
                "observed": {
                    "incomplete_actions": len(inc_actions),
                    "stale_actions": len(stale_actions),
                    "incomplete_limitations": [row["limitation"] for row in inc_limits],
                    "stale_limitations": [row["limitation"] for row in stale_limits],
                },
            }
        )

        mixed = copy.deepcopy(actionable_eval)
        for item in mixed["runs"][0].get("checks") or []:
            if item.get("id") == "tool.repeat_loop":
                item["status"] = "unknown"
        write_json(root / "unknown-alongside.json", mixed)
        mixed_rec, _, cmd = recommend(root / "unknown-alongside.json", root / "unknown-alongside-out", first_party, adapters)
        commands.append(cmd)
        mixed_actions = [
            row
            for row in actions(recs(mixed_rec))
            if any(item.get("check_id") == "tool.unpaired" for item in row["evidence"])
        ]
        unknown_repeat = [
            row
            for row in limitations(recs(mixed_rec))
            if row["limitation"] == "recommend.unknown_finding"
            and any(item.get("check_id") == "tool.repeat_loop" for item in row.get("evidence") or [])
        ]
        assert mixed_actions
        assert unknown_repeat, recs(mixed_rec)
        opt_out_rows = [
            row
            for row in recs(actionable)
            if any(item.get("check_id") == "judge.completeness" for item in row.get("evidence") or [])
        ]
        assert not opt_out_rows
        matrix.append(
            {
                "id": "unknown-retained",
                "scenario": "unknown-hard-check-alongside-action",
                "expected": "Material unknown findings remain null limitations beside actions; judge opt-out not_applicable is not a fake failure",
                "observed": {
                    "unpaired_actions": len(mixed_actions),
                    "unknown_limitations": [row["limitation"] for row in limitations(recs(mixed_rec)) if row["limitation"] == "recommend.unknown_finding"],
                    "opt_out_judge_rows": len(opt_out_rows),
                },
            }
        )

        after = tree_hashes(tracked)
        assert after == before, {key: (before[key], after[key]) for key in before if before[key] != after.get(key)}
        matrix.append(
            {
                "id": "readonly",
                "scenario": "ingest-evaluate-recommend-hashes",
                "expected": "All source/skill/adapter hashes identical afterward; only output artifacts written",
                "observed": {"files": len(after), "unchanged": after == before},
            }
        )

        first_again, first_summary, cmd = recommend(
            root / "actionable-firstparty-evaluate" / "receipt.json",
            root / "repeat-a",
            first_party,
            adapters,
        )
        commands.append(cmd)
        second_again, second_summary, cmd = recommend(
            root / "actionable-firstparty-evaluate" / "receipt.json",
            root / "repeat-b",
            first_party,
            adapters,
        )
        commands.append(cmd)
        third_again, _, cmd = recommend(
            root / "actionable-firstparty-evaluate" / "receipt.json",
            root / "repeat-a",
            first_party,
            adapters,
        )
        commands.append(cmd)
        assert recs(first_again) == recs(second_again)
        assert recs(first_again) == recs(third_again)
        assert first_summary["receipt"] != second_summary["receipt"] or recs(first_again) == recs(second_again)
        identity = [row["id"] for row in recs(first_again)]
        assert identity == [row["id"] for row in recs(second_again)]
        assert json.dumps(recs(first_again), sort_keys=True) == json.dumps(recs(third_again), sort_keys=True)
        matrix.append(
            {
                "id": "repeat-identity",
                "scenario": "same-evidence-rerun",
                "expected": "Stable recommendation identity and immutable results; no duplicate invented trend/correction history",
                "observed": {
                    "ids": identity,
                    "identical_rows": recs(first_again) == recs(second_again),
                    "same_out_reuse": recs(first_again) == recs(third_again),
                },
            }
        )

        result = {
            "status": "pass",
            "api": {
                "function": "recommend_receipt",
                "signature": "recommend_receipt(receipt, *, out=None, first_party_root=None, adapter_root=None) -> (receipt, Path)",
                "cli": "python3 session-eval/scripts/recommend.py --receipt RECEIPT --out OUT [--first-party-root ROOT] [--adapter-root ROOT]",
                "returns": "(enriched styrir-session-eval/v0 receipt, immutable Path)",
            },
            "provider_calls": 0,
            "matrix": matrix,
            "commands": [" ".join(item) for item in commands],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
