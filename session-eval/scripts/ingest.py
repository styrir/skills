#!/usr/bin/env python3
"""Portable, local session-eval ingestion for Claude, Codex, Pi, OMP and Grok.

The module deliberately contains only ingestion and normalization.  It does not
run checks, render reports, call providers, launch WorkGraph, or upload source
content.  ``main`` is the terminal entry point; the helper functions are also
importable by small local integrations and smoke scenarios.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import io
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import unquote

UNKNOWN = "unknown"


class AuthoredToken(str):
    """Bounded ingester-authored metadata, not untrusted payload text."""

PARSER_VERSION = "1.0.0"


RECEIPT_SCHEMA = "session-eval-ingest/v1"
PRIVATE_SCHEMA = "session-eval-private/v1"
HARNESSES = ("claude", "codex", "pi", "omp", "grok")
PARSER_NAMES = {
    "claude": "claude-jsonl-adapter",
    "codex": "codex-rollout-adapter",
    "pi": "pi-v3-adapter",
    "omp": "omp-v3-adapter",
    "grok": "grok-session-adapter",
}
_SKILL_MD = "SKILL.md"
_SKILL_PATH_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789~/.%@+_:-\\"
)


_TOKEN_FIELDS = ("input", "output", "cache_read", "cache_create", "total")
_TOKEN_ALIASES = {
    "input_tokens": "input",
    "inputTokens": "input",
    "prompt_tokens": "input",
    "promptTokens": "input",
    "input": "input",
    "output_tokens": "output",
    "outputTokens": "output",
    "completion_tokens": "output",
    "completionTokens": "output",
    "output": "output",
    "cache_read_input_tokens": "cache_read",
    "cacheReadInputTokens": "cache_read",
    "cache_read_tokens": "cache_read",
    "cachedReadTokens": "cache_read",
    "cached_read_tokens": "cache_read",
    "cache_read": "cache_read",
    "cache_creation_input_tokens": "cache_create",
    "cacheCreationInputTokens": "cache_create",
    "cacheCreationTokens": "cache_create",
    "cache_creation_tokens": "cache_create",
    "cache_create_tokens": "cache_create",
    "cache_create": "cache_create",
    "total_tokens": "total",
    "totalTokens": "total",
    "total": "total",
}
_SENSITIVE_KEYS = {
    "content",
    "text",
    "input",
    "output",
    "result",
    "arguments",
    "args",
    "prompt",
    "response",
    "tool_result",
    "toolResult",
    "tool_calls",
    "toolCalls",
    "tool_use",
    "toolUse",
    "reasoning",
    "system",
    "system_prompt",
    "systemPrompt",
    "terminal_output",
    "terminalOutput",
    "credential_pin",
    "credentialPin",
    "hash",
    "secret",
    "token",
    "access_token",
    "accessToken",
}

_TERMINAL_MARKERS = {
    "result",
    "task_complete",
    "task_completed",
    "session_end",
    "session_ended",
    "session_complete",
    "session_completed",
    "run_complete",
    "run_completed",
    "agent_end",
    "agent_ended",
}
_LIVE_MARKERS = {
    "live",
    "running",
    "active",
    "session_live",
    "run_live",
    "task_started",
    "session_started",
    "run_started",
    "agent_started",
    "heartbeat",
}
_SCOPED_TERMINAL_MARKERS = {
    "claude": {"result", "session_end", "session_ended", "run_complete", "run_completed"},
    "codex": {"task_complete", "task_completed", "session_end", "session_ended", "run_complete", "run_completed"},
    "pi": {"session_end", "session_ended", "run_complete", "run_completed", "agent_end", "agent_ended"},
    "omp": {"session_end", "session_ended", "run_complete", "run_completed", "agent_end", "agent_ended"},
    "grok": {"session_end", "session_ended", "session_complete", "session_completed", "run_complete", "run_completed", "agent_end", "agent_ended"},
}
_MAX_SIDECAR_BYTES = 16 * 1024 * 1024


@dataclass
class SourceRecord:
    """A parsed source row with an evidence anchor."""

    path: Path
    line: int
    data: dict[str, Any]
    role: str
    raw_hash: str
    ordinal: Any = None


@dataclass
class UsageCandidate:
    field: str
    value: int | float
    source_path: str
    line: int
    kind: str
    record_identity: str
    evidence_hash: str
    aggregate: bool = False


@dataclass
class InputGroup:
    harness: str
    primary: list[Path]
    sidecars: list[Path]
    label: str = ""


class IngestError(Exception):
    """An expected local-input error suitable for a concise CLI message."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _absolute_lexical(path: str | Path) -> Path:
    value = Path(path).expanduser()
    if not value.is_absolute():
        value = Path.cwd().resolve() / value
    return Path(os.path.normpath(str(value)))


def _output_root(path: str | Path) -> Path:
    """Canonicalize host aliases while preserving the requested final entry."""

    value = _absolute_lexical(path)
    return value.parent.resolve() / value.name

def _safe_label(value: Any, limit: int = 240) -> str:
    """Return a structural label without copying arbitrary payload text."""

    if value is None:
        return UNKNOWN
    text = str(value).replace("\x00", "")
    text = text.replace("<", "[").replace(">", "]")
    text = " ".join(text.split())
    # Common credential formats should never survive into an exported label.
    text = re.sub(r"(?i)(?:sk|pk|token|secret|key)[-_][A-Za-z0-9._=-]{6,}", "[REDACTED]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._=-]{8,}", "Bearer [REDACTED]", text)
    return text[:limit] if text else UNKNOWN


_SOURCE_PATH_FINGERPRINT = 12
_EXPORTED_ALIAS_RE = re.compile(r"#[0-9a-f]{" + str(_SOURCE_PATH_FINGERPRINT) + r"}")


def _source_path_fingerprint(raw_path: str) -> str:
    return sha256_text("source-path:" + raw_path)[:_SOURCE_PATH_FINGERPRINT]


def _looks_like_exported_alias(path: str) -> bool:
    return bool(_EXPORTED_ALIAS_RE.search(Path(path).name))


def _export_source_path(raw_path: str) -> str:
    """Public evidence pointer for one opened source path.

    Ordinary paths that survive ``_safe_label`` and do not match the reserved
    alias form are returned as-is.  Redacted, truncated, or alias-lookalike
    raw paths receive a fingerprint of the canonical raw path.  A raw path
    that already looks exported is never treated as a trusted alias.
    """

    labeled = _safe_label(raw_path)
    if labeled == raw_path and not _looks_like_exported_alias(raw_path):
        return raw_path
    fingerprint = _source_path_fingerprint(raw_path)
    original_suffix = Path(raw_path).suffix
    extra = f"#{fingerprint}{original_suffix}"
    stem = labeled
    if original_suffix and stem.endswith(original_suffix):
        stem = stem[: -len(original_suffix)]
    budget = 240 - len(extra)
    if budget < 1:
        budget = 1
    if len(stem) > budget:
        stem = stem[:budget]
    return f"{stem}{extra}"


def _source_path_export_map(paths: Iterable[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in paths:
        if raw not in mapping:
            mapping[raw] = _export_source_path(raw)
    return mapping


def _rewrite_exported_paths(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_rewrite_exported_paths(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_exported_paths(item, mapping) for key, item in value.items()}
    return value


def _string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        if parsed >= 0 and parsed.is_integer():
            return int(parsed)
        if parsed >= 0:
            return parsed
    return None


def _first(mapping: Any, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _nested(mapping: Any, *keys: str) -> Any:
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _timestamp(value: Any) -> str | None:
    """Normalize common ISO/epoch values without claiming missing chronology."""

    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Grok updates have been observed in epoch seconds; milliseconds are
        # recognized only when the magnitude makes that interpretation clear.
        seconds = float(value)
        if seconds > 100_000_000_000:
            seconds /= 1000
        try:
            return datetime.fromtimestamp(seconds, timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _event_range(line: int) -> dict[str, int]:
    return {"start_line": int(line), "end_line": int(line)}


def _empty_lineage() -> dict[str, Any]:
    return {
        "parent": UNKNOWN,
        "children": UNKNOWN,
        "attempt": UNKNOWN,
        "continuation_of": UNKNOWN,
        "continued_by": UNKNOWN,
    }


def _ref(value: Any) -> str | None:
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        value = str(value).strip()
        return value or None
    if isinstance(value, dict):
        return _ref(_first(value, "id", "ref", "session_id", "sessionId", "thread_id", "threadId"))
    return None


def _refs(value: Any) -> list[str] | None:
    if not isinstance(value, (list, tuple)):
        one = _ref(value)
        return [one] if one is not None else None
    result = []
    for item in value:
        ref = _ref(item)
        if ref is not None and ref not in result:
            result.append(ref)
    return result


def _lineage_from(mapping: Any, *, turn: bool = False) -> dict[str, Any]:
    """Read only explicit relationship fields; never infer from order or names."""

    result = _empty_lineage()
    if not isinstance(mapping, dict):
        return result

    parent_keys = (
        ("parentId", "parent_id", "parent", "parent_ref")
        if turn
        else (
            "parent_thread_id",
            "parentThreadId",
            "parent_session_id",
            "parentSessionId",
            "parent_run_id",
            "parentRunId",
            "parent_ref",
            "parent",
        )
    )
    for key in parent_keys:
        ref = _ref(mapping.get(key))
        if ref is not None:
            result["parent"] = ref
            break

    for key in ("children", "child_ids", "childIds", "child_refs", "childRefs"):
        if key in mapping:
            refs = _refs(mapping[key])
            if refs is not None:
                result["children"] = refs
                break
    for key in ("child_id", "childId", "child_run_id", "childRunId", "child_agent_id", "childAgentId"):
        if key in mapping:
            ref = _ref(mapping[key])
            if ref is not None:
                result["children"] = [ref]
                break

    attempt = _first(mapping, "attempt", "attempt_info")
    if isinstance(attempt, dict):
        attempt_id = _ref(attempt)
        number = _number(_first(attempt, "number", "attempt_number", "attemptNumber", "index"))
        if attempt_id is not None or number is not None:
            result["attempt"] = {
                "id": attempt_id if attempt_id is not None else UNKNOWN,
                "number": number if number is not None else UNKNOWN,
            }
    elif attempt is not None:
        attempt_id = _ref(attempt)
        if attempt_id is not None:
            result["attempt"] = {"id": attempt_id, "number": UNKNOWN}
    if result["attempt"] == UNKNOWN:
        attempt_id = _ref(_first(mapping, "attempt_id", "attemptId", "retry_of", "retryOf"))
        number = _number(_first(mapping, "attempt_number", "attemptNumber"))
        if attempt_id is not None or number is not None:
            result["attempt"] = {
                "id": attempt_id if attempt_id is not None else UNKNOWN,
                "number": number if number is not None else UNKNOWN,
            }

    for key in ("continuation_of", "continuationOf", "continued_from", "continuedFrom", "continuation_ref"):
        ref = _ref(mapping.get(key))
        if ref is not None:
            result["continuation_of"] = ref
            break
    for key in ("continued_by", "continuedBy", "continuation_children"):
        refs = _refs(mapping.get(key))
        if refs is not None:
            result["continued_by"] = refs
            break
    return result
def _run_lineage_from(mapping: Any) -> dict[str, Any]:
    """Read run/agent parent links without confusing turn parentId fields."""

    result = _lineage_from(mapping, turn=False)
    if not isinstance(mapping, dict):
        return result
    if result["parent"] == UNKNOWN:
        for key in ("parentId", "parent_id", "parentAgentId", "parent_agent_id"):
            ref = _ref(mapping.get(key))
            if ref is not None:
                result["parent"] = ref
                break
    return result



def _merge_lineage(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if value != UNKNOWN:
            if target.get(key, UNKNOWN) == UNKNOWN:
                target[key] = copy.deepcopy(value)
            elif isinstance(target[key], list) and isinstance(value, list):
                for ref in value:
                    if ref not in target[key]:
                        target[key].append(ref)


def _record_timestamp(data: dict[str, Any]) -> str | None:
    return _timestamp(
        _first(
            data,
            "timestamp",
            "ts",
            "time",
            "created_at",
            "createdAt",
            "started_at",
            "startedAt",
            "updated_at",
            "updatedAt",
        )
    )


def _marker(data: dict[str, Any], scope: str = "generic") -> tuple[str | None, str | None]:
    """Return explicit run lifecycle evidence for an adapter-scoped record."""

    if not isinstance(data, dict):
        return None, None
    candidates = []
    for key in ("type", "event", "event_type", "eventType", "customType", "kind", "action", "method"):
        value = data.get(key)
        if isinstance(value, str):
            candidates.append((key, value.casefold().replace("-", "_").replace(" ", "_")))
    terminal_markers = _SCOPED_TERMINAL_MARKERS.get(scope, _TERMINAL_MARKERS)
    for key, value in candidates:
        if value in terminal_markers:
            return "terminal", AuthoredToken(f"{key}:{value}")
    if data.get("ended") is True or data.get("is_ended") is True or data.get("isEnded") is True:
        return "terminal", AuthoredToken("ended.metadata")
    if any(data.get(key) not in (None, "") for key in ("ended_at", "endedAt", "end_time", "endTime")):
        return "terminal", AuthoredToken("ended.metadata")
    for key, value in candidates:
        if value in _LIVE_MARKERS:
            return "live", AuthoredToken(f"{key}:{value}")
    return None, None


def _message_role(data: dict[str, Any], default: str = UNKNOWN) -> str:
    message = data.get("message") if isinstance(data.get("message"), dict) else data
    role = _first(message, "role", "speaker", "author_role")
    if isinstance(role, str) and role:
        return _safe_label(role)
    event_type = _first(data, "type", "event")
    if isinstance(event_type, str) and event_type.casefold() in {"assistant", "user", "system", "developer"}:
        return event_type.casefold()
    return default


def _message_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("payload")
    if isinstance(payload, dict):
        return payload
    message = data.get("message")
    if isinstance(message, dict):
        return message
    return data


def _iter_dicts(value: Any, prefix: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        yield prefix, value
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                yield from _iter_dicts(child, child_prefix)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                child_prefix = f"{prefix}[{index}]"
                yield from _iter_dicts(child, child_prefix)


def _iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_strings(child)


def _skill_path_candidates(value: Any) -> list[str]:
    """Extract SKILL.md path tokens without scanning payloads via backtracking regex.

    ccdiag (MIT) and claude-dashboard walk JSONL line-by-line and keep only
    structured fields. Large tool-result strings that mention SKILL.md must
    still yield path tokens; they must not hang ingest.
    """

    result: list[str] = []
    for text in _iter_strings(value):
        start = 0
        while True:
            pos = text.find(_SKILL_MD, start)
            if pos < 0:
                break
            index = pos
            while index > 0 and text[index - 1] in _SKILL_PATH_CHARS:
                index -= 1
            candidate = text[index : pos + len(_SKILL_MD)].replace("\\", "/")
            if "/" not in candidate:
                candidate = _SKILL_MD
            if candidate not in result:
                result.append(candidate)

            start = pos + len(_SKILL_MD)

    return result



def _skill_name(path: str) -> str:
    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if parts and parts[-1].casefold() == "skill.md":
        return parts[-2] if len(parts) > 1 else UNKNOWN
    return Path(path).stem or UNKNOWN


def _digest_if_file(path: str | Path) -> str:
    try:
        candidate = _absolute(path)
        if candidate.is_file():
            return sha256_file(candidate)
    except OSError:
        pass
    return UNKNOWN


def _skill_entry(path: str, source: str, confidence: str, observed_digest: Any = None) -> dict[str, Any]:
    expanded = Path(path).expanduser()
    display_path = str(expanded.resolve()) if expanded.exists() else str(expanded)
    observed = observed_digest if isinstance(observed_digest, str) and observed_digest else None
    current = _digest_if_file(expanded)
    # A path mention or loaded path does not prove which bytes were loaded.
    # Keep that historical digest unknown and expose current bytes separately.
    result: dict[str, Any] = {
        "name": _safe_label(_skill_name(display_path)),
        "path": display_path,
        "digest": observed or UNKNOWN,
        "source": _safe_label(source),
        "confidence": confidence,
        "digest_relation": "observed_load" if observed else "historical_unknown",
    }
    if current != UNKNOWN:
        result["current_on_disk_digest"] = current
        if observed:
            result["digest_relation"] = (
                "historical_differs_from_current" if observed != current else "historical_matches_current"
            )
    return result


def _add_skill(state: dict[str, Any], entry: dict[str, Any]) -> None:
    key = (entry.get("path"), entry.get("name"), entry.get("source"))
    existing = state["skills"].get(key)
    if existing is None:
        state["skills"][key] = entry
        return
    rank = {"high": 3, "medium": 2, "low": 1}
    if rank.get(entry.get("confidence", "low"), 0) > rank.get(existing.get("confidence", "low"), 0):
        merged = entry
    else:
        merged = existing
    # A path can be observed first as a low-information mention and later with
    # an authoritative historical digest from the same source.  Keep both
    # observations instead of allowing the first entry to erase the digest.
    if merged.get("digest") in (None, UNKNOWN) and existing.get("digest") not in (None, UNKNOWN):
        merged["digest"] = existing["digest"]
    if merged.get("digest") in (None, UNKNOWN) and entry.get("digest") not in (None, UNKNOWN):
        merged["digest"] = entry["digest"]
    for field in ("current_on_disk_digest", "version"):
        if merged.get(field) in (None, UNKNOWN) and existing.get(field) not in (None, UNKNOWN):
            merged[field] = existing[field]
        if merged.get(field) in (None, UNKNOWN) and entry.get(field) not in (None, UNKNOWN):
            merged[field] = entry[field]
    digest = merged.get("digest", UNKNOWN)
    current = merged.get("current_on_disk_digest", UNKNOWN)
    if digest not in (None, UNKNOWN):
        merged["digest_relation"] = (
            "historical_matches_current" if current not in (None, UNKNOWN) and digest == current
            else "historical_differs_from_current" if current not in (None, UNKNOWN)
            else "observed_load"
        )
    else:
        merged["digest_relation"] = "historical_unknown"
    state["skills"][key] = merged


def _observe_skills(state: dict[str, Any], data: Any, source: str, confidence: str = "low") -> None:
    for path in _skill_path_candidates(data):
        _add_skill(state, _skill_entry(path, source, confidence))


def _capture_unknown(
    state: dict[str, Any],
    record: SourceRecord,
    mapping: Any,
    known: set[str],
    prefix: str = "",
) -> None:
    """Keep schema-drift values in owner-only state, never in the receipt."""

    if not isinstance(mapping, dict):
        return
    for key, value in mapping.items():
        key_text = str(key)
        if key_text in known:
            continue
        if key_text in _SENSITIVE_KEYS or key_text.casefold() in {item.casefold() for item in _SENSITIVE_KEYS}:
            continue
        field = f"{prefix}.{key_text}" if prefix else key_text
        state["unknowns"].append(
            {
                "source_path": str(record.path),
                "event_range": _event_range(record.line),
                "field": field,
                "value": copy.deepcopy(value),
                "record_identity": _record_identity(record),
            }
        )


def _record_identity(record: SourceRecord, fallback: str | None = None) -> str:
    explicit = _first(record.data, "id", "event_id", "eventId", "uuid", "request_id", "requestId")
    if explicit is None:
        explicit = fallback
    if explicit is None:
        explicit = record.ordinal
    if explicit is None:
        explicit = f"line:{record.line}"
    return _safe_label(explicit)


def _open_source_spool(path: Path) -> tuple[Any, str, int]:
    """Copy one opened regular source into a private immutable spool.

    The source descriptor is opened once without following the final path
    component.  Parsing and later private preservation both consume this
    closed, mode-0400 spool, so a source mutation cannot produce mixed
    hashes/records/snapshots and no full source buffer is retained.
    """

    path = _absolute(path)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise IngestError("platform lacks O_NOFOLLOW; refusing to read source safely")
    try:
        source_fd = os.open(path, os.O_RDONLY | nofollow)
    except OSError as exc:
        raise IngestError(f"cannot read {path}: {exc}") from exc
    spool: Any = None
    try:
        info = os.fstat(source_fd)
        if not stat.S_ISREG(info.st_mode):
            raise IngestError(f"input is not a regular file: {path}")
        spool = tempfile.TemporaryFile(mode="w+b")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            spool.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        spool.flush()
        os.fchmod(spool.fileno(), 0o400)
        spool.seek(0)
        return spool, digest.hexdigest(), size
    except IngestError:
        if spool is not None:
            spool.close()
        raise
    except OSError as exc:
        if spool is not None:
            spool.close()
        raise IngestError(f"cannot read {path}: {exc}") from exc
    finally:
        os.close(source_fd)


def _register_file(state: dict[str, Any], path: Path, role: str) -> Any:
    path = _absolute(path)
    key = (str(path), role)
    existing = state["files"].get(key)
    if existing is not None:
        existing["spool"].seek(0)
        return existing["spool"]
    spool, digest, size = _open_source_spool(path)
    state["files"][key] = {
        "path": str(path),
        "role": role,
        "sha256": digest,
        "size": size,
        "spool": spool,
    }
    return spool


def _add_issue(state: dict[str, Any], issue: dict[str, Any]) -> None:
    key = (issue.get("source_path"), issue.get("line"), issue.get("kind"))
    if key in state["issue_keys"]:
        return
    state["issue_keys"].add(key)
    state["issues"].append(issue)


def _read_jsonl(state: dict[str, Any], path: Path, role: str = "primary") -> Iterator[SourceRecord]:
    path = _absolute(path)
    spool = _register_file(state, path, role)
    spool.seek(0)
    line_number = 0
    while True:
        raw_line = spool.readline()
        if not raw_line:
            break
        line_number += 1
        if not raw_line.strip():
            continue
        raw_hash = sha256_bytes(raw_line)
        try:
            text = raw_line.decode("utf-8")
            value = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _add_issue(
                state,
                {
                    "source_path": str(path),
                    "line": line_number,
                    "kind": "malformed_jsonl",
                    "evidence_hash": raw_hash,
                },
            )
            continue
        if not isinstance(value, dict):
            _add_issue(
                state,
                {
                    "source_path": str(path),
                    "line": line_number,
                    "kind": "record_not_object",
                    "evidence_hash": raw_hash,
                },
            )
            continue
        ordinal = _first(value, "ordinal", "seq", "sequence", "index")
        record = SourceRecord(path, line_number, value, role, raw_hash, ordinal)
        state["record_count"] += 1
        state["last_record"] = record
        yield record


def _read_json(state: dict[str, Any], path: Path, role: str = "sidecar") -> dict[str, Any] | None:
    path = _absolute(path)
    spool = _register_file(state, path, role)
    entry = state["files"][(str(path), role)]
    if entry["size"] > _MAX_SIDECAR_BYTES:
        _add_issue(
            state,
            {
                "source_path": str(path),
                "line": 1,
                "kind": "sidecar_too_large",
                "evidence_hash": entry["sha256"],
            },
        )
        return None
    spool.seek(0)
    decoder = io.TextIOWrapper(spool, encoding="utf-8")
    try:
        value = json.load(decoder)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _add_issue(
            state,
            {
                "source_path": str(path),
                "line": 1,
                "kind": "malformed_json",
                "evidence_hash": entry["sha256"],
            },
        )
        return None
    finally:
        decoder.detach()
    if not isinstance(value, dict):
        _add_issue(
            state,
            {
                "source_path": str(path),
                "line": 1,
                "kind": "sidecar_not_object",
                "evidence_hash": entry["sha256"],
            },
        )
        return None
    return value

def _iter_primary_records(state: dict[str, Any], paths: Sequence[Path]) -> Iterator[SourceRecord]:
    for path in paths:
        yield from _read_jsonl(state, path, "primary")


def _new_state(harness: str) -> dict[str, Any]:
    return {
        "harness": harness,
        "parser": PARSER_NAMES[harness],
        "files": {},
        "record_count": 0,
        "last_record": None,
        "issue_keys": set(),
        "issues": [],
        "unknowns": [],
        "skills": {},
        "turns": [],
        "pending": {},
        "lineage": _empty_lineage(),
        "usage": [],
        "cost": [],
        "resolved_calls": set(),
        "grok_observations": {},
        "primary_ids": set(),
        "primary_id_sources": {},
        "primary_cohort_valid": True,
        "gaps": [],
        "native_id": None,
        "native_source": None,
        "native_kind": None,
        "display_name": None,
        "started_at": None,
        "ended_at": None,
        "cwd": None,
        "model": None,
        "lifecycle": [],
        "checks": [],
    }


def _set_native(state: dict[str, Any], value: Any, source: str, kind: str = "session_id") -> None:
    ref = _ref(value)
    if ref is None or state["native_id"] is not None:
        return
    state["native_id"] = ref
    state["native_source"] = source
    state["native_kind"] = kind


def _set_if_missing(state: dict[str, Any], key: str, value: Any) -> None:
    if value in (None, "", UNKNOWN):
        return
    if state.get(key) in (None, "", UNKNOWN):
        state[key] = value


def _observe_common(state: dict[str, Any], record: SourceRecord) -> None:
    ts = _record_timestamp(record.data)
    _set_if_missing(state, "started_at", ts)
    _observe_skills(state, record.data, f"{state['harness']}.tool_or_text", "low")
    _merge_lineage(state["lineage"], _lineage_from(record.data, turn=False))
    for key in ("payload", "data", "metadata"):
        nested = record.data.get(key)
        if isinstance(nested, dict):
            _merge_lineage(state["lineage"], _lineage_from(nested, turn=False))

def _add_lifecycle(state: dict[str, Any], record: SourceRecord, lifecycle_state: str, kind: str) -> None:
    state["lifecycle"].append(
        {
            "state": lifecycle_state,
            "kind": kind if isinstance(kind, AuthoredToken) else _safe_label(kind),
            "source_path": str(record.path),
            "line": record.line,
            "evidence_hash": record.raw_hash,
            "timestamp": _record_timestamp(record.data),
        }
    )
    if lifecycle_state == "terminal":
        _set_if_missing(state, "ended_at", _record_timestamp(record.data))


def _observe_record_lifecycle(state: dict[str, Any], record: SourceRecord) -> None:
    lifecycle_state, kind = _marker(record.data)
    if lifecycle_state and kind:
        _add_lifecycle(state, record, lifecycle_state, kind)


def _turn(
    state: dict[str, Any],
    record: SourceRecord,
    role: str,
    identifier: Any = None,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    turn_id = _ref(identifier) or f"line:{record.line}"
    result = {
        "id": turn_id,
        "role": _safe_label(role),
        "tool_calls": [],
        "errors": [],
        "source_line": record.line,
        "source_path": str(record.path),
        "lineage": lineage if lineage is not None else _lineage_from(record.data, turn=True),
    }
    state["turns"].append(result)
    return result


def _tool_call(
    state: dict[str, Any],
    turn: dict[str, Any],
    record: SourceRecord,
    identifier: Any,
    name: Any,
) -> None:
    call_id = _ref(identifier) or f"unknown@{record.line}"
    pending = state["pending"].get(call_id, [])
    if call_id in state["resolved_calls"] or pending:
        # OMP can report one semantic call in both its operational start event
        # and Pi-shaped assistant message.  Merge those observations by the
        # run/agent-local call id instead of creating a second pending call.
        if pending:
            existing_turn, existing_call, _existing_record = pending[0]
            new_name = _safe_label(name)
            if existing_call["name"] == UNKNOWN and new_name != UNKNOWN:
                existing_call["name"] = new_name
            _merge_lineage(existing_turn["lineage"], turn["lineage"])
        if turn in state["turns"] and not turn["tool_calls"] and not turn["errors"]:
            state["turns"].remove(turn)
        return
    call = {
        "id": call_id,
        "name": _safe_label(name),
        "status": "pending",
        "source_line": record.line,
        "source_path": str(record.path),
    }
    turn["tool_calls"].append(call)
    state["pending"].setdefault(call_id, []).append((turn, call, record))


def _tool_result(
    state: dict[str, Any],
    record: SourceRecord,
    identifier: Any,
    is_error: Any = False,
    turn: dict[str, Any] | None = None,
) -> None:
    call_id = _ref(identifier)
    if call_id is not None and state["pending"].get(call_id):
        _turn_obj, call, _call_record = state["pending"][call_id].pop(0)
        if not state["pending"][call_id]:
            state["resolved_calls"].add(call_id)
        call["status"] = "error" if is_error is True else "ok"
        call["result_source_line"] = record.line
        call["result_source_path"] = str(record.path)
        if is_error is True and turn is not None:
            turn["errors"].append(
                {"kind": "tool.error", "source_line": record.line, "source_path": str(record.path)}
            )
        return
    if turn is not None:
        turn["errors"].append(
            {
                "kind": "tool.result_unpaired",
                "source_line": record.line,
                "source_path": str(record.path),
            }
        )


def _add_usage(
    state: dict[str, Any],
    field: str,
    value: Any,
    record: SourceRecord,
    kind: str,
    record_identity: str,
    aggregate: bool = False,
) -> None:
    number = _number(value)
    if number is None or field not in _TOKEN_FIELDS:
        return
    state["usage"].append(
        UsageCandidate(
            field,
            number,
            str(record.path),
            record.line,
            kind,
            _safe_label(record_identity),
            record.raw_hash,
            aggregate,
        )
    )


def _add_cost(state: dict[str, Any], value: Any, record: SourceRecord, kind: str, identity: str) -> None:
    number = _number(value)
    if number is None:
        return
    state["cost"].append(
        UsageCandidate(
            "cost_usd",
            number,
            str(record.path),
            record.line,
            kind,
            _safe_label(identity),
            record.raw_hash,
            aggregate=True,
        )
    )


def _usage_from_mapping(
    state: dict[str, Any],
    mapping: Any,
    record: SourceRecord,
    kind: str,
    identity: str,
    aggregate: bool,
) -> None:
    if not isinstance(mapping, dict):
        return
    for key, value in mapping.items():
        field = _TOKEN_ALIASES.get(str(key))
        if field is not None:
            _add_usage(state, field, value, record, kind, identity, aggregate)
    # Keep explicit nested usage records discoverable without walking prompts or
    # tool payloads.  Nested aggregate objects are common in Codex/Grok.
    for key, child in mapping.items():
        if not isinstance(child, dict):
            continue
        key_text = str(key)
        key_folded = key_text.casefold()
        if not (
            any(token in key_folded for token in ("usage", "token", "count"))
            or key_folded in {"info", "session", "stats", "statistics", "tokens"}
        ):
            continue
        child_aggregate = aggregate or any(
            token in key_folded for token in ("total", "aggregate", "cumulative", "session")
        )
        _usage_from_mapping(state, child, record, kind, identity, child_aggregate)


def _finish_pairing(state: dict[str, Any], terminal: bool, snapshot_hash: str) -> None:
    if not terminal:
        # Pending calls remain observable as pending.  EOF is not a failure.
        return
    for call_id, pending in state["pending"].items():
        for turn, call, record in pending:
            call["status"] = "unpaired"
            turn["errors"].append(
                {
                    "kind": "tool.unpaired",
                    "tool_call_id": call_id,
                    "source_line": record.line,
                    "source_path": str(record.path),
                }
            )
            state["checks"].append(
                {
                    "id": "tool.unpaired",
                    "status": "fail",
                    "kind": "code",
                    "class": "hard_fail",
                    "channel": "behavior",
                    "observed": "unpaired_after_explicit_end",
                    "error": None,
                    "evidence": [
                        {
                            "source_path": str(record.path),
                            "snapshot_hash": snapshot_hash,
                            "parser_version": PARSER_VERSION,
                            "event_range": _event_range(record.line),
                            "evidence_hash": record.raw_hash,
                        }
                    ],
                }
            )


def _lifecycle_state(state: dict[str, Any]) -> str:
    if any(item["state"] == "terminal" for item in state["lifecycle"]):
        return "terminal"
    if any(item["state"] == "live" for item in state["lifecycle"]):
        return "live"
    return "unknown"


def _snapshot_manifest(state: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    files = list(state["files"].values())
    files.sort(key=lambda item: (0 if item["role"] == "primary" else 1, item["path"], item["role"]))
    manifest = [
        {"path": item["path"], "role": item["role"], "sha256": item["sha256"]}
        for item in files
    ]
    return sha256_text(_canonical(manifest)), manifest


def _usage_result(state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    values: dict[str, int | float | str] = {field: UNKNOWN for field in _TOKEN_FIELDS}
    provenance: list[dict[str, Any]] = []
    by_field: dict[str, list[UsageCandidate]] = {field: [] for field in _TOKEN_FIELDS}
    for candidate in state["usage"]:
        by_field.setdefault(candidate.field, []).append(candidate)

    selected: dict[str, list[UsageCandidate]] = {}
    for field in _TOKEN_FIELDS:
        candidates = by_field.get(field, [])
        if not candidates:
            continue
        direct = [candidate for candidate in candidates if not candidate.aggregate]
        aggregate = [candidate for candidate in candidates if candidate.aggregate]
        chosen: list[UsageCandidate]
        if direct:
            # A direct record identity/range is counted once.  Same-value sidecar
            # views do not inflate a direct total.
            seen: set[tuple[str, str, int | float]] = set()
            unique_direct = []
            for candidate in direct:
                key = (candidate.record_identity, candidate.field, candidate.value)
                if key not in seen:
                    seen.add(key)
                    unique_direct.append(candidate)
            direct_total = sum(candidate.value for candidate in unique_direct)
            chosen = unique_direct
            if aggregate:
                aggregate_max = max(candidate.value for candidate in aggregate)
                if aggregate_max > direct_total:
                    chosen = [max(aggregate, key=lambda item: item.value)]
        else:
            # Cumulative/repeated aggregate records are represented by the
            # greatest observed total, never added together.
            seen_aggregate: set[tuple[str, str, int | float]] = set()
            unique_aggregate = []
            for candidate in aggregate:
                key = (candidate.record_identity, candidate.field, candidate.value)
                if key not in seen_aggregate:
                    seen_aggregate.add(key)
                    unique_aggregate.append(candidate)
            chosen = [max(unique_aggregate, key=lambda item: item.value)]
        if chosen:
            selected[field] = chosen
            values[field] = sum(item.value for item in chosen) if len(chosen) > 1 else chosen[0].value

    if values["total"] == UNKNOWN:
        known_components = [values[field] for field in _TOKEN_FIELDS[:-1] if values[field] != UNKNOWN]
        if known_components:
            values["total"] = sum(known_components)
            components = [item for field in _TOKEN_FIELDS[:-1] for item in selected.get(field, [])]
            if components:
                first = components[0]
                provenance.append(
                    {
                        "source_path": first.source_path,
                        "line_or_event_range": _event_range(first.line),
                        "field": "total",
                        "kind": "aggregate",
                        "record_identity": "derived:" + sha256_text(_canonical([item.record_identity for item in components]))[:16],
                        "evidence_hash": sha256_text(_canonical([item.evidence_hash for item in components])),
                    }
                )

    for field in _TOKEN_FIELDS:
        for candidate in selected.get(field, []):
            provenance.append(
                {
                    "source_path": candidate.source_path,
                    "line_or_event_range": _event_range(candidate.line),
                    "field": field,
                    "kind": candidate.kind,
                    "record_identity": candidate.record_identity,
                    "evidence_hash": candidate.evidence_hash,
                }
            )
    # Keep cost in the same provenance channel because cost is evidence-bound.
    cost_value: int | float | str = UNKNOWN
    if state["cost"]:
        unique: dict[tuple[str, int | float], UsageCandidate] = {}
        for candidate in state["cost"]:
            unique[(candidate.record_identity, candidate.value)] = candidate
        candidate = max(unique.values(), key=lambda item: item.value)
        cost_value = candidate.value
        provenance.append(
            {
                "source_path": candidate.source_path,
                "line_or_event_range": _event_range(candidate.line),
                "field": "cost_usd",
                "kind": candidate.kind,
                "record_identity": candidate.record_identity,
                "evidence_hash": candidate.evidence_hash,
            }
        )
    return values, provenance


def _build_lifecycle(state: dict[str, Any], snapshot_hash: str) -> dict[str, Any]:
    state_name = _lifecycle_state(state)
    evidence = []
    for item in state["lifecycle"]:
        evidence.append(
            {
                "source_path": item["source_path"],
                "snapshot_hash": snapshot_hash,
                "parser_version": PARSER_VERSION,
                "event_range": _event_range(item["line"]),
                "kind": item["kind"],
                "evidence_hash": item["evidence_hash"],
            }
        )
    if not evidence and state["last_record"] is not None:
        last = state["last_record"]
        evidence.append(
            {
                "source_path": str(last.path),
                "snapshot_hash": snapshot_hash,
                "parser_version": PARSER_VERSION,
                "event_range": _event_range(last.line),
                "kind": AuthoredToken("eof_without_terminal"),
                "evidence_hash": last.raw_hash,
            }
        )
    return {"state": state_name, "evidence": evidence}


def _redact_structural(value: Any) -> Any:
    """Defensive final pass: only approved structural containers leave ingest."""

    if isinstance(value, AuthoredToken):
        return str(value)
    if isinstance(value, str):
        return _safe_label(value)
    if isinstance(value, list):
        return [_redact_structural(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_structural(item) for key, item in value.items()}
    return value


def _finalize_run(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_hash, raw_manifest = _snapshot_manifest(state)
    export_map = _source_path_export_map(item["path"] for item in raw_manifest)
    public_manifest = [
        {"path": export_map[item["path"]], "role": item["role"], "sha256": item["sha256"]}
        for item in raw_manifest
    ]
    lifecycle_state = _lifecycle_state(state)
    _finish_pairing(state, lifecycle_state == "terminal", snapshot_hash)
    tokens, usage_provenance = _usage_result(state)
    primary_raw = str(next(path for path, role in state["files"] if role == "primary"))
    native_identity: Any
    if state["native_id"] is None:
        native_identity = UNKNOWN
        local_id = f"{state['harness']}:path:{sha256_text('run-path:' + primary_raw)[:16]}"
    else:
        native_identity = {
            "id": state["native_id"],
            "kind": state["native_kind"] or "session_id",
            "source": state["native_source"] or UNKNOWN,
        }
        local_id = f"{state['harness']}:{state['native_id']}"

    parse_errors = []
    for issue in state["issues"]:
        item = dict(issue)
        line = int(item.get("line", 1))
        item["snapshot_hash"] = snapshot_hash
        item["parser_version"] = PARSER_VERSION
        item["event_range"] = _event_range(line)
        parse_errors.append(item)
    run = {
        "id": local_id,
        "harness": state["harness"],
        "native_identity": native_identity,
        "display_name": (
            _safe_label(state["display_name"])
            if state["display_name"]
            else Path(export_map[primary_raw]).stem
        ),
        "parser": state["parser"],
        "parser_version": PARSER_VERSION,
        "source_path": primary_raw,
        "source_snapshot": {"sha256": snapshot_hash, "files": public_manifest},
        "started_at": state["started_at"] or UNKNOWN,
        "ended_at": state["ended_at"] or UNKNOWN,
        "cwd": _safe_label(state["cwd"] or UNKNOWN),
        "model": _safe_label(state["model"] or UNKNOWN),
        "tokens": tokens,
        "cost_usd": next(
            (item.value for item in state["cost"] if item.value is not None), UNKNOWN
        ),
        "usage_provenance": usage_provenance,
        "skills": list(state["skills"].values()),
        "lineage": state["lineage"],
        "turns": sorted(state["turns"], key=lambda item: (item["source_path"], item["source_line"])),
        "checks": state["checks"],
        "lifecycle": _build_lifecycle(state, snapshot_hash),
        "parse_errors": parse_errors,
        "coverage": {
            "malformed_records": len(state["issues"]),
            "unknown_fields": len(state["unknowns"]),
            "gaps": state["gaps"],
            "coverage_gaps": state["gaps"],
        },
    }
    # _usage_result is authoritative for cost provenance/dedup; mirror selected
    # value in the run while avoiding a second accumulation path.
    cost_values = [candidate.value for candidate in state["cost"]]
    if cost_values:
        run["cost_usd"] = max(cost_values)
    run = _rewrite_exported_paths(run, export_map)
    private = {
        "run_id": local_id,
        "snapshot_hash": snapshot_hash,
        "unknown_fields": state["unknowns"],
        "source_manifest": public_manifest,
        # Kept only in memory until the exact opened bytes are persisted; the
        # ingest orchestrator removes this non-JSON field before ledger write.
        # Tuples are keyed by the public pointer that the receipt exposes, not
        # by looking up raw-path state with a display label.
        "source_blobs": [
            (export_map[item["path"]], item["role"], state["files"][(item["path"], item["role"])]["spool"])
            for item in raw_manifest
        ],
    }
    return _redact_structural(run), private


# ---------------------------------------------------------------------------
# Claude adapter


def _claude_content_items(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if isinstance(content, list):
        return [item for item in content if isinstance(item, dict)]
    if isinstance(content, dict):
        return [content]
    return []


def _parse_claude(group: InputGroup) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _new_state("claude")
    for record in _iter_primary_records(state, group.primary):
        data = record.data
        _observe_common(state, record)
        _capture_unknown(
            state,
            record,
            data,
            {"sessionId", "timestamp", "cwd", "gitBranch", "type", "message", "result", "uuid", "id", "parentUuid", "requestId"},
        )
        _set_native(state, _first(data, "sessionId", "session_id"), "sessionId")
        _set_if_missing(state, "cwd", _first(data, "cwd", "workingDirectory"))
        _set_if_missing(state, "display_name", _first(data, "title", "name", "label"))
        lifecycle_state, kind = _marker(data, "claude")
        if lifecycle_state:
            _add_lifecycle(state, record, lifecycle_state, kind or "marker")
        message = data.get("message") if isinstance(data.get("message"), dict) else None
        if message:
            _capture_unknown(
                state,
                record,
                message,
                {"role", "model", "model_id", "modelId", "content", "usage", "stop_reason", "stopReason", "id"},
                "message",
            )
            _set_if_missing(state, "model", _first(message, "model", "model_id", "modelId"))
            usage = message.get("usage")
            if isinstance(usage, dict):
                identity = _record_identity(record, f"assistant:{record.line}")
                for source_key, field in _TOKEN_ALIASES.items():
                    if source_key in usage:
                        _add_usage(state, field, usage[source_key], record, "primary_direct", identity, False)
                _usage_from_mapping(state, {"usage": usage}, record, "primary_direct", identity, False)
            role = _message_role(data)
            turn = _turn(state, record, role, _first(message, "id") or _first(data, "uuid", "id"))
            for item in _claude_content_items(message):
                item_type = _first(item, "type")
                if item_type == "tool_use":
                    _tool_call(state, turn, record, _first(item, "id"), _first(item, "name", "tool_name"))
                elif item_type == "tool_result":
                    _tool_result(
                        state,
                        record,
                        _first(item, "tool_use_id", "toolUseId", "id"),
                        _first(item, "is_error", "isError") is True,
                        turn,
                    )
        result = data.get("result")
        identity = _record_identity(record, f"result:{record.line}")
        _add_cost(
            state,
            _first(data, "total_cost_usd", "totalCostUsd"),
            record,
            "primary_direct",
            identity,
        )
        if isinstance(result, dict):
            _add_cost(
                state,
                _first(result, "total_cost_usd", "totalCostUsd"),
                record,
                "primary_direct",
                identity,
            )
            _set_if_missing(state, "ended_at", _timestamp(_first(result, "ended_at", "endedAt")))
        _set_if_missing(state, "ended_at", _timestamp(_first(data, "ended_at", "endedAt")))
    return _finalize_run(state)


# ---------------------------------------------------------------------------
# Codex adapter


def _codex_payload(record: SourceRecord) -> dict[str, Any]:
    payload = record.data.get("payload")
    return payload if isinstance(payload, dict) else record.data


def _parse_codex(group: InputGroup) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _new_state("codex")
    for record in _iter_primary_records(state, group.primary):
        data = record.data
        payload = _codex_payload(record)
        _observe_common(state, record)
        _capture_unknown(state, record, data, {"timestamp", "ordinal", "seq", "type", "payload"})
        envelope_type = _first(data, "type")
        payload_type = _first(payload, "type", "event", "kind")
        if envelope_type == "session_meta":
            _set_native(state, _first(payload, "session_id", "sessionId", "id"), "session_meta.payload.session_id")
            _set_if_missing(state, "cwd", _first(payload, "cwd", "working_directory", "workingDirectory"))
            _set_if_missing(state, "model", _first(payload, "model", "model_provider", "modelProvider"))
            _set_if_missing(state, "display_name", _first(payload, "title", "thread_name", "nickname", "agent_name"))
            _merge_lineage(state["lineage"], _lineage_from(payload, turn=False))
        marker_data = dict(data)
        marker_data["type"] = payload_type or envelope_type
        lifecycle_state, kind = _marker(marker_data, "codex")
        if lifecycle_state:
            _add_lifecycle(state, record, lifecycle_state, kind or "marker")
        if payload_type == "message" or (envelope_type == "response_item" and _message_role(payload) != UNKNOWN):
            role = _message_role(payload)
            turn = _turn(state, record, role, _first(payload, "id", "item_id", "itemId"), _lineage_from(payload, turn=True))
            content = payload.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and _first(item, "type") in {"custom_tool_call", "tool_call"}:
                        _tool_call(state, turn, record, _first(item, "call_id", "callId", "id"), _first(item, "name", "tool_name"))
            _observe_skills(state, payload, "codex.message", "low")
        if payload_type == "custom_tool_call":
            turn = _turn(state, record, "assistant", _first(payload, "id", "call_id", "callId"), _lineage_from(payload, turn=True))
            _tool_call(state, turn, record, _first(payload, "call_id", "callId", "id"), _first(payload, "name", "tool_name"))
        elif payload_type in {"custom_tool_call_output", "tool_result"}:
            turn = _turn(state, record, "tool", _first(payload, "id", "call_id", "callId"), _lineage_from(payload, turn=True))
            _tool_result(state, record, _first(payload, "call_id", "callId", "tool_call_id", "toolCallId", "id"), _first(payload, "is_error", "isError") is True, turn)
        if payload_type in {"token_count", "token_usage_record", "usage", "token_usage"} or envelope_type == "token_usage_record":
            identity = _record_identity(record, f"usage:{record.line}")
            _usage_from_mapping(state, payload, record, "aggregate", identity, True)
        _capture_unknown(state, record, payload, {"type", "event", "kind", "role", "id", "item_id", "itemId", "content", "call_id", "callId", "name", "tool_name", "input", "output", "is_error", "isError", "info", "usage", "token_usage", "total_token_usage", "last_token_usage"}, "payload")
    return _finalize_run(state)


# ---------------------------------------------------------------------------
# Pi and OMP adapters


def _pi_message(data: dict[str, Any]) -> dict[str, Any]:
    message = data.get("message")
    return message if isinstance(message, dict) else data


def _pi_content(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if isinstance(content, list):
        return [item for item in content if isinstance(item, dict)]
    if isinstance(content, dict):
        return [content]
    return []


def _parse_pi_like(group: InputGroup, harness: str) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _new_state(harness)
    for record in _iter_primary_records(state, group.primary):
        data = record.data
        _observe_common(state, record)
        known = {"type", "version", "id", "timestamp", "cwd", "message", "parentId", "parent_id", "provider", "modelId", "model_id", "model", "thinkingLevel", "thinking_level", "customType", "data", "title", "status", "state", "ended", "isError", "is_error", "toolCallId", "tool_call_id", "toolName", "tool_name"}
        _capture_unknown(state, record, data, known)
        record_type = _first(data, "type", "event")
        custom_type = _first(data, "customType", "custom_type")
        record_type_text = str(record_type).casefold() if isinstance(record_type, str) else ""
        custom_text = str(custom_type).casefold() if isinstance(custom_type, str) else ""
        if record_type_text == "session":
            _set_native(state, _first(data, "id", "sessionId", "session_id"), "session.id")
            _merge_lineage(state["lineage"], _run_lineage_from(data))
            _set_if_missing(state, "cwd", _first(data, "cwd", "workingDirectory"))
        if record_type_text == "model_change":
            _set_if_missing(state, "model", _first(data, "modelId", "model_id", "model"))
            _set_if_missing(state, "cwd", _first(data, "cwd"))
        if record_type_text in {"title", "title_change"}:
            _set_if_missing(state, "display_name", _first(data, "title", "name"))
        if harness == "omp" and custom_text == "tool_execution_start":
            details = data.get("data") if isinstance(data.get("data"), dict) else data
            _merge_lineage(state["lineage"], _run_lineage_from(details))
            call_lineage = _lineage_from(data, turn=True)
            _merge_lineage(call_lineage, _lineage_from(details, turn=True))
            turn = _turn(
                state,
                record,
                "assistant",
                _first(details, "id", "toolCallId", "tool_call_id"),
                call_lineage,
            )
            _tool_call(state, turn, record, _first(details, "toolCallId", "tool_call_id", "id"), _first(details, "toolName", "tool_name", "name"))
        if record_type_text in {"agent_start", "agent_started", "agent_spawn", "child_start", "child_spawn"}:
            _merge_lineage(state["lineage"], _run_lineage_from(data))
            details = data.get("data") if isinstance(data.get("data"), dict) else None
            if details is not None:
                _merge_lineage(state["lineage"], _run_lineage_from(details))
        message = _pi_message(data)
        role = _message_role(data)
        if isinstance(data.get("message"), dict) or record_type_text == "message":
            turn_lineage = _lineage_from(data, turn=True)
            _merge_lineage(turn_lineage, _lineage_from(message, turn=True))
            turn = _turn(
                state,
                record,
                role,
                _first(data, "id", "eventId", "event_id") or _first(message, "id"),
                turn_lineage,
            )
            for item in _pi_content(message):
                item_type = str(_first(item, "type") or "").casefold()
                if item_type in {"toolcall", "tool_call", "custom_tool_call"}:
                    _tool_call(state, turn, record, _first(item, "id", "toolCallId", "tool_call_id"), _first(item, "name", "tool_name"))
                elif item_type in {"toolresult", "tool_result"}:
                    _tool_result(state, record, _first(item, "toolCallId", "tool_call_id", "id"), _first(item, "isError", "is_error") is True, turn)
            if role == "toolResult" or role.casefold() == "toolresult":
                _tool_result(state, record, _first(message, "toolCallId", "tool_call_id"), _first(message, "isError", "is_error") is True, turn)
            _observe_skills(state, data, f"{harness}.message", "low")
            usage = _first(message, "usage", "tokens", "token_usage")
            if isinstance(usage, dict):
                _usage_from_mapping(state, usage, record, "primary_direct", _record_identity(record, f"usage:{record.line}"), False)
        if record_type_text in {"toolcall", "tool_call"}:
            turn = _turn(state, record, "assistant", _first(data, "id", "toolCallId", "tool_call_id"), _lineage_from(data, turn=True))
            _tool_call(state, turn, record, _first(data, "id", "toolCallId", "tool_call_id"), _first(data, "name", "toolName", "tool_name"))
        if record_type_text in {"toolresult", "tool_result"}:
            turn = _turn(state, record, "tool", _first(data, "id", "toolCallId", "tool_call_id"), _lineage_from(data, turn=True))
            _tool_result(state, record, _first(data, "toolCallId", "tool_call_id", "id"), _first(data, "isError", "is_error") is True, turn)
        if harness == "omp" and record_type_text == "credential_pin":
            # Explicitly known sensitive metadata: retain only the occurrence
            # anchor, never provider/hash values in private unknown storage.
            state["unknowns"].append(
                {
                    "source_path": str(record.path),
                    "event_range": _event_range(record.line),
                    "field": "credential_pin",
                    "value": "[REDACTED]",
                    "record_identity": _record_identity(record),
                }
            )
        lifecycle_data = dict(data)
        if custom_type is not None:
            lifecycle_data["type"] = custom_type
        lifecycle_state, kind = _marker(lifecycle_data, harness)
        if lifecycle_state:
            _add_lifecycle(state, record, lifecycle_state, kind or "marker")
        usage = _first(data, "usage", "tokens", "token_usage")
        direct_usage = {key: value for key, value in data.items() if str(key) in _TOKEN_ALIASES}
        if direct_usage:
            _usage_from_mapping(
                state,
                direct_usage,
                record,
                "primary_direct",
                _record_identity(record, f"usage:{record.line}"),
                False,
            )
        if isinstance(usage, dict):
            _usage_from_mapping(state, usage, record, "primary_direct", _record_identity(record, f"usage:{record.line}"), False)
    if not state["native_id"] and harness == "omp":
        parent_name = group.primary[0].parent.name
        match = re.match(r"^\d+_([^/]+)$", parent_name)
        if match:
            _set_native(state, match.group(1), "path", "path_session_id")
    return _finalize_run(state)


def _parse_pi(group: InputGroup) -> tuple[dict[str, Any], dict[str, Any]]:
    return _parse_pi_like(group, "pi")


def _parse_omp(group: InputGroup) -> tuple[dict[str, Any], dict[str, Any]]:
    return _parse_pi_like(group, "omp")


# ---------------------------------------------------------------------------
# Grok adapter


def _grok_session_object(summary: dict[str, Any]) -> tuple[dict[str, Any], str]:
    info = summary.get("info") if isinstance(summary.get("info"), dict) else summary.get("session_info")
    if not isinstance(info, dict):
        info = {}
    return info, "summary.info" if summary.get("info") is info else "summary.session_info"


def _grok_tool_calls(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("tool_calls") or value.get("toolCalls")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]



def _grok_nested_payloads(value: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return operational Grok envelopes without traversing prompt payloads."""

    result: list[tuple[str, dict[str, Any]]] = []
    queue: list[tuple[str, Any]] = [("", value)]
    seen: set[int] = set()
    nested_keys = (
        "params",
        "update",
        "sessionUpdate",
        "session_update",
        "payload",
        "data",
        "event",
        "chunk",
        "toolCall",
        "tool_call",
        "toolResult",
        "tool_result",
        "_meta",
        "meta",
    )
    while queue:
        prefix, current = queue.pop(0)
        if not isinstance(current, dict) or id(current) in seen:
            continue
        seen.add(id(current))
        result.append((prefix, current))
        for key in nested_keys:
            child = current.get(key)
            if isinstance(child, dict):
                child_prefix = f"{prefix}.{key}" if prefix else key
                queue.append((child_prefix, child))
            elif isinstance(child, list):
                for index, item in enumerate(child):
                    if isinstance(item, dict):
                        child_prefix = f"{prefix}.{key}[{index}]" if prefix else f"{key}[{index}]"
                        queue.append((child_prefix, item))
    return result


def _grok_kind(mapping: dict[str, Any]) -> str:
    for key in ("type", "event", "event_type", "eventType", "kind", "method", "updateType", "update_type"):
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            normalized = value.casefold().replace("-", "_").replace(" ", "_")
            return normalized.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
    return ""


def _grok_primary_metadata(state: dict[str, Any], record: SourceRecord) -> None:
    for prefix, payload in _grok_nested_payloads(record.data):
        session_id = _first(payload, "sessionId", "session_id", "sessionID")
        ref = _ref(session_id)
        if ref is not None:
            state["primary_ids"].add(ref)
            source = f"primary.{prefix}.sessionId" if prefix else "primary.sessionId"
            state["primary_id_sources"].setdefault(ref, source)


def _grok_primary_context(state: dict[str, Any], record: SourceRecord) -> None:
    for _, payload in _grok_nested_payloads(record.data):
        _set_if_missing(state, "cwd", _first(payload, "cwd", "working_directory", "workingDirectory"))
        _set_if_missing(state, "model", _first(payload, "current_model_id", "currentModelId", "model_id", "modelId", "model"))
        _set_if_missing(state, "started_at", _record_timestamp(payload))


def _grok_sidecar_identities(value: Any) -> list[str]:
    """Collect only session identities, never arbitrary nested object ids."""

    found: list[str] = []

    def add(candidate: Any) -> None:
        ref = _ref(candidate)
        if ref is not None and ref not in found:
            found.append(ref)

    if not isinstance(value, dict):
        return found
    for key in ("sessionId", "session_id", "sessionID", "session_id_ref"):
        add(value.get(key))
    for key in ("info", "session_info", "session"):
        child = value.get(key)
        if isinstance(child, dict):
            add(_first(child, "id", "sessionId", "session_id", "sessionID"))
    for _, mapping in _iter_dicts(value):
        for key in ("sessionId", "session_id", "sessionID", "session_id_ref"):
            add(mapping.get(key))
    return found


def _grok_identity_gap(
    state: dict[str, Any],
    reason: str,
    *,
    path: Path | None = None,
    expected: str | None = None,
    observed: Sequence[str] | None = None,
) -> None:
    gap: dict[str, Any] = {"kind": "coverage_gap", "reason": reason, "harness": "grok"}
    if path is not None:
        gap["source_path"] = str(_absolute(path))
    if expected is not None:
        gap["expected_identity"] = expected
    if observed is not None:
        gap["observed_identity"] = list(observed)
    state["gaps"].append(gap)


def _grok_summary_identity(summary: dict[str, Any]) -> tuple[str | None, str]:
    info, info_source = _grok_session_object(summary)
    return _ref(_first(info, "id", "session_id", "sessionId")), info_source + ".id"


def _grok_select_cohort(
    state: dict[str, Any],
    group: InputGroup,
    sidecars: dict[str, Any],
) -> dict[str, Any]:
    """Select one Grok identity cohort before admitting enrichment."""

    primary_ids = sorted(state["primary_ids"])
    if len(primary_ids) > 1:
        state["primary_cohort_valid"] = False
        _grok_identity_gap(
            state,
            "grok primary identity conflict; primary streams rejected (no merged evidence)",
            path=group.primary[0],
            observed=primary_ids,
        )
        return {}

    if primary_ids:
        selected = primary_ids[0]
        _set_native(
            state,
            selected,
            state["primary_id_sources"].get(selected, "primary.sessionId"),
        )
    else:
        summary = sidecars.get("summary.json")
        summary_identity: str | None = None
        summary_source: str | None = None
        if isinstance(summary, dict):
            summary_identity, summary_source = _grok_summary_identity(summary)
        if summary_identity is not None:
            _set_native(state, summary_identity, summary_source or "summary.id")
        else:
            sidecar_identities: dict[str, str] = {}
            sidecar_paths: dict[str, Path] = {}
            for name, value in sidecars.items():
                path = next((candidate for candidate in group.sidecars if candidate.name == name), group.primary[0])
                for identity in _grok_sidecar_identities(value):
                    sidecar_identities.setdefault(identity, name)
                    sidecar_paths.setdefault(identity, path)
            identities = sorted(sidecar_identities)
            if len(identities) > 1:
                _grok_identity_gap(
                    state,
                    "grok sidecar identity conflict; sidecars rejected (no merged evidence)",
                    path=sidecar_paths[identities[0]],
                    observed=identities,
                )
                return {}
            if identities:
                selected = identities[0]
                _set_native(
                    state,
                    selected,
                    f"sidecar.{sidecar_identities[selected]}.sessionId",
                )

    admitted: dict[str, Any] = {}
    for name, value in sidecars.items():
        path = next((candidate for candidate in group.sidecars if candidate.name == name), group.primary[0])
        if _grok_sidecar_allowed(state, path, value):
            admitted[name] = value
    return admitted


def _grok_sidecar_record(
    state: dict[str, Any],
    group: InputGroup,
    name: str,
    data: Any,
) -> SourceRecord:
    path = next((candidate for candidate in group.sidecars if candidate.name == name), group.primary[0])
    absolute = _absolute(path)
    entry = state["files"].get((str(absolute), "sidecar"))
    evidence_hash = entry["sha256"] if entry is not None else sha256_text(_canonical(data))
    return SourceRecord(absolute, 1, data if isinstance(data, dict) else {}, "sidecar", evidence_hash, name)


def _grok_sidecar_allowed(state: dict[str, Any], path: Path, value: Any) -> bool:
    identities = _grok_sidecar_identities(value)
    expected = _ref(state.get("native_id"))
    if expected is None or not identities or all(identity == expected for identity in identities):
        return True
    state["gaps"].append(
        {
            "kind": "coverage_gap",
            "reason": "grok sidecar identity mismatch; sidecar ignored",
            "harness": "grok",
            "source_path": str(_absolute(path)),
            "expected_identity": expected,
            "observed_identity": identities,
        }
    )
    return False


def _grok_anchor(record: SourceRecord) -> dict[str, Any]:
    return {
        "source_path": str(record.path),
        "source_line": record.line,
        "evidence_hash": record.raw_hash,
    }


def _grok_anchor_record(anchor: dict[str, Any], role: str = "primary") -> SourceRecord:
    return SourceRecord(
        Path(str(anchor["source_path"])),
        int(anchor["source_line"]),
        {},
        role,
        str(anchor["evidence_hash"]),
    )

def _grok_call_target(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("toolCall", "tool_call", "call"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def _grok_public_anchor(anchor: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "source_path": anchor["source_path"],
        "source_line": anchor["source_line"],
        "evidence_hash": anchor["evidence_hash"],
    }


def _grok_observation(state: dict[str, Any], call_id: str) -> dict[str, Any]:
    observations = state["grok_observations"]
    entry = observations.get(call_id)
    if entry is None:
        entry = {
            "id": call_id,
            "call": None,
            "call_turn": None,
            "call_anchors": [],
            "result_turn": None,
            "result_anchors": [],
        }
        observations[call_id] = entry
    return entry


def _grok_add_call(
    state: dict[str, Any],
    record: SourceRecord,
    identifier: Any,
    name: Any,
    turn_id: Any = None,
    lineage: dict[str, Any] | None = None,
    turn: dict[str, Any] | None = None,
) -> None:
    call_id = _ref(identifier)
    if call_id is None:
        return
    entry = _grok_observation(state, call_id)
    anchor = _grok_anchor(record)
    entry["call_anchors"].append(anchor)
    if turn is not None and entry["call_turn"] is None:
        entry["call_turn"] = turn
    incoming_lineage = lineage if lineage is not None else _empty_lineage()
    call = entry["call"]
    if call is None:
        entry["call"] = {
            "name": _safe_label(name),
            "turn_id": _ref(turn_id),
            "lineage": copy.deepcopy(incoming_lineage),
            "anchor": anchor,
        }
        return
    if call["name"] == UNKNOWN and _safe_label(name) != UNKNOWN:
        call["name"] = _safe_label(name)
    if call["turn_id"] is None:
        call["turn_id"] = _ref(turn_id)
    _merge_lineage(call["lineage"], incoming_lineage)


def _grok_add_result(
    state: dict[str, Any],
    record: SourceRecord,
    identifier: Any,
    is_error: bool,
    turn: dict[str, Any] | None = None,
) -> None:
    call_id = _ref(identifier)
    if call_id is None:
        if turn is not None:
            turn["errors"].append(
                {
                    "kind": "tool.result_unpaired",
                    "source_line": record.line,
                    "source_path": str(record.path),
                }
            )
        return
    entry = _grok_observation(state, call_id)
    if turn is not None and entry["result_turn"] is None:
        entry["result_turn"] = turn
    anchor = _grok_anchor(record)
    entry["result_anchors"].append({**anchor, "is_error": bool(is_error)})


def _grok_materialize_tools(state: dict[str, Any]) -> None:
    """Derive one semantic call/result from all primary Grok streams."""

    for call_id, entry in state["grok_observations"].items():
        call = entry["call"]
        results = entry["result_anchors"]
        if call is None:
            if not results:
                continue
            result = results[0]
            turn = entry["result_turn"]
            if turn is None:
                result_record = _grok_anchor_record(result)
                turn = _turn(state, result_record, "tool", call_id)
            turn["errors"].append(
                {
                    "kind": "tool.result_unpaired",
                    "source_line": result["source_line"],
                    "source_path": result["source_path"],
                }
            )
            continue

        call_record = _grok_anchor_record(call["anchor"])
        turn = entry["call_turn"]
        if turn is None:
            turn = _turn(state, call_record, "assistant", call["turn_id"], call["lineage"])
        call_value: dict[str, Any] = {
            "id": call_id,
            "name": call["name"],
            "status": "pending",
            "source_line": call["anchor"]["source_line"],
            "source_path": call["anchor"]["source_path"],
            "evidence": [
                _grok_public_anchor(anchor, "call")
                for anchor in entry["call_anchors"]
            ],
        }
        if results:
            call_value["status"] = "error" if any(item["is_error"] for item in results) else "ok"
            first_result = results[0]
            call_value["result_source_line"] = first_result["source_line"]
            call_value["result_source_path"] = first_result["source_path"]
            call_value["evidence"].extend(
                _grok_public_anchor(item, "result") for item in results
            )
            if call_value["status"] == "error":
                error_anchor = next(item for item in results if item["is_error"])
                turn["errors"].append(
                    {
                        "kind": "tool.error",
                        "source_line": error_anchor["source_line"],
                        "source_path": error_anchor["source_path"],
                    }
                )
            result_turn = entry["result_turn"]
            if (
                result_turn is not None
                and result_turn in state["turns"]
                and not result_turn["tool_calls"]
                and not result_turn["errors"]
            ):
                state["turns"].remove(result_turn)
        else:
            state["pending"].setdefault(call_id, []).append((turn, call_value, call_record))
        turn["tool_calls"].append(call_value)


def _grok_process_nested(state: dict[str, Any], record: SourceRecord) -> None:
    payloads = _grok_nested_payloads(record.data)
    top_kind = _grok_kind(record.data)
    chat_kinds = {"assistant", "user", "system", "reasoning", "tool_result", "toolresult"}
    for index, (prefix, payload) in enumerate(payloads):
        kind = _grok_kind(payload)
        if index == 0 and top_kind in chat_kinds:
            continue
        lifecycle_state, lifecycle_kind = _marker(payload, "grok")
        if lifecycle_state:
            suffix = f"{prefix}.{kind}" if prefix else kind
            composed = f"primary.{suffix or 'marker'}:{lifecycle_kind}"
            _add_lifecycle(
                state,
                record,
                lifecycle_state,
                AuthoredToken(composed) if isinstance(lifecycle_kind, AuthoredToken) else composed,
            )

        meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else payload.get("meta")
        if isinstance(meta, dict):
            _usage_from_mapping(
                state,
                meta,
                record,
                "aggregate",
                _record_identity(record, f"grok.meta:{prefix or 'record'}"),
                True,
            )
        if kind in {"turn_completed", "turn_complete", "update", "session_update"}:
            _usage_from_mapping(
                state,
                payload,
                record,
                "primary_direct",
                _record_identity(record, f"grok.update:{prefix or 'record'}"),
                False,
            )

        target = _grok_call_target(payload)
        call_id = _first(target, "id", "toolCallId", "tool_call_id", "callId", "call_id")
        if kind in {"tool_call", "toolcall", "custom_tool_call"} and call_id is not None:
            _grok_add_call(
                state,
                record,
                call_id,
                _first(target, "name", "toolName", "tool_name", "title"),
                _first(payload, "turnId", "turn_id", "turnID", "id"),
                _lineage_from(payload, turn=True),
            )
        elif kind in {"tool_call_update", "toolcall_update", "tool_result", "toolresult"} and call_id is not None:
            status = str(_first(target, "status", "state", "phase") or "").casefold()
            error = _first(target, "error", "errorMessage", "error_message")
            has_result = any(key in target for key in ("result", "output", "error", "errorMessage", "error_message", "isError", "is_error"))
            completed_status = status in {"completed", "complete", "done", "success", "succeeded", "failed", "error", "errored", "cancelled", "canceled"}
            if kind in {"tool_result", "toolresult"} or completed_status or has_result:
                is_error = status in {"failed", "error", "errored", "cancelled", "canceled"} or error not in (None, "")
                if _first(target, "isError", "is_error") is True:
                    is_error = True
                _grok_add_result(state, record, call_id, is_error)
        elif kind in {"user_message_chunk", "agent_message_chunk", "agent_thought_chunk"}:
            role = {
                "user_message_chunk": "user",
                "agent_message_chunk": "assistant",
                "agent_thought_chunk": "reasoning",
            }[kind]
            _turn(
                state,
                record,
                role,
                _first(payload, "turnId", "turn_id", "messageId", "message_id", "id"),
                _lineage_from(payload, turn=True),
            )
        elif kind == "turn_started":
            _turn(
                state,
                record,
                "assistant",
                _first(payload, "turnId", "turn_id", "id"),
                _lineage_from(payload, turn=True),
            )


def _parse_grok(group: InputGroup) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _new_state("grok")
    # Read each primary twice from the immutable spool: the first pass collects
    # identities for cohort selection, and the second pass derives chronology/tools
    # without retaining every decoded source record.
    for record in _iter_primary_records(state, group.primary):
        _grok_primary_metadata(state, record)

    sidecars: dict[str, Any] = {}
    for path in group.sidecars:
        if path.name not in {"summary.json", "usage.json", "prompt_context.json", "signals.json"}:
            continue
        value = _read_json(state, path, "sidecar")
        if value is not None:
            sidecars[path.name] = value
    # Identity selection is complete before any sidecar enrichment occurs.
    summaries = _grok_select_cohort(state, group, sidecars)

    summary = summaries.get("summary.json")
    if isinstance(summary, dict):
        info, info_source = _grok_session_object(summary)
        _set_native(state, _first(info, "id", "session_id", "sessionId"), info_source + ".id")
        _set_if_missing(state, "cwd", _first(info, "cwd", "working_directory", "workingDirectory"))
        _set_if_missing(state, "model", _first(info, "current_model_id", "currentModelId", "model", "model_id"))
        _set_if_missing(state, "display_name", _first(summary, "session_summary", "title", "name") or _first(info, "title", "name"))
        _set_if_missing(state, "started_at", _timestamp(_first(info, "created_at", "createdAt", "started_at", "startedAt")))
        ended = _first(info, "ended_at", "endedAt", "finished_at", "finishedAt")
        summary_record = _grok_sidecar_record(state, group, "summary.json", summary)
        if ended is not None:
            state["ended_at"] = _timestamp(ended)
            _add_lifecycle(state, summary_record, "terminal", AuthoredToken("summary.ended_metadata"))
        status = _first(info, "status", "state")
        if isinstance(status, str) and status.casefold() in {"live", "active", "running"}:
            _add_lifecycle(state, summary_record, "live", f"summary.status:{status.casefold()}")
        _merge_lineage(state["lineage"], _lineage_from(info, turn=False))
        _capture_unknown(
            state,
            summary_record,
            summary,
            {"info", "session_info", "session_summary", "title", "name"},
        )

    context = summaries.get("prompt_context.json")
    if context is not None:
        for path in _skill_path_candidates(context):
            _add_skill(state, _skill_entry(path, "grok.prompt_context", "high"))
        for _, item in _iter_dicts(context):
            path_value = _first(item, "path", "file", "skill_path", "skillPath")
            if isinstance(path_value, str) and "SKILL.md" in path_value:
                _add_skill(state, _skill_entry(path_value, "grok.prompt_context", "high", _first(item, "digest", "sha256", "hash")))

    usage = summaries.get("usage.json")
    if isinstance(usage, dict):
        info = usage.get("session") if isinstance(usage.get("session"), dict) else usage
        pseudo = _grok_sidecar_record(state, group, "usage.json", usage)
        _usage_from_mapping(state, info, pseudo, "sidecar", _record_identity(pseudo, "usage.session"), True)
        turns = usage.get("turns")
        if isinstance(turns, list):
            for index, turn_usage in enumerate(turns):
                if isinstance(turn_usage, dict):
                    _usage_from_mapping(state, turn_usage, pseudo, "sidecar", f"usage.turn:{index}", False)
        _add_cost(state, _first(info, "cost_usd", "costUsd", "total_cost_usd"), pseudo, "sidecar", _record_identity(pseudo, "usage.cost"))

    signals = summaries.get("signals.json")
    if isinstance(signals, dict):
        pseudo = _grok_sidecar_record(state, group, "signals.json", signals)
        status = _first(signals, "status", "state", "lifecycle")
        if isinstance(status, str):
            lifecycle_state, kind = _marker({"status": status, "type": status}, "grok")
            if lifecycle_state:
                _add_lifecycle(state, pseudo, lifecycle_state, kind or "signals.marker")

    if state["primary_cohort_valid"]:
        for record in _iter_primary_records(state, group.primary):
            data = record.data
            _grok_primary_context(state, record)
            _observe_common(state, record)
            _capture_unknown(state, record, data, {"type", "ts", "timestamp", "content", "tool_calls", "toolCalls", "tool_call_id", "toolCallId", "id", "role", "_meta", "meta"})
            _grok_process_nested(state, record)
            record_type = str(_first(data, "type") or "").casefold()
            if record_type == "assistant" or record_type in {"user", "system", "reasoning"}:
                role = record_type
                turn = _turn(state, record, role, _first(data, "id", "message_id", "messageId"), _lineage_from(data, turn=True))
                for call in _grok_tool_calls(data):
                    _grok_add_call(
                        state,
                        record,
                        _first(call, "id", "call_id", "callId"),
                        _first(call, "name", "tool_name", "title"),
                        _first(data, "turnId", "turn_id", "turnID", "id"),
                        _lineage_from(data, turn=True),
                        turn,
                    )
                _observe_skills(state, data, "grok.chat_history", "low")
            elif record_type in {"tool_result", "toolresult"}:
                turn = _turn(state, record, "tool", _first(data, "id", "tool_call_id", "toolCallId"), _lineage_from(data, turn=True))
                _grok_add_result(state, record, _first(data, "tool_call_id", "toolCallId", "id"), _first(data, "is_error", "isError") is True, turn)
            _observe_skills(state, data, "grok.primary", "low")

    _grok_materialize_tools(state)
    if not state["native_id"]:
        # A directory id is a display/fallback only; native identity remains
        # unknown unless primary/sidecar metadata explicitly supplies it.
        _set_if_missing(state, "display_name", unquote(Path(group.label or group.primary[0].parent).name))
    return _finalize_run(state)


_ADAPTERS = {
    "claude": _parse_claude,
    "codex": _parse_codex,
    "pi": _parse_pi,
    "omp": _parse_omp,
    "grok": _parse_grok,
}


def _coerce_since(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if value is None:
        return datetime.now(timezone.utc) - timedelta(days=7)
    text = str(value).strip()
    if text.casefold() in {"all", "none", "0"}:
        return None
    try:
        days = float(text)
    except ValueError:
        days = -1
    if days >= 0:
        return datetime.now(timezone.utc) - timedelta(days=days)
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise IngestError(f"invalid --since value: {text}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _under(path: Path, root: Path | None) -> bool:
    if root is None:
        return False
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _default_output_dir() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate / ".styrir" / "runs" / f"{datetime.now(timezone.utc):%Y-%m-%d}-session-eval"
    return current / ".styrir" / "runs" / f"{datetime.now(timezone.utc):%Y-%m-%d}-session-eval"


def _default_skill_roots() -> list[Path]:
    roots = [
        Path.home() / "Code" / "skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".codex" / "skills",
        Path.home() / ".pi" / "agent" / "skills",
        Path.home() / ".omp" / "agent" / "skills",
        Path.home() / ".grok" / "skills",
    ]
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            roots.extend(
                candidate / relative
                for relative in (".claude/skills", ".pi/skills", ".omp/skills")
            )
            break
    return [root for root in roots if root.is_dir()]


def _eligible(path: Path, since: datetime | None) -> bool:
    if since is None:
        return True
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return False
    return mtime >= since


def _is_primary_jsonl(path: Path, harness: str) -> bool:
    name = path.name
    if path.suffix != ".jsonl":
        return False
    if harness == "grok":
        return name in {"chat_history.jsonl", "events.jsonl", "updates.jsonl"}
    if harness == "codex":
        return name not in {"session_index.jsonl", "history.jsonl"} and (
            name.startswith("rollout-") or name.endswith(".jsonl")
        )
    return name not in {"history.jsonl", "session_index.jsonl"}


def _looks_like_grok(path: Path) -> bool:
    return path.name in {"chat_history.jsonl", "events.jsonl", "updates.jsonl", "summary.json", "usage.json", "prompt_context.json"} or ".grok" in path.parts


def infer_harness(path: str | Path) -> str | None:
    candidate = _absolute(path)
    parts = {part.casefold() for part in candidate.parts}
    name = candidate.name.casefold()
    if ".omp" in parts or "omp" in parts or "omp" in name:
        return "omp"
    if ".pi" in parts or "pi" in parts or "pi" in name:
        return "pi"
    if ".codex" in parts or name.startswith("rollout-") or "codex" in name:
        return "codex"
    if ".claude" in parts or "claude" in name:
        return "claude"
    if _looks_like_grok(candidate):
        return "grok"
    if candidate.is_file() and candidate.suffix == ".jsonl":
        saw_v3 = False
        saw_omp_marker = False
        try:
            with candidate.open("rb") as handle:
                for index, raw in enumerate(handle):
                    if index >= 64:
                        break
                    if not raw.strip():
                        continue
                    value = json.loads(raw.decode("utf-8"))
                    if not isinstance(value, dict):
                        continue
                    if "payload" in value and "ordinal" in value:
                        return "codex"
                    if value.get("version") == 3 or value.get("type") in {"session", "model_change", "thinking_level_change", "message"}:
                        saw_v3 = True
                    if "customType" in value or "custom_type" in value or "credential_pin" in value:
                        saw_omp_marker = True
                    if value.get("sessionId") or value.get("result"):
                        return "claude"
                    record_type = value.get("type")
                    message = value.get("message")
                    if isinstance(message, dict) and record_type in {"assistant", "user", "system", "tool_result", "result"}:
                        return "claude"
                    if record_type in {"assistant", "user", "system", "tool_result", "reasoning"}:
                        return "grok"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if saw_v3:
            return "omp" if saw_omp_marker else "pi"
    return None




def _grok_group(
    path: Path,
    since: datetime | None = None,
    exclude: Path | None = None,
) -> InputGroup | None:
    directory = path if path.is_dir() else path.parent
    known_primary = [
        directory / name
        for name in ("chat_history.jsonl", "events.jsonl", "updates.jsonl")
        if (directory / name).is_file()
        and not _under(directory / name, exclude)
        and _eligible(directory / name, since)
    ]
    if (
        path.is_file()
        and path.name in {"chat_history.jsonl", "events.jsonl", "updates.jsonl"}
        and path not in known_primary
        and not _under(path, exclude)
        and _eligible(path, since)
    ):
        known_primary.insert(0, path)
    if not known_primary:
        return None
    sidecars = [
        directory / name
        for name in ("summary.json", "signals.json", "usage.json", "prompt_context.json")
        if (directory / name).is_file()
        and not _under(directory / name, exclude)
        and _eligible(directory / name, since)
    ]
    return InputGroup("grok", known_primary, sidecars, str(directory))


def discover_groups(
    harnesses: Sequence[str],
    paths: Sequence[str | Path] | None = None,
    since: datetime | None = None,
    exclude: str | Path | None = None,
) -> dict[str, list[InputGroup]]:
    """Discover explicit local inputs; primary streams always remain authoritative."""

    exclude_path = _absolute(exclude) if exclude is not None else None

    selected_paths = [_absolute(path) for path in (paths or [])]
    result: dict[str, list[InputGroup]] = {harness: [] for harness in harnesses}
    if not selected_paths:
        roots = {
            "claude": Path.home() / ".claude" / "projects",
            "codex": Path.home() / ".codex" / "sessions",
            "pi": Path.home() / ".pi" / "agent" / "sessions",
            "omp": Path.home() / ".omp" / "agent" / "sessions",
            "grok": Path.home() / ".grok" / "sessions",
        }
        selected_paths = [roots[harness] for harness in harnesses if roots[harness].exists()]

    seen: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
    for path in selected_paths:
        if not path.exists() or _under(path, exclude_path):
            continue
        candidates: list[tuple[str, Path]] = []
        if path.is_file():
            if _eligible(path, since):
                inferred = infer_harness(path)
                candidates.append((inferred or "", path))
        elif path.is_dir():
            primary_here = any(
                (path / name).is_file()
                and not _under(path / name, exclude_path)
                and _eligible(path / name, since)
                for name in ("chat_history.jsonl", "events.jsonl", "updates.jsonl")
            )
            if primary_here:
                candidates.append(("grok", path))
            elif _looks_like_grok(path):
                # A sessions root (for example ~/.grok/sessions) is not itself
                # a session. Discover each child session directory instead.
                session_dirs = sorted(
                    {
                        child.parent
                        for child in path.rglob("*.jsonl")
                        if child.name in {"chat_history.jsonl", "events.jsonl", "updates.jsonl"}
                        and not _under(child, exclude_path)
                        and _eligible(child, since)
                    }
                )
                candidates.extend(("grok", child) for child in session_dirs)
            else:
                for child in sorted(path.rglob("*.jsonl")):
                    if _under(child, exclude_path) or not _eligible(child, since):
                        continue
                    inferred = infer_harness(child)
                    candidates.append((inferred or "", child))
        for inferred, candidate in candidates:
            if _under(candidate, exclude_path):
                continue
            if inferred in harnesses:
                harness_candidates = [inferred]
            elif not inferred:
                harness_candidates = list(harnesses)
            else:
                harness_candidates = []
            for harness in harness_candidates:
                if harness == "grok":
                    group = _grok_group(candidate, since, exclude_path)
                    if group is None:
                        continue
                else:
                    primary = (
                        [candidate]
                        if candidate.is_file() and _eligible(candidate, since)
                        else sorted(
                            child
                            for child in candidate.rglob("*.jsonl")
                            if _is_primary_jsonl(child, harness)
                            and not _under(child, exclude_path)
                            and _eligible(child, since)
                        )
                    )
                    if not primary:
                        continue
                    group = InputGroup(
                        harness,
                        primary,
                        [],
                        str(candidate.parent if candidate.is_file() else candidate),
                    )
                key = (group.harness, tuple(str(p) for p in group.primary), tuple(str(p) for p in group.sidecars))
                if key not in seen:
                    seen.add(key)
                    result[harness].append(group)
    for harness in result:
        result[harness].sort(key=lambda group: tuple(str(path) for path in group.primary))
    return result


def _open_secure_dir(path: Path) -> int:
    """Open/create a directory chain without following symlinks."""

    path = _absolute_lexical(path)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    if not nofollow or not directory:
        raise IngestError("platform lacks no-follow directory support")
    try:
        fd = os.open(os.sep, os.O_RDONLY | directory)
    except OSError as exc:
        raise IngestError(f"cannot open output root: {exc}") from exc
    components = [part for part in path.parts if part not in {"", os.sep}]
    try:
        for index, component in enumerate(components):
            try:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | directory | nofollow,
                    dir_fd=fd,
                )
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                try:
                    next_fd = os.open(
                        component,
                        os.O_RDONLY | directory | nofollow,
                        dir_fd=fd,
                    )
                except OSError as exc:
                    raise IngestError(f"unsafe output directory {path}: {exc}") from exc
            except OSError as exc:
                raise IngestError(f"unsafe output directory {path}: {exc}") from exc
            try:
                info = os.fstat(next_fd)
                if not stat.S_ISDIR(info.st_mode):
                    raise IngestError(f"output component is not a directory: {path}")
                if index == len(components) - 1:
                    if info.st_uid != os.getuid():
                        raise IngestError(f"output directory is not owned by current user: {path}")
                    os.fchmod(next_fd, 0o700)
            except BaseException:
                os.close(next_fd)
                raise
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _secure_dir(path: Path) -> None:
    fd = _open_secure_dir(path)
    os.close(fd)


def _secure_read_file(parent_fd: int, name: str) -> bytes | None:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, os.O_RDONLY | nofollow, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise IngestError(f"unsafe output file {name}: {exc}") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise IngestError(f"output file is not regular: {name}")
        if info.st_uid != os.getuid():
            raise IngestError(f"output file is not owned by current user: {name}")
        os.fchmod(fd, 0o600)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError as exc:
        raise IngestError(f"cannot inspect output file {name}: {exc}") from exc
    finally:
        os.close(fd)


def _secure_write_new(parent_fd: int, name: str, payload: bytes) -> bool:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
            dir_fd=parent_fd,
        )
    except FileExistsError:
        return False
    except OSError as exc:
        raise IngestError(f"cannot create output file {name}: {exc}") from exc
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        return True
    except OSError as exc:
        raise IngestError(f"cannot write output file {name}: {exc}") from exc


def _write_secure_payload(path: Path, payload: bytes) -> Path:
    """Write an immutable owner-only file, collision-safe and symlink-safe."""

    path = _absolute_lexical(path)
    parent_fd = _open_secure_dir(path.parent)
    try:
        digest = sha256_bytes(payload)[:16]
        candidate_index = 0
        while True:
            if candidate_index == 0:
                candidate = path
            else:
                suffix = f"-{digest}" if candidate_index == 1 else f"-{digest}-{candidate_index}"
                candidate = path.with_name(path.stem + suffix + path.suffix)
            existing = _secure_read_file(parent_fd, candidate.name)
            if existing is not None:
                if existing == payload:
                    return candidate
                candidate_index += 1
                continue
            if _secure_write_new(parent_fd, candidate.name, payload):
                return candidate
    finally:
        os.close(parent_fd)


def _secure_stream_equal(parent_fd: int, name: str, source: Any) -> bool | None:
    """Compare an existing owner-only file with a binary source spool."""

    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, os.O_RDONLY | nofollow, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise IngestError(f"unsafe output file {name}: {exc}") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise IngestError(f"output file is not regular: {name}")
        if info.st_uid != os.getuid():
            raise IngestError(f"output file is not owned by current user: {name}")
        os.fchmod(fd, 0o600)
        source.seek(0)
        while True:
            expected = source.read(1024 * 1024)
            actual = os.read(fd, 1024 * 1024)
            if expected != actual:
                return False
            if not expected:
                return True
    except OSError as exc:
        raise IngestError(f"cannot compare output file {name}: {exc}") from exc
    finally:
        os.close(fd)


def _secure_write_stream_new(parent_fd: int, name: str, source: Any, expected_sha256: str) -> bool:
    """Create a snapshot from a spool without materializing it in memory."""

    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
            dir_fd=parent_fd,
        )
    except FileExistsError:
        return False
    except OSError as exc:
        raise IngestError(f"cannot create output file {name}: {exc}") from exc
    failed = True
    try:
        os.fchmod(fd, 0o600)
        source.seek(0)
        digest = hashlib.sha256()
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(fd, view)
                view = view[written:]
        if digest.hexdigest() != expected_sha256:
            raise IngestError("opened source spool changed before snapshot write")
        failed = False
        return True
    except OSError as exc:
        raise IngestError(f"cannot write output file {name}: {exc}") from exc
    finally:
        os.close(fd)
        if failed:
            try:
                os.unlink(name, dir_fd=parent_fd)
            except OSError:
                pass


def _write_private_snapshot(
    out: Path,
    manifest: list[dict[str, str]],
    source_blobs: Sequence[tuple[str, str, Any]],
) -> None:
    private_root = _absolute_lexical(out) / ".private"
    root = private_root / "snapshots"
    _secure_dir(private_root)
    _secure_dir(root)
    blobs: dict[tuple[str, str], Any] = {}
    for path, role, spool in source_blobs:
        key = (path, role)
        if key in blobs:
            raise IngestError("opened source spool association mismatch")
        blobs[key] = spool
    consumed: set[tuple[str, str]] = set()
    for index, item in enumerate(manifest):
        key = (item["path"], item["role"])
        spool = blobs.get(key)
        if spool is None or getattr(spool, "closed", False):
            raise IngestError(f"opened source spool unavailable for {item['path']}")
        consumed.add(key)
        snapshot_dir = root / item["sha256"]
        _secure_dir(snapshot_dir)
        parent_fd = _open_secure_dir(snapshot_dir)
        try:
            source_name = Path(item["path"]).name
            safe_name = f"{index:03d}-{sha256_text(item['path'] + ':' + item['role'])[:12]}-{source_name}"
            existing = _secure_stream_equal(parent_fd, safe_name, spool)
            if existing is True:
                continue
            if existing is False:
                raise IngestError(f"immutable snapshot collision: {item['path']}")
            if _secure_write_stream_new(parent_fd, safe_name, spool, item["sha256"]):
                continue
            existing = _secure_stream_equal(parent_fd, safe_name, spool)
            if existing is not True:
                raise IngestError(f"immutable snapshot collision: {item['path']}")
        finally:
            os.close(parent_fd)
    if consumed != set(blobs):
        raise IngestError("opened source spool association mismatch")



def _write_private_file(path: Path, value: Any) -> None:
    _write_secure_payload(path, _canonical(value).encode("utf-8"))


def _write_immutable_json(path: Path, value: Any) -> Path:
    return _write_secure_payload(path, _canonical(value).encode("utf-8"))


def ingest(
    paths: Sequence[str | Path] | None = None,
    harnesses: Sequence[str] | None = None,
    out: str | Path | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    since: str | datetime | None = None,
) -> tuple[dict[str, Any], Path]:
    """Ingest local streams and write an immutable, redacted v0 receipt.

    ``paths`` are explicit files/directories.  ``harnesses`` defaults to all
    five adapters.  The returned tuple is the receipt and its stable
    ``receipt.json`` (or collision-safe alternate) path.  This stage only
    populates normalized runs; downstream checks and rendering consume the
    same ``styrir-session-eval/v0`` document.
    """

    requested: list[str] = []
    for item in (harnesses or HARNESSES):
        for harness in str(item).split(","):
            normalized = harness.strip().casefold()
            if not normalized:
                continue
            if normalized == "all":
                for name in HARNESSES:
                    if name not in requested:
                        requested.append(name)
            elif normalized not in requested:
                requested.append(normalized)
    invalid = [harness for harness in requested if harness not in HARNESSES]
    if invalid:
        raise IngestError("unsupported harness: " + ", ".join(invalid))
    since_dt = _coerce_since(since)
    out_path = _output_root(out or _default_output_dir())
    _secure_dir(out_path)
    groups = discover_groups(requested, paths, since_dt, out_path)
    runs: list[dict[str, Any]] = []
    private_runs: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    observed: list[str] = []
    gaps: list[dict[str, Any]] = []
    effective_skill_roots = list(skill_roots) if skill_roots else _default_skill_roots()
    for harness in requested:
        harness_groups = groups.get(harness, [])
        if not harness_groups:
            gaps.append({"harness": harness, "kind": "coverage_gap", "reason": "no primary stream found"})
            continue
        observed.append(harness)
        adapter = _ADAPTERS[harness]
        for group in harness_groups:
            try:
                run, private = adapter(group)
            except (IngestError, OSError, ValueError) as exc:
                # A discovered primary is retained as a coverage/error row
                # rather than being silently dropped.
                gaps.append(
                    {
                        "harness": harness,
                        "kind": "ingest_error",
                        "reason": _safe_label(str(exc)),
                        "source": group.label,
                    }
                )
                continue
            source_blobs = private.pop("source_blobs", [])
            try:
                _write_private_snapshot(out_path, run["source_snapshot"]["files"], source_blobs)
            finally:
                for _path, _role, spool in source_blobs:
                    spool.close()
            runs.append(run)
            private_runs.append(private)
            gaps.extend(run.get("coverage", {}).get("gaps", []))
            malformed.extend(run.get("parse_errors", []))

    # Skill roots resolve only current bytes for an observed path.  They never
    # fill the historical digest, because a mention does not prove loaded bytes.
    if effective_skill_roots:
        for run in runs:
            for skill in run.get("skills", []):
                if skill.get("current_on_disk_digest") not in (None, UNKNOWN):
                    continue
                for root in effective_skill_roots:
                    root_path = _absolute(root)
                    skill_path = Path(str(skill.get("path", ""))).expanduser()
                    candidates = [skill_path]
                    if not skill_path.is_absolute():
                        candidates.insert(0, root_path / skill_path)
                    candidate = next((item for item in candidates if item.is_file()), None)
                    if candidate is not None:
                        skill["current_on_disk_digest"] = sha256_file(candidate)
                        if skill.get("digest") not in (None, UNKNOWN):
                            skill["digest_relation"] = (
                                "historical_matches_current"
                                if skill["digest"] == skill["current_on_disk_digest"]
                                else "historical_differs_from_current"
                            )
                        else:
                            skill["digest_relation"] = "historical_unknown"
                        break

    skill_rollup: list[dict[str, Any]] = []
    seen_skills: set[tuple[Any, Any, Any]] = set()
    for run in runs:
        for skill in run.get("skills", []):
            key = (skill.get("name"), skill.get("path"), skill.get("digest"))
            if key not in seen_skills:
                seen_skills.add(key)
                skill_rollup.append(skill)
    missing = [
        gap
        for gap in gaps
        if gap.get("kind") == "coverage_gap" and gap.get("reason") == "no primary stream found"
    ]
    sessions_malformed = sum(1 for run in runs if run.get("parse_errors"))
    coverage = {
        "sessions_ingested": len(runs),
        "sessions_malformed": sessions_malformed,
        "missing_requested_inputs": missing,
        "empty": not runs,
        "requested_harnesses": requested,
        "observed_harnesses": observed,
        "coverage_gaps": gaps,
        "gaps": gaps,
        "malformed_count": len(malformed),
        "malformed_records": malformed,
        "run_count": len(runs),
        "unknown_field_count": sum(len(item.get("unknown_fields", [])) for item in private_runs),
        "primary_streams_are_authoritative": True,
        "eof_is_not_terminal": True,
    }
    snapshots = [
        {
            "native_identity": run.get("native_identity", UNKNOWN),
            "source_path": run["source_path"],
            "sha256": run["source_snapshot"]["sha256"],
            "parser": run["parser"],
            "parser_version": run["parser_version"],
        }
        for run in runs
    ]
    receipt = {
        "schema": "styrir-session-eval/v0",
        "catalog_id": UNKNOWN,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "since": since_dt.isoformat() if since_dt is not None else UNKNOWN,
        "harnesses_requested": requested,
        "harnesses_found": observed,
        "coverage": coverage,
        # Ingestion does not decide behavioral checks; hard_pass is therefore
        # deliberately false rather than a vacuous success.
        "hard_pass": False,
        "infra_ok": not any(gap.get("kind") == "ingest_error" for gap in gaps),
        "feedback_outcome": None,
        "redaction": {"policy": "default-local", "applied": True},
        "approvals": [],
        "runs": runs,
        "skills": skill_rollup,
        "checks": [],
        "comparisons": [],
        "recommendations": [],
        "parse_errors": len(malformed),
        "proof_gaps": gaps,
        "provenance": {
            "parser": "session-eval-ingest",
            "parser_version": PARSER_VERSION,
            "snapshots": snapshots,
            "local_only": True,
            "provider_calls": 0,
            "native_workflow_required": False,
            "source_snapshot_rule": "ordered path/role/content-sha256 manifest",
            "private_unknown_storage": ".private/unknown-fields.json",
        },
        "ingest": {
            "schema_version": RECEIPT_SCHEMA,
            "adapters": {harness: PARSER_NAMES[harness] for harness in requested},
            "malformed_rows_counted": True,
            "unknown_fields_private": True,
        },
    }
    private_payload = {
        "schema_version": PRIVATE_SCHEMA,
        "runs": private_runs,
    }
    _write_private_file(out_path / ".private" / "unknown-fields.json", private_payload)
    immutable_id = sha256_text(_canonical(receipt))
    _write_immutable_json(out_path / "receipts" / f"{immutable_id}.json", receipt)
    requested_path = out_path / "receipt.json"
    if requested_path.exists() and requested_path.read_bytes() != _canonical(receipt).encode("utf-8"):
        requested_path = _write_immutable_json(out_path / f"receipt-{immutable_id}.json", receipt)
    else:
        requested_path = _write_immutable_json(requested_path, receipt)
    # Per-run immutable records make changed-byte identity auditable even when a
    # caller chooses to reuse one output directory.
    for run in runs:
        run_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", run["id"])
        run_path = out_path / "run_receipts" / f"{run_slug}--{run['source_snapshot']['sha256']}.json"
        _write_immutable_json(
            run_path,
            {"schema": "styrir-session-eval/v0", "ingest_schema_version": RECEIPT_SCHEMA, "run": run},
        )
    return receipt, requested_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval-ingest",
        description="Normalize local Claude/Codex/Pi/OMP/Grok session streams into a redacted receipt.",
    )
    parser.add_argument("inputs", nargs="*", help="optional positional local stream files/directories")
    parser.add_argument("--path", "--input", dest="paths", action="append", help="local stream file or session directory (repeatable)")
    parser.add_argument("--harness", action="append", dest="harnesses", help="claude, codex, pi, omp or grok (repeatable; comma-separated/all accepted)")
    parser.add_argument("--out", "--output", default=None, help="output directory (default: .styrir/runs/YYYY-MM-DD-session-eval under the nearest repository)")
    parser.add_argument("--since", default=None, help="mtime lower bound: ISO-8601, number of days, or all (default: 7 days)")
    parser.add_argument("--skill-root", action="append", default=[], help="skill root used to resolve observed activation paths")
    parser.add_argument("--pretty", action="store_true", help="pretty-print the command summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        input_paths = list(args.paths or []) + list(args.inputs or [])
        receipt, path = ingest(input_paths, args.harnesses, args.out, args.skill_root, args.since)
    except IngestError as exc:
        parser.error(str(exc))
        return 2
    summary = {
        "receipt": str(path),
        "runs": receipt["coverage"]["run_count"],
        "malformed": receipt["coverage"]["malformed_count"],
        "coverage_gaps": len(receipt["coverage"]["coverage_gaps"]),
        "observed_harnesses": receipt["coverage"]["observed_harnesses"],
    }
    if args.pretty:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
