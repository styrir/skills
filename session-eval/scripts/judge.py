#!/usr/bin/env python3
"""Opt-in session-eval LLM judges.

Consumes a ``styrir-session-eval/v0`` receipt plus hash-verified frozen
snapshots.  Default is zero provider calls.  Live authority is an ephemeral
in-process capability from direct interactive approval; ``granted=true`` in a
receipt, source file, or JSON object is never authority.

Transport is one stdlib HTTP OpenAI-compatible chat-completions request with
no redirects, retries, or tools.  Provider, model, recipient, and auth-env
are explicit arguments and are never inferred.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import ingest as ingest_mod

UNKNOWN = ingest_mod.UNKNOWN
RECEIPT_SCHEMA = "styrir-session-eval/v0"
CATALOG_ID = "session-eval-check-catalog/v1"
RUBRIC_SET = "session-eval-judge-rubrics/v1"
JUDGE_VERSION = "1.0.0"

JUDGE_IDS = (
    "judge.completeness",
    "judge.grounding",
    "judge.tool_selection",
    "judge.friction",
)

CATALOG_META: dict[str, dict[str, str]] = {
    "judge.completeness": {"class": "expected_behavior", "kind": "llm", "channel": "behavior"},
    "judge.grounding": {"class": "expected_behavior", "kind": "llm", "channel": "behavior"},
    "judge.tool_selection": {"class": "expected_behavior", "kind": "llm", "channel": "behavior"},
    "judge.friction": {"class": "expected_behavior", "kind": "llm", "channel": "behavior"},
}

SCOPE_STRUCTURAL = "structural_claims"
SCOPE_POINTERS = "evidence_pointers"
SCOPE_SEMANTIC = "semantic_summaries"
ALLOWED_SCOPES = (SCOPE_STRUCTURAL, SCOPE_POINTERS, SCOPE_SEMANTIC)

RUBRICS: dict[str, dict[str, Any]] = {
    "judge.completeness": {
        "question": "Were active user requests fulfilled, or explicitly disclosed as pending, blocked, failed, or ignored?",
        "pass": "Every active request is fulfilled, or is non-fulfilled and disclosed.",
        "fail": "At least one active request is pending, blocked, failed, or ignored without disclosure.",
        "unknown": "Requests cannot be enumerated; outcome evidence is missing; approval/provider/parse error; or lifecycle is unknown and remaining work cannot be distinguished from an open stream.",
        "observed": {
            "pass": "all_disclosed_or_fulfilled",
            "fail": "undisclosed_unmet_request",
            "unknown": "requests_unenumerable",
            "provider": "provider_error",
        },
    },
    "judge.grounding": {
        "question": "Do assistant claims about files, commands, or test results contradict evidence this session actually read or recorded?",
        "pass": "At least one claim is evaluable, every judged claim has supporting recorded evidence, and none is contradicted. Claims outside the selected scope are disclosed as unjudged.",
        "fail": "At least one claim contradicts files or results the session actually read/recorded.",
        "unknown": "Any selected claim lacks enough readable evidence to decide and no selected claim is contradicted; no claims can be isolated; or approval/provider/parse error. A wholly unverified claim set is never pass.",
        "observed": {
            "pass": "no_contradiction",
            "fail": "claim_contradicted",
            "unknown": "claims_unevaluable",
            "provider": "provider_error",
        },
    },
    "judge.tool_selection": {
        "question": "Was the selected tool appropriate for the stated step, given tools actually available in this session?",
        "pass": "Selected tool is appropriate for the stated step among recorded available tools.",
        "fail": "Wrong tool for the stated step while a better recorded available tool existed.",
        "unknown": "Stated step missing, tool inventory missing, selection missing, or approval/provider/parse error.",
        "observed": {
            "pass": "appropriate_selection",
            "fail": "wrong_tool_available_better",
            "unknown": "selection_unevaluable",
            "provider": "provider_error",
        },
    },
    "judge.friction": {
        "question": "Did the assistant cause avoidable user re-prompting?",
        "pass": "No avoidable user re-prompting attributable to the assistant.",
        "fail": "At least one avoidable re-prompt caused by the assistant.",
        "unknown": "Follow-ups exist but cause cannot be attributed; user side missing; approval/provider/parse error.",
        "observed": {
            "pass": "no_avoidable_reprompt",
            "fail": "avoidable_reprompt",
            "unknown": "friction_unevaluable",
            "provider": "provider_error",
        },
    },
}

REQUIRED_KINDS: dict[str, tuple[str, ...]] = {
    "judge.completeness": ("request", "outcome", "lifecycle"),
    "judge.grounding": ("claim",),
    "judge.tool_selection": ("step", "selection", "inventory"),
    "judge.friction": ("lifecycle",),
}

PRECLASSIFIED_KEYS = {
    "status",
    "verdict",
    "pass",
    "fail",
    "observed",
    "preclassified",
    "judgment",
    "score",
}
FORBIDDEN_PAYLOAD_KEYS = {
    "payload",
    "arguments",
    "args",
    "content",
    "text",
    "secret",
    "raw",
    "prompt",
    "terminal",
    "tool_result",
    "toolResult",
    "body",
    "message",
}

SECRET_PATTERN = re.compile(
    r"(?i)(?:(?:api[_-]?key|secret(?:[_-]?key)?|password|passwd|access[_-]?token|auth[_-]?token|"
    r"private[_-]?key)\s*[\"']?\s*[:=]\s*[\"']?[^\s,\"']{8,}"
    r"|sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)

BOUNDED_REJECT_REASONS = frozenset(
    {
        "auth_missing",
        "redirect_refused",
        "http_error",
        "transport_failure",
        "invalid_json",
        "tools_not_allowed",
        "malformed_output",
        "unsupported_status",
        "unsupported_evidence_reference",
    }
)


class JudgeError(Exception):
    """An expected local-input error suitable for a concise CLI message."""


class _ApprovalCapability:
    """Ephemeral live authority. Not serializable. Not reconstructable from JSON."""

    __slots__ = ("_secret", "_binding", "approval_id")

    def __init__(self, binding: dict[str, Any], approval_id: str) -> None:
        self._secret = object()
        self._binding = binding
        self.approval_id = approval_id

    def binding(self) -> dict[str, Any]:
        return copy.deepcopy(self._binding)


_ISSUED: dict[int, _ApprovalCapability] = {}
_ATTEMPT_ROWS: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}


def _canonical(value: Any) -> str:
    return ingest_mod._canonical(value)


def sha256_bytes(value: bytes) -> str:
    return ingest_mod.sha256_bytes(value)


def sha256_text(value: str) -> str:
    return ingest_mod.sha256_text(value)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _error(kind: str, message: str) -> dict[str, str]:
    return {"kind": kind, "channel": "infra", "message": message}


def _safe_label(value: Any, limit: int = 240) -> str:
    return ingest_mod._safe_label(value, limit=limit)


def _strip_sha_prefix(value: str) -> str:
    text = str(value or "")
    if text.startswith("sha256:"):
        return text[7:]
    return text


def _check(
    check_id: str,
    status: str,
    observed: str,
    evidence: list[dict[str, Any]] | None = None,
    error: dict[str, str] | None = None,
    judge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = CATALOG_META[check_id]
    row = {
        "id": check_id,
        "class": meta["class"],
        "kind": meta["kind"],
        "channel": meta["channel"],
        "status": status,
        "observed": observed,
        "evidence": evidence or [],
        "error": error,
        "judge": judge
        or {
            "rubric_id": check_id,
            "rubric_set": RUBRIC_SET,
            "model": None,
            "provider": None,
            "approval_id": None,
            "explanation": None,
        },
    }
    return row


def _identity(
    check_id: str,
    *,
    model: str | None,
    provider: str | None,
    approval_id: str | None,
    explanation: str | None = None,
    attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "rubric_id": check_id,
        "rubric_set": RUBRIC_SET,
        "model": model,
        "provider": provider,
        "approval_id": approval_id,
        "explanation": explanation,
    }
    if attempt is not None:
        block["attempt"] = attempt
    return block


def _is_capability(value: Any) -> bool:
    if not isinstance(value, _ApprovalCapability):
        return False
    issued = _ISSUED.get(id(value._secret))
    return issued is value


def _run_snapshot_hash(run: dict[str, Any]) -> str:
    snapshot = run.get("source_snapshot")
    if isinstance(snapshot, dict) and snapshot.get("sha256"):
        return str(snapshot["sha256"])
    return UNKNOWN


def _run_parser_version(run: dict[str, Any]) -> str:
    return str(run.get("parser_version") or UNKNOWN)


def _lifecycle_state(run: dict[str, Any]) -> str:
    lifecycle = run.get("lifecycle")
    if isinstance(lifecycle, dict):
        state = lifecycle.get("state")
        if state in {"terminal", "live", "unknown"}:
            return state
    return "unknown"


def _snapshot_file_path(snapshot_root: Path, index: int, item: dict[str, Any]) -> Path:
    path = str(item.get("path") or "")
    role = str(item.get("role") or "primary")
    digest = str(item.get("sha256") or "")
    basename = Path(path).name or "source"
    token = sha256_text(f"{path}:{role}")[:12]
    return snapshot_root / digest / f"{index:03d}-{token}-{basename}"


def _derive_snapshot_root(receipt_path: Path | None, snapshot_root: str | Path | None) -> Path | None:
    if snapshot_root is not None:
        return Path(snapshot_root).expanduser()
    if receipt_path is not None:
        candidate = receipt_path.parent / ".private" / "snapshots"
        if candidate.is_dir():
            return candidate
        nested = receipt_path.parent.parent / ".private" / "snapshots"
        if nested.is_dir():
            return nested
    return None


def _load_receipt(receipt: dict[str, Any] | None, receipt_path: str | Path | None) -> tuple[dict[str, Any], Path | None]:
    path = Path(receipt_path).expanduser() if receipt_path is not None else None
    if receipt is not None:
        return copy.deepcopy(receipt), path
    if path is None:
        raise JudgeError("judge requires a receipt object or --receipt path")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise JudgeError(f"missing receipt: {path}") from exc
    except OSError as exc:
        raise JudgeError(f"unreadable receipt: {path}") from exc
    except json.JSONDecodeError as exc:
        raise JudgeError(f"invalid receipt JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise JudgeError("receipt must be an object")
    return payload, path


def _load_semantic_evidence(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    payload = value
    if isinstance(value, (str, Path)):
        path = Path(value).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JudgeError(f"unreadable semantic evidence: {path}: {exc}") from exc
    items: list[Any]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        inner = payload.get("items", payload.get("evidence"))
        if isinstance(inner, list):
            items = inner
        else:
            items = [payload]
    else:
        raise JudgeError("semantic evidence must be an object, list, or JSON path")
    return [item for item in items if isinstance(item, dict)]


def _line_bytes(data: bytes, start_line: int, end_line: int) -> bytes | None:
    if start_line < 1 or end_line < start_line:
        return None
    offset = 0
    line_no = 0
    chunks: list[bytes] = []
    while offset <= len(data):
        end = data.find(b"\n", offset)
        if end == -1:
            raw = data[offset:]
            offset = len(data) + 1
        else:
            raw = data[offset : end + 1]
            offset = end + 1
        line_no += 1
        if start_line <= line_no <= end_line:
            chunks.append(raw)
        if line_no >= end_line:
            break
        if end == -1:
            break
    if line_no < end_line or not chunks:
        return None
    return b"".join(chunks)


def _verify_span(
    run: dict[str, Any],
    snapshot_root: Path | None,
    item: dict[str, Any],
) -> tuple[bool, str]:
    source_path = str(item.get("source_path") or "")
    expected_hash = _strip_sha_prefix(str(item.get("evidence_hash") or ""))
    event_range = item.get("event_range") if isinstance(item.get("event_range"), dict) else {}
    try:
        start = int(event_range.get("start_line") or 0)
        end = int(event_range.get("end_line") or start)
    except (TypeError, ValueError):
        return False, "invalid_event_range"
    snapshot = run.get("source_snapshot") if isinstance(run.get("source_snapshot"), dict) else {}
    files = snapshot.get("files") if isinstance(snapshot.get("files"), list) else []
    if snapshot_root is None:
        return False, "snapshot_root_unavailable"
    matched = False
    for index, file_item in enumerate(files):
        if not isinstance(file_item, dict):
            continue
        if str(file_item.get("path") or "") != source_path:
            continue
        matched = True
        frozen = _snapshot_file_path(snapshot_root, index, file_item)
        try:
            data = frozen.read_bytes()
        except OSError:
            return False, "frozen_unreadable"
        actual_file = sha256_bytes(data)
        expected_file = _strip_sha_prefix(str(file_item.get("sha256") or ""))
        if expected_file and actual_file != expected_file:
            return False, "frozen_hash_mismatch"
        raw = _line_bytes(data, start, end)
        if raw is None:
            return False, "span_missing"
        digest = sha256_bytes(raw)
        digest_stripped = sha256_bytes(raw.strip())
        if expected_hash and expected_hash not in {digest, digest_stripped}:
            return False, "evidence_hash_mismatch"
        item_snap = _strip_sha_prefix(str(item.get("snapshot_hash") or ""))
        run_snap = _strip_sha_prefix(_run_snapshot_hash(run))
        if item_snap and run_snap and item_snap != run_snap:
            return False, "snapshot_mismatch"
        return True, "ok"
    if not matched:
        return False, "source_not_in_snapshot"
    return False, "source_not_in_snapshot"


def _pointer(run: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    event_range = item.get("event_range") if isinstance(item.get("event_range"), dict) else {}
    start = int(event_range.get("start_line") or 1)
    end = int(event_range.get("end_line") or start)
    return {
        "source_path": str(item.get("source_path") or run.get("source_path") or UNKNOWN),
        "snapshot_hash": str(item.get("snapshot_hash") or _run_snapshot_hash(run)),
        "parser_version": str(item.get("parser_version") or _run_parser_version(run)),
        "event_range": {"start_line": start, "end_line": end},
        "evidence_hash": str(item.get("evidence_hash") or UNKNOWN),
    }


def _sanitize_labels(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, inner in value.items():
            name = str(key)
            if name in PRECLASSIFIED_KEYS or name in FORBIDDEN_PAYLOAD_KEYS:
                continue
            cleaned[_safe_label(name, 80)] = _sanitize_labels(inner)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_labels(item) for item in value[:32]]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = _safe_label(value)
    if SECRET_PATTERN.search(str(value)):
        return "[REDACTED]"
    return text


def _normalize_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    kind = str(raw.get("kind") or "").strip()
    if not kind:
        return None
    item_id = str(raw.get("id") or kind)
    labels = raw.get("labels") if isinstance(raw.get("labels"), dict) else {}
    extra = {key: value for key, value in raw.items() if key not in {"id", "kind", "labels", "summary", "source_path", "snapshot_hash", "parser_version", "event_range", "evidence_hash", "run_id"}}
    merged_labels = dict(labels)
    for key, value in extra.items():
        if key in PRECLASSIFIED_KEYS or key in FORBIDDEN_PAYLOAD_KEYS:
            continue
        merged_labels.setdefault(key, value)
    event_range = raw.get("event_range") if isinstance(raw.get("event_range"), dict) else None
    if event_range is None:
        return None
    summary = raw.get("summary")
    return {
        "id": _safe_label(item_id, 80),
        "kind": _safe_label(kind, 80),
        "labels": _sanitize_labels(merged_labels),
        "summary": _safe_label(summary) if isinstance(summary, str) and summary.strip() else None,
        "source_path": str(raw.get("source_path") or ""),
        "snapshot_hash": str(raw.get("snapshot_hash") or ""),
        "parser_version": str(raw.get("parser_version") or ""),
        "event_range": {
            "start_line": int(event_range.get("start_line") or 0),
            "end_line": int(event_range.get("end_line") or event_range.get("start_line") or 0),
        },
        "evidence_hash": str(raw.get("evidence_hash") or ""),
        "run_id": str(raw.get("run_id") or ""),
    }


def _items_for_run(items: list[dict[str, Any]], run: dict[str, Any]) -> list[dict[str, Any]]:
    run_id = str(run.get("id") or "")
    snap = _run_snapshot_hash(run)
    selected: list[dict[str, Any]] = []
    for raw in items:
        normalized = _normalize_item(raw)
        if normalized is None:
            continue
        item_run = normalized["run_id"]
        item_snap = _strip_sha_prefix(normalized["snapshot_hash"])
        if item_run and item_run != run_id:
            continue
        if item_snap and item_snap != _strip_sha_prefix(snap):
            continue
        selected.append(normalized)
    return selected


def _kinds(items: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("kind") or "") for item in items}


def _evidence_sufficient(rubric_id: str, items: list[dict[str, Any]], run: dict[str, Any]) -> tuple[bool, str]:
    kinds = _kinds(items)
    required = REQUIRED_KINDS[rubric_id]
    if any(kind not in kinds for kind in required):
        return False, "missing_required_kinds"
    if rubric_id == "judge.completeness":
        requests = [item for item in items if item["kind"] == "request"]
        if not requests:
            return False, "requests_unenumerable"
        lifecycle = _lifecycle_state(run)
        if lifecycle == "unknown":
            return False, "lifecycle_unknown"
        for request in requests:
            request_id = str((request.get("labels") or {}).get("request_id") or request["id"])
            withdrawn = bool((request.get("labels") or {}).get("withdrawn"))
            if withdrawn:
                continue
            outcomes = [
                item
                for item in items
                if item["kind"] == "outcome"
                and str((item.get("labels") or {}).get("request_id") or "") == request_id
            ]
            if not outcomes:
                return False, "missing_outcome"
        return True, "ok"
    if rubric_id == "judge.grounding":
        claims = [item for item in items if item["kind"] == "claim"]
        if not claims:
            return False, "claims_unevaluable"
        return True, "ok"
    if rubric_id == "judge.tool_selection":
        if not any(item["kind"] == "inventory" for item in items):
            return False, "missing_inventory"
        inventory = next(item for item in items if item["kind"] == "inventory")
        names = (inventory.get("labels") or {}).get("tools") or (inventory.get("labels") or {}).get("tool_names")
        if not isinstance(names, list) or not names:
            return False, "missing_inventory"
        if not any(item["kind"] == "step" for item in items):
            return False, "missing_step"
        if not any(item["kind"] == "selection" for item in items):
            return False, "missing_selection"
        return True, "ok"
    if rubric_id == "judge.friction":
        followups = [item for item in items if item["kind"] == "followup"]
        single_turn = any(
            item["kind"] == "lifecycle" and bool((item.get("labels") or {}).get("single_turn"))
            for item in items
        )
        if followups:
            if not any(item["kind"] == "assistant_behavior" for item in items):
                return False, "friction_unevaluable"
            return True, "ok"
        if single_turn:
            return True, "ok"
        return False, "friction_unevaluable"
    return False, "unknown_rubric"


def _proposed_scope(items: list[dict[str, Any]]) -> list[str]:
    scope = [SCOPE_STRUCTURAL, SCOPE_POINTERS]
    if any(item.get("summary") for item in items):
        scope.append(SCOPE_SEMANTIC)
    return scope


def _payload_item(item: dict[str, Any], scope: Sequence[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {"id": item["id"], "kind": item["kind"]}
    if SCOPE_STRUCTURAL in scope:
        payload["labels"] = item.get("labels") or {}
    if SCOPE_POINTERS in scope:
        payload["source_path"] = item.get("source_path")
        payload["snapshot_hash"] = item.get("snapshot_hash")
        payload["parser_version"] = item.get("parser_version")
        payload["event_range"] = item.get("event_range")
        payload["evidence_hash"] = item.get("evidence_hash")
    if SCOPE_SEMANTIC in scope and item.get("summary"):
        payload["summary"] = item["summary"]
    return payload


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_forbidden(inner) for inner in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden(inner) for inner in value)
    if isinstance(value, str):
        if SECRET_PATTERN.search(value):
            return True
    return False

def _rubric_observed(rubric_id: str) -> dict[str, str]:
    return dict(RUBRICS[rubric_id]["observed"])


def _status_observed_pairing(rubric_id: str) -> dict[str, list[str]]:
    observed = _rubric_observed(rubric_id)
    return {
        "pass": [observed["pass"]],
        "fail": [observed["fail"]],
        "unknown": [observed["unknown"], observed["provider"]],
    }


def _allowed_observed_tokens(rubric_id: str) -> list[str]:
    observed = _rubric_observed(rubric_id)
    return [observed["pass"], observed["fail"], observed["unknown"], observed["provider"]]


def _rubric_instruction(rubric_id: str) -> dict[str, Any]:
    spec = RUBRICS[rubric_id]
    pairing = _status_observed_pairing(rubric_id)
    allowed = _allowed_observed_tokens(rubric_id)
    return {
        "rubric_id": rubric_id,
        "rubric_set": RUBRIC_SET,
        "question": spec["question"],
        "predicates": {
            "pass": spec["pass"],
            "fail": spec["fail"],
            "unknown": spec["unknown"],
        },
        "allowed_status": ["pass", "fail", "unknown"],
        "allowed_observed": allowed,
        "status_observed_pairing": pairing,
        "response_schema": {
            "rubric_id": rubric_id,
            "status": ["pass", "fail", "unknown"],
            "observed": allowed,
            "status_observed_pairing": pairing,
            "explanation": "string citing evidence_ids only",
            "evidence_ids": ["string"],
        },
    }


def _system_prompt(rubric_id: str) -> str:
    instruction = _rubric_instruction(rubric_id)
    return (
        "You are a session-eval rubric judge. Return one JSON object only. "
        "Use only the supplied structural claims, evidence pointers, and rubric definition. "
        "Do not invent evidence, do not request raw transcripts, and do not "
        "echo prompts, tool payloads, secrets, or terminal output. "
        f"Question: {instruction['question']} "
        f"Pass: {instruction['predicates']['pass']} "
        f"Fail: {instruction['predicates']['fail']} "
        f"Unknown: {instruction['predicates']['unknown']} "
        "Allowed status: pass, fail, unknown. "
        f"Allowed observed pairing: {_canonical(instruction['status_observed_pairing'])}. "
        "Return one JSON object with keys rubric_id, status, observed, explanation, evidence_ids. "
        "status and observed must use the supplied pairing. explanation must cite evidence_ids only."
    )


def _reject_reason(reason: str) -> str:
    text = str(reason or "").strip()
    if text in BOUNDED_REJECT_REASONS:
        return text
    return "unaccepted_response"


def _chat_body(model: str, rubric_id: str, run: dict[str, Any], items: list[dict[str, Any]], scope: Sequence[str]) -> dict[str, Any]:
    instruction = _rubric_instruction(rubric_id)
    user = {
        "rubric_id": rubric_id,
        "rubric_set": RUBRIC_SET,
        "run_id": run.get("id"),
        "snapshot_hash": _run_snapshot_hash(run),
        "parser_version": _run_parser_version(run),
        "lifecycle": _lifecycle_state(run),
        "scope": list(scope),
        "rubric": instruction,
        "evidence": [_payload_item(item, scope) for item in items],
    }
    return {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _system_prompt(rubric_id)},
            {"role": "user", "content": _canonical(user)},
        ],
    }




class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def _authorization_header(auth_env: str | None) -> str | None:
    if auth_env is None:
        return None
    name = str(auth_env).strip()
    if not name:
        raise JudgeError("auth_env is empty")
    value = os.environ.get(name)
    if value is None or value == "":
        raise JudgeError(f"auth environment {name} is missing")
    if value.lower().startswith("bearer "):
        return value
    return f"Bearer {value}"


def _one_http_call(
    recipient: str,
    body: dict[str, Any],
    auth_env: str | None,
) -> tuple[int | None, dict[str, Any] | None, str]:
    payload = _canonical(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"session-eval-judge/{JUDGE_VERSION}",
    }
    try:
        auth = _authorization_header(auth_env)
    except JudgeError:
        return None, None, "auth_missing"
    if auth is not None:
        headers["Authorization"] = auth
    request = urllib.request.Request(recipient, data=payload, headers=headers, method="POST")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=60) as response:
            status = int(getattr(response, "status", 0) or 0)
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code or 0)
        try:
            raw = exc.read() if exc.fp is not None else b""
        except OSError:
            raw = b""
        if status in {301, 302, 303, 307, 308}:
            return status, None, "redirect_refused"
        if status < 200 or status >= 300:
            return status, None, "http_error"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None, None, "transport_failure"
    if status < 200 or status >= 300:
        return status, None, "http_error"
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, None, "invalid_json"
    if not isinstance(parsed, dict):
        return status, None, "invalid_json"
    return status, parsed, "ok"


def _parse_verdict(parsed: dict[str, Any], rubric_id: str, allowed_ids: set[str]) -> tuple[dict[str, Any] | None, str]:
    if parsed.get("tools") or parsed.get("tool_calls"):
        return None, "tools_not_allowed"
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, "malformed_output"
    first = choices[0]
    if not isinstance(first, dict):
        return None, "malformed_output"
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    if isinstance(content, list):
        texts = [
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {None, "text"}
        ]
        content = "".join(texts)
    if not isinstance(content, str) or not content.strip():
        return None, "malformed_output"
    text = content.strip()
    try:
        verdict = json.loads(text)
    except json.JSONDecodeError:
        return None, "malformed_output"
    if isinstance(verdict, str):
        try:
            verdict = json.loads(verdict)
        except json.JSONDecodeError:
            return None, "malformed_output"
    if not isinstance(verdict, dict):
        return None, "malformed_output"
    if verdict.get("rubric_id") not in {None, rubric_id}:
        return None, "unsupported_status"
    status = verdict.get("status")
    observed = verdict.get("observed")
    if status not in {"pass", "fail", "unknown"}:
        return None, "unsupported_status"
    pairing = _status_observed_pairing(rubric_id)
    allowed_for_status = set(pairing[status])
    if observed not in allowed_for_status:
        return None, "unsupported_status"
    refs = verdict.get("evidence_ids") or verdict.get("evidence") or []
    if not isinstance(refs, list):
        return None, "unsupported_evidence_reference"

    evidence_ids: list[str] = []
    for ref in refs:
        name = str(ref)
        if name not in allowed_ids:
            return None, "unsupported_evidence_reference"
        evidence_ids.append(name)
    explanation = verdict.get("explanation")
    if status in {"pass", "fail"}:
        if not isinstance(explanation, str) or not explanation.strip():
            return None, "malformed_output"
        if SECRET_PATTERN.search(explanation):
            explanation = "Anchored explanation redacted."
        explanation = _safe_label(explanation, 400)
    else:
        explanation = _safe_label(explanation, 400) if isinstance(explanation, str) else None
    return {
        "status": status,
        "observed": observed,
        "explanation": explanation,
        "evidence_ids": evidence_ids,
    }, "ok"


def _rollup(all_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for check in all_checks:
        check_id = str(check.get("id") or "")
        if not check_id:
            continue
        entry = counts.setdefault(
            check_id,
            {
                "id": check_id,
                "class": check.get("class"),
                "kind": check.get("kind"),
                "channel": check.get("channel"),
                "pass": 0,
                "fail": 0,
                "not_applicable": 0,
                "unknown": 0,
            },
        )
        status = check.get("status")
        if status in entry:
            entry[status] += 1
    return [counts[key] for key in sorted(counts)]


def _opt_in(
    rubric_ids: Sequence[str] | None,
    provider: str | None,
    model: str | None,
    recipient: str | None,
    approval: Any,
) -> bool:
    if rubric_ids:
        return True
    if provider or model or recipient:
        return True
    if approval is not None:
        return True
    return False


def _normalize_rubrics(rubric_ids: Sequence[str] | None) -> list[str]:
    if not rubric_ids:
        return []
    seen: list[str] = []
    for item in rubric_ids:
        name = str(item)
        if name not in JUDGE_IDS:
            raise JudgeError(f"unknown rubric id: {name}")
        if name not in seen:
            seen.append(name)
    return seen


def _existing_attempts(receipt: dict[str, Any]) -> dict[tuple[str, str, str, str, str, str], dict[str, Any]]:
    found: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    runs = receipt.get("runs") if isinstance(receipt.get("runs"), list) else []
    for run in runs:
        if not isinstance(run, dict):
            continue
        for check in run.get("checks") or []:
            if not isinstance(check, dict):
                continue
            block = check.get("judge") if isinstance(check.get("judge"), dict) else {}
            attempt = block.get("attempt") if isinstance(block.get("attempt"), dict) else None
            if not attempt:
                continue
            key = (
                str(attempt.get("run_id") or run.get("id") or ""),
                _strip_sha_prefix(str(attempt.get("snapshot_hash") or "")),
                str(attempt.get("rubric_id") or check.get("id") or ""),
                str(attempt.get("model") or block.get("model") or ""),
                str(attempt.get("approval_id") or block.get("approval_id") or ""),
                str(attempt.get("payload_hash") or ""),
            )
            if all(key[:5]):
                found[key] = check
    return found


def _audit_from_capability(capability: _ApprovalCapability) -> dict[str, Any]:
    binding = capability.binding()
    return {
        "approval_id": capability.approval_id,
        "granted": True,
        "provider": binding.get("provider"),
        "model": binding.get("model"),
        "recipient": binding.get("recipient"),
        "scope": list(binding.get("scope") or []),
        "purpose": list(binding.get("purpose") or []),
        "runs": list(binding.get("runs") or []),
        "payload_hash": binding.get("payload_hash"),
    }


def _na_row(check_id: str) -> dict[str, Any]:
    return _check(check_id, "not_applicable", "judge_opt_out_zero_provider_calls")


def _unknown_row(
    check_id: str,
    observed: str,
    error: dict[str, str] | None,
    *,
    model: str | None = None,
    provider: str | None = None,
    approval_id: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    explanation: str | None = None,
    attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _check(
        check_id,
        "unknown",
        observed,
        evidence,
        error,
        _identity(
            check_id,
            model=model,
            provider=provider,
            approval_id=approval_id,
            explanation=explanation,
            attempt=attempt,
        ),
    )


def _replace_run_judges(run: dict[str, Any], judge_rows: list[dict[str, Any]]) -> None:
    existing = [item for item in (run.get("checks") or []) if isinstance(item, dict)]
    kept = [item for item in existing if item.get("id") not in JUDGE_IDS]
    run["checks"] = kept + judge_rows


def _write_receipt(document: dict[str, Any], out: str | Path | None, loaded_path: Path | None) -> Path:
    out_dir = ingest_mod._output_root(
        out or ((loaded_path.parent / "judge") if loaded_path is not None else ingest_mod._default_output_dir() / "judge")
    )
    ingest_mod._secure_dir(out_dir)
    immutable_id = sha256_text(_canonical(document))
    ingest_mod._write_immutable_json(out_dir / "receipts" / f"{immutable_id}.json", document)
    requested_path = out_dir / "receipt.json"
    if requested_path.exists() and requested_path.read_bytes() != _canonical(document).encode("utf-8"):
        requested_path = ingest_mod._write_immutable_json(out_dir / f"receipt-{immutable_id}.json", document)
    else:
        requested_path = ingest_mod._write_immutable_json(requested_path, document)
    return requested_path


def _prepare_core(
    receipt: dict[str, Any],
    *,
    snapshot_root: Path | None,
    rubric_ids: Sequence[str],
    provider: str | None,
    model: str | None,
    recipient: str | None,
    semantic_items: list[dict[str, Any]],
    scope: Sequence[str] | None = None,
) -> dict[str, Any]:
    runs = [run for run in (receipt.get("runs") or []) if isinstance(run, dict)]
    requested = list(rubric_ids)
    missing_identity = not (provider and model and recipient and requested)
    per_run: list[dict[str, Any]] = []
    callable_ok = not missing_identity
    reason = "ready" if callable_ok else "incomplete_identity"
    bodies: list[dict[str, Any]] = []
    for run in runs:
        run_items = _items_for_run(semantic_items, run)
        run_scope = list(scope) if scope is not None else _proposed_scope(run_items)
        for name in run_scope:
            if name not in ALLOWED_SCOPES:
                callable_ok = False
                reason = "invalid_scope"
        prepared_rubrics: list[dict[str, Any]] = []
        for rubric_id in requested:
            ok_span = True
            span_reason = "ok"
            for item in run_items:
                verified, detail = _verify_span(run, snapshot_root, item)
                if not verified:
                    ok_span = False
                    span_reason = detail
                    break
            sufficient, evidence_reason = _evidence_sufficient(rubric_id, run_items, run)
            ready = ok_span and sufficient and not missing_identity and reason != "invalid_scope"
            body = None
            if ready:
                body = _chat_body(str(model), rubric_id, run, run_items, run_scope)
                if _contains_forbidden(body):
                    ready = False
                    callable_ok = False
                    reason = "forbidden_payload"
                    body = None
                else:
                    bodies.append(body)
            prepared_rubrics.append(
                {
                    "rubric_id": rubric_id,
                    "ready": ready,
                    "reason": "ok" if ready else span_reason if not ok_span else evidence_reason if not sufficient else reason,
                    "evidence": [_pointer(run, item) for item in run_items],
                    "item_ids": [item["id"] for item in run_items],
                    "items": run_items,
                    "body": body,
                    "scope": run_scope,
                }
            )
        per_run.append(
            {
                "run_id": run.get("id"),
                "snapshot_hash": _run_snapshot_hash(run),
                "parser_version": _run_parser_version(run),
                "lifecycle": _lifecycle_state(run),
                "scope": run_scope,
                "rubrics": prepared_rubrics,
            }
        )
    payload_hash = sha256_text(_canonical(bodies)) if bodies else sha256_text("")
    preview = {
        "callable": bool(callable_ok and bodies),
        "reason": reason if not (callable_ok and bodies) else "ready",
        "provider": provider,
        "model": model,
        "recipient": recipient,
        "rubric_ids": requested,
        "scope": list(scope) if scope is not None else (per_run[0]["scope"] if per_run else [SCOPE_STRUCTURAL, SCOPE_POINTERS]),
        "purpose": requested,
        "runs": [{"run_id": item["run_id"], "snapshot_hash": item["snapshot_hash"]} for item in per_run],
        "payload": bodies,
        "payload_hash": payload_hash,
        "zero_calls": not (callable_ok and bodies),
        "prepared": per_run,
    }
    return preview


def prepare_judge_request(
    receipt: dict[str, Any],
    *,
    snapshot_root: str | Path | None,
    rubric_ids: Sequence[str],
    provider: str,
    model: str,
    recipient: str,
    semantic_evidence: Any = None,
) -> dict[str, Any]:
    """Return a preview of the exact outbound request. Never calls a provider."""

    document = copy.deepcopy(receipt)
    items = _load_semantic_evidence(semantic_evidence)
    requested = _normalize_rubrics(rubric_ids)
    root = Path(snapshot_root).expanduser() if snapshot_root is not None else None
    return _prepare_core(
        document,
        snapshot_root=root,
        rubric_ids=requested,
        provider=provider,
        model=model,
        recipient=recipient,
        semantic_items=items,
    )


def approve_interactively(preview: dict[str, Any] | None) -> _ApprovalCapability | None:
    """Grant live authority only for the displayed preview. TTY or host stdin."""

    if not isinstance(preview, dict):
        return None
    if preview.get("callable") is not True:
        return None
    token = str(preview.get("payload_hash") or "")[:12]
    if not token:
        return None
    lines = [
        "session-eval judge approval",
        f"provider={preview.get('provider')}",
        f"model={preview.get('model')}",
        f"recipient={preview.get('recipient')}",
        f"rubrics={','.join(preview.get('rubric_ids') or [])}",
        f"scope={','.join(preview.get('scope') or [])}",
        f"purpose={','.join(preview.get('purpose') or [])}",
        "runs="
        + ";".join(
            f"{item.get('run_id')}@{item.get('snapshot_hash')}"
            for item in (preview.get("runs") or [])
            if isinstance(item, dict)
        ),
        f"payload_hash={preview.get('payload_hash')}",
        f"Type APPROVE {token} to authorize this exact payload, or anything else to deny.",
    ]
    try:
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
    except OSError:
        return None
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None
    try:
        answer = sys.stdin.readline()
    except OSError:
        return None
    if answer is None:
        return None
    if answer.strip() != f"APPROVE {token}":
        return None
    binding = {
        "provider": preview.get("provider"),
        "model": preview.get("model"),
        "recipient": preview.get("recipient"),
        "scope": list(preview.get("scope") or []),
        "purpose": list(preview.get("purpose") or []),
        "runs": list(preview.get("runs") or []),
        "payload_hash": preview.get("payload_hash"),
        "rubric_ids": list(preview.get("rubric_ids") or []),
    }
    approval_id = "approval-" + sha256_text(_canonical(binding))[:16]
    capability = _ApprovalCapability(binding, approval_id)
    _ISSUED[id(capability._secret)] = capability
    return capability


def _binding_match(
    capability: _ApprovalCapability,
    *,
    provider: str | None,
    model: str | None,
    recipient: str | None,
    rubric_ids: Sequence[str],
    preview: dict[str, Any],
    run: dict[str, Any],
) -> tuple[bool, str]:
    binding = capability.binding()
    if str(binding.get("provider") or "") != str(provider or ""):
        return False, "provider_mismatch"
    if str(binding.get("model") or "") != str(model or ""):
        return False, "model_mismatch"
    if str(binding.get("recipient") or "") != str(recipient or ""):
        return False, "recipient_mismatch"
    purpose = [str(item) for item in (binding.get("purpose") or [])]
    if list(rubric_ids) != purpose and set(rubric_ids) - set(purpose):
        return False, "purpose_mismatch"
    approved_scope = [str(item) for item in (binding.get("scope") or [])]
    preview_scope = [str(item) for item in (preview.get("scope") or [])]
    if approved_scope and preview_scope and set(preview_scope) - set(approved_scope):
        return False, "scope_mismatch"
    approved_runs = binding.get("runs") if isinstance(binding.get("runs"), list) else []
    run_id = str(run.get("id") or "")
    snap = _run_snapshot_hash(run)
    for item in approved_runs:
        if not isinstance(item, dict):
            continue
        if str(item.get("run_id") or "") == run_id and _strip_sha_prefix(str(item.get("snapshot_hash") or "")) == _strip_sha_prefix(snap):
            return True, "ok"
    return False, "run_snapshot_mismatch"


def judge_receipt(
    receipt: dict[str, Any],
    *,
    out: str | Path | None = None,
    snapshot_root: str | Path | None = None,
    rubric_ids: Sequence[str] | None = None,
    provider: str | None = None,
    model: str | None = None,
    recipient: str | None = None,
    approval: Any = None,
    semantic_evidence: Any = None,
    auth_env: str | None = None,
) -> tuple[dict[str, Any], Path]:
    """Apply opt-in judges. Default is zero provider calls."""

    document, loaded_path = _load_receipt(receipt, None)
    if document.get("schema") not in (None, RECEIPT_SCHEMA):
        raise JudgeError(f"unsupported receipt schema: {document.get('schema')}")
    snapshot_dir = _derive_snapshot_root(loaded_path, snapshot_root)
    requested = _normalize_rubrics(rubric_ids)
    opted = _opt_in(requested, provider, model, recipient, approval)
    semantic_items = _load_semantic_evidence(semantic_evidence)
    attempts = _existing_attempts(document)
    provider_calls = 0
    live = approval if _is_capability(approval) else None

    runs = [copy.deepcopy(run) for run in (document.get("runs") or []) if isinstance(run, dict)]
    all_checks: list[dict[str, Any]] = []

    if not opted:
        for run in runs:
            rows = [_na_row(check_id) for check_id in JUDGE_IDS]
            _replace_run_judges(run, rows)
            all_checks.extend(run.get("checks") or [])
        if not runs:
            all_checks.extend(_na_row(check_id) for check_id in JUDGE_IDS)
        enriched = dict(document)
        provenance = dict(enriched.get("provenance") or {}) if isinstance(enriched.get("provenance"), dict) else {}
        provenance.update(
            {
                "judge": "session-eval-judge",
                "judge_version": JUDGE_VERSION,
                "judge_rubric_set": RUBRIC_SET,
                "provider_calls": 0,
                "judge_invoked": False,
            }
        )
        if runs:
            enriched["runs"] = runs
            all_from_runs = [item for run in runs for item in (run.get("checks") or []) if isinstance(item, dict)]
            enriched["checks"] = _rollup(all_from_runs)
        else:
            enriched["checks"] = _rollup(all_checks)
        enriched["provenance"] = provenance
        enriched["schema"] = RECEIPT_SCHEMA
        if "approvals" not in enriched or not isinstance(enriched.get("approvals"), list):
            enriched["approvals"] = list(document.get("approvals") or []) if isinstance(document.get("approvals"), list) else []
        path = _write_receipt(enriched, out, loaded_path)
        return enriched, path

    if not requested:
        requested = list(JUDGE_IDS)

    identity_complete = bool(provider and model and recipient)
    preview = None
    if identity_complete:
        preview = _prepare_core(
            {"runs": runs, "schema": document.get("schema")},
            snapshot_root=snapshot_dir,
            rubric_ids=requested,
            provider=provider,
            model=model,
            recipient=recipient,
            semantic_items=semantic_items,
            scope=(live.binding().get("scope") if live else None),
        )

    for run in runs:
        rows: list[dict[str, Any]] = []
        for check_id in JUDGE_IDS:
            if check_id not in requested:
                rows.append(_na_row(check_id))
                continue
            if not identity_complete:
                rows.append(
                    _unknown_row(
                        check_id,
                        "incomplete_identity",
                        _error("internal", "opt-in missing provider, model, recipient, or run identity"),
                        model=model,
                        provider=provider,
                    )
                )
                continue
            if live is None:
                rows.append(
                    _unknown_row(
                        check_id,
                        "approval_not_live",
                        _error("internal", "live interactive approval capability is required"),
                        model=model,
                        provider=provider,
                    )
                )
                continue
            assert preview is not None
            matched, match_reason = _binding_match(
                live,
                provider=provider,
                model=model,
                recipient=recipient,
                rubric_ids=requested,
                preview=preview,
                run=run,
            )
            if not matched:
                rows.append(
                    _unknown_row(
                        check_id,
                        "approval_mismatch",
                        _error("internal", "approval does not bind this run snapshot, provider, model, recipient, scope, or purpose"),
                        model=model,
                        provider=provider,
                        approval_id=None,
                    )
                )
                continue
            prepared_run = next(
                (item for item in preview.get("prepared") or [] if item.get("run_id") == run.get("id")),
                None,
            )
            prepared = None
            if prepared_run:
                prepared = next(
                    (item for item in prepared_run.get("rubrics") or [] if item.get("rubric_id") == check_id),
                    None,
                )
            approval_id = live.approval_id
            current_payload_hash = str(preview.get("payload_hash") or "")
            if prepared is None or not prepared.get("ready") or prepared.get("body") is None:
                reason = str((prepared or {}).get("reason") or preview.get("reason") or "insufficient_evidence")
                local_unknown = _rubric_observed(check_id)["unknown"]
                observed = {
                    "missing_required_kinds": local_unknown,
                    "requests_unenumerable": "requests_unenumerable",
                    "missing_outcome": local_unknown,
                    "lifecycle_unknown": local_unknown,
                    "claims_unevaluable": "claims_unevaluable",
                    "missing_inventory": "selection_unevaluable",
                    "missing_step": "selection_unevaluable",
                    "missing_selection": "selection_unevaluable",
                    "friction_unevaluable": "friction_unevaluable",
                    "frozen_hash_mismatch": "snapshot_mismatch",
                    "evidence_hash_mismatch": "snapshot_mismatch",
                    "span_missing": "snapshot_mismatch",
                    "frozen_unreadable": "snapshot_mismatch",
                    "source_not_in_snapshot": "snapshot_mismatch",
                    "snapshot_mismatch": "snapshot_mismatch",
                    "snapshot_root_unavailable": "snapshot_mismatch",
                }.get(reason, local_unknown)

                kind = "io" if "snapshot" in reason or reason.startswith("frozen") or reason == "span_missing" else "internal"
                rows.append(
                    _unknown_row(
                        check_id,
                        observed,
                        _error(kind, "insufficient permitted semantic evidence or snapshot mismatch"),
                        model=model,
                        provider=provider,
                        approval_id=approval_id,
                        evidence=list((prepared or {}).get("evidence") or []),
                    )
                )
                continue
            if str(live.binding().get("payload_hash") or "") != current_payload_hash:
                rows.append(
                    _unknown_row(
                        check_id,
                        "approval_mismatch",
                        _error("internal", "approval does not bind this outbound payload"),
                        model=model,
                        provider=provider,
                        approval_id=approval_id,
                        evidence=list(prepared.get("evidence") or []),
                    )
                )
                continue
            attempt_key = (
                str(run.get("id") or ""),
                _strip_sha_prefix(_run_snapshot_hash(run)),
                check_id,
                str(model or ""),
                str(approval_id or ""),
                current_payload_hash,
            )
            prior = attempts.get(attempt_key) or _ATTEMPT_ROWS.get(attempt_key)
            if prior is not None:
                reused = copy.deepcopy(prior)
                block = dict(reused.get("judge") or {})
                attempt = dict(block.get("attempt") or {})
                if str(attempt.get("payload_hash") or "") != current_payload_hash:
                    rows.append(
                        _unknown_row(
                            check_id,
                            "approval_mismatch",
                            _error("internal", "cached attempt does not bind this outbound payload"),
                            model=model,
                            provider=provider,
                            approval_id=approval_id,
                            evidence=list(prepared.get("evidence") or []),
                        )
                    )
                    continue
                attempt["reused"] = True
                block["attempt"] = attempt
                reused["judge"] = block
                rows.append(reused)
                continue
            body = prepared["body"]
            status_code, parsed, transport_reason = _one_http_call(str(recipient), body, auth_env)
            provider_calls += 1
            attempt = {
                "run_id": run.get("id"),
                "snapshot_hash": _run_snapshot_hash(run),
                "rubric_id": check_id,
                "model": model,
                "provider": provider,
                "approval_id": approval_id,
                "payload_hash": preview.get("payload_hash"),
                "http_status": status_code,
                "called": True,
                "reused": False,
            }
            evidence_rows = list(prepared.get("evidence") or [])
            if transport_reason != "ok" or parsed is None:

                bounded = _reject_reason(transport_reason)
                attempt["reject_reason"] = bounded
                row = _unknown_row(
                    check_id,
                    _rubric_observed(check_id)["provider"],
                    _error("provider", f"unaccepted_response:{bounded}"),
                    model=model,
                    provider=provider,
                    approval_id=approval_id,
                    evidence=evidence_rows,
                    attempt=attempt,
                )
                _ATTEMPT_ROWS[attempt_key] = copy.deepcopy(row)
                rows.append(row)
                continue
            allowed_ids = set(prepared.get("item_ids") or [])
            verdict, parse_reason = _parse_verdict(parsed, check_id, allowed_ids)
            if verdict is None:
                bounded = _reject_reason(parse_reason)
                attempt["reject_reason"] = bounded
                row = _unknown_row(
                    check_id,
                    _rubric_observed(check_id)["provider"],
                    _error("provider", f"unaccepted_response:{bounded}"),
                    model=model,
                    provider=provider,
                    approval_id=approval_id,
                    evidence=evidence_rows,
                    attempt=attempt,
                )
                _ATTEMPT_ROWS[attempt_key] = copy.deepcopy(row)
                rows.append(row)
                continue
            id_to_pointer = {
                item_id: pointer
                for item_id, pointer in zip(prepared.get("item_ids") or [], evidence_rows)
            }
            cited = [id_to_pointer[item_id] for item_id in verdict["evidence_ids"] if item_id in id_to_pointer]
            if not cited:
                cited = evidence_rows
            if check_id == "judge.grounding" and verdict["status"] == "pass":
                claims = [item for item in (prepared.get("items") or []) if item.get("kind") == "claim"]
                relations = [
                    str((item.get("labels") or {}).get("relation") or "")
                    for item in (prepared.get("items") or [])
                    if item.get("kind") == "recorded_result"
                ]
                if claims and not any(rel in {"supporting", "contradicting"} for rel in relations):
                    row = _unknown_row(
                        check_id,
                        "claims_unevaluable",
                        _error("provider", "provider returned an error"),
                        model=model,
                        provider=provider,
                        approval_id=approval_id,
                        evidence=cited,
                        attempt=attempt,
                    )
                    _ATTEMPT_ROWS[attempt_key] = copy.deepcopy(row)
                    rows.append(row)
                    continue
            if verdict["status"] == "unknown":
                row = _unknown_row(
                    check_id,
                    str(verdict["observed"]),
                    None if verdict["observed"] != "provider_error" else _error("provider", "provider returned an error"),
                    model=model,
                    provider=provider,
                    approval_id=approval_id,
                    evidence=cited,
                    explanation=verdict.get("explanation"),
                    attempt=attempt,
                )
                _ATTEMPT_ROWS[attempt_key] = copy.deepcopy(row)
                rows.append(row)
                continue
            row = _check(
                check_id,
                str(verdict["status"]),
                str(verdict["observed"]),
                cited,
                None,
                _identity(
                    check_id,
                    model=model,
                    provider=provider,
                    approval_id=approval_id,
                    explanation=verdict.get("explanation"),
                    attempt=attempt,
                ),
            )
            _ATTEMPT_ROWS[attempt_key] = copy.deepcopy(row)
            rows.append(row)
        _replace_run_judges(run, rows)
        all_checks.extend(run.get("checks") or [])

    if not runs:
        for check_id in JUDGE_IDS:
            if check_id not in requested:
                all_checks.append(_na_row(check_id))
            elif not identity_complete:
                all_checks.append(
                    _unknown_row(
                        check_id,
                        "incomplete_identity",
                        _error("internal", "opt-in missing provider, model, recipient, or run identity"),
                        model=model,
                        provider=provider,
                    )
                )
            else:
                all_checks.append(
                    _unknown_row(
                        check_id,
                        "approval_not_live",
                        _error("internal", "live interactive approval capability is required"),
                        model=model,
                        provider=provider,
                    )
                )

    enriched = dict(document)
    provenance = dict(enriched.get("provenance") or {}) if isinstance(enriched.get("provenance"), dict) else {}
    previous_calls = provenance.get("provider_calls")
    try:
        previous_count = int(previous_calls or 0)
    except (TypeError, ValueError):
        previous_count = 0
    provenance.update(
        {
            "judge": "session-eval-judge",
            "judge_version": JUDGE_VERSION,
            "judge_rubric_set": RUBRIC_SET,
            "provider_calls": previous_count + provider_calls,
            "judge_invoked": bool(opted),
            "judge_provider_calls_this_run": provider_calls,
        }
    )
    if runs:
        enriched["runs"] = runs
        all_from_runs = [item for run in runs for item in (run.get("checks") or []) if isinstance(item, dict)]
        enriched["checks"] = _rollup(all_from_runs)
        judge_errors = [
            item
            for item in all_from_runs
            if isinstance(item, dict) and item.get("id") in JUDGE_IDS and item.get("error")
        ]
    else:
        enriched["checks"] = _rollup(all_checks)
        judge_errors = [item for item in all_checks if item.get("error")]
    if judge_errors:
        enriched["infra_ok"] = False
    approvals = list(document.get("approvals") or []) if isinstance(document.get("approvals"), list) else []
    if live is not None:
        audit = _audit_from_capability(live)
        if not any(isinstance(item, dict) and item.get("approval_id") == audit["approval_id"] for item in approvals):
            approvals.append(audit)
    enriched["approvals"] = approvals
    enriched["provenance"] = provenance
    enriched["schema"] = RECEIPT_SCHEMA
    if "catalog_id" not in enriched or enriched.get("catalog_id") in (None, UNKNOWN):
        enriched["catalog_id"] = CATALOG_ID
    path = _write_receipt(enriched, out, loaded_path)
    return enriched, path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval-judge",
        description="Opt-in session-eval judges. Default is zero provider calls.",
    )
    parser.add_argument("--receipt", default=None, help="path to styrir-session-eval/v0 receipt.json")
    parser.add_argument("--snapshot-root", default=None, help="frozen snapshot directory")
    parser.add_argument("--out", "--output", default=None, help="output directory for the judged immutable receipt")
    parser.add_argument("--rubric", dest="rubrics", action="append", default=[], help="judge rubric id (repeatable)")
    parser.add_argument("--provider", default=None, help="provider identity; never inferred")
    parser.add_argument("--model", default=None, help="model identity; never inferred")
    parser.add_argument("--recipient", default=None, help="exact OpenAI-compatible chat completions URL")
    parser.add_argument("--evidence", default=None, help="JSON file of locally prepared redacted semantic evidence")
    parser.add_argument("--auth-env", default=None, help="environment variable holding the bearer token; omitted means no Authorization header")
    parser.add_argument("--preview", action="store_true", help="print the exact outbound preview and exit without calling")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        document, _loaded = _load_receipt(None, args.receipt)
        if args.preview:
            if not (args.provider and args.model and args.recipient and args.rubrics):
                preview = {
                    "callable": False,
                    "reason": "incomplete_identity",
                    "provider": args.provider,
                    "model": args.model,
                    "recipient": args.recipient,
                    "rubric_ids": args.rubrics,
                    "zero_calls": True,
                }
            else:
                preview = prepare_judge_request(
                    document,
                    snapshot_root=args.snapshot_root,
                    rubric_ids=args.rubrics,
                    provider=args.provider,
                    model=args.model,
                    recipient=args.recipient,
                    semantic_evidence=args.evidence,
                )
            dumped = json.dumps(preview, indent=2 if args.pretty else None, ensure_ascii=False, sort_keys=not args.pretty)
            print(dumped)
            return 0
        approval = None
        if args.rubrics and args.provider and args.model and args.recipient:
            preview = prepare_judge_request(
                document,
                snapshot_root=args.snapshot_root,
                rubric_ids=args.rubrics,
                provider=args.provider,
                model=args.model,
                recipient=args.recipient,
                semantic_evidence=args.evidence,
            )
            approval = approve_interactively(preview)
        judged, path = judge_receipt(
            document,
            out=args.out,
            snapshot_root=args.snapshot_root,
            rubric_ids=args.rubrics or None,
            provider=args.provider,
            model=args.model,
            recipient=args.recipient,
            approval=approval,
            semantic_evidence=args.evidence,
            auth_env=args.auth_env,
        )
    except (JudgeError, ingest_mod.IngestError) as exc:
        parser.error(str(exc))
        return 2
    summary = {
        "receipt": str(path),
        "hard_pass": judged.get("hard_pass"),
        "infra_ok": judged.get("infra_ok"),
        "provider_calls": (judged.get("provenance") or {}).get("judge_provider_calls_this_run"),
        "approvals": [item.get("approval_id") for item in (judged.get("approvals") or []) if isinstance(item, dict)],
    }
    print(json.dumps(summary, indent=2 if args.pretty else None, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
