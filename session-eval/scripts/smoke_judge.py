#!/usr/bin/env python3
"""Synthetic regression matrix for session-eval/scripts/judge.py.

Builder does not execute this file and does not call a provider. Parent runs
local rows, inspects the preview payload, then requests direct user approval
before any real-provider invocation.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import ingest as ingest_mod
import judge as judge_mod
from judge import (
    JUDGE_IDS,
    PRECLASSIFIED_KEYS,
    RUBRICS,
    approve_interactively,
    judge_receipt,
    prepare_judge_request,
)


PROVIDER = "anthropic"
MODEL = "claude-opus-5"
REAL_RECIPIENT = "http://127.0.0.1:8318/v1/chat/completions"
SECRET = "sk-live-SMOKESECRETVALUE99"
_CONTRACT = Path(__file__).resolve().parent.parent / "references" / "judge-contract.md"


def _strip_md(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = text.replace("**", "")
    return " ".join(text.split())


def load_contract_rubrics() -> dict[str, dict[str, Any]]:
    text = _CONTRACT.read_text(encoding="utf-8")
    parts = re.split(r"^## Rubric: ", text, flags=re.M)
    found: dict[str, dict[str, Any]] = {}
    for part in parts[1:]:
        header, _, body = part.partition("\n")
        match = re.match(r"`([^`]+)`", header.strip())
        if not match:
            continue
        rubric_id = match.group(1)

        def field(label: str, source: str = body) -> str:
            matched = re.search(rf"\*\*{re.escape(label)}\.\*\*\s*(.+)", source)
            return _strip_md(matched.group(1)) if matched else ""

        obs_match = re.search(r"`observed`(?: tokens)?:\s*(.+)", body)
        tokens = re.findall(r"`([^`]+)`", obs_match.group(1)) if obs_match else []
        found[rubric_id] = {
            "question": field("Question"),
            "pass": field("Pass"),
            "fail": field("Fail"),
            "unknown": field("Unknown"),
            "observed": tokens,
        }
    return found


def outbound_messages(preview: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    bodies = preview.get("payload") or []
    if not bodies or not isinstance(bodies[0], dict):
        raise AssertionError("missing payload body")
    messages = bodies[0].get("messages") or []
    system = next((item.get("content") or "" for item in messages if isinstance(item, dict) and item.get("role") == "system"), "")
    user_raw = next((item.get("content") or "" for item in messages if isinstance(item, dict) and item.get("role") == "user"), "")
    user = json.loads(str(user_raw))
    if not isinstance(user, dict):
        raise AssertionError("user payload is not an object")
    return str(system), user


def assert_no_preclassified(value: Any) -> None:
    if isinstance(value, dict):
        overlap = {str(key) for key in value} & PRECLASSIFIED_KEYS
        assert not overlap, overlap
        for inner in value.values():
            assert_no_preclassified(inner)
    elif isinstance(value, list):
        for inner in value:
            assert_no_preclassified(inner)


def assert_runtime_matches_contract(spec_map: dict[str, dict[str, Any]]) -> None:
    assert set(spec_map) == set(JUDGE_IDS), spec_map.keys()
    for rubric_id in JUDGE_IDS:
        spec = spec_map[rubric_id]
        runtime = RUBRICS[rubric_id]
        assert runtime["question"] == spec["question"], (rubric_id, runtime["question"], spec["question"])
        assert runtime["pass"] == spec["pass"], (rubric_id, runtime["pass"], spec["pass"])
        assert runtime["fail"] == spec["fail"], (rubric_id, runtime["fail"], spec["fail"])
        assert runtime["unknown"] == spec["unknown"], (rubric_id, runtime["unknown"], spec["unknown"])
        tokens = spec["observed"]
        assert len(tokens) == 4, (rubric_id, tokens)
        assert runtime["observed"]["pass"] == tokens[0]
        assert runtime["observed"]["fail"] == tokens[1]
        assert runtime["observed"]["unknown"] == tokens[2]
        assert runtime["observed"]["provider"] == tokens[3]


def assert_outbound_matches_contract(preview: dict[str, Any], rubric_id: str, spec: dict[str, Any]) -> None:
    system, user = outbound_messages(preview)
    rubric = user.get("rubric")
    assert isinstance(rubric, dict), user
    assert rubric.get("question") == spec["question"]
    predicates = rubric.get("predicates") or {}
    assert predicates.get("pass") == spec["pass"]
    assert predicates.get("fail") == spec["fail"]
    assert predicates.get("unknown") == spec["unknown"]
    assert rubric.get("allowed_observed") == spec["observed"]
    pairing = rubric.get("status_observed_pairing") or {}
    assert pairing.get("pass") == [spec["observed"][0]]
    assert pairing.get("fail") == [spec["observed"][1]]
    unknown_pair = pairing.get("unknown") or []
    assert spec["observed"][2] in unknown_pair
    assert spec["observed"][3] in unknown_pair
    blob = system + canonical(user)
    assert spec["question"] in blob
    for token in spec["observed"]:
        assert token in blob
    assert_no_preclassified(user.get("evidence") or [])
    assert preview["payload_hash"] == sha256_text(canonical(preview.get("payload") or []))



class TTY:
    """Minimal TTY stand-in. Does not subclass TextIOBase (encoding is read-only there)."""

    def __init__(self, data: str = "") -> None:
        self._buf = io.StringIO(data)

    def isatty(self) -> bool:
        return True

    def readline(self, *args: Any, **kwargs: Any) -> str:
        return self._buf.readline(*args, **kwargs)

    def write(self, s: str) -> int:
        return len(s) if s else 0

    def flush(self) -> None:
        return None


def _loopback_synthetic_recipient(recipient: str) -> bool:
    if not recipient.startswith("http://127.0.0.1:"):
        return False
    if ":8318" in recipient or recipient.endswith("://127.0.0.1:8318") or "/127.0.0.1:8318/" in recipient:
        return False
    return True


def grant(preview: dict[str, Any]) -> Any:
    recipient = str(preview.get("recipient") or "")
    if not _loopback_synthetic_recipient(recipient):
        raise AssertionError("simulated approval is bound to the loopback synthetic test server only")
    token = str(preview.get("payload_hash") or "")[:12]
    old_in, old_out = sys.stdin, sys.stdout
    sys.stdin = TTY(f"APPROVE {token}\n")
    sys.stdout = TTY()
    try:
        capability = approve_interactively(preview)
    finally:
        sys.stdin, sys.stdout = old_in, old_out
    if capability is None:
        raise AssertionError("interactive approval did not grant a capability")
    return capability


def canonical(value: Any) -> str:
    return ingest_mod._canonical(value)


def sha256_bytes(value: bytes) -> str:
    return ingest_mod.sha256_bytes(value)


def sha256_text(value: str) -> str:
    return ingest_mod.sha256_text(value)


def line_hash(content: bytes, start: int, end: int | None = None) -> str:
    end_line = end or start
    offset = 0
    line_no = 0
    chunks: list[bytes] = []
    while offset <= len(content):
        nl = content.find(b"\n", offset)
        if nl == -1:
            raw = content[offset:]
            offset = len(content) + 1
        else:
            raw = content[offset : nl + 1]
            offset = nl + 1
        line_no += 1
        if start <= line_no <= end_line:
            chunks.append(raw)
        if line_no >= end_line:
            break
        if nl == -1:
            break
    return sha256_bytes(b"".join(chunks))


def write_frozen(snapshot_root: Path, source_path: str, content: bytes, role: str = "primary") -> tuple[str, list[dict[str, str]]]:
    digest = sha256_bytes(content)
    token = sha256_text(f"{source_path}:{role}")[:12]
    dest_dir = snapshot_root / digest
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"000-{token}-{Path(source_path).name}"
    dest.write_bytes(content)
    manifest = [{"path": source_path, "role": role, "sha256": digest}]
    return sha256_text(canonical(manifest)), manifest


def base_receipt(
    run_id: str,
    source_path: str,
    snapshot_hash: str,
    files: list[dict[str, str]],
    *,
    hard_pass: bool = False,
    infra_ok: bool = True,
    checks: list[dict[str, Any]] | None = None,
    lifecycle: str = "terminal",
) -> dict[str, Any]:
    deterministic = checks or [
        {
            "id": "tool.unpaired",
            "class": "hard_fail",
            "kind": "code",
            "channel": "behavior",
            "status": "fail" if not hard_pass else "pass",
            "observed": "unpaired_after_explicit_end" if not hard_pass else "all_paired",
            "evidence": [],
            "error": None,
        }
    ]
    run = {
        "id": run_id,
        "harness": "omp",
        "native_identity": {"id": run_id.split(":", 1)[-1], "kind": "session_id", "source": "id"},
        "display_name": "judge-smoke",
        "parser": "omp-jsonl-adapter",
        "parser_version": "1.0.0",
        "source_path": source_path,
        "source_snapshot": {"sha256": snapshot_hash, "files": files},
        "started_at": "2026-09-13T10:00:00Z",
        "ended_at": "2026-09-13T11:00:00Z",
        "cwd": "unknown",
        "model": "unknown",
        "tokens": {"input": "unknown", "output": "unknown", "cache_read": "unknown", "cache_create": "unknown", "total": "unknown"},
        "cost_usd": "unknown",
        "usage_provenance": [],
        "skills": [],
        "lineage": {},
        "turns": [],
        "checks": list(deterministic) + [
            {
                "id": check_id,
                "class": "expected_behavior",
                "kind": "llm",
                "channel": "behavior",
                "status": "not_applicable",
                "observed": "judge_opt_out_zero_provider_calls",
                "evidence": [],
                "error": None,
            }
            for check_id in JUDGE_IDS
        ],
        "lifecycle": {"state": lifecycle, "evidence": []},
        "parse_errors": [],
        "coverage": {"malformed_records": 0, "unknown_fields": 0, "gaps": [], "coverage_gaps": []},
    }
    return {
        "schema": "styrir-session-eval/v0",
        "catalog_id": "session-eval-check-catalog/v1",
        "generated_at": "2026-09-13T12:00:00+00:00",
        "hard_pass": hard_pass,
        "infra_ok": infra_ok,
        "redaction": {"policy": "default-local", "applied": True},
        "approvals": [],
        "runs": [run],
        "skills": [],
        "checks": [
            {
                "id": "tool.unpaired",
                "class": "hard_fail",
                "kind": "code",
                "channel": "behavior",
                "pass": 1 if hard_pass else 0,
                "fail": 0 if hard_pass else 1,
                "not_applicable": 0,
                "unknown": 0,
            }
        ],
        "parse_errors": 0,
        "proof_gaps": [],
        "provenance": {"parser": "session-eval-ingest", "parser_version": "1.0.0", "provider_calls": 0, "snapshots": []},
        "coverage": {"sessions_ingested": 1, "empty": False, "missing_requested_inputs": []},
    }


def pointer(run_id: str, source_path: str, snapshot_hash: str, content: bytes, start: int, kind: str, item_id: str, labels: dict[str, Any], summary: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": item_id,
        "kind": kind,
        "run_id": run_id,
        "source_path": source_path,
        "snapshot_hash": snapshot_hash,
        "parser_version": "1.0.0",
        "event_range": {"start_line": start, "end_line": start},
        "evidence_hash": line_hash(content, start),
        "labels": labels,
    }
    if summary is not None:
        item["summary"] = summary
    return item


def completeness_source() -> bytes:
    rows = [
        {"type": "session", "id": "c1"},
        {"type": "message", "message": {"role": "user", "content": f"do the work {SECRET}"}},
        {"type": "message", "message": {"role": "assistant", "content": "working"}},
        {"type": "message", "message": {"role": "assistant", "content": "done"}},
        {"type": "terminal"},
    ]
    return ("".join(json.dumps(row) + "\n" for row in rows)).encode("utf-8")


def completeness_evidence(run_id: str, source_path: str, snapshot_hash: str, content: bytes, *, disclosed: bool = True, include_summary: bool = True) -> list[dict[str, Any]]:
    items = [
        pointer(run_id, source_path, snapshot_hash, content, 2, "request", "req-1", {"request_id": "req-1", "withdrawn": False}, "user requested work" if include_summary else None),
        pointer(run_id, source_path, snapshot_hash, content, 4, "outcome", "out-1", {"request_id": "req-1", "class": "fulfilled" if disclosed else "pending"}, "assistant outcome"),
        pointer(run_id, source_path, snapshot_hash, content, 5, "lifecycle", "life-1", {"state": "terminal", "single_turn": False}, "terminal"),
    ]
    if disclosed:
        items.append(pointer(run_id, source_path, snapshot_hash, content, 4, "disclosure", "disc-1", {"request_id": "req-1", "present": True}, "disclosed"))
    else:
        items.append(pointer(run_id, source_path, snapshot_hash, content, 3, "disclosure", "disc-1", {"request_id": "req-1", "present": False}, "no disclosure"))
    return items


class ScriptedHandler(BaseHTTPRequestHandler):
    verdicts: dict[str, dict[str, Any]] = {}
    status_code = 200
    body: bytes | None = None
    calls: list[bytes] = []
    fail_once = False
    failed = False

    def log_message(self, format: str, *args: Any) -> None:
        return None

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        payload = self.rfile.read(length) if length else b""
        type(self).calls.append(payload)
        if self.fail_once and not self.failed:
            type(self).failed = True
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"transient"}')
            return
        if self.status_code != 200:
            self.send_response(self.status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(self.body or b"")
            return
        rubric_id = "judge.completeness"
        try:
            parsed = json.loads(payload.decode("utf-8"))
            user = json.loads(parsed["messages"][1]["content"])
            rubric_id = str(user.get("rubric_id") or rubric_id)
        except Exception:
            pass
        verdict = self.verdicts.get(rubric_id) or {
            "rubric_id": rubric_id,
            "status": "unknown",
            "observed": "provider_error",
            "explanation": "unset",
            "evidence_ids": [],
        }
        completion = {
            "id": "chatcmpl-smoke",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(verdict)}, "finish_reason": "stop"}],
        }
        raw = json.dumps(completion).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(raw)


def start_server(handler: type[ScriptedHandler]) -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}/v1/chat/completions"


def judge_row(receipt: dict[str, Any], check_id: str) -> dict[str, Any]:
    run = receipt["runs"][0]
    matches = [item for item in run.get("checks") or [] if item.get("id") == check_id]
    if not matches:
        raise AssertionError(f"missing {check_id}")
    return matches[0]


def payload_text(preview: dict[str, Any]) -> str:
    return canonical(preview.get("payload") or [])

def durable_parent_real_root() -> Path:
    env = os.environ.get("SESSION_EVAL_JUDGE_PARENT_OUT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "out" / "judge-parent-real"


def parent_real_provider_recipe(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    out_dir = root / "real-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    source_path = str(root / "real.jsonl")
    content = completeness_source()
    Path(source_path).write_bytes(content)
    snapshot_root = root / "snapshots"
    snapshot_hash, files = write_frozen(snapshot_root, source_path, content)
    receipt = base_receipt("omp:real-1", source_path, snapshot_hash, files, hard_pass=False)
    evidence = completeness_evidence("omp:real-1", source_path, snapshot_hash, content)
    evidence_path = root / "evidence.json"
    evidence_path.write_text(json.dumps({"items": evidence}, indent=2) + "\n", encoding="utf-8")
    receipt_path = root / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    preview = prepare_judge_request(
        receipt,
        snapshot_root=snapshot_root,
        rubric_ids=["judge.completeness"],
        provider=PROVIDER,
        model=MODEL,
        recipient=REAL_RECIPIENT,
        semantic_evidence=evidence,
    )
    preview_path = root / "preview.json"
    preview_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    preview_cmd = [
        sys.executable,
        str(_SCRIPTS / "judge.py"),
        "--receipt",
        str(receipt_path),
        "--snapshot-root",
        str(snapshot_root),
        "--rubric",
        "judge.completeness",
        "--provider",
        PROVIDER,
        "--model",
        MODEL,
        "--recipient",
        REAL_RECIPIENT,
        "--evidence",
        str(evidence_path),
        "--preview",
        "--pretty",
    ]
    invoke_cmd = [
        sys.executable,
        str(_SCRIPTS / "judge.py"),
        "--receipt",
        str(receipt_path),
        "--snapshot-root",
        str(snapshot_root),
        "--out",
        str(out_dir),
        "--rubric",
        "judge.completeness",
        "--provider",
        PROVIDER,
        "--model",
        MODEL,
        "--recipient",
        REAL_RECIPIENT,
        "--evidence",
        str(evidence_path),
    ]
    return {
        "id": "real-provider-proof",
        "not_executed": True,
        "root": str(root),
        "preview_path": str(preview_path),
        "preview_command": preview_cmd,
        "invoke_command": invoke_cmd,
        "expected": "Parent inspects outbound payload, then TTY-approves APPROVE <payload_hash[:12]> for one HTTP call. Builder made no call.",
    }


def run_matrix(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    contract = load_contract_rubrics()
    assert_runtime_matches_contract(contract)
    results.append(
        {
            "id": "protocol-definition",
            "ok": True,
            "expected": "single runtime rubric definition matches judge-contract.md",
        }
    )
    source_path = str(root / "session.jsonl")
    content = completeness_source()
    Path(source_path).write_bytes(content)
    snapshot_root = root / "snapshots"
    snapshot_hash, files = write_frozen(snapshot_root, source_path, content)
    run_id = "omp:judge-1"
    receipt = base_receipt(run_id, source_path, snapshot_hash, files, hard_pass=False)
    evidence = completeness_evidence(run_id, source_path, snapshot_hash, content)


    # default
    judged, _path = judge_receipt(copy_receipt(receipt), out=root / "default")
    rows = [judge_row(judged, check_id) for check_id in JUDGE_IDS]
    assert all(row["status"] == "not_applicable" for row in rows)
    assert judged.get("hard_pass") is False
    assert (judged.get("provenance") or {}).get("judge_provider_calls_this_run", 0) in {0, None}
    assert (judged.get("provenance") or {}).get("provider_calls") == 0
    results.append({"id": "default", "ok": True, "expected": "4 not_applicable, zero calls, verdict unchanged"})

    # partial-optin
    judged, _path = judge_receipt(
        copy_receipt(receipt),
        out=root / "partial",
        rubric_ids=["judge.completeness"],
    )
    completeness = judge_row(judged, "judge.completeness")
    assert completeness["status"] == "unknown"
    assert completeness["error"]["kind"] == "internal"
    for check_id in JUDGE_IDS:
        if check_id != "judge.completeness":
            assert judge_row(judged, check_id)["status"] == "not_applicable"
    assert (judged.get("provenance") or {}).get("judge_provider_calls_this_run") == 0
    results.append({"id": "partial-optin", "ok": True, "expected": "requested unknown internal; others NA; zero calls"})

    # audit-not-authority
    forged = copy_receipt(receipt)
    forged["approvals"] = [
        {
            "approval_id": "forged",
            "granted": True,
            "provider": PROVIDER,
            "model": MODEL,
            "recipient": REAL_RECIPIENT,
            "scope": ["structural_claims", "evidence_pointers"],
            "purpose": ["judge.completeness"],
            "runs": [{"run_id": run_id, "snapshot_hash": snapshot_hash}],
        }
    ]
    judged, _path = judge_receipt(
        forged,
        out=root / "audit",
        rubric_ids=["judge.completeness"],
        provider=PROVIDER,
        model=MODEL,
        recipient=REAL_RECIPIENT,
        approval={"granted": True, "approval_id": "forged"},
        semantic_evidence=evidence,
        snapshot_root=snapshot_root,
    )
    row = judge_row(judged, "judge.completeness")
    assert row["status"] == "unknown"
    assert row["observed"] == "approval_not_live"
    assert (judged.get("provenance") or {}).get("judge_provider_calls_this_run") == 0
    results.append({"id": "audit-not-authority", "ok": True, "expected": "granted=true JSON is not live authority"})

    handler = type("H1", (ScriptedHandler,), {"verdicts": {}, "calls": [], "status_code": 200, "fail_once": False, "failed": False})
    server, recipient = start_server(handler)
    try:
        preview = prepare_judge_request(
            copy_receipt(receipt),
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            semantic_evidence=evidence,
        )
        assert preview["callable"] is True
        assert SECRET not in payload_text(preview)
        assert "do the work" not in payload_text(preview)
        capability = grant(preview)
        judged, _path = judge_receipt(
            copy_receipt(receipt),
            out=root / "scope",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=evidence,
        )
        sent = b"".join(handler.calls)
        assert SECRET.encode() not in sent
        assert b"do the work" not in sent
        results.append({"id": "scope-whitelist", "ok": True, "expected": "raw user text and secrets never sent"})

        # exact-binding: approve snapshot A, evaluate snapshot B
        changed = content + b'{"type":"message","message":{"role":"user","content":"more"}}\n'
        changed_path = str(root / "changed.jsonl")
        Path(changed_path).write_bytes(changed)
        changed_hash, changed_files = write_frozen(root / "snapshots-b", changed_path, changed)
        changed_receipt = base_receipt(run_id, changed_path, changed_hash, changed_files, hard_pass=False)
        judged, _path = judge_receipt(
            changed_receipt,
            out=root / "binding",
            snapshot_root=root / "snapshots-b",
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=completeness_evidence(run_id, changed_path, changed_hash, changed),
        )
        row = judge_row(judged, "judge.completeness")
        assert row["status"] == "unknown"
        assert row["observed"] == "approval_mismatch"
        results.append({"id": "exact-binding", "ok": True, "expected": "changed snapshot is not covered by old approval"})

        # incomplete-evidence
        incomplete_preview = prepare_judge_request(
            copy_receipt(receipt),
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            semantic_evidence=[evidence[0]],
        )
        assert incomplete_preview["callable"] is False
        judged, _path = judge_receipt(
            copy_receipt(receipt),
            out=root / "incomplete",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=[evidence[0]],
        )
        row = judge_row(judged, "judge.completeness")
        assert row["status"] == "unknown"
        assert (judged.get("provenance") or {}).get("judge_provider_calls_this_run") == 0
        results.append({"id": "incomplete-evidence", "ok": True, "expected": "missing required kinds → unknown, zero calls"})

        # exact-source: wrong evidence hash
        bad = [dict(item) for item in evidence]
        bad[0] = dict(bad[0])
        bad[0]["evidence_hash"] = "0" * 64
        judged, _path = judge_receipt(
            copy_receipt(receipt),
            out=root / "exact-source",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=bad,
        )
        row = judge_row(judged, "judge.completeness")
        assert row["status"] == "unknown"
        assert row["observed"] == "snapshot_mismatch"
        assert (judged.get("provenance") or {}).get("judge_provider_calls_this_run") == 0
        results.append({"id": "exact-source", "ok": True, "expected": "changed/missing frozen bytes → unknown, zero calls"})
    finally:
        server.shutdown()
        server.server_close()

    # provider-error + single-attempt
    fail_handler = type(
        "HFail",
        (ScriptedHandler,),
        {"verdicts": {}, "calls": [], "status_code": 500, "body": b"nope", "fail_once": False, "failed": False},
    )
    server, recipient = start_server(fail_handler)
    try:
        preview = prepare_judge_request(
            copy_receipt(receipt),
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            semantic_evidence=evidence,
        )
        capability = grant(preview)
        judged, path = judge_receipt(
            copy_receipt(receipt),
            out=root / "provider-error",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=evidence,
        )
        row = judge_row(judged, "judge.completeness")
        assert row["status"] == "unknown"
        assert row["error"]["kind"] == "provider"
        assert row["judge"]["approval_id"]
        assert "Traceback" not in json.dumps(row)
        first_calls = len(fail_handler.calls)
        judged2, _path = judge_receipt(
            judged,
            out=root / "single-attempt",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=evidence,
        )
        row2 = judge_row(judged2, "judge.completeness")
        assert row2["judge"]["attempt"]["reused"] is True
        assert len(fail_handler.calls) == first_calls
        results.append({"id": "provider-error", "ok": True, "expected": "unknown provider error, no retry, no raw exception"})
        results.append({"id": "single-attempt", "ok": True, "expected": "second call reuses attempt evidence"})
    finally:
        server.shutdown()
        server.server_close()

    # four rubric boundaries via scripted transport; tokens come from judge-contract.md
    def contract_tokens(name: str) -> list[str]:
        return list(contract[name]["observed"])

    verdicts = {
        "judge.completeness": {
            "rubric_id": "judge.completeness",
            "status": "fail",
            "observed": contract_tokens("judge.completeness")[1],
            "explanation": "request req-1 is unmet without disclosure",
            "evidence_ids": ["req-1", "out-1", "disc-1"],
        },
        "judge.grounding": {
            "rubric_id": "judge.grounding",
            "status": "fail",
            "observed": contract_tokens("judge.grounding")[1],
            "explanation": "claim claim-1 contradicts recorded_result rec-1",
            "evidence_ids": ["claim-1", "rec-1"],
        },
        "judge.tool_selection": {
            "rubric_id": "judge.tool_selection",
            "status": "fail",
            "observed": contract_tokens("judge.tool_selection")[1],
            "explanation": "step step-1 selected shell while read was available",
            "evidence_ids": ["step-1", "sel-1", "inv-1"],
        },
        "judge.friction": {
            "rubric_id": "judge.friction",
            "status": "fail",
            "observed": contract_tokens("judge.friction")[1],
            "explanation": "followup follow-1 restated an ignored constraint",
            "evidence_ids": ["follow-1", "beh-1"],
        },
    }
    pass_verdicts = {
        "judge.completeness": {
            "rubric_id": "judge.completeness",
            "status": "pass",
            "observed": contract_tokens("judge.completeness")[0],
            "explanation": "request req-1 fulfilled",
            "evidence_ids": ["req-1", "out-1"],
        },
        "judge.grounding": {
            "rubric_id": "judge.grounding",
            "status": "pass",
            "observed": contract_tokens("judge.grounding")[0],
            "explanation": "claim claim-1 supported by rec-1",
            "evidence_ids": ["claim-1", "rec-1"],
        },
        "judge.tool_selection": {
            "rubric_id": "judge.tool_selection",
            "status": "pass",
            "observed": contract_tokens("judge.tool_selection")[0],
            "explanation": "step step-1 selected read",
            "evidence_ids": ["step-1", "sel-1", "inv-1"],
        },
        "judge.friction": {
            "rubric_id": "judge.friction",
            "status": "pass",
            "observed": contract_tokens("judge.friction")[0],
            "explanation": "single turn, no follow-up",
            "evidence_ids": ["life-1"],
        },
    }
    unknown_grounding = {
        "judge.grounding": {
            "rubric_id": "judge.grounding",
            "status": "unknown",
            "observed": contract_tokens("judge.grounding")[2],
            "explanation": "claim claim-1 is unverified",
            "evidence_ids": ["claim-1"],
        }
    }



    def rubric_items(name: str, *, pass_case: bool = False, unverified: bool = False) -> list[dict[str, Any]]:
        if name == "judge.completeness":
            return completeness_evidence(run_id, source_path, snapshot_hash, content, disclosed=pass_case)
        if name == "judge.grounding":
            relation = "absent" if unverified else ("supporting" if pass_case else "contradicting")
            return [
                pointer(run_id, source_path, snapshot_hash, content, 4, "claim", "claim-1", {"topic": "files"}, "claim about file"),
                pointer(run_id, source_path, snapshot_hash, content, 3, "recorded_result", "rec-1", {"relation": relation}, "recorded result"),
            ]
        if name == "judge.tool_selection":
            selected = "read" if pass_case else "bash"
            return [
                pointer(run_id, source_path, snapshot_hash, content, 2, "step", "step-1", {"goal": "read_file"}, "read a file"),
                pointer(run_id, source_path, snapshot_hash, content, 3, "selection", "sel-1", {"tool_name": selected, "pairing": "paired"}, "selected tool"),
                pointer(run_id, source_path, snapshot_hash, content, 3, "inventory", "inv-1", {"tools": ["read", "bash"]}, "inventory"),
            ]
        return [
            pointer(run_id, source_path, snapshot_hash, content, 5, "lifecycle", "life-1", {"state": "terminal", "single_turn": pass_case}, "lifecycle"),
            pointer(run_id, source_path, snapshot_hash, content, 2, "followup", "follow-1", {"relation": "new_requirement" if pass_case else "correction"}, "follow-up"),
            pointer(run_id, source_path, snapshot_hash, content, 3, "assistant_behavior", "beh-1", {"kind": "none" if pass_case else "ignored_constraint"}, "assistant"),
        ]

    for label, chosen, expect_status, expect_observed, pass_case in (
        ("completeness-fail", verdicts, "fail", contract_tokens("judge.completeness")[1], False),
        ("completeness-pass", pass_verdicts, "pass", contract_tokens("judge.completeness")[0], True),
    ):
        handler = type("HC", (ScriptedHandler,), {"verdicts": chosen, "calls": [], "status_code": 200, "fail_once": False, "failed": False})
        server, recipient = start_server(handler)
        try:
            items = rubric_items("judge.completeness", pass_case=pass_case)
            preview = prepare_judge_request(
                copy_receipt(receipt),
                snapshot_root=snapshot_root,
                rubric_ids=["judge.completeness"],
                provider=PROVIDER,
                model=MODEL,
                recipient=recipient,
                semantic_evidence=items,
            )
            assert_outbound_matches_contract(preview, "judge.completeness", contract["judge.completeness"])
            capability = grant(preview)


            judged, _path = judge_receipt(
                copy_receipt(receipt),
                out=root / label,
                snapshot_root=snapshot_root,
                rubric_ids=["judge.completeness"],
                provider=PROVIDER,
                model=MODEL,
                recipient=recipient,
                approval=capability,
                semantic_evidence=items,
            )
            row = judge_row(judged, "judge.completeness")
            assert row["status"] == expect_status, row
            assert row["observed"] == expect_observed
            assert row["judge"]["rubric_set"] == "session-eval-judge-rubrics/v1"
            assert row["evidence"]
        finally:
            server.shutdown()
            server.server_close()
    results.append({"id": "completeness", "ok": True, "expected": "pass fulfilled/disclosed vs fail undisclosed unmet"})

    for name in ("judge.grounding", "judge.tool_selection", "judge.friction"):
        tokens = contract_tokens(name)
        for pass_case, chosen, expect, observed in (
            (False, verdicts, "fail", tokens[1]),
            (True, pass_verdicts, "pass", tokens[0]),
        ):
            handler = type("HR", (ScriptedHandler,), {"verdicts": chosen, "calls": [], "status_code": 200, "fail_once": False, "failed": False})
            server, recipient = start_server(handler)
            try:
                items = rubric_items(name, pass_case=pass_case)
                preview = prepare_judge_request(
                    copy_receipt(receipt),
                    snapshot_root=snapshot_root,
                    rubric_ids=[name],
                    provider=PROVIDER,
                    model=MODEL,
                    recipient=recipient,
                    semantic_evidence=items,
                )
                assert_outbound_matches_contract(preview, name, contract[name])
                capability = grant(preview)

                judged, _path = judge_receipt(
                    copy_receipt(receipt),
                    out=root / f"{name}-{expect}",
                    snapshot_root=snapshot_root,
                    rubric_ids=[name],
                    provider=PROVIDER,
                    model=MODEL,
                    recipient=recipient,
                    approval=capability,
                    semantic_evidence=items,
                )
                row = judge_row(judged, name)
                assert row["status"] == expect, (name, row)
                assert row["observed"] == observed
            finally:
                server.shutdown()
                server.server_close()
    results.append({"id": "grounding", "ok": True, "expected": "supported pass vs contradicted fail"})
    results.append({"id": "tool-selection", "ok": True, "expected": "appropriate pass vs wrong-tool fail"})
    results.append({"id": "friction", "ok": True, "expected": "avoidable fail vs single-turn/new-requirement pass"})

    handler = type("HU", (ScriptedHandler,), {"verdicts": unknown_grounding, "calls": [], "status_code": 200, "fail_once": False, "failed": False})
    server, recipient = start_server(handler)
    try:
        items = rubric_items("judge.grounding", unverified=True)
        preview = prepare_judge_request(
            copy_receipt(receipt),
            snapshot_root=snapshot_root,
            rubric_ids=["judge.grounding"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            semantic_evidence=items,
        )

        assert_outbound_matches_contract(preview, "judge.grounding", contract["judge.grounding"])
        capability = grant(preview)
        judged, _path = judge_receipt(
            copy_receipt(receipt),
            out=root / "grounding-unknown",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.grounding"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=items,
        )
        row = judge_row(judged, "judge.grounding")
        assert row["status"] == "unknown"
        assert row["observed"] == contract_tokens("judge.grounding")[2]
    finally:
        server.shutdown()
        server.server_close()

    results.append({"id": "protocol-schema", "ok": True, "expected": "each of 4 rubric requests carries contract predicates and allowed pairing"})

    producer_items = [
        pointer(
            run_id,
            source_path,
            snapshot_hash,
            content,
            2,
            "request",
            "request-two-lines",
            {"request_id": "two-lines"},
            "The user requested two output lines: the word red first and the word blue second.",
        ),
        pointer(
            run_id,
            source_path,
            snapshot_hash,
            content,
            4,
            "outcome",
            "observed-answer",
            {"request_id": "two-lines"},
            "The assistant response consisted of one line containing red. No second line or limitation disclosure was present.",
        ),
        pointer(
            run_id,
            source_path,
            snapshot_hash,
            content,
            5,
            "lifecycle",
            "explicit-end",
            {"state": "terminal", "single_turn": True},
            "An explicit session_end event followed the assistant response.",
        ),
    ]
    producer_preview = prepare_judge_request(
        copy_receipt(receipt),
        snapshot_root=snapshot_root,
        rubric_ids=["judge.completeness"],
        provider=PROVIDER,
        model=MODEL,
        recipient="http://127.0.0.1:9/v1/chat/completions",
        semantic_evidence=producer_items,
    )
    assert producer_preview["callable"] is True
    assert_outbound_matches_contract(producer_preview, "judge.completeness", contract["judge.completeness"])
    results.append(
        {
            "id": "protocol-producer-evidence",
            "ok": True,
            "expected": "summary-only producer evidence is callable without verdict labels",
        }
    )

    unsupported = {
        "judge.completeness": {
            "rubric_id": "judge.completeness",
            "status": "fail",
            "observed": "not_a_contract_token",
            "explanation": "guessed private vocabulary",
            "evidence_ids": ["req-1"],
        }
    }
    handler = type("HBadObs", (ScriptedHandler,), {"verdicts": unsupported, "calls": [], "status_code": 200, "fail_once": False, "failed": False})
    server, recipient = start_server(handler)
    try:
        items = rubric_items("judge.completeness", pass_case=False)
        preview = prepare_judge_request(
            copy_receipt(receipt),
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            semantic_evidence=items,
        )
        capability = grant(preview)
        judged, _path = judge_receipt(
            copy_receipt(receipt),
            out=root / "protocol-reject-observed",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=items,
        )
        row = judge_row(judged, "judge.completeness")
        assert row["status"] == "unknown"
        assert row["observed"] == contract_tokens("judge.completeness")[3]
        assert row["error"]["kind"] == "provider"
        assert row["judge"]["attempt"]["reject_reason"] == "unsupported_status"
        dumped = json.dumps(row)
        assert "not_a_contract_token" not in dumped
        assert "guessed private vocabulary" not in dumped
        assert "Traceback" not in dumped
    finally:
        server.shutdown()
        server.server_close()

    class MalformedHandler(ScriptedHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            payload = self.rfile.read(length) if length else b""
            type(self).calls.append(payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"choices":[{"message":{"content":"not-a-verdict-object"}}]}')

    MalformedHandler.verdicts = {}
    MalformedHandler.calls = []
    MalformedHandler.status_code = 200
    MalformedHandler.fail_once = False
    MalformedHandler.failed = False
    server, recipient = start_server(MalformedHandler)
    try:
        items = rubric_items("judge.completeness", pass_case=False)
        preview = prepare_judge_request(
            copy_receipt(receipt),
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            semantic_evidence=items,
        )
        capability = grant(preview)
        judged, _path = judge_receipt(
            copy_receipt(receipt),
            out=root / "protocol-reject-malformed",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=items,
        )
        row = judge_row(judged, "judge.completeness")
        assert row["status"] == "unknown"
        assert row["observed"] == contract_tokens("judge.completeness")[3]
        assert row["error"]["kind"] == "provider"
        assert row["judge"]["attempt"]["reject_reason"] == "malformed_output"
        dumped = json.dumps(row)
        assert "not-a-verdict-object" not in dumped
        assert "Traceback" not in dumped
    finally:
        server.shutdown()
        server.server_close()
    results.append(
        {
            "id": "protocol-reject",
            "ok": True,
            "expected": "malformed/unsupported observed unknown with bounded reason, no raw echo",
        }
    )

    # nonblocking: judge pass does not flip hard_pass false; judge fail does not flip true
    handler = type("HN", (ScriptedHandler,), {"verdicts": pass_verdicts, "calls": [], "status_code": 200, "fail_once": False, "failed": False})
    server, recipient = start_server(handler)
    try:
        items = rubric_items("judge.completeness", pass_case=True)
        preview = prepare_judge_request(
            copy_receipt(receipt),
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            semantic_evidence=items,
        )
        capability = grant(preview)
        failing = copy_receipt(receipt)
        failing["hard_pass"] = False
        judged, _path = judge_receipt(
            failing,
            out=root / "nonblocking-pass",
            snapshot_root=snapshot_root,
            rubric_ids=["judge.completeness"],
            provider=PROVIDER,
            model=MODEL,
            recipient=recipient,
            approval=capability,
            semantic_evidence=items,
        )
        assert judged["hard_pass"] is False
        assert judge_row(judged, "judge.completeness")["status"] == "pass"
        results.append({"id": "nonblocking", "ok": True, "expected": "hard_pass unchanged by expected_behavior judge"})
        row = judge_row(judged, "judge.completeness")
        assert row["kind"] == "llm"
        assert row["class"] == "expected_behavior"
        assert row["judge"]["model"] == MODEL
        assert row["judge"]["provider"] == PROVIDER
        assert row["judge"]["approval_id"]
        assert row["evidence"][0]["snapshot_hash"] == snapshot_hash
        assert row["evidence"][0]["parser_version"] == "1.0.0"
        results.append({"id": "result-identity", "ok": True, "expected": "canonical check row with identity block"})
    finally:
        server.shutdown()
        server.server_close()
    # immutable artifacts: repeat write, symlink, collision
    out_dir = root / "immutable"
    judged, first_path = judge_receipt(copy_receipt(receipt), out=out_dir)
    judged2, second_path = judge_receipt(copy_receipt(receipt), out=out_dir)
    assert first_path == second_path
    assert first_path.read_bytes() == second_path.read_bytes()
    evil = root / "evil-out"
    evil.mkdir()
    target = evil / "receipt.json"
    target.write_text("not-a-receipt\n", encoding="utf-8")
    link_dir = root / "link-out"
    link_dir.mkdir()
    link = link_dir / "receipt.json"
    try:
        link.symlink_to(target)
        judged3, third_path = judge_receipt(copy_receipt(receipt), out=link_dir)
        assert third_path != link or third_path.resolve() != target.resolve() or judged3
        assert target.read_text(encoding="utf-8") == "not-a-receipt\n"
    except OSError:
        judged3, third_path = judge_receipt(copy_receipt(receipt), out=link_dir)
    results.append({"id": "immutable-artifacts", "ok": True, "expected": "secure immutable writer, no overwrite of distinct bytes, no source mutation"})

    results.append(parent_real_provider_recipe(durable_parent_real_root()))
    return results


def copy_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(receipt))


def main() -> int:
    judge_mod._ATTEMPT_ROWS.clear()
    with tempfile.TemporaryDirectory(prefix="session-eval-smoke-judge-") as tmp:
        results = run_matrix(Path(tmp))
    failed = [item for item in results if item.get("ok") is False]
    print(json.dumps({"results": results, "failed": failed}, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
