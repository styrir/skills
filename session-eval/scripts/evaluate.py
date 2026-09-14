#!/usr/bin/env python3
"""Deterministic session-eval catalog evaluator.

Consumes a ``styrir-session-eval/v0`` ingest receipt plus hash-verified frozen
snapshots.  Enriches the same receipt schema with catalog checks, coverage,
``hard_pass`` and ``infra_ok``.  Does not ingest live bytes as historical truth,
does not reimplement the skill-history registry, and does not duplicate
WorkGraph publication scoring.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import re
import subprocess
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import ingest as ingest_mod

UNKNOWN = ingest_mod.UNKNOWN
CATALOG_ID = "session-eval-check-catalog/v1"
EVALUATOR_VERSION = "1.0.0"
CLAIM_LANGUAGE_VERSION = "1.0.0"
RECEIPT_SCHEMA = "styrir-session-eval/v0"
WORKGRAPH_BIN_DEFAULT = Path("/Users/brooks/Code/agent-ops/bin/workgraph-eval-score")
DEFAULT_FIRST_PARTY_ROOT = Path.home() / "Code" / "skills"

# Envelope keys stripped only when the whole event is treated as args.
_ENVELOPE_KEYS = {
    "id",
    "call_id",
    "callId",
    "tool_call_id",
    "toolCallId",
    "tool_use_id",
    "toolUseId",
    "timestamp",
    "ts",
    "time",
    "created_at",
    "createdAt",
    "started_at",
    "startedAt",
    "ended_at",
    "endedAt",
    "event_id",
    "eventId",
    "uuid",
    "parentUuid",
    "request_id",
    "requestId",
    "sessionId",
    "session_id",
    "ordinal",
    "seq",
    "sequence",
}

_ARG_KEYS = ("arguments", "args", "input", "parameters", "params")
_SHELL_TOOLS = {
    "bash",
    "shell",
    "zsh",
    "sh",
    "command",
    "run_terminal_cmd",
    "terminal",
    "powershell",
    "cmd",
}
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_EPOCH_INT_RE = re.compile(r"^\d{9,12}$")
_SKILL_PATH_RE = re.compile(r"(?i)(?:^|[\\/])SKILL\.md$")
_SIDECAR_INDEX_RE = re.compile(r"(?i)(session_index\.jsonl|\.sqlite3?$)")

# Versioned explicit claim-language patterns (CLAIM_LANGUAGE_VERSION).
# Ambiguous prose that does not match remains unknown, never invented certainty.
CLAIM_LANGUAGE = {
    "version": CLAIM_LANGUAGE_VERSION,
    "command_success": (
        r"\b(?:all\s+)?(?:unit\s+|integration\s+)?tests?\s+passed\b",
        r"\b(?:the\s+)?(?:command|check|pytest|lint|typecheck|type-?check|build|npm\s+test|cargo\s+test)\s+"
        r"(?:has\s+)?(?:passed|succeeded)\b",
        r"\bexit(?:ed)?(?:\s+with)?(?:\s+code)?\s*0\b",
        r"\b(?:command|check)\s+completed\s+successfully\b",
        r"\b(?P<cmd>pytest|npm\s+test|cargo\s+test|lint|typecheck|type-?check|build)\s+(?:passed|succeeded|ok)\b",
    ),
    "command_failure": (
        r"\b(?:all\s+)?(?:unit\s+|integration\s+)?tests?\s+failed\b",
        r"\b(?:the\s+)?(?:command|check|pytest|lint|typecheck|type-?check|build|npm\s+test|cargo\s+test)\s+"
        r"(?:has\s+)?(?:failed|errored)\b",
        r"\bexit(?:ed)?(?:\s+with)?(?:\s+code)?\s+[1-9]\d*\b",
        r"\b(?P<cmd>pytest|npm\s+test|cargo\s+test|lint|typecheck|type-?check|build)\s+failed\b",
    ),
    "completion": (
        r"\b(?:the\s+)?(?:task|work|implementation|feature|change|fix|assignment)\s+is\s+(?:complete|done|finished)\b",
        r"\b(?:i(?:'ve| have)\s+)?(?:completed|finished)\s+(?:the\s+)?(?:task|work|implementation|feature|change|fix|assignment)\b",
        r"\ball\s+(?:tasks?|acceptance\s+checks?)\s+(?:are\s+)?(?:complete|done|passed)\b",
        r"\b(?:implementation|assignment)\s+(?:is\s+)?complete\b",
    ),
    "acceptance_named": (
        r"\b(pytest|npm\s+test|cargo\s+test|lint(?:er)?|typecheck|type-?check|unit\s+tests?|acceptance\s+checks?|tests?)\b",
    ),
    "command_named": (
        r"`([^`]+)`",
        r"\b(pytest|npm\s+test|cargo\s+test|lint|typecheck|type-?check|build)\b",
    ),
}

_COMMAND_SUCCESS_RE = [re.compile(p, re.I) for p in CLAIM_LANGUAGE["command_success"]]
_COMMAND_FAILURE_RE = [re.compile(p, re.I) for p in CLAIM_LANGUAGE["command_failure"]]
_COMPLETION_RE = [re.compile(p, re.I) for p in CLAIM_LANGUAGE["completion"]]
_ACCEPTANCE_NAMED_RE = [re.compile(p, re.I) for p in CLAIM_LANGUAGE["acceptance_named"]]
_COMMAND_NAMED_RE = [re.compile(p, re.I) for p in CLAIM_LANGUAGE["command_named"]]

# Key/token regex for tool.secret_pattern. Never emit the matched text.
SECRET_PATTERN = re.compile(
    r"(?i)(?:(?:api[_-]?key|secret(?:[_-]?key)?|password|passwd|access[_-]?token|auth[_-]?token|"
    r"private[_-]?key)\s*[\"']?\s*[:=]\s*[\"']?[^\s,\"']{8,}"
    r"|sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)

CATALOG_META: dict[str, dict[str, str]] = {
    "ingest.parse_error": {"class": "hard_fail", "kind": "code", "channel": "infra"},
    "ingest.schema_unknown_ok": {"class": "expected_behavior", "kind": "code", "channel": "behavior"},
    "ingest.sidecar_not_stream": {"class": "hard_fail", "kind": "code", "channel": "infra"},
    "session.identity_missing": {"class": "hard_fail", "kind": "code", "channel": "behavior"},
    "session.incomplete": {"class": "expected_behavior", "kind": "code", "channel": "behavior"},
    "session.clock_skew": {"class": "expected_behavior", "kind": "code", "channel": "behavior"},
    "tool.unpaired": {"class": "hard_fail", "kind": "code", "channel": "behavior"},
    "tool.result_error": {"class": "expected_behavior", "kind": "code", "channel": "behavior"},
    "tool.repeat_loop": {"class": "hard_fail", "kind": "code", "channel": "behavior"},
    "tool.secret_pattern": {"class": "hard_fail", "kind": "code", "channel": "behavior"},
    "tokens.unknown_not_zero": {"class": "hard_fail", "kind": "code", "channel": "infra"},
    "tokens.accounting_present": {"class": "expected_behavior", "kind": "code", "channel": "behavior"},
    "skill.registry_unreadable": {"class": "hard_fail", "kind": "code", "channel": "behavior"},
    "skill.digest_drift": {"class": "expected_behavior", "kind": "code", "channel": "behavior"},
    "skill.opaque_third_party": {"class": "expected_behavior", "kind": "code", "channel": "behavior"},
    "skill.activation_untracked": {"class": "expected_behavior", "kind": "code", "channel": "behavior"},
    "claim.command_outcome": {"class": "hard_fail", "kind": "code", "channel": "behavior"},
    "claim.completion": {"class": "hard_fail", "kind": "code", "channel": "behavior"},
    "closeout.full_md_leaked": {"class": "hard_fail", "kind": "code", "channel": "infra"},
    "closeout.eval_score_fail": {"class": "hard_fail", "kind": "code", "channel": "behavior"},
    "judge.completeness": {"class": "expected_behavior", "kind": "llm", "channel": "behavior"},
    "judge.grounding": {"class": "expected_behavior", "kind": "llm", "channel": "behavior"},
    "judge.tool_selection": {"class": "expected_behavior", "kind": "llm", "channel": "behavior"},
    "judge.friction": {"class": "expected_behavior", "kind": "llm", "channel": "behavior"},
}

CODE_CHECK_IDS = [check_id for check_id, meta in CATALOG_META.items() if meta["kind"] == "code"]
JUDGE_IDS = [check_id for check_id, meta in CATALOG_META.items() if meta["kind"] == "llm"]


class EvaluateError(Exception):
    """An expected local-input error suitable for a concise CLI message."""

_ACTIVE_FROZEN: ContextVar[dict[str, list[dict[str, Any]]] | None] = ContextVar("_ACTIVE_FROZEN", default=None)


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


def _check(
    check_id: str,
    status: str,
    observed: str,
    evidence: list[dict[str, Any]] | None = None,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    meta = CATALOG_META[check_id]
    return {
        "id": check_id,
        "class": meta["class"],
        "kind": meta["kind"],
        "channel": meta["channel"],
        "status": status,
        "observed": observed,
        "evidence": evidence or [],
        "error": error,
    }


def _evidence(
    source_path: str,
    snapshot_hash: str,
    parser_version: str,
    start_line: int,
    end_line: int | None = None,
    evidence_hash: str = UNKNOWN,
) -> dict[str, Any]:
    return {
        "source_path": source_path,
        "snapshot_hash": snapshot_hash,
        "parser_version": parser_version,
        "event_range": {"start_line": int(start_line), "end_line": int(end_line or start_line)},
        "evidence_hash": evidence_hash,
    }


def _run_snapshot_hash(run: dict[str, Any]) -> str:
    snapshot = run.get("source_snapshot")
    if isinstance(snapshot, dict) and snapshot.get("sha256"):
        return str(snapshot["sha256"])
    return UNKNOWN

def _source_file_digest(run: dict[str, Any], source_path: str) -> str:
    snapshot = run.get("source_snapshot") if isinstance(run.get("source_snapshot"), dict) else {}
    files = snapshot.get("files") if isinstance(snapshot.get("files"), list) else []
    for item in files:
        if isinstance(item, dict) and str(item.get("path") or "") == source_path:
            digest = item.get("sha256")
            if digest not in (None, "", UNKNOWN):
                return str(digest)
    return UNKNOWN


def _span_evidence_hash(
    frozen: dict[str, list[dict[str, Any]]] | None,
    source_path: str,
    line: int,
) -> str:
    if not frozen:
        return UNKNOWN
    record = _line_record(frozen, source_path, line)
    digest = record.get("raw_hash") if record else None
    if digest not in (None, "", UNKNOWN):
        return str(digest)
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


def _native_present(run: dict[str, Any]) -> bool:
    native = run.get("native_identity")
    if native in (None, "", UNKNOWN):
        return False
    if isinstance(native, dict):
        ident = native.get("id")
        return ident not in (None, "", UNKNOWN)
    return True


def _fallback_stem_used(run: dict[str, Any]) -> bool:
    run_id = str(run.get("id") or "")
    harness = str(run.get("harness") or "")
    source = str(run.get("source_path") or "")
    stem = Path(source).stem if source else ""
    if not run_id or not harness:
        return False
    if (not _native_present(run)) and run_id.startswith(f"{harness}:path:") and len(run_id.split(":")) >= 3:
        return True
    expected = f"{harness}:{stem}"
    return (not _native_present(run)) and run_id == expected and bool(stem)


def _snapshot_file_path(snapshot_root: Path, index: int, item: dict[str, str]) -> Path:
    path = str(item.get("path") or "")
    role = str(item.get("role") or "primary")
    digest = str(item.get("sha256") or "")
    basename = Path(path).name or "source"
    token = sha256_text(f"{path}:{role}")[:12]
    return snapshot_root / digest / f"{index:03d}-{token}-{basename}"


def _load_unknown_fields(private_root: Path | None) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    if private_root is None:
        return result
    path = private_root / "unknown-fields.json"
    if not path.is_file():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return result
    for item in payload.get("runs") or []:
        if isinstance(item, dict) and item.get("run_id"):
            fields = item.get("unknown_fields")
            result[str(item["run_id"])] = fields if isinstance(fields, list) else []
    return result


def _frozen_format(item: dict[str, Any]) -> str:
    path = str(item.get("path") or "")
    role = str(item.get("role") or "primary")
    name = Path(path).name.casefold()
    suffix = Path(path).suffix.casefold()
    if suffix in {".sqlite", ".sqlite3", ".db"}:
        return "binary"
    if name in {"summary.json", "usage.json", "prompt_context.json", "signals.json"}:
        return "json"
    if role == "sidecar" and suffix == ".json":
        return "json"
    if suffix == ".jsonl" or role == "primary":
        return "jsonl"
    if suffix == ".json":
        return "json"
    return "binary"


def _load_frozen_sources(
    run: dict[str, Any],
    snapshot_root: Path | None,
    evaluation_errors: list[dict[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    """Load hash-verified frozen snapshot bytes. Never consult live source bytes."""

    files: dict[str, list[dict[str, Any]]] = {}
    manifest = ((run.get("source_snapshot") or {}).get("files") or []) if isinstance(run.get("source_snapshot"), dict) else []
    if snapshot_root is None:
        evaluation_errors.append(_error("io", "snapshot root unavailable"))
        return files
    for index, item in enumerate(manifest):
        if not isinstance(item, dict):
            continue
        source_path = str(item.get("path") or "")
        expected = str(item.get("sha256") or "")
        role = str(item.get("role") or "primary")
        frozen = _snapshot_file_path(snapshot_root, index, item)
        try:
            data = frozen.read_bytes()
        except OSError as exc:
            evaluation_errors.append(_error("io", f"unreadable frozen snapshot: {frozen.name}: {exc}"))
            continue
        actual = sha256_bytes(data)
        if expected and actual != expected:
            evaluation_errors.append(_error("io", f"frozen snapshot hash mismatch: {frozen.name}"))
            continue
        fmt = _frozen_format(item)
        if fmt == "binary":
            continue
        if fmt == "json":
            record: dict[str, Any] = {
                "line": 1,
                "raw_hash": sha256_bytes(data),
                "text": None,
                "object": None,
                "parse_error": False,
                "source_path": source_path,
                "role": role,
                "format": "json",
            }
            try:
                text = data.decode("utf-8")
                record["text"] = text
                value = json.loads(text)
                if isinstance(value, dict):
                    record["object"] = value
                else:
                    record["parse_error"] = True
            except (UnicodeDecodeError, json.JSONDecodeError):
                record["parse_error"] = True
            files[source_path] = [record]
            files.setdefault(_snapshot_key(source_path, role), [record])
            continue
        lines: list[dict[str, Any]] = []
        offset = 0
        line_no = 0
        while offset < len(data):
            end = data.find(b"\n", offset)
            if end == -1:
                raw_line = data[offset:]
                offset = len(data)
            else:
                raw_line = data[offset : end + 1]
                offset = end + 1
            line_no += 1
            if not raw_line.strip():
                continue
            record = {
                "line": line_no,
                "raw_hash": sha256_bytes(raw_line),
                "text": None,
                "object": None,
                "parse_error": False,
                "source_path": source_path,
                "role": role,
                "format": "jsonl",
            }
            try:
                text = raw_line.decode("utf-8")
                record["text"] = text.rstrip("\n")
                value = json.loads(text)
                if isinstance(value, dict):
                    record["object"] = value
                else:
                    record["parse_error"] = True
            except (UnicodeDecodeError, json.JSONDecodeError):
                record["parse_error"] = True
            lines.append(record)
        files[source_path] = lines
        files.setdefault(_snapshot_key(source_path, role), lines)
    return files


def _snapshot_key(path: str, role: str) -> str:
    return f"{path}::{role}"


def _iter_frozen_records(frozen: dict[str, list[dict[str, Any]]]) -> Iterable[dict[str, Any]]:
    seen: set[tuple[str, int]] = set()
    for records in frozen.values():
        for record in records:
            key = (str(record.get("source_path")), int(record.get("line") or 0))
            if key in seen:
                continue
            seen.add(key)
            yield record


def _line_record(frozen: dict[str, list[dict[str, Any]]], source_path: str | None, line: Any) -> dict[str, Any] | None:
    if not source_path or line in (None, UNKNOWN):
        return None
    try:
        line_no = int(line)
    except (TypeError, ValueError):
        return None
    for record in frozen.get(source_path) or []:
        if int(record.get("line") or 0) == line_no:
            return record
    for records in frozen.values():
        for record in records:
            if record.get("source_path") == source_path and int(record.get("line") or 0) == line_no:
                return record
    return None


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _node_id(node: dict[str, Any]) -> str | None:
    for key in (
        "id",
        "call_id",
        "callId",
        "toolCallId",
        "tool_call_id",
        "tool_use_id",
        "toolUseId",
        "toolCallId",
    ):
        value = node.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return str(value)
    return None


def _extract_args_from_node(node: dict[str, Any]) -> tuple[bool, Any]:
    for key in _ARG_KEYS:
        if key in node:
            return True, node[key]
    payload = node.get("payload")
    if isinstance(payload, dict):
        for key in _ARG_KEYS:
            if key in payload:
                return True, payload[key]
    data = node.get("data")
    if isinstance(data, dict):
        for key in _ARG_KEYS:
            if key in data:
                return True, data[key]
    return False, None


def _tool_args_for_call(
    frozen: dict[str, list[dict[str, Any]]],
    call: dict[str, Any],
) -> tuple[bool, Any]:
    record = _line_record(frozen, call.get("source_path"), call.get("source_line"))
    if not record or not isinstance(record.get("object"), dict):
        return False, None
    call_id = str(call.get("id") or "")
    matched: list[Any] = []
    for node in _walk_dicts(record["object"]):
        found, extracted = _extract_args_from_node(node)
        if not found:
            continue
        node_id = _node_id(node)
        if call_id and node_id == call_id:
            return True, extracted
        matched.append(extracted)
    if len(matched) == 1:
        return True, matched[0]
    if not call_id and matched:
        return True, matched[0]
    obj = record["object"]
    found, extracted = _extract_args_from_node(obj)
    if found:
        return True, extracted
    return False, None


def _result_payload_from_record(record: dict[str, Any] | None, call_id: str | None) -> tuple[Any, bool | None, int | None]:
    if not record or not isinstance(record.get("object"), dict):
        return None, None, None
    payload = None
    is_error: bool | None = None
    exit_code: int | None = None
    obj = record["object"]
    for node in _walk_dicts(obj):
        node_id = _node_id(node)
        if call_id and node_id not in {None, str(call_id)} and node.get("tool_use_id") not in {None, call_id} and node.get("toolCallId") not in {None, call_id} and node.get("call_id") not in {None, call_id}:
            continue
        if "is_error" in node:
            is_error = node.get("is_error") is True
        elif "isError" in node:
            is_error = node.get("isError") is True
        for key in ("exit_code", "exitCode", "exit"):
            value = node.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                exit_code = value
        for key in ("content", "output", "result"):
            if key in node and payload is None:
                payload = node[key]
        inner = node.get("payload")
        if isinstance(inner, dict):
            for key in ("exit_code", "exitCode", "exit"):
                value = inner.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    exit_code = value
            if payload is None:
                for key in ("content", "output", "result"):
                    if key in inner:
                        payload = inner[key]
                        break
    if payload is None:
        for key in ("content", "output", "result"):
            if key in obj:
                payload = obj[key]
                break
    if is_error is None:
        if obj.get("is_error") is True or obj.get("isError") is True:
            is_error = True
        elif obj.get("is_error") is False or obj.get("isError") is False:
            is_error = False
    return payload, is_error, exit_code


def _canonicalize_args(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonicalize_args(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, list):
        return [_canonicalize_args(item) for item in value]
    return value


def _prepare_args(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in "[{":
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return value
            return parsed
        return value
    return value


def normalized_args_digest(value: Any) -> str:
    prepared = _prepare_args(value)
    canonical = _canonicalize_args(prepared)
    return sha256_text(_canonical(canonical))


def _result_hash(payload: Any) -> str:
    return sha256_text(_canonical(_canonicalize_args(payload)))


def _agent_key(run: dict[str, Any], turn: dict[str, Any]) -> tuple[Any, Any, Any]:
    turn_lineage = turn.get("lineage") if isinstance(turn.get("lineage"), dict) else {}
    run_lineage = run.get("lineage") if isinstance(run.get("lineage"), dict) else {}

    def _pick(mapping: dict[str, Any], key: str) -> Any:
        value = mapping.get(key)
        if value in (None, UNKNOWN, "", []):
            return None
        return value

    parent = _pick(turn_lineage, "parent") or _pick(run_lineage, "parent")
    attempt = _pick(turn_lineage, "attempt") or _pick(run_lineage, "attempt")
    if isinstance(attempt, dict):
        attempt_id = attempt.get("id") or attempt.get("number")
    else:
        attempt_id = attempt
    child = None
    children = turn_lineage.get("children")
    if children not in (None, UNKNOWN) and children:
        child = tuple(children) if isinstance(children, list) else children
    return (parent, attempt_id, child)


def _content_texts(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str) and value.strip():
        return [value]
    if isinstance(value, list):
        for item in value:
            texts.extend(_content_texts(item))
        return texts
    if not isinstance(value, dict):
        return []
    item_type = str(value.get("type") or "").casefold()
    if item_type in {
        "tool_use",
        "tooluse",
        "toolcall",
        "tool_call",
        "tool_result",
        "toolresult",
        "custom_tool_call",
        "custom_tool_call_output",
        "tool_call_update",
        "reasoning",
        "thinking",
        "thought",
        "agent_thought_chunk",
        "input_text",
        "user_message_chunk",
    }:
        return []
    for key in ("text", "content"):
        inner = value.get(key)
        if isinstance(inner, str) and inner.strip():
            texts.append(inner)
        elif inner is not None and inner is not value:
            texts.extend(_content_texts(inner))
    return texts


_NON_ASSISTANT_ROLES = {"user", "system", "tool", "reasoning", "developer"}
_TOOL_EVENT_KINDS = {
    "custom_tool_call",
    "custom_tool_call_output",
    "tool_result",
    "toolresult",
    "tool_call",
    "toolcall",
    "tool_call_update",
    "toolcall_update",
}
_REASONING_EVENT_KINDS = {"reasoning", "agent_thought_chunk", "thinking", "thought"}


def _assistant_visible_texts(record: dict[str, Any]) -> list[str]:
    """User-visible assistant text from one frozen source record.

    Codex ``response_item.payload`` messages and Grok nested
    ``agent_message_chunk`` payloads are included. Sidecars, system/user/tool
    records, and reasoning are excluded.
    """

    if str(record.get("role") or "").casefold() == "sidecar":
        return []
    obj = record.get("object")
    if not isinstance(obj, dict):
        return []
    texts: list[str] = []
    envelope_type = str(obj.get("type") or "").casefold()
    payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else None
    if payload is not None:
        payload_type = str(payload.get("type") or payload.get("event") or payload.get("kind") or "").casefold()
        payload_role = str(payload.get("role") or "").casefold()
        if (
            payload_role not in _NON_ASSISTANT_ROLES
            and payload_type not in _TOOL_EVENT_KINDS
            and payload_type not in _REASONING_EVENT_KINDS
            and (payload_type == "message" or (envelope_type == "response_item" and payload_role == "assistant"))
            and payload_role in {"", "assistant"}
        ):
            texts.extend(_content_texts(payload.get("content")))
            texts.extend(_content_texts(payload.get("text")))
    for _, nested in ingest_mod._grok_nested_payloads(obj):
        kind = ingest_mod._grok_kind(nested)
        if kind != "agent_message_chunk":
            continue
        texts.extend(_content_texts(nested.get("content")))
        texts.extend(_content_texts(nested.get("text")))
        message = nested.get("message") if isinstance(nested.get("message"), dict) else None
        if message is not None and str(message.get("role") or "").casefold() not in _NON_ASSISTANT_ROLES:
            texts.extend(_content_texts(message.get("content")))
            texts.extend(_content_texts(message.get("text")))
    role = str(obj.get("role") or "").casefold()
    typ = str(obj.get("type") or "").casefold()
    message = obj.get("message") if isinstance(obj.get("message"), dict) else None
    message_role = str((message or {}).get("role") or "").casefold()
    if message_role:
        role = message_role
    if role not in _NON_ASSISTANT_ROLES and typ not in (_NON_ASSISTANT_ROLES | _TOOL_EVENT_KINDS | _REASONING_EVENT_KINDS):
        if role == "assistant" or typ == "assistant":
            if message is not None:
                texts.extend(_content_texts(message.get("content")))
                texts.extend(_content_texts(message.get("text")))
            texts.extend(_content_texts(obj.get("content")))
            texts.extend(_content_texts(obj.get("text")))
    unique: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if text not in seen:
            seen.add(text)
            unique.append(text)
    return unique


def _collect_claims(run: dict[str, Any], frozen: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], bool]:
    """Extract claims from normalized assistant turns' anchored source payloads."""

    if not frozen:
        return [], False
    claims: list[dict[str, Any]] = []
    unread = False
    turns = run.get("turns") if isinstance(run.get("turns"), list) else []
    for turn_index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        if str(turn.get("role") or "").casefold() != "assistant":
            continue
        record = _line_record(frozen, turn.get("source_path"), turn.get("source_line"))
        if record is None:
            unread = True
            continue
        if str(record.get("role") or "").casefold() == "sidecar":
            continue
        if record.get("parse_error") or not isinstance(record.get("object"), dict):
            unread = True
            continue
        for text in _assistant_visible_texts(record):
            extracted = _extract_claims(text, record)
            for claim in extracted:
                claim["bound"] = True
                claim["turn_index"] = turn_index
                claim["agent"] = _agent_key(run, turn)
            claims.extend(extracted)
    if claims:
        return claims, True
    return claims, not unread


def _command_name_from_args(tool_name: str, args: Any) -> str | None:
    if isinstance(args, dict):
        for key in ("command", "cmd", "script"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                return value
        argv = args.get("argv")
        if isinstance(argv, list) and argv:
            return " ".join(str(item) for item in argv)
    if isinstance(args, str) and args.strip():
        return args
    if str(tool_name).casefold() in _SHELL_TOOLS:
        return None
    return None


def _identity_matches(claimed: str | None, command: str | None, tool_name: str) -> bool:
    if not claimed:
        return False
    claimed_cf = claimed.casefold()
    if command and claimed_cf in command.casefold():
        return True
    if claimed_cf == str(tool_name).casefold():
        return True
    return False


def _named_commands(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _COMMAND_NAMED_RE:
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            value = value.strip()
            if value and value.casefold() not in {item.casefold() for item in found}:
                found.append(value)
    return found


def _named_acceptance(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _ACCEPTANCE_NAMED_RE:
        for match in pattern.finditer(text):
            value = (match.group(1) if match.lastindex else match.group(0)).strip()
            if value and value.casefold() not in {item.casefold() for item in found}:
                found.append(value)
    return found


def _extract_claims(text: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for pattern in _COMMAND_SUCCESS_RE:
        match = pattern.search(text)
        if match:
            cmd = None
            if "cmd" in match.re.groupindex:
                cmd = match.group("cmd")
            named = _named_commands(text)
            claims.append(
                {
                    "kind": "command_outcome",
                    "polarity": "success",
                    "command": cmd or (named[0] if named else None),
                    "text_hash": sha256_text(text),
                    "line": record.get("line"),
                    "source_path": record.get("source_path"),
                    "raw_hash": record.get("raw_hash"),
                    "ambiguous": False,
                }
            )
            break
    else:
        for pattern in _COMMAND_FAILURE_RE:
            match = pattern.search(text)
            if match:
                cmd = None
                if "cmd" in match.re.groupindex:
                    cmd = match.group("cmd")
                named = _named_commands(text)
                claims.append(
                    {
                        "kind": "command_outcome",
                        "polarity": "failure",
                        "command": cmd or (named[0] if named else None),
                        "text_hash": sha256_text(text),
                        "line": record.get("line"),
                        "source_path": record.get("source_path"),
                        "raw_hash": record.get("raw_hash"),
                        "ambiguous": False,
                    }
                )
                break
    for pattern in _COMPLETION_RE:
        if pattern.search(text):
            claims.append(
                {
                    "kind": "completion",
                    "polarity": "success",
                    "command": None,
                    "acceptance": _named_acceptance(text),
                    "text_hash": sha256_text(text),
                    "line": record.get("line"),
                    "source_path": record.get("source_path"),
                    "raw_hash": record.get("raw_hash"),
                    "ambiguous": False,
                }
            )
            break
    return claims


def _source_line_of(item: dict[str, Any]) -> int:
    try:
        return int(item.get("source_line") if item.get("source_line") not in (None, UNKNOWN) else 0)
    except (TypeError, ValueError):
        return 0


def _event_position(item: dict[str, Any]) -> tuple[str, int]:
    return (str(item.get("source_path") or ""), _source_line_of(item))


def _to_epoch_seconds(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 100_000_000_000:
            seconds /= 1000
        return seconds
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if _EPOCH_INT_RE.match(text):
            return float(text)
        if _ISO_RE.match(text):
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
    return None


def _frozen_event_time(frozen: dict[str, list[dict[str, Any]]], source_path: Any, line: Any) -> float | None:
    record = _line_record(frozen, str(source_path) if source_path else None, line)
    if not record or not isinstance(record.get("object"), dict):
        return None
    stamp = ingest_mod._record_timestamp(record["object"])
    if stamp is None:
        nested = record["object"].get("params")
        if isinstance(nested, dict):
            stamp = ingest_mod._record_timestamp(nested)
    if stamp is None:
        return None
    raw = _first_timestamp_value(record["object"])
    epoch = _to_epoch_seconds(raw)
    if epoch is not None:
        return epoch
    return _to_epoch_seconds(stamp)


def _first_timestamp_value(obj: dict[str, Any]) -> Any:
    for key in ("timestamp", "ts", "time", "created_at", "createdAt", "started_at", "startedAt"):
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    params = obj.get("params")
    if isinstance(params, dict):
        for key in ("timestamp", "ts", "time"):
            if key in params and params[key] not in (None, ""):
                return params[key]
    return None


def _order_events(
    events: list[dict[str, Any]],
    frozen: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], bool]:
    if not events:
        return events, False

    def time_of(item: dict[str, Any]) -> float | None:
        if "time" in item:
            return item.get("time")
        return _frozen_event_time(frozen, item.get("source_path"), item.get("source_line"))

    for item in events:
        item["time"] = time_of(item)
    streams: dict[str, list[dict[str, Any]]] = {}
    for item in events:
        streams.setdefault(str(item.get("source_path") or ""), []).append(item)
    for items in streams.values():
        items.sort(key=_source_line_of)
    if len(streams) <= 1:
        return [item for items in streams.values() for item in items], False



    tools = [item for item in events if item.get("kind") == "tool"]
    resets = [item for item in events if item.get("kind") in {"user_turn", "terminal"}]
    timed_ok = all(time_of(item) is not None for item in events)
    if timed_ok:
        buckets: dict[float, list[dict[str, Any]]] = {}
        for item in events:
            stamp = time_of(item)
            if stamp is None:
                continue
            buckets.setdefault(stamp, []).append(item)
        ordered: list[dict[str, Any]] = []
        ambiguous = False
        for stamp in sorted(buckets):
            bucket = buckets[stamp]
            paths = {str(item.get("source_path") or "") for item in bucket}
            if len(paths) == 1:
                bucket.sort(key=_source_line_of)
            else:
                kinds = {item.get("kind") for item in bucket}
                if {"user_turn", "terminal"} & kinds and "tool" in kinds:
                    ambiguous = True
            ordered.extend(bucket)
        return ordered, ambiguous

    tool_paths = {str(item.get("source_path") or "") for item in tools}
    foreign_resets = [item for item in resets if str(item.get("source_path") or "") not in tool_paths]
    untimed_foreign = [item for item in foreign_resets if time_of(item) is None]
    if untimed_foreign and tools:
        return [item for items in streams.values() for item in items], True
    if len(tool_paths) > 1 and any(time_of(item) is None for item in tools):
        return [item for items in streams.values() for item in items], True
    return [item for items in streams.values() for item in items], False


def _is_authoritative_terminal_kind(kind: str, harness: Any) -> bool:
    """True only for ingest-authored terminal markers, never EOF or live."""

    text = str(kind or "").casefold()
    if not text or "eof_without_terminal" in text:
        return False
    if text in {"ended.metadata", "summary.ended_metadata"} or text.endswith("ended.metadata"):
        return True
    token = text.rsplit(":", 1)[-1].replace("-", "_")
    if token in ingest_mod._LIVE_MARKERS:
        return False
    harness_name = str(harness or "").casefold()
    scoped = ingest_mod._SCOPED_TERMINAL_MARKERS.get(harness_name, ingest_mod._TERMINAL_MARKERS)
    return token in scoped or token in ingest_mod._TERMINAL_MARKERS


def _authoritative_terminal_events(run: dict[str, Any]) -> list[dict[str, Any]]:
    lifecycle = run.get("lifecycle") if isinstance(run.get("lifecycle"), dict) else {}
    evidence = lifecycle.get("evidence") if isinstance(lifecycle.get("evidence"), list) else []
    harness = run.get("harness")
    events: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        if not _is_authoritative_terminal_kind(kind, harness):
            continue
        event_range = item.get("event_range") if isinstance(item.get("event_range"), dict) else {}
        line = event_range.get("start_line")
        if line in (None, UNKNOWN):
            line = event_range.get("end_line")
        events.append(
            {
                "kind": "terminal",
                "lifecycle_kind": kind,
                "source_path": item.get("source_path"),
                "source_line": line,
                "evidence_hash": item.get("evidence_hash"),
            }
        )
    return events


def _tool_invocations(
    run: dict[str, Any],
    frozen: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], bool]:
    events: list[dict[str, Any]] = []
    turns = run.get("turns") if isinstance(run.get("turns"), list) else []
    for turn_index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "").casefold()
        agent = _agent_key(run, turn)
        if role == "user":
            events.append(
                {
                    "kind": "user_turn",
                    "turn_index": turn_index,
                    "agent": agent,
                    "source_line": turn.get("source_line"),
                    "source_path": turn.get("source_path"),
                }
            )
            continue
        for call in turn.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            args_available, args = _tool_args_for_call(frozen, call)
            digest = normalized_args_digest(args) if args_available else None
            result_record = _line_record(frozen, call.get("result_source_path") or call.get("source_path"), call.get("result_source_line"))
            payload, is_error, exit_code = _result_payload_from_record(result_record, str(call.get("id") or ""))
            status = str(call.get("status") or "")
            if is_error is None:
                if status == "error":
                    is_error = True
                elif status == "ok":
                    is_error = False
            result_available = True
            if status == "ok" and result_record is None:
                result_available = False
            events.append(
                {
                    "kind": "tool",
                    "turn_index": turn_index,
                    "agent": agent,
                    "call": call,
                    "name": str(call.get("name") or UNKNOWN),
                    "args": args,
                    "args_available": args_available,
                    "args_digest": digest,
                    "status": status,
                    "is_error": is_error,
                    "exit_code": exit_code,
                    "result_available": result_available,
                    "result_hash": _result_hash(payload) if payload is not None else None,
                    "command": _command_name_from_args(str(call.get("name") or ""), args if args_available else None),
                    "source_line": call.get("source_line"),
                    "source_path": call.get("source_path"),
                    "result_source_line": call.get("result_source_line"),
                    "result_source_path": call.get("result_source_path"),
                    "paired": status in {"ok", "error"},
                }
            )
    events.extend(_authoritative_terminal_events(run))
    return _order_events(events, frozen)


def _timestamp_kind(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if 1_000_000_000 <= number <= 9_999_999_999:
            return "epoch"
        return None
    if isinstance(value, str):
        text = value.strip()
        if _ISO_RE.match(text):
            return "iso"
        if _EPOCH_INT_RE.match(text):
            return "epoch"
    return None


def _collect_timestamp_kinds(obj: Any) -> set[str]:
    kinds: set[str] = set()
    for node in _walk_dicts(obj):
        for key in ("timestamp", "ts", "time", "created_at", "createdAt", "started_at", "startedAt", "ended_at", "endedAt"):
            kind = _timestamp_kind(node.get(key))
            if kind:
                kinds.add(kind)
    return kinds


def _usage_emitted(run: dict[str, Any]) -> bool:
    tokens = run.get("tokens")
    return isinstance(tokens, dict)


def _usage_present(run: dict[str, Any], frozen: dict[str, list[dict[str, Any]]]) -> bool:
    provenance = run.get("usage_provenance")
    if isinstance(provenance, list) and provenance:
        return True
    tokens = run.get("tokens")
    if isinstance(tokens, dict) and any(value not in (None, UNKNOWN) for value in tokens.values()):
        if any(value not in (None, UNKNOWN, 0) for value in tokens.values()):
            return True
        if any(isinstance(value, (int, float)) and value != 0 for value in tokens.values()):
            return True
    for record in _iter_frozen_records(frozen):
        obj = record.get("object")
        if not isinstance(obj, dict):
            continue
        for node in _walk_dicts(obj):
            if any(key in node for key in ("usage", "tokens", "token_usage", "input_tokens", "inputTokens", "totalTokens")):
                return True
    return False


def _frozen_has_usage_fields(frozen: dict[str, list[dict[str, Any]]]) -> bool:
    for record in _iter_frozen_records(frozen):
        obj = record.get("object")
        if not isinstance(obj, dict):
            continue
        for node in _walk_dicts(obj):
            if any(key in node for key in ("usage", "tokens", "token_usage", "input_tokens", "inputTokens", "totalTokens", "total_tokens")):
                return True
    return False


def _pointer(run: dict[str, Any], source_path: str | None, line: Any, evidence_hash: str | None = None) -> dict[str, Any]:
    path = str(source_path or run.get("source_path") or UNKNOWN)
    try:
        start = int(line)
    except (TypeError, ValueError):
        start = 1
    snapshot = _run_snapshot_hash(run)
    span = evidence_hash
    if span in (None, "", UNKNOWN):
        span = _span_evidence_hash(_ACTIVE_FROZEN.get(), path, start)
    return _evidence(path, snapshot, _run_parser_version(run), start, start, span)


def _run_pointer(run: dict[str, Any]) -> dict[str, Any]:
    return _pointer(run, run.get("source_path"), 1)


def check_ingest_parse_error(run: dict[str, Any], frozen: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    parse_errors = run.get("parse_errors") if isinstance(run.get("parse_errors"), list) else []
    frozen_errors = [record for record in _iter_frozen_records(frozen) if record.get("parse_error")]
    evidence = []
    for item in parse_errors:
        if not isinstance(item, dict):
            continue
        evidence.append(
            _pointer(
                run,
                item.get("source_path"),
                (item.get("event_range") or {}).get("start_line") or item.get("line"),
                item.get("evidence_hash"),
            )
        )
    if not evidence:
        for record in frozen_errors:
            evidence.append(_pointer(run, record.get("source_path"), record.get("line"), record.get("raw_hash")))
    if parse_errors or frozen_errors:
        return _check(
            "ingest.parse_error",
            "fail",
            "record_not_object",
            evidence,
            _error("parse", "JSONL line is not an object"),
        )
    if run.get("source_path"):
        return _check("ingest.parse_error", "pass", "records_are_objects", [_run_pointer(run)])
    return _check("ingest.parse_error", "unknown", "primary_unopened")


def check_ingest_schema_unknown_ok(
    run: dict[str, Any],
    unknowns: list[dict[str, Any]] | None,
    private_available: bool,
) -> dict[str, Any]:
    if not private_available:
        return _check(
            "ingest.schema_unknown_ok",
            "unknown",
            "private_unknown_store_unreadable",
            [_run_pointer(run)],
            _error("io", "private unknown-field store unavailable"),
        )
    if unknowns:
        evidence = [
            _pointer(
                run,
                item.get("source_path"),
                (item.get("event_range") or {}).get("start_line"),
                UNKNOWN,
            )
            for item in unknowns
            if isinstance(item, dict)
        ]
        return _check("ingest.schema_unknown_ok", "pass", "unknown_fields_retained", evidence or [_run_pointer(run)])
    return _check("ingest.schema_unknown_ok", "not_applicable", "no_unknown_fields", [_run_pointer(run)])


def check_ingest_sidecar_not_stream(run: dict[str, Any]) -> dict[str, Any]:
    files = ((run.get("source_snapshot") or {}).get("files") or []) if isinstance(run.get("source_snapshot"), dict) else []
    primary = [item for item in files if isinstance(item, dict) and item.get("role") == "primary"]
    sidecars = [item for item in files if isinstance(item, dict) and item.get("role") == "sidecar"]
    index_sidecars = [
        item
        for item in sidecars
        if _SIDECAR_INDEX_RE.search(str(item.get("path") or ""))
    ]
    sqlite_primary = [
        item
        for item in primary
        if str(item.get("path") or "").casefold().endswith((".sqlite", ".sqlite3"))
    ]
    jsonl_primary = [
        item
        for item in primary
        if str(item.get("path") or "").casefold().endswith(".jsonl")
    ]
    if sqlite_primary and jsonl_primary:
        return _check("ingest.sidecar_not_stream", "fail", "sqlite_used_as_primary", [_run_pointer(run)])
    if index_sidecars and primary:
        return _check("ingest.sidecar_not_stream", "pass", "stream_primary_sidecar_enrichment", [_run_pointer(run)])
    if not index_sidecars:
        return _check("ingest.sidecar_not_stream", "not_applicable", "no_index_sidecar", [_run_pointer(run)])
    return _check("ingest.sidecar_not_stream", "unknown", "sidecar_stream_relationship_unresolved", [_run_pointer(run)])


def check_session_identity_missing(run: dict[str, Any]) -> dict[str, Any]:
    if _native_present(run) or _fallback_stem_used(run):
        observed = "native_identity" if _native_present(run) else "fallback_source_stem"
        return _check("session.identity_missing", "pass", observed, [_run_pointer(run)])
    return _check("session.identity_missing", "fail", "identity_absent", [_run_pointer(run)])


def check_session_incomplete(run: dict[str, Any]) -> dict[str, Any]:
    state = _lifecycle_state(run)
    if state == "live":
        return _check("session.incomplete", "not_applicable", "live_session", [_run_pointer(run)])
    if state == "terminal":
        return _check("session.incomplete", "pass", "explicit_terminal", [_run_pointer(run)])
    return _check("session.incomplete", "fail", "no_explicit_terminal", [_run_pointer(run)])


def check_session_clock_skew(run: dict[str, Any], frozen: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if str(run.get("harness") or "") != "grok":
        return _check("session.clock_skew", "not_applicable", "not_grok", [_run_pointer(run)])
    kinds: set[str] = set()
    for record in _iter_frozen_records(frozen):
        obj = record.get("object")
        if isinstance(obj, dict):
            kinds |= _collect_timestamp_kinds(obj)
    if not ({"iso", "epoch"} <= kinds):
        return _check("session.clock_skew", "not_applicable", "no_mixed_timestamp_scales", [_run_pointer(run)])
    observed_kinds = {
        _timestamp_kind(run.get("started_at")),
        _timestamp_kind(run.get("ended_at")),
    }
    observed_kinds.discard(None)
    if len(observed_kinds) > 1:
        return _check("session.clock_skew", "fail", "mixed_scales_unnormalized", [_run_pointer(run)])
    return _check("session.clock_skew", "pass", "normalized_to_one_scale", [_run_pointer(run)])


def check_tool_unpaired(run: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    state = _lifecycle_state(run)
    tools = [item for item in events if item.get("kind") == "tool"]
    if state == "live":
        return _check("tool.unpaired", "not_applicable", "live_session", [_run_pointer(run)])
    if state == "unknown":
        evidence = [_pointer(run, item.get("source_path"), item.get("source_line")) for item in tools if item.get("status") == "pending"]
        return _check("tool.unpaired", "unknown", "lifecycle_unknown", evidence or [_run_pointer(run)])
    unpaired = [item for item in tools if item.get("status") in {"pending", "unpaired"} or not item.get("paired")]
    if unpaired:
        evidence = [
            _pointer(run, item.get("source_path"), item.get("source_line"), UNKNOWN)
            for item in unpaired
        ]
        return _check("tool.unpaired", "fail", "unpaired_after_explicit_end", evidence)
    if not tools:
        return _check("tool.unpaired", "pass", "no_unpaired_tools", [_run_pointer(run)])
    return _check("tool.unpaired", "pass", "all_tools_paired", [_run_pointer(run)])


def check_tool_result_error(run: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    results = [item for item in events if item.get("kind") == "tool" and item.get("status") in {"ok", "error"}]
    if not results:
        return _check("tool.result_error", "not_applicable", "no_tool_results", [_run_pointer(run)])
    errors = [item for item in results if item.get("is_error") is True or item.get("status") == "error"]
    if errors:
        evidence = [_pointer(run, item.get("result_source_path") or item.get("source_path"), item.get("result_source_line") or item.get("source_line")) for item in errors]
        return _check("tool.result_error", "fail", "tool_result_is_error", evidence)
    return _check("tool.result_error", "pass", "no_tool_result_errors", [_run_pointer(run)])


_LOOP_ENUMERATION_CAP = 4096


def _loop_model_event(item: dict[str, Any]) -> dict[str, Any] | None:
    kind = item.get("kind")
    if kind == "user_turn":
        return {"kind": "user", "time": item.get("time"), "orig": item}
    if kind == "terminal":
        return {"kind": "terminal", "time": item.get("time"), "orig": item}
    if kind != "tool":
        return None
    missing_success = item.get("is_error") is False and (
        item.get("result_available") is False or not item.get("result_hash")
    )
    if not item.get("args_available", True):
        args: Any = "?"
    else:
        args = item.get("args_digest")
        if args is None:
            args = "x"
    return {
        "kind": "tool",
        "agent": item.get("agent", "main"),
        "tool": item.get("name") or "read",
        "args": args,
        "result": "?" if missing_success else item.get("result_hash"),
        "success": item.get("is_error") is False,
        "time": item.get("time"),
        "orig": item,
    }


def _loop_concrete(sequence: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], int]:
    streak = 0
    previous = None
    previous_result = None
    failed = False
    streak_items: list[dict[str, Any]] = []
    failing: list[dict[str, Any]] = []
    max_items: list[dict[str, Any]] = []
    max_streak = 0
    for event in sequence:
        if event.get("kind") in {"user", "terminal"}:
            streak, previous, previous_result = 0, None, None
            streak_items = []
            continue
        if event.get("kind") != "tool":
            continue
        identity = (event.get("agent", "main"), event.get("tool", "read"), event.get("args", "x"))
        result = event.get("result")
        reset = previous is not None and identity != previous
        if (
            event.get("success")
            and result is not None
            and previous_result is not None
            and result != previous_result
            and previous is not None
            and identity[1] == previous[1]
        ):
            reset = True
        if reset:
            streak, previous_result = 0, None
            streak_items = []
        streak += 1
        streak_items.append(event)
        previous = identity
        if result is not None:
            previous_result = result
        if streak > max_streak:
            max_streak = streak
            max_items = list(streak_items)
        if streak >= 4:
            failed = True
            failing = list(streak_items)
    return ("fail" if failed else "pass", failing or max_items, max_streak)


def _loop_hole_product(sequence: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    result_idx = [index for index, event in enumerate(sequence) if event.get("result") == "?"]
    args_idx = [index for index, event in enumerate(sequence) if event.get("args") == "?"]
    if not result_idx and not args_idx:
        return [sequence]
    result_labels = sorted(
        {str(event.get("result")) for event in sequence if event.get("result") not in {None, "?"}}
    )
    result_labels += [f"fresh-r{index}" for index in range(len(result_idx))]
    args_labels = sorted(
        {str(event.get("args")) for event in sequence if event.get("args") not in {None, "?"}}
    )
    args_labels += [f"fresh-a{index}" for index in range(len(args_idx))]
    if not result_labels:
        result_labels = ["fresh-r0"]
    if not args_labels:
        args_labels = ["fresh-a0"]
    result_space = len(result_labels) ** len(result_idx) if result_idx else 1
    args_space = len(args_labels) ** len(args_idx) if args_idx else 1
    if result_space * args_space > _LOOP_ENUMERATION_CAP:
        same = copy.deepcopy(sequence)
        same_result = next((event.get("result") for event in sequence if event.get("result") not in {None, "?"}), "R")
        same_args = next((event.get("args") for event in sequence if event.get("args") not in {None, "?"}), "x")
        for index in result_idx:
            same[index]["result"] = same_result
        for index in args_idx:
            same[index]["args"] = same_args
        distinct = copy.deepcopy(sequence)
        for offset, index in enumerate(result_idx):
            distinct[index]["result"] = f"fresh-r{offset}"
        for offset, index in enumerate(args_idx):
            distinct[index]["args"] = f"fresh-a{offset}"
        return [same, distinct]
    result_choices = list(itertools.product(result_labels, repeat=len(result_idx))) if result_idx else [()]
    args_choices = list(itertools.product(args_labels, repeat=len(args_idx))) if args_idx else [()]
    completed: list[list[dict[str, Any]]] = []
    for result_values in result_choices:
        for args_values in args_choices:
            clone = copy.deepcopy(sequence)
            for index, value in zip(result_idx, result_values):
                clone[index]["result"] = value
            for index, value in zip(args_idx, args_values):
                clone[index]["args"] = value
            completed.append(clone)
    return completed


def _loop_uncertain(sequence: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], int]:
    outcomes: set[str] = set()
    evidence: list[dict[str, Any]] = []
    max_streak = 0
    for completed in _loop_hole_product(sequence):
        status, items, streak = _loop_concrete(completed)
        outcomes.add(status)
        if streak > max_streak:
            max_streak = streak
        if status == "fail" and items:
            evidence = items
        elif not evidence:
            evidence = items
        if "pass" in outcomes and "fail" in outcomes:
            return "unknown", evidence, max_streak
    if len(outcomes) == 1:
        return next(iter(outcomes)), evidence, max_streak
    return "unknown", evidence, max_streak


def _loop_merge_streams(streams: list[list[dict[str, Any]]]) -> tuple[str, list[dict[str, Any]], int]:
    outcomes: set[str] = set()
    evidence: list[dict[str, Any]] = []
    max_streak = 0
    truncated = False
    generated = 0

    def merge(prefix: list[dict[str, Any]], remaining: list[list[dict[str, Any]]]) -> None:
        nonlocal truncated, generated, max_streak, evidence
        if truncated or ("pass" in outcomes and "fail" in outcomes):
            return
        if not any(remaining):
            generated += 1
            if generated > _LOOP_ENUMERATION_CAP:
                truncated = True
                return
            status, items, streak = _loop_uncertain(prefix)
            outcomes.add(status)
            if streak > max_streak:
                max_streak = streak
            if status == "fail" and items:
                evidence = items
            elif not evidence:
                evidence = items
            return
        for index, stream in enumerate(remaining):
            if not stream:
                continue
            event = stream[0]
            timestamp = event.get("time")
            if timestamp is not None and any(
                other.get("time") is not None and other["time"] < timestamp
                for items in remaining
                for other in items
            ):
                continue
            next_remaining = [list(items) for items in remaining]
            next_remaining[index] = stream[1:]
            merge(prefix + [event], next_remaining)

    merge([], streams)
    if truncated or len(outcomes) != 1:
        if len(outcomes) == 1 and not truncated:
            return next(iter(outcomes)), evidence, max_streak
        if truncated:
            return "unknown", evidence, max_streak
        return "unknown", evidence, max_streak
    return next(iter(outcomes)), evidence, max_streak


def _loop_streams(events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in events:
        modeled = _loop_model_event(item)
        if modeled is None:
            continue
        grouped.setdefault(str(item.get("source_path") or ""), []).append(modeled)
    streams: list[list[dict[str, Any]]] = []
    for items in grouped.values():
        items.sort(key=lambda event: _source_line_of(event.get("orig") or {}))
        streams.append(items)
    return streams


def check_tool_repeat_loop(
    run: dict[str, Any],
    events: list[dict[str, Any]],
    chronology_unknown: bool = False,
) -> dict[str, Any]:
    tools = [item for item in events if item.get("kind") == "tool"]
    if not tools:
        return _check("tool.repeat_loop", "not_applicable", "no_tool_calls", [_run_pointer(run)])
    streams = _loop_streams(events)
    if not streams:
        return _check("tool.repeat_loop", "not_applicable", "no_tool_calls", [_run_pointer(run)])
    status, modeled_items, max_streak = _loop_merge_streams(streams)
    orig_items = [item.get("orig") or item for item in modeled_items]
    if status == "fail":
        evidence = [_pointer(run, item.get("source_path"), item.get("source_line")) for item in orig_items]
        return _check("tool.repeat_loop", "fail", "consecutive_repeat_ge_4", evidence or [_run_pointer(run)])
    if status == "unknown":
        observed = (
            "chronology_or_evidence_unresolved"
            if chronology_unknown or len(streams) > 1
            else "argument_or_result_evidence_unresolved"
        )
        return _check("tool.repeat_loop", "unknown", observed, [_run_pointer(run)])
    observed = "repeat_under_4" if max_streak else "single_or_progressed"
    evidence = [_pointer(run, item.get("source_path"), item.get("source_line")) for item in orig_items]
    return _check("tool.repeat_loop", "pass", observed, evidence or [_run_pointer(run)])



def check_tool_secret_pattern(run: dict[str, Any], frozen: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    scanned = False
    for record in _iter_frozen_records(frozen):
        text = record.get("text")
        if text is None:
            continue
        scanned = True
        if SECRET_PATTERN.search(text):
            matches.append(record)
    if not scanned:
        return _check(
            "tool.secret_pattern",
            "unknown",
            "source_unreadable",
            [_run_pointer(run)],
            _error("io", "frozen source lines unavailable"),
        )
    if matches:
        evidence = [
            _pointer(run, item.get("source_path"), item.get("line"), item.get("raw_hash"))
            for item in matches
        ]
        return _check("tool.secret_pattern", "fail", "secret_pattern_matched", evidence)
    return _check("tool.secret_pattern", "pass", "no_secret_pattern", [_run_pointer(run)])


def check_tokens_unknown_not_zero(run: dict[str, Any], frozen: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if not _usage_emitted(run):
        return _check("tokens.unknown_not_zero", "not_applicable", "no_token_fields", [_run_pointer(run)])
    tokens = run.get("tokens") if isinstance(run.get("tokens"), dict) else {}
    cost = run.get("cost_usd")
    source_has_usage = _frozen_has_usage_fields(frozen)
    zeros = [
        field
        for field, value in tokens.items()
        if value == 0 or value == 0.0
    ]
    cost_zero = cost == 0 or cost == 0.0
    if zeros or cost_zero:
        if not source_has_usage:
            return _check("tokens.unknown_not_zero", "fail", "absent_usage_written_zero", [_run_pointer(run)])
    if all(value == UNKNOWN for value in tokens.values()) or not zeros:
        if cost in (UNKNOWN, None) or not cost_zero or source_has_usage:
            return _check("tokens.unknown_not_zero", "pass", "absent_usage_unknown", [_run_pointer(run)])
    return _check("tokens.unknown_not_zero", "pass", "usage_present_nonzero_or_unknown", [_run_pointer(run)])


def check_tokens_accounting_present(run: dict[str, Any], frozen: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if not _usage_present(run, frozen):
        return _check("tokens.accounting_present", "not_applicable", "no_usage_object", [_run_pointer(run)])
    tokens = run.get("tokens") if isinstance(run.get("tokens"), dict) else {}
    provenance = run.get("usage_provenance") if isinstance(run.get("usage_provenance"), list) else []
    seen: set[tuple[Any, Any]] = set()
    duplicate = False
    for item in provenance:
        if not isinstance(item, dict):
            continue
        key = (item.get("record_identity"), item.get("field"))
        if key in seen:
            duplicate = True
            break
        seen.add(key)
    numeric = {field: tokens.get(field) for field in ("input", "output", "cache_read", "cache_create", "total")}
    known_parts = [
        numeric[field]
        for field in ("input", "output", "cache_read", "cache_create")
        if isinstance(numeric[field], (int, float)) and not isinstance(numeric[field], bool)
    ]
    total = numeric.get("total")
    inconsistent = False
    if known_parts and isinstance(total, (int, float)) and not isinstance(total, bool):
        part_sum = sum(known_parts)
        # Allow a recorded total that is the component sum or an explicit total field.
        if total != part_sum and len(known_parts) == 4:
            inconsistent = True
        elif total < max(known_parts):
            inconsistent = True
    if duplicate or inconsistent:
        observed = "double_counted" if duplicate else "inconsistent_usage"
        return _check("tokens.accounting_present", "fail", observed, [_run_pointer(run)])
    return _check("tokens.accounting_present", "pass", "usage_consistent", [_run_pointer(run)])


def check_skill_registry_unreadable(
    run: dict[str, Any],
    registry: dict[str, Any] | None,
) -> dict[str, Any]:
    session_skills = [item for item in (run.get("skills") or []) if isinstance(item, dict) and item.get("path")]
    if not session_skills:
        return _check("skill.registry_unreadable", "not_applicable", "no_skill_path_in_context", [_run_pointer(run)])
    if registry is None:
        return _check(
            "skill.registry_unreadable",
            "unknown",
            "registry_unavailable",
            [_run_pointer(run)],
        )
    entries = registry.get("skills") if isinstance(registry.get("skills"), list) else []
    by_path = {
        str(item.get("path")): item
        for item in entries
        if isinstance(item, dict) and item.get("path")
    }
    evidence = [_pointer(run, run.get("source_path"), 1)]
    missing = False
    for skill in session_skills:
        path = str(skill.get("path"))
        entry = by_path.get(path)
        if entry is None:
            missing = True
            continue
        readable = entry.get("readable")
        name = entry.get("name") or entry.get("frontmatter_name")
        if readable is False or not name or name == UNKNOWN:
            missing = True
    if missing:
        return _check("skill.registry_unreadable", "fail", "skill_missing_or_unnamed", evidence)
    return _check("skill.registry_unreadable", "pass", "skill_frontmatter_name_present", evidence)


def check_skill_digest_drift(run: dict[str, Any], registry: dict[str, Any] | None) -> dict[str, Any]:
    if registry is None:
        return _check("skill.digest_drift", "unknown", "registry_unavailable", [_run_pointer(run)])
    entries = registry.get("skills") if isinstance(registry.get("skills"), list) else []
    drifted = False
    comparable = False
    for item in entries:
        if not isinstance(item, dict):
            continue
        snapshots = item.get("snapshots")
        if isinstance(snapshots, list) and len(snapshots) >= 2:
            digests = [snap.get("digest") for snap in snapshots if isinstance(snap, dict)]
            known = [digest for digest in digests if digest not in (None, UNKNOWN)]
            if len(known) >= 2:
                comparable = True
                if len(set(known)) > 1:
                    drifted = True
        historical = item.get("historical_loaded_digest") or item.get("digest")
        current = item.get("current_on_disk_digest")
        if historical not in (None, UNKNOWN) and current not in (None, UNKNOWN):
            comparable = True
            if historical != current:
                drifted = True
    if not comparable:
        return _check("skill.digest_drift", "not_applicable", "no_comparable_snapshots", [_run_pointer(run)])
    if drifted:
        return _check("skill.digest_drift", "fail", "digest_changed", [_run_pointer(run)])
    return _check("skill.digest_drift", "pass", "digest_equal", [_run_pointer(run)])


def check_skill_opaque_third_party(
    run: dict[str, Any],
    registry: dict[str, Any] | None,
    first_party_root: Path,
) -> dict[str, Any]:
    if registry is None:
        return _check("skill.opaque_third_party", "unknown", "registry_unavailable", [_run_pointer(run)])
    activations = registry.get("activations") if isinstance(registry.get("activations"), list) else []
    skills = registry.get("skills") if isinstance(registry.get("skills"), list) else run.get("skills") or []
    if not activations and not skills:
        return _check("skill.opaque_third_party", "not_applicable", "no_activation_path", [_run_pointer(run)])
    root = first_party_root.expanduser().resolve()
    opaque = False
    resolved = False
    unresolved = False
    for item in list(activations) + [entry for entry in skills if isinstance(entry, dict)]:
        if not isinstance(item, dict):
            continue
        ownership = item.get("ownership") or item.get("resolved_source")
        path_value = item.get("resolved_path") or item.get("path")
        if ownership in {"unresolved", UNKNOWN} or not path_value:
            unresolved = True
            continue
        try:
            resolved_path = Path(str(path_value)).expanduser().resolve()
            resolved = True
            try:
                resolved_path.relative_to(root)
                first_party = True
            except ValueError:
                first_party = False
            if item.get("first_party") is False or ownership == "third_party":
                first_party = False
            if not first_party:
                opaque = True
        except OSError:
            unresolved = True
    if unresolved and not resolved:
        return _check("skill.opaque_third_party", "unknown", "ownership_unresolved", [_run_pointer(run)])
    if not resolved:
        return _check("skill.opaque_third_party", "not_applicable", "no_resolvable_ownership", [_run_pointer(run)])
    if opaque:
        return _check("skill.opaque_third_party", "fail", "outside_first_party_root", [_run_pointer(run)])
    return _check("skill.opaque_third_party", "pass", "first_party_source", [_run_pointer(run)])


def check_skill_activation_untracked(run: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    skills = [item for item in (run.get("skills") or []) if isinstance(item, dict)]
    skill_like = False
    for item in events:
        if item.get("kind") != "tool":
            continue
        name = str(item.get("name") or "").casefold()
        command = str(item.get("command") or "")
        if "skill" in name or _SKILL_PATH_RE.search(command):
            skill_like = True
        args = item.get("args")
        if isinstance(args, dict):
            for value in args.values():
                if isinstance(value, str) and _SKILL_PATH_RE.search(value):
                    skill_like = True
        if isinstance(args, str) and _SKILL_PATH_RE.search(args):
            skill_like = True
    if skills:
        skill_like = True
    if not skill_like:
        return _check("skill.activation_untracked", "not_applicable", "no_skill_mention", [_run_pointer(run)])
    digestable = [
        item
        for item in skills
        if item.get("digest") not in (None, UNKNOWN) or item.get("path")
    ]
    missing = [
        item
        for item in skills
        if item.get("digest") in (None, UNKNOWN) and not item.get("path")
    ]
    if skills and all(item.get("digest") not in (None, UNKNOWN) for item in skills):
        return _check("skill.activation_untracked", "pass", "digestable_skill_present", [_run_pointer(run)])
    if digestable and not missing:
        # Path present is not by itself a digest. Require a digestable SKILL.md.
        if all(item.get("digest") not in (None, UNKNOWN) for item in digestable):
            return _check("skill.activation_untracked", "pass", "digestable_skill_present", [_run_pointer(run)])
        return _check("skill.activation_untracked", "fail", "no_digestable_skill", [_run_pointer(run)])
    if skills:
        return _check("skill.activation_untracked", "fail", "no_digestable_skill", [_run_pointer(run)])
    return _check("skill.activation_untracked", "fail", "no_digestable_skill", [_run_pointer(run)])


def _bind_claims(run: dict[str, Any], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach normalized turn order and agent/attempt identity to extracted claims."""

    turns = run.get("turns") if isinstance(run.get("turns"), list) else []
    for claim in claims:
        if claim.get("bound") and claim.get("turn_index") is not None:
            continue
        path = str(claim.get("source_path") or "")
        try:
            line = int(claim.get("line"))
        except (TypeError, ValueError):
            claim["bound"] = False
            claim["turn_index"] = None
            claim["agent"] = None
            continue
        matches: list[tuple[int, tuple[Any, Any, Any]]] = []
        for index, turn in enumerate(turns):
            if not isinstance(turn, dict):
                continue
            if str(turn.get("source_path") or "") != path:
                continue
            try:
                turn_line = int(turn.get("source_line"))
            except (TypeError, ValueError):
                continue
            if turn_line == line:
                matches.append((index, _agent_key(run, turn)))
        if len(matches) != 1:
            claim["bound"] = False
            claim["turn_index"] = None
            claim["agent"] = None
        else:
            claim["bound"] = True
            claim["turn_index"] = matches[0][0]
            claim["agent"] = matches[0][1]
    return claims


def _final_outcome_for_claim(
    events: list[dict[str, Any]],
    claim: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """Return (status, event) where status is success|failure|unknown."""

    if not claim.get("bound"):
        return "unknown", None
    try:
        claim_order = int(claim.get("turn_index"))
    except (TypeError, ValueError):
        return "unknown", None
    claim_agent = claim.get("agent")
    claimed = claim.get("command")
    candidates = []
    for item in events:
        if item.get("kind") != "tool":
            continue
        try:
            item_order = int(item.get("turn_index"))
        except (TypeError, ValueError):
            continue
        if item_order >= claim_order:
            continue
        if item.get("agent") != claim_agent:
            continue
        if claimed:
            if not _identity_matches(claimed, item.get("command"), str(item.get("name") or "")):
                continue
        candidates.append(item)
    if claimed and not candidates:
        return "unknown", None
    if not claimed:
        shell = [
            item
            for item in candidates
            if str(item.get("name") or "").casefold() in _SHELL_TOOLS or item.get("command")
        ]
        if len(shell) == 1:
            candidates = shell
        elif len({(item.get("name"), item.get("args_digest")) for item in candidates}) != 1:
            return "unknown", None
    if not candidates:
        return "unknown", None
    final = candidates[-1]
    if final.get("exit_code") is not None:
        return ("success" if final["exit_code"] == 0 else "failure"), final
    if final.get("is_error") is True or final.get("status") == "error":
        return "failure", final
    if final.get("status") == "pending" or not final.get("paired"):
        return "unknown", final
    return "unknown", final


def check_claim_command_outcome(
    run: dict[str, Any],
    frozen: dict[str, list[dict[str, Any]]],
    events: list[dict[str, Any]],
    proof_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    claims, readable = _collect_claims(run, frozen)
    _bind_claims(run, claims)
    command_claims = [item for item in claims if item.get("kind") == "command_outcome"]
    if not readable and not command_claims:
        return _check(
            "claim.command_outcome",
            "unknown",
            "source_unreadable",
            [_run_pointer(run)],
            _error("io", "frozen source unavailable for claim extraction"),
        )
    if not command_claims:
        return _check("claim.command_outcome", "not_applicable", "no_command_outcome_claim", [_run_pointer(run)])
    results = []
    evidence = []
    for claim in command_claims:
        evidence.append(_pointer(run, claim.get("source_path"), claim.get("line"), claim.get("raw_hash")))
        outcome, event = _final_outcome_for_claim(events, claim)
        if event is not None:
            evidence.append(_pointer(run, event.get("result_source_path") or event.get("source_path"), event.get("result_source_line") or event.get("source_line")))
        expected = "success" if claim.get("polarity") == "success" else "failure"
        if outcome == "unknown":
            results.append("unknown")
            proof_gaps.append(
                {
                    "id": "claim.historical_policy_unavailable",
                    "check_id": "claim.command_outcome",
                    "run_id": run.get("id"),
                    "reason": "command identity, attempt association or final outcome is ambiguous/missing",
                }
            )
        elif outcome == expected:
            results.append("pass")
        else:
            results.append("fail")
    if "fail" in results:
        return _check("claim.command_outcome", "fail", "final_outcome_contradicts_claim", evidence)
    if "unknown" in results:
        return _check("claim.command_outcome", "unknown", "command_outcome_unresolved", evidence)
    return _check("claim.command_outcome", "pass", "final_outcome_agrees", evidence)


def check_claim_completion(
    run: dict[str, Any],
    frozen: dict[str, list[dict[str, Any]]],
    events: list[dict[str, Any]],
    proof_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    claims, readable = _collect_claims(run, frozen)
    _bind_claims(run, claims)
    completion_claims = [item for item in claims if item.get("kind") == "completion"]
    if not readable and not completion_claims:
        return _check(
            "claim.completion",
            "unknown",
            "source_unreadable",
            [_run_pointer(run)],
            _error("io", "frozen source unavailable for claim extraction"),
        )
    if not completion_claims:
        return _check("claim.completion", "not_applicable", "no_completion_claim", [_run_pointer(run)])
    evidence = [_pointer(run, item.get("source_path"), item.get("line"), item.get("raw_hash")) for item in completion_claims]
    statuses: list[str] = []
    for claim in completion_claims:
        acceptance = [item for item in (claim.get("acceptance") or []) if item.casefold() not in {"task", "work", "implementation", "feature", "change", "fix", "assignment"}]
        named_checks = [
            item
            for item in acceptance
            if item.casefold() not in {"acceptance checks", "acceptance check"}
        ]
        # A recorded completion claim with no identifiable acceptance-check set
        # remains applicable unknown.
        if not named_checks:
            statuses.append("unknown")
            proof_gaps.append(
                {
                    "id": "claim.historical_policy_unavailable",
                    "check_id": "claim.completion",
                    "run_id": run.get("id"),
                    "reason": "acceptance-check set cannot be established",
                }
            )
            continue
        check_statuses = []
        for named in named_checks:
            synthetic = {
                "command": named,
                "line": claim.get("line"),
                "polarity": "success",
                "bound": claim.get("bound"),
                "turn_index": claim.get("turn_index"),
                "agent": claim.get("agent"),
                "source_path": claim.get("source_path"),
            }
            outcome, event = _final_outcome_for_claim(events, synthetic)
            if event is not None:
                evidence.append(
                    _pointer(
                        run,
                        event.get("result_source_path") or event.get("source_path"),
                        event.get("result_source_line") or event.get("source_line"),
                    )
                )
            check_statuses.append(outcome)
        if any(status == "failure" for status in check_statuses):
            statuses.append("fail")
        elif any(status == "unknown" for status in check_statuses):
            statuses.append("unknown")
            proof_gaps.append(
                {
                    "id": "claim.historical_policy_unavailable",
                    "check_id": "claim.completion",
                    "run_id": run.get("id"),
                    "reason": "attempt association or final outcomes cannot be established",
                }
            )
        else:
            statuses.append("pass")
    if "fail" in statuses:
        return _check("claim.completion", "fail", "acceptance_final_attempt_failed", evidence)
    if "unknown" in statuses:
        return _check("claim.completion", "unknown", "acceptance_set_or_outcome_unresolved", evidence)
    return _check("claim.completion", "pass", "acceptance_checks_succeeded", evidence)


def check_judges() -> list[dict[str, Any]]:
    return [
        _check(check_id, "not_applicable", "judge_opt_out_zero_provider_calls")
        for check_id in JUDGE_IDS
    ]


def _html_leaks_full_md(report_html: Path, workgraph_dir: Path | None) -> tuple[str, list[dict[str, str]]]:
    try:
        text = report_html.read_text(encoding="utf-8")
    except OSError as exc:
        return "unread", [_error("io", f"unreadable report html: {exc}")]
    if re.search(r"stages/.+/full\.md", text):
        return "leaked_path", []
    if workgraph_dir is not None:
        full_md = list(workgraph_dir.glob("stages/**/full.md"))
        for path in full_md:
            try:
                contents = path.read_text(encoding="utf-8")
            except OSError:
                continue
            snippet = contents.strip()
            if snippet and snippet[:200] in text:
                return "leaked_contents", []
    return "clean", []



def check_closeout_full_md_leaked(
    report_html: Path | None,
    workgraph_dir: Path | None,
) -> dict[str, Any]:
    if report_html is None:
        return _check("closeout.full_md_leaked", "not_applicable", "report_html_not_emitted")
    status, errors = _html_leaks_full_md(report_html, workgraph_dir)
    evidence = [
        {
            "source_path": str(report_html),
            "snapshot_hash": UNKNOWN,
            "parser_version": EVALUATOR_VERSION,
            "event_range": {"start_line": 1, "end_line": 1},
            "evidence_hash": UNKNOWN,
        }
    ]
    if status == "unread":
        return _check("closeout.full_md_leaked", "unknown", "report_html_unreadable", evidence, errors[0] if errors else _error("io", "unreadable report html"))
    if status != "clean":
        return _check("closeout.full_md_leaked", "fail", status, evidence)
    return _check("closeout.full_md_leaked", "pass", "html_excludes_full_md", evidence)


def _workgraph_argv(
    evidence: Path,
    manifest: Path | None,
    allowlist: Path | None,
    binary: Path,
) -> list[str] | None:
    if manifest is None or allowlist is None:
        return None
    return [
        str(binary),
        "score",
        "--evidence",
        str(evidence),
        "--manifest",
        str(manifest),
        "--allowlist",
        str(allowlist),
    ]


def invoke_workgraph_score(
    evidence: Path,
    manifest: Path | None,
    allowlist: Path | None,
    binary: Path,
) -> dict[str, Any]:
    argv = _workgraph_argv(evidence, manifest, allowlist, binary)
    if argv is None:
        return {
            "invoked": False,
            "argv": [],
            "result": None,
            "error": _error("io", "workgraph score requires --evidence, --manifest and --allowlist"),
        }
    if not binary.is_file():
        return {
            "invoked": False,
            "argv": argv,
            "result": None,
            "error": _error("io", f"workgraph-eval-score missing: {binary}"),
        }
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        return {
            "invoked": True,
            "argv": argv,
            "result": None,
            "error": _error("io", f"workgraph-eval-score execution failed: {exc}"),
        }
    stdout = completed.stdout or ""
    try:
        payload = json.loads(stdout) if stdout.strip() else None
    except json.JSONDecodeError:
        payload = None
    if completed.returncode == 2 or payload is None:
        message = (completed.stderr or stdout or "workgraph-eval-score failed").strip()
        return {
            "invoked": True,
            "argv": argv,
            "result": payload if isinstance(payload, dict) else None,
            "error": _error("io", message[:500]),
        }
    if not isinstance(payload, dict):
        return {
            "invoked": True,
            "argv": argv,
            "result": None,
            "error": _error("internal", "workgraph-eval-score returned a non-object"),
        }
    return {"invoked": True, "argv": argv, "result": payload, "error": None}


def check_closeout_eval_score_fail(
    requested: bool,
    workgraph: dict[str, Any] | None,
) -> dict[str, Any]:
    if not requested:
        return _check("closeout.eval_score_fail", "not_applicable", "workgraph_not_requested")
    if workgraph is None:
        return _check(
            "closeout.eval_score_fail",
            "unknown",
            "workgraph_result_missing",
            [],
            _error("io", "workgraph-eval-score produced no result"),
        )
    if workgraph.get("error") and not workgraph.get("result"):
        return _check(
            "closeout.eval_score_fail",
            "unknown",
            "workgraph_execution_error",
            [],
            workgraph.get("error"),
        )
    result = workgraph.get("result") if isinstance(workgraph.get("result"), dict) else None
    if result is None:
        return _check(
            "closeout.eval_score_fail",
            "unknown",
            "workgraph_result_missing",
            [],
            _error("io", "workgraph-eval-score produced no result"),
        )
    if result.get("hard_pass") is True:
        return _check("closeout.eval_score_fail", "pass", "workgraph_hard_pass_true")
    if result.get("hard_pass") is False:
        return _check("closeout.eval_score_fail", "fail", "workgraph_hard_pass_false")
    return _check(
        "closeout.eval_score_fail",
        "unknown",
        "workgraph_hard_pass_absent",
        [],
        _error("internal", "attached workgraph-eval-result lacks hard_pass"),
    )


def _evaluate_run(
    run: dict[str, Any],
    frozen: dict[str, list[dict[str, Any]]],
    unknowns: list[dict[str, Any]] | None,
    private_available: bool,
    registry: dict[str, Any] | None,
    first_party_root: Path,
    proof_gaps: list[dict[str, Any]],
    evaluation_errors: list[dict[str, str]],
) -> list[dict[str, Any]]:
    token = _ACTIVE_FROZEN.set(frozen)
    try:
        events, chronology_unknown = _tool_invocations(run, frozen)
        results = [
            check_ingest_parse_error(run, frozen),
            check_ingest_schema_unknown_ok(run, unknowns, private_available),
            check_ingest_sidecar_not_stream(run),
            check_session_identity_missing(run),
            check_session_incomplete(run),
            check_session_clock_skew(run, frozen),
            check_tool_unpaired(run, events),
            check_tool_result_error(run, events),
            check_tool_repeat_loop(run, events, chronology_unknown),
            check_tool_secret_pattern(run, frozen),
            check_tokens_unknown_not_zero(run, frozen),
            check_tokens_accounting_present(run, frozen),
            check_skill_registry_unreadable(run, registry),
            check_skill_digest_drift(run, registry),
            check_skill_opaque_third_party(run, registry, first_party_root),
            check_skill_activation_untracked(run, events),
            check_claim_command_outcome(run, frozen, events, proof_gaps),
            check_claim_completion(run, frozen, events, proof_gaps),
        ]
        if evaluation_errors:
            for item in results:
                if item["status"] == "pass" and item["channel"] == "behavior" and item.get("error"):
                    item["status"] = "unknown"
        return results
    finally:
        _ACTIVE_FROZEN.reset(token)


def _rollup(all_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for check in all_checks:
        entry = counts.setdefault(
            check["id"],
            {
                "id": check["id"],
                "class": check["class"],
                "kind": check["kind"],
                "channel": check["channel"],
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


def _suite_verdict(
    all_checks: list[dict[str, Any]],
    evaluation_errors: list[dict[str, str]],
    sessions_ingested: int,
    missing_requested_inputs: list[Any],
) -> tuple[bool, bool, dict[str, Any]]:
    decided = [
        item
        for item in all_checks
        if item.get("class") == "hard_fail"
        and item.get("channel") == "behavior"
        and item.get("kind") == "code"
        and item.get("status") in {"pass", "fail"}
    ]
    unknown_gates = [
        item
        for item in all_checks
        if item.get("class") == "hard_fail"
        and item.get("channel") == "behavior"
        and item.get("kind") == "code"
        and item.get("status") == "unknown"
    ]
    hard_pass = bool(decided) and all(item["status"] == "pass" for item in decided) and not unknown_gates
    infra_rows = [
        item
        for item in all_checks
        if item.get("channel") == "infra" and item.get("status") != "not_applicable"
    ]
    infra_fail = any(item.get("status") == "fail" for item in infra_rows)
    infra_unknown = any(item.get("status") == "unknown" for item in infra_rows)
    check_errors = [item.get("error") for item in all_checks if item.get("error")]
    infra_ok = (not infra_fail) and (not infra_unknown) and (not evaluation_errors) and (not check_errors)
    empty = sessions_ingested == 0 or not decided
    coverage = {
        "sessions_ingested": sessions_ingested,
        "applicable_hard_fail_decided": len(decided),
        "applicable_hard_fail_unknown": len(unknown_gates),
        "missing_requested_inputs": missing_requested_inputs,
        "empty": empty,
    }
    return hard_pass, infra_ok, coverage


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


def _derive_private_root(receipt_path: Path | None, snapshot_root: Path | None) -> Path | None:
    if snapshot_root is not None:
        parent = snapshot_root.parent
        if parent.name == ".private":
            return parent
    if receipt_path is not None:
        candidate = receipt_path.parent / ".private"
        if candidate.is_dir():
            return candidate
        nested = receipt_path.parent.parent / ".private"
        if nested.is_dir():
            return nested
    return None


def _load_receipt(receipt: dict[str, Any] | None, receipt_path: str | Path | None) -> tuple[dict[str, Any], Path | None]:
    path = Path(receipt_path).expanduser() if receipt_path is not None else None
    if receipt is not None:
        return copy.deepcopy(receipt), path
    if path is None:
        raise EvaluateError("evaluate requires a receipt object or --receipt path")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluateError(f"missing receipt: {path}") from exc
    except OSError as exc:
        raise EvaluateError(f"unreadable receipt: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluateError(f"invalid receipt JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise EvaluateError("receipt must be an object")
    return payload, path


def _load_registry(registry: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if registry is None:
        return None
    if isinstance(registry, dict):
        return registry
    path = Path(registry).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluateError(f"unreadable registry evidence: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvaluateError("registry evidence must be an object")
    return payload


def evaluate_receipt(
    receipt: dict[str, Any] | None = None,
    receipt_path: str | Path | None = None,
    snapshot_root: str | Path | None = None,
    out: str | Path | None = None,
    workgraph: str | Path | None = None,
    workgraph_manifest: str | Path | None = None,
    workgraph_allowlist: str | Path | None = None,
    workgraph_bin: str | Path | None = None,
    registry: dict[str, Any] | str | Path | None = None,
    first_party_root: str | Path | None = None,
    report_html: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Pure enrichment of an ingest receipt with catalog checks.

    Returns the enriched ``styrir-session-eval/v0`` receipt and the immutable
    path it was written to.  Frozen snapshots are hash-verified; live source
    bytes are never used as historical truth.
    """

    document, loaded_path = _load_receipt(receipt, receipt_path)
    if document.get("schema") not in (None, RECEIPT_SCHEMA):
        raise EvaluateError(f"unsupported receipt schema: {document.get('schema')}")
    snapshot_dir = _derive_snapshot_root(loaded_path, snapshot_root)
    private_root = _derive_private_root(loaded_path, snapshot_dir)
    unknown_by_run = _load_unknown_fields(private_root)
    private_available = bool(unknown_by_run) or (private_root is not None and (private_root / "unknown-fields.json").is_file())
    registry_obj = _load_registry(registry)
    first_party = Path(first_party_root).expanduser() if first_party_root else DEFAULT_FIRST_PARTY_ROOT
    evaluation_errors: list[dict[str, str]] = []
    proof_gaps: list[dict[str, Any]] = []
    existing_gaps = document.get("proof_gaps")
    if isinstance(existing_gaps, list):
        proof_gaps.extend(item for item in existing_gaps if isinstance(item, dict))

    runs = document.get("runs") if isinstance(document.get("runs"), list) else []
    all_checks: list[dict[str, Any]] = []
    enriched_runs: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        frozen = _load_frozen_sources(run, snapshot_dir, evaluation_errors)
        run_copy = copy.deepcopy(run)
        run_checks = _evaluate_run(
            run_copy,
            frozen,
            unknown_by_run.get(str(run.get("id"))),
            private_available,
            registry_obj,
            first_party,
            proof_gaps,
            evaluation_errors,
        )
        run_copy["checks"] = run_checks
        enriched_runs.append(run_copy)
        all_checks.extend(run_checks)

    judges = check_judges()
    all_checks.extend(judges)

    workgraph_requested = workgraph is not None
    workgraph_info: dict[str, Any] | None = None
    workgraph_dir = Path(workgraph).expanduser() if workgraph is not None else None
    if workgraph_requested:
        binary = Path(workgraph_bin).expanduser() if workgraph_bin else WORKGRAPH_BIN_DEFAULT
        manifest = Path(workgraph_manifest).expanduser() if workgraph_manifest else None
        allowlist = Path(workgraph_allowlist).expanduser() if workgraph_allowlist else None
        workgraph_info = invoke_workgraph_score(workgraph_dir, manifest, allowlist, binary)
        if workgraph_info.get("error"):
            evaluation_errors.append(workgraph_info["error"])
    html_path = Path(report_html).expanduser() if report_html else None
    closeout_html = check_closeout_full_md_leaked(html_path, workgraph_dir)
    closeout_score = check_closeout_eval_score_fail(workgraph_requested, workgraph_info)
    all_checks.append(closeout_html)
    all_checks.append(closeout_score)
    if enriched_runs:
        enriched_runs[0]["checks"] = list(enriched_runs[0].get("checks") or []) + [closeout_html, closeout_score] + judges

    coverage_in = document.get("coverage") if isinstance(document.get("coverage"), dict) else {}
    missing = coverage_in.get("missing_requested_inputs") or []
    if not isinstance(missing, list):
        missing = []
    sessions_ingested = len(enriched_runs)
    hard_pass, infra_ok, coverage_core = _suite_verdict(all_checks, evaluation_errors, sessions_ingested, missing)
    coverage = dict(coverage_in)
    coverage.update(coverage_core)
    coverage["sessions_ingested"] = sessions_ingested
    coverage["sessions_malformed"] = coverage_in.get("sessions_malformed") or sum(
        1 for run in enriched_runs if run.get("parse_errors")
    )
    coverage["empty"] = coverage_core["empty"]
    if evaluation_errors:
        coverage["evaluation_errors"] = evaluation_errors

    parse_errors = document.get("parse_errors")
    if not isinstance(parse_errors, int):
        parse_errors = sum(len(run.get("parse_errors") or []) for run in enriched_runs)

    provenance = document.get("provenance") if isinstance(document.get("provenance"), dict) else {}
    provenance = dict(provenance)
    provenance.update(
        {
            "evaluator": "session-eval-evaluate",
            "evaluator_version": EVALUATOR_VERSION,
            "catalog_id": CATALOG_ID,
            "claim_language_version": CLAIM_LANGUAGE_VERSION,
            "workgraph_invoked": bool(workgraph_info and workgraph_info.get("invoked")),
        }
    )
    if workgraph_info is not None:
        provenance["workgraph"] = {
            "invoked": bool(workgraph_info.get("invoked")),
            "argv": workgraph_info.get("argv") or [],
            "result": workgraph_info.get("result"),
            "error": workgraph_info.get("error"),
        }
    else:
        provenance["workgraph"] = {"invoked": False, "argv": [], "result": None, "error": None}

    seen_gaps: set[str] = set()
    unique_gaps: list[dict[str, Any]] = []
    for item in proof_gaps:
        key = _canonical(item)
        if key in seen_gaps:
            continue
        seen_gaps.add(key)
        unique_gaps.append(item)

    enriched = dict(document)
    enriched.update(
        {
            "schema": RECEIPT_SCHEMA,
            "catalog_id": CATALOG_ID,
            "generated_at": _now(),
            "runs": enriched_runs,
            "checks": _rollup(all_checks),
            "hard_pass": hard_pass,
            "infra_ok": infra_ok,
            "coverage": coverage,
            "parse_errors": parse_errors,
            "proof_gaps": unique_gaps,
            "provenance": provenance,
        }
    )

    out_dir = ingest_mod._output_root(out or ((loaded_path.parent / "evaluate") if loaded_path is not None else ingest_mod._default_output_dir() / "evaluate"))
    ingest_mod._secure_dir(out_dir)
    immutable_id = sha256_text(_canonical(enriched))
    ingest_mod._write_immutable_json(out_dir / "receipts" / f"{immutable_id}.json", enriched)
    requested_path = out_dir / "receipt.json"
    if requested_path.exists() and requested_path.read_bytes() != _canonical(enriched).encode("utf-8"):
        requested_path = ingest_mod._write_immutable_json(out_dir / f"receipt-{immutable_id}.json", enriched)
    else:
        requested_path = ingest_mod._write_immutable_json(requested_path, enriched)
    return enriched, requested_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval-evaluate",
        description="Run the versioned session-eval check catalog against an ingest receipt and frozen snapshots.",
    )
    parser.add_argument("--receipt", required=True, help="path to styrir-session-eval/v0 ingest receipt.json")
    parser.add_argument("--snapshot-root", default=None, help="frozen snapshot directory (default: <receipt-dir>/.private/snapshots)")
    parser.add_argument("--out", "--output", default=None, help="output directory for the enriched immutable receipt")
    parser.add_argument("--workgraph", default=None, help="optional .pipeline/<slug> or workgraph-eval evidence dir; invokes workgraph-eval-score")
    parser.add_argument("--workgraph-manifest", default=None, help="acceptance manifest required by workgraph-eval-score score")
    parser.add_argument("--workgraph-allowlist", default=None, help="mutation allowlist required by workgraph-eval-score score")
    parser.add_argument("--workgraph-bin", default=None, help="path to workgraph-eval-score (default: /Users/brooks/Code/agent-ops/bin/workgraph-eval-score)")
    parser.add_argument("--registry", default=None, help="optional supplied skill-registry evidence JSON; omitted skill checks are unknown")
    parser.add_argument("--first-party-root", default=None, help="configured first-party skill root (default: ~/Code/skills)")
    parser.add_argument("--report-html", default=None, help="optional report.html to check for stages/**/full.md leakage")
    parser.add_argument("--pretty", action="store_true", help="pretty-print the command summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        receipt, path = evaluate_receipt(
            receipt_path=args.receipt,
            snapshot_root=args.snapshot_root,
            out=args.out,
            workgraph=args.workgraph,
            workgraph_manifest=args.workgraph_manifest,
            workgraph_allowlist=args.workgraph_allowlist,
            workgraph_bin=args.workgraph_bin,
            registry=args.registry,
            first_party_root=args.first_party_root,
            report_html=args.report_html,
        )
    except (EvaluateError, ingest_mod.IngestError) as exc:
        parser.error(str(exc))
        return 2
    summary = {
        "receipt": str(path),
        "catalog_id": receipt.get("catalog_id"),
        "hard_pass": receipt.get("hard_pass"),
        "infra_ok": receipt.get("infra_ok"),
        "coverage": {
            "sessions_ingested": receipt.get("coverage", {}).get("sessions_ingested"),
            "empty": receipt.get("coverage", {}).get("empty"),
            "applicable_hard_fail_decided": receipt.get("coverage", {}).get("applicable_hard_fail_decided"),
            "applicable_hard_fail_unknown": receipt.get("coverage", {}).get("applicable_hard_fail_unknown"),
            "missing_requested_inputs": receipt.get("coverage", {}).get("missing_requested_inputs"),
        },
        "workgraph_invoked": receipt.get("provenance", {}).get("workgraph_invoked"),
        "claim_language_version": CLAIM_LANGUAGE_VERSION,
    }
    if args.pretty:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
