#!/usr/bin/env python3
"""Redacted ATIF-v1.8 export for canonical session-eval receipts.

Consumes the ``styrir-session-eval/v0`` receipt produced by ``ingest.py`` and
writes one Harbor ATIF document per normalized run.  Message, tool-argument,
and result payloads are omitted and marked; unknown usage is omitted rather
than zeroed.  Harbor/Phoenix/OTel are not runtime dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "ATIF-v1.8"
PRODUCER = "session-eval-atif"
PRODUCER_VERSION = "1.0.0"
HARBOR_COMMIT = "88fdbc9d42e907c0414654f041ece5eaf798f538"
HARBOR_RFC = (
    "https://github.com/harbor-framework/harbor/blob/"
    f"{HARBOR_COMMIT}/rfcs/0001-trajectory-format.md"
)
HARBOR_MODELS = "src/harbor/models/trajectories/"
RECEIPT_SCHEMA = "styrir-session-eval/v0"
EXPORT_MANIFEST_SCHEMA = "session-eval-atif/v1"
UNKNOWN = "unknown"
REDACTED_MESSAGE = ""
SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
OFFICIAL_SCHEMA_PATH = SCHEMA_DIR / "atif-v1.8.schema.json"
PROVENANCE_PATH = SCHEMA_DIR / "atif-v1.8.provenance.json"

SCHEMA_VERSIONS = (
    "ATIF-v1.0",
    "ATIF-v1.1",
    "ATIF-v1.2",
    "ATIF-v1.3",
    "ATIF-v1.4",
    "ATIF-v1.5",
    "ATIF-v1.6",
    "ATIF-v1.7",
    "ATIF-v1.8",
)
TRAJECTORY_KEYS = {
    "schema_version",
    "session_id",
    "trajectory_id",
    "agent",
    "steps",
    "notes",
    "final_metrics",
    "continued_trajectory_ref",
    "extra",
    "subagent_trajectories",
}
AGENT_KEYS = {"name", "version", "model_name", "tool_definitions", "extra"}
STEP_KEYS = {
    "step_id",
    "timestamp",
    "source",
    "model_name",
    "reasoning_effort",
    "message",
    "reasoning_content",
    "tool_calls",
    "observation",
    "metrics",
    "is_copied_context",
    "llm_call_count",
    "extra",
}
AGENT_ONLY_FIELDS = (
    "model_name",
    "reasoning_effort",
    "reasoning_content",
    "tool_calls",
    "metrics",
)
TOOL_CALL_KEYS = {"tool_call_id", "function_name", "arguments", "extra"}
OBSERVATION_KEYS = {"results"}
OBSERVATION_RESULT_KEYS = {
    "source_call_id",
    "content",
    "subagent_trajectory_ref",
    "extra",
}
METRICS_KEYS = {
    "prompt_tokens",
    "completion_tokens",
    "cached_tokens",
    "cost_usd",
    "prompt_token_ids",
    "completion_token_ids",
    "logprobs",
    "extra",
}
FINAL_METRICS_KEYS = {
    "total_prompt_tokens",
    "total_completion_tokens",
    "total_cached_tokens",
    "total_cost_usd",
    "total_steps",
    "extra",
}
SUBAGENT_REF_KEYS = {"trajectory_id", "session_id", "trajectory_path", "extra"}
CONTENT_PART_KEYS = {"type", "text", "source"}
IMAGE_SOURCE_KEYS = {"media_type", "path"}
AUDIO_SOURCE_KEYS = {"media_type", "path", "duration_sec"}
IMAGE_MEDIA = {"image/jpeg", "image/png", "image/gif", "image/webp"}
AUDIO_MEDIA = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/aac",
    "audio/ogg",
    "audio/flac",
    "audio/webm",
    "audio/aiff",
}
ROLE_TO_SOURCE = {
    "user": "user",
    "human": "user",
    "assistant": "agent",
    "ai": "agent",
    "model": "agent",
    "system": "system",
    "developer": "system",
    "reasoning": "agent",
}
RESULT_ROLES = {"tool", "toolresult", "tool_result"}
TOKEN_FIELDS = ("input", "output", "cache_read", "cache_create", "total")
OMITTED_PAYLOADS = (
    "message",
    "reasoning_content",
    "tool_calls.arguments",
    "observation.results.content",
)


class AtifError(Exception):
    """Export failed against the canonical receipt or ATIF contract."""


def _ingest_module() -> Any:
    path = Path(__file__).resolve().parent / "ingest.py"
    existing = sys.modules.get("_session_eval_ingest")
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location("_session_eval_ingest", path)
    if spec is None or spec.loader is None:
        raise AtifError(f"cannot load ingest module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_session_eval_ingest"] = module
    spec.loader.exec_module(module)
    return module


def _write_immutable_json(path: Path, value: Any) -> Path:
    return _ingest_module()._write_immutable_json(path, value)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_official_schema() -> dict[str, Any]:
    if not OFFICIAL_SCHEMA_PATH.is_file():
        raise AtifError(f"pinned ATIF schema missing: {OFFICIAL_SCHEMA_PATH}")
    return json.loads(OFFICIAL_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_schema_provenance() -> dict[str, Any]:
    if not PROVENANCE_PATH.is_file():
        raise AtifError(f"ATIF schema provenance missing: {PROVENANCE_PATH}")
    return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))


def _is_unknown(value: Any) -> bool:
    return value is None or value == UNKNOWN or value == ""


def _known_string(value: Any) -> str | None:
    if _is_unknown(value) or isinstance(value, bool):
        return None
    if isinstance(value, str):
        return value
    return None


def _known_number(value: Any) -> int | float | None:
    if _is_unknown(value) or isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0:
        return int(value) if value.is_integer() else value
    return None


def _known_int(value: Any) -> int | None:
    number = _known_number(value)
    if isinstance(number, int):
        return number
    if isinstance(number, float) and number.is_integer():
        return int(number)
    return None


def _iso_timestamp(value: Any) -> str | None:
    text = _known_string(value)
    if text is None:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return text


def _role_key(value: Any) -> str:
    if not isinstance(value, str):
        return UNKNOWN
    return value.strip().casefold() or UNKNOWN


def _native_id(run: Mapping[str, Any]) -> str | None:
    identity = run.get("native_identity")
    if isinstance(identity, dict):
        return _known_string(identity.get("id"))
    return _known_string(identity)


def _source_key(turn: Mapping[str, Any]) -> tuple[str, int, str]:
    path = str(turn.get("source_path") or "")
    line = turn.get("source_line")
    number = line if isinstance(line, int) else 0
    return path, number, str(turn.get("id") or "")


def _redaction_extra(omitted: Sequence[str], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = extra or {}
    payload["redaction"] = {
        "policy": "default-local",
        "omitted": list(omitted),
    }
    return payload


def _lineage_extra(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _lineage_extra(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_lineage_extra(item) for item in value]
    return value


def _token_coverage(tokens: Mapping[str, Any] | None) -> dict[str, str]:
    mapping = tokens if isinstance(tokens, dict) else {}
    coverage: dict[str, str] = {}
    for field in TOKEN_FIELDS:
        coverage[field] = "unknown" if _known_number(mapping.get(field)) is None else "known"
    return coverage


def _harbor_prompt_total(tokens: Mapping[str, Any]) -> tuple[int | None, str]:
    """Harbor total_prompt_tokens is all prompt tokens, including cached.

    Normalized receipts keep input, cache_read, and cache_create separate.
    Emit a total only when every prompt-side component is known.  If a harness
    already reported an inclusive input (session total equals input+output while
    cache is a nonempty subset of input), do not add cache again.
    """

    prompt_input = _known_int(tokens.get("input"))
    cache_read = _known_int(tokens.get("cache_read"))
    cache_create = _known_int(tokens.get("cache_create"))
    if prompt_input is None or cache_read is None or cache_create is None:
        return None, "omitted_unknown_prompt_component"
    cached = cache_read + cache_create
    output = _known_int(tokens.get("output"))
    total = _known_int(tokens.get("total"))
    if (
        cached > 0
        and prompt_input >= cached
        and output is not None
        and total is not None
        and total == prompt_input + output
    ):
        return prompt_input, "inclusive_input"
    return prompt_input + cache_read + cache_create, "summed_components"


def _final_metrics(run: Mapping[str, Any], step_count: int) -> dict[str, Any] | None:
    tokens = run.get("tokens") if isinstance(run.get("tokens"), dict) else {}
    metrics: dict[str, Any] = {}
    prompt, prompt_basis = _harbor_prompt_total(tokens)
    completion = _known_int(tokens.get("output"))
    cached = _known_int(tokens.get("cache_read"))
    cost = _known_number(run.get("cost_usd"))
    if prompt is not None:
        metrics["total_prompt_tokens"] = prompt
    if completion is not None:
        metrics["total_completion_tokens"] = completion
    if cached is not None:
        metrics["total_cached_tokens"] = cached
    if cost is not None:
        metrics["total_cost_usd"] = float(cost)
    metrics["total_steps"] = step_count
    extra: dict[str, Any] = {
        "token_coverage": _token_coverage(tokens),
        "prompt_token_basis": prompt_basis,
    }
    created = _known_int(tokens.get("cache_create"))
    if created is not None:
        extra["cache_create_tokens"] = created
    total = _known_int(tokens.get("total"))
    if total is not None:
        extra["total_tokens"] = total
    observed_input = _known_int(tokens.get("input"))
    if observed_input is not None:
        extra["observed_input_tokens"] = observed_input
    metrics["extra"] = extra
    return metrics


def _tool_call_object(call: Mapping[str, Any]) -> dict[str, Any]:
    call_id = _known_string(call.get("id")) or UNKNOWN
    name = _known_string(call.get("name")) or UNKNOWN
    extra: dict[str, Any] = _redaction_extra(["arguments"])
    status = _known_string(call.get("status"))
    if status is not None:
        extra["pairing"] = status
    if not _is_unknown(call.get("source_path")):
        extra["source_path"] = str(call.get("source_path"))
    if isinstance(call.get("source_line"), int):
        extra["source_line"] = call["source_line"]
    if not _is_unknown(call.get("result_source_path")):
        extra["result_source_path"] = str(call.get("result_source_path"))
    if isinstance(call.get("result_source_line"), int):
        extra["result_source_line"] = call["result_source_line"]
    evidence = call.get("evidence")
    if isinstance(evidence, list) and evidence:
        extra["evidence"] = evidence
    return {
        "tool_call_id": call_id,
        "function_name": name,
        "arguments": {},
        "extra": extra,
    }


def _observation_for_calls(calls: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    results: list[dict[str, Any]] = []
    for call in calls:
        status = str(call.get("status") or "")
        if status not in {"ok", "error"}:
            continue
        extra: dict[str, Any] = _redaction_extra(["content"], {"status": status})
        if not _is_unknown(call.get("result_source_path")):
            extra["result_source_path"] = str(call.get("result_source_path"))
        if isinstance(call.get("result_source_line"), int):
            extra["result_source_line"] = call["result_source_line"]
        results.append(
            {
                "source_call_id": _known_string(call.get("id")) or UNKNOWN,
                "extra": extra,
            }
        )
    if not results:
        return None
    return {"results": results}


def _step_extra(
    turn: Mapping[str, Any],
    *,
    omitted: Sequence[str],
    observed_role: str,
    source: str,
    kind: str | None = None,
) -> dict[str, Any]:
    extra = _redaction_extra(omitted)
    extra["turn_id"] = turn.get("id")
    extra["source_path"] = turn.get("source_path")
    extra["source_line"] = turn.get("source_line")
    extra["observed_role"] = observed_role
    if kind is not None:
        extra["kind"] = kind
    elif observed_role == "reasoning" and source == "agent":
        extra["kind"] = "reasoning"
    lineage = turn.get("lineage")
    if isinstance(lineage, dict):
        extra["lineage"] = _lineage_extra(lineage)
    errors = turn.get("errors")
    if isinstance(errors, list) and errors:
        extra["errors"] = errors
    return extra


def _turns_in_order(run: Mapping[str, Any]) -> list[dict[str, Any]]:
    turns = run.get("turns")
    if not isinstance(turns, list):
        return []
    ordered = [item for item in turns if isinstance(item, dict)]
    ordered.sort(key=_source_key)
    return ordered


def _consumed_results(turns: Sequence[Mapping[str, Any]]) -> set[tuple[str, int]]:
    consumed: set[tuple[str, int]] = set()
    for turn in turns:
        for call in turn.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            path = call.get("result_source_path")
            line = call.get("result_source_line")
            if isinstance(path, str) and isinstance(line, int):
                consumed.add((path, line))
    return consumed


def _steps_from_run(run: Mapping[str, Any]) -> list[dict[str, Any]]:
    turns = _turns_in_order(run)
    consumed = _consumed_results(turns)
    steps: list[dict[str, Any]] = []
    for turn in turns:
        role = _role_key(turn.get("role"))
        path = str(turn.get("source_path") or "")
        line = turn.get("source_line") if isinstance(turn.get("source_line"), int) else None
        calls = [item for item in (turn.get("tool_calls") or []) if isinstance(item, dict)]
        if (
            not calls
            and line is not None
            and (path, line) in consumed
        ):
            continue
        source = ROLE_TO_SOURCE.get(role)
        kind = None
        if source is None and role in RESULT_ROLES:
            source = "system"
            kind = "unpaired_tool_result"
        if source is None:
            source = "system"
            kind = "unmapped_role"
        omitted = ["message"]
        if source == "agent":
            omitted = ["message", "reasoning_content"]
        step: dict[str, Any] = {
            "step_id": len(steps) + 1,
            "source": source,
            "message": REDACTED_MESSAGE,
            "extra": _step_extra(
                turn,
                omitted=omitted,
                observed_role=role,
                source=source,
                kind=kind,
            ),
        }
        if source == "agent" and calls:
            step["tool_calls"] = [_tool_call_object(call) for call in calls]
            observation = _observation_for_calls(calls)
            if observation is not None:
                step["observation"] = observation
        elif calls:
            # Non-agent turns must not carry ATIF agent-only tool_calls.
            step["extra"]["unexported_tool_calls"] = [
                {"id": call.get("id"), "name": call.get("name"), "status": call.get("status")}
                for call in calls
            ]
        steps.append(step)
    if not steps:
        steps.append(
            {
                "step_id": 1,
                "source": "system",
                "message": REDACTED_MESSAGE,
                "extra": _redaction_extra(
                    ["message"],
                    {"omission": "no_observed_turns"},
                ),
            }
        )
    return steps


def to_atif(run: Mapping[str, Any]) -> dict[str, Any]:
    """Convert one normalized run into a redacted ATIF-v1.8 document."""

    if not isinstance(run, Mapping):
        raise AtifError("run must be an object")
    run_id = _known_string(run.get("id"))
    harness = _known_string(run.get("harness"))
    parser = _known_string(run.get("parser"))
    parser_version = _known_string(run.get("parser_version"))
    if run_id is None or harness is None or parser is None or parser_version is None:
        raise AtifError("run is missing id, harness, parser, or parser_version")
    steps = _steps_from_run(run)
    native = run.get("native_identity")
    session_id = _native_id(run) or run_id
    agent: dict[str, Any] = {
        "name": harness,
        "version": parser_version,
        "extra": {
            "parser": parser,
            "parser_version": parser_version,
            "harness": harness,
        },
    }
    model = _known_string(run.get("model"))
    if model is not None:
        agent["model_name"] = model
    extra: dict[str, Any] = {
        "export": {
            "producer": PRODUCER,
            "producer_version": PRODUCER_VERSION,
            "schema_pin": {
                "spec": SCHEMA_VERSION,
                "commit": HARBOR_COMMIT,
                "rfc": HARBOR_RFC,
                "models": HARBOR_MODELS,
                "schema": str(OFFICIAL_SCHEMA_PATH),
            },
        },
        "redaction": {
            "policy": "default-local",
            "omitted": list(OMITTED_PAYLOADS),
        },
        "source": {
            "run_id": run_id,
            "harness": harness,
            "native_identity": native if native is not None else UNKNOWN,
            "display_name": run.get("display_name", UNKNOWN),
            "parser": parser,
            "parser_version": parser_version,
            "source_path": run.get("source_path"),
            "source_snapshot": run.get("source_snapshot"),
            "started_at": run.get("started_at", UNKNOWN),
            "ended_at": run.get("ended_at", UNKNOWN),
            "cwd": run.get("cwd", UNKNOWN),
            "lifecycle": run.get("lifecycle"),
            "usage_provenance": run.get("usage_provenance") or [],
            "skills": run.get("skills") or [],
        },
        "lineage": _lineage_extra(run.get("lineage") or UNKNOWN),
        "unknowns": {
            "tokens": _token_coverage(run.get("tokens") if isinstance(run.get("tokens"), dict) else {}),
            "cost_usd": "unknown" if _known_number(run.get("cost_usd")) is None else "known",
        },
    }
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "trajectory_id": run_id,
        "agent": agent,
        "steps": steps,
        "notes": (
            "Redacted session-eval ATIF export. Dialogue text, tool arguments, "
            "and observation content are omitted per SE-PRIVACY-001. Unknown "
            "usage and cost are omitted, never zeroed. One document per "
            f"normalized session against Harbor {SCHEMA_VERSION} at {HARBOR_COMMIT}."
        ),
        "final_metrics": _final_metrics(run, len(steps)),
        "extra": extra,
    }
    return document


def _unexpected_keys(value: Mapping[str, Any], allowed: set[str], path: str, errors: list[str]) -> None:
    extra = sorted(str(key) for key in value if key not in allowed)
    if extra:
        errors.append(f"{path}: unexpected properties {extra}")


def _require_type(value: Any, expected: type | tuple[type, ...], path: str, errors: list[str]) -> bool:
    if not isinstance(value, expected):
        errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
        return False
    return True


def _validate_content_part(part: Any, path: str, errors: list[str]) -> None:
    if not _require_type(part, dict, path, errors):
        return
    _unexpected_keys(part, CONTENT_PART_KEYS, path, errors)
    kind = part.get("type")
    if kind not in {"text", "image", "audio"}:
        errors.append(f"{path}.type: must be text, image, or audio")
        return
    if kind == "text":
        if "text" not in part or not isinstance(part.get("text"), str):
            errors.append(f"{path}.text: required string when type=text")
        if part.get("source") is not None:
            errors.append(f"{path}.source: not allowed when type=text")
        return
    source = part.get("source")
    if not isinstance(source, dict):
        errors.append(f"{path}.source: required object when type={kind}")
        return
    if part.get("text") is not None:
        errors.append(f"{path}.text: not allowed when type={kind}")
    if kind == "image":
        _unexpected_keys(source, IMAGE_SOURCE_KEYS, f"{path}.source", errors)
        if source.get("media_type") not in IMAGE_MEDIA or not isinstance(source.get("path"), str):
            errors.append(f"{path}.source: invalid image source")
    else:
        _unexpected_keys(source, AUDIO_SOURCE_KEYS, f"{path}.source", errors)
        if source.get("media_type") not in AUDIO_MEDIA or not isinstance(source.get("path"), str):
            errors.append(f"{path}.source: invalid audio source")


def _validate_message(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for index, part in enumerate(value):
            _validate_content_part(part, f"{path}[{index}]", errors)
        return
    errors.append(f"{path}: message must be a string or content-part array")


def _validate_metrics(value: Any, path: str, errors: list[str]) -> None:
    if value is None:
        return
    if not _require_type(value, dict, path, errors):
        return
    _unexpected_keys(value, METRICS_KEYS, path, errors)
    for key in ("prompt_tokens", "completion_tokens", "cached_tokens"):
        if key in value and not isinstance(value[key], int):
            errors.append(f"{path}.{key}: expected integer")
    if "cost_usd" in value and not isinstance(value["cost_usd"], (int, float)):
        errors.append(f"{path}.cost_usd: expected number")


def _validate_subagent_ref(value: Any, path: str, errors: list[str]) -> None:
    if not _require_type(value, dict, path, errors):
        return
    _unexpected_keys(value, SUBAGENT_REF_KEYS, path, errors)
    if value.get("trajectory_id") is None and value.get("trajectory_path") is None:
        errors.append(f"{path}: trajectory_id or trajectory_path is required")


def _validate_observation(value: Any, path: str, errors: list[str], tool_call_ids: set[str]) -> None:
    if value is None:
        return
    if not _require_type(value, dict, path, errors):
        return
    _unexpected_keys(value, OBSERVATION_KEYS, path, errors)
    results = value.get("results")
    if not isinstance(results, list):
        errors.append(f"{path}.results: required array")
        return
    for index, result in enumerate(results):
        result_path = f"{path}.results[{index}]"
        if not isinstance(result, dict):
            errors.append(f"{result_path}: expected object")
            continue
        _unexpected_keys(result, OBSERVATION_RESULT_KEYS, result_path, errors)
        call_id = result.get("source_call_id")
        if call_id is not None:
            if not isinstance(call_id, str):
                errors.append(f"{result_path}.source_call_id: expected string")
            elif call_id not in tool_call_ids:
                errors.append(
                    f"{result_path}.source_call_id {call_id!r} is not in this step's tool_calls"
                )
        content = result.get("content")
        if content is not None and not isinstance(content, (str, list)):
            errors.append(f"{result_path}.content: expected string or content-part array")
        if isinstance(content, list):
            for part_index, part in enumerate(content):
                _validate_content_part(part, f"{result_path}.content[{part_index}]", errors)
        refs = result.get("subagent_trajectory_ref")
        if refs is not None:
            if not isinstance(refs, list):
                errors.append(f"{result_path}.subagent_trajectory_ref: expected array")
            else:
                for ref_index, ref in enumerate(refs):
                    _validate_subagent_ref(ref, f"{result_path}.subagent_trajectory_ref[{ref_index}]", errors)


def _validate_step(step: Any, index: int, errors: list[str]) -> None:
    path = f"steps[{index}]"
    if not _require_type(step, dict, path, errors):
        return
    _unexpected_keys(step, STEP_KEYS, path, errors)
    if step.get("step_id") != index + 1:
        errors.append(f"{path}.step_id: expected {index + 1}, got {step.get('step_id')!r}")
    source = step.get("source")
    if source not in {"system", "user", "agent"}:
        errors.append(f"{path}.source: must be system, user, or agent")
    if "message" not in step:
        errors.append(f"{path}.message: required")
    else:
        _validate_message(step.get("message"), f"{path}.message", errors)
    if source != "agent":
        for field in AGENT_ONLY_FIELDS:
            if step.get(field) is not None:
                errors.append(f"{path}.{field}: only valid when source is agent")
    timestamp = step.get("timestamp")
    if timestamp is not None:
        if not isinstance(timestamp, str):
            errors.append(f"{path}.timestamp: expected string")
        else:
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{path}.timestamp: invalid ISO-8601 value")
    tool_call_ids: set[str] = set()
    tool_calls = step.get("tool_calls")
    if tool_calls is not None:
        if not isinstance(tool_calls, list):
            errors.append(f"{path}.tool_calls: expected array")
        else:
            for call_index, call in enumerate(tool_calls):
                call_path = f"{path}.tool_calls[{call_index}]"
                if not isinstance(call, dict):
                    errors.append(f"{call_path}: expected object")
                    continue
                _unexpected_keys(call, TOOL_CALL_KEYS, call_path, errors)
                if not isinstance(call.get("tool_call_id"), str):
                    errors.append(f"{call_path}.tool_call_id: required string")
                else:
                    tool_call_ids.add(call["tool_call_id"])
                if not isinstance(call.get("function_name"), str):
                    errors.append(f"{call_path}.function_name: required string")
                if not isinstance(call.get("arguments"), dict):
                    errors.append(f"{call_path}.arguments: required object")
    _validate_observation(step.get("observation"), f"{path}.observation", errors, tool_call_ids)
    _validate_metrics(step.get("metrics"), f"{path}.metrics", errors)
    if step.get("llm_call_count") == 0 and source == "agent":
        for field in ("metrics", "reasoning_content"):
            if step.get(field) is not None:
                errors.append(f"{path}.{field}: must be absent when llm_call_count is 0")


def _validate_agent(agent: Any, errors: list[str]) -> None:
    if not _require_type(agent, dict, "agent", errors):
        return
    _unexpected_keys(agent, AGENT_KEYS, "agent", errors)
    if not isinstance(agent.get("name"), str):
        errors.append("agent.name: required string")
    if not isinstance(agent.get("version"), str):
        errors.append("agent.version: required string")


def _validate_final_metrics(value: Any, errors: list[str]) -> None:
    if value is None:
        return
    if not _require_type(value, dict, "final_metrics", errors):
        return
    _unexpected_keys(value, FINAL_METRICS_KEYS, "final_metrics", errors)
    for key in ("total_prompt_tokens", "total_completion_tokens", "total_cached_tokens", "total_steps"):
        if key in value and not isinstance(value[key], int):
            errors.append(f"final_metrics.{key}: expected integer")
    if "total_cost_usd" in value and not isinstance(value["total_cost_usd"], (int, float)):
        errors.append("final_metrics.total_cost_usd: expected number")


def validate_atif(document: Mapping[str, Any]) -> list[str]:
    """Validate a document against the pinned ATIF-v1.8 model constraints.

    This encodes the official Harbor Pydantic rules (required fields, extra
    forbid, sequential step_ids, agent-only fields, and tool-call references).
    It does not assert producer-specific extra contents.
    """

    errors: list[str] = []
    if not isinstance(document, Mapping):
        return ["document: expected object"]
    _unexpected_keys(document, TRAJECTORY_KEYS, "$", errors)
    if document.get("schema_version") not in SCHEMA_VERSIONS:
        errors.append("schema_version: must be a documented ATIF version")
    _validate_agent(document.get("agent"), errors)
    steps = document.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps: required non-empty array")
    else:
        for index, step in enumerate(steps):
            _validate_step(step, index, errors)
    if "session_id" in document and document["session_id"] is not None and not isinstance(document["session_id"], str):
        errors.append("session_id: expected string")
    if "trajectory_id" in document and document["trajectory_id"] is not None and not isinstance(document["trajectory_id"], str):
        errors.append("trajectory_id: expected string")
    _validate_final_metrics(document.get("final_metrics"), errors)
    embedded = document.get("subagent_trajectories")
    if embedded is not None:
        if not isinstance(embedded, list):
            errors.append("subagent_trajectories: expected array")
        else:
            seen: set[str] = set()
            for index, child in enumerate(embedded):
                child_errors = validate_atif(child) if isinstance(child, Mapping) else [f"subagent_trajectories[{index}]: expected object"]
                errors.extend(f"subagent_trajectories[{index}].{item}" if not item.startswith("subagent_trajectories") else item for item in child_errors)
                if isinstance(child, Mapping):
                    trajectory_id = child.get("trajectory_id")
                    if not isinstance(trajectory_id, str) or not trajectory_id:
                        errors.append(f"subagent_trajectories[{index}].trajectory_id is required")
                    elif trajectory_id in seen:
                        errors.append(f"subagent_trajectories[{index}].trajectory_id {trajectory_id!r} is not unique")
                    else:
                        seen.add(trajectory_id)
    return errors


def validate_with_harbor(document: Mapping[str, Any], harbor_src: str | Path | None = None) -> list[str]:
    """Optionally validate with Harbor's pinned Pydantic Trajectory model."""

    root = Path(harbor_src) if harbor_src else None
    if root is None:
        env = os.environ.get("HARBOR_SRC")
        root = Path(env) if env else None
    if root is None:
        return ["harbor validation skipped: HARBOR_SRC not set"]
    src = root / "src" if (root / "src" / "harbor").is_dir() else root
    if not (src / "harbor" / "models" / "trajectories" / "trajectory.py").is_file():
        return [f"harbor models missing under {src}"]
    src_text = str(src)
    inserted = src_text not in sys.path
    if inserted:
        sys.path.insert(0, src_text)
    try:
        from harbor.models.trajectories.trajectory import Trajectory  # type: ignore

        Trajectory.model_validate(dict(document))
    except Exception as exc:
        return [str(exc)]
    finally:
        if inserted and sys.path and sys.path[0] == src_text:
            sys.path.pop(0)
    return []


def _runs_from_receipt(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(receipt, Mapping):
        raise AtifError("receipt must be an object")
    schema = receipt.get("schema")
    if schema not in (RECEIPT_SCHEMA, None) and "runs" not in receipt and "run" not in receipt:
        raise AtifError(f"unsupported receipt schema: {schema!r}")
    if "runs" in receipt:
        runs = receipt.get("runs")
        if not isinstance(runs, list):
            raise AtifError("receipt.runs must be an array")
        return [item for item in runs if isinstance(item, dict)]
    run = receipt.get("run")
    if isinstance(run, dict):
        return [run]
    raise AtifError("canonical receipt has no runs")


def load_receipt(path: str | Path) -> dict[str, Any]:
    receipt_path = Path(path)
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AtifError(f"cannot read receipt {receipt_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AtifError("receipt must be a JSON object")
    return payload


def _document_path(out: Path, run: Mapping[str, Any]) -> Path:
    run_id = str(run.get("id") or "run")
    snapshot = UNKNOWN
    source_snapshot = run.get("source_snapshot")
    if isinstance(source_snapshot, dict) and source_snapshot.get("sha256"):
        snapshot = str(source_snapshot["sha256"])
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", run_id)
    return out / "atif" / f"{slug}--{snapshot}.json"


def export_atif(receipt: Mapping[str, Any], out: str | Path) -> tuple[list[dict[str, Any]], Path]:
    """Write one redacted ATIF document per normalized run.

    Returns the documents and the immutable export manifest path.  Repeat
    export of the same receipt bytes reuses unchanged history files.
    """

    runs = _runs_from_receipt(receipt)
    out_path = Path(out)
    documents: list[dict[str, Any]] = []
    listings: list[dict[str, Any]] = []
    for run in runs:
        document = to_atif(run)
        errors = validate_atif(document)
        if errors:
            raise AtifError("ATIF document failed pinned schema validation: " + "; ".join(errors))
        target = _document_path(out_path, run)
        written = _write_immutable_json(target, document)
        documents.append(document)
        listings.append(
            {
                "run_id": run.get("id"),
                "harness": run.get("harness"),
                "native_identity": run.get("native_identity"),
                "source_path": run.get("source_path"),
                "source_snapshot": (run.get("source_snapshot") or {}).get("sha256")
                if isinstance(run.get("source_snapshot"), dict)
                else UNKNOWN,
                "path": str(written),
                "sha256": hashlib.sha256(_canonical(document).encode("utf-8")).hexdigest(),
            }
        )
    manifest = {
        "schema": EXPORT_MANIFEST_SCHEMA,
        "atif_schema_version": SCHEMA_VERSION,
        "harbor_commit": HARBOR_COMMIT,
        "receipt_schema": receipt.get("schema", RECEIPT_SCHEMA),
        "redaction": {"policy": "default-local", "applied": True},
        "documents": listings,
    }
    manifest_path = _write_immutable_json(out_path / "atif-manifest.json", manifest)
    return documents, manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval-atif",
        description="Export redacted ATIF-v1.8 documents from a canonical session-eval receipt.",
    )
    parser.add_argument("--receipt", required=True, help="path to styrir-session-eval/v0 receipt.json")
    parser.add_argument("--out", required=True, help="output directory for ATIF documents and manifest")
    parser.add_argument("--validate", action="store_true", help="validate written documents against the pinned ATIF-v1.8 constraints")
    parser.add_argument("--harbor-src", default=None, help="optional Harbor checkout root or src/ for official Pydantic validation")
    parser.add_argument("--pretty", action="store_true", help="pretty-print the command summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        receipt = load_receipt(args.receipt)
        documents, manifest_path = export_atif(receipt, args.out)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validation_errors: list[str] = []
        if args.validate or args.harbor_src:
            load_official_schema()
            load_schema_provenance()
            for index, document in enumerate(documents):
                validation_errors.extend(
                    f"document[{index}]: {item}" for item in validate_atif(document)
                )
                if args.harbor_src:
                    harbor_errors = validate_with_harbor(document, args.harbor_src)
                    validation_errors.extend(
                        f"document[{index}] harbor: {item}" for item in harbor_errors
                    )
            if validation_errors:
                raise AtifError("; ".join(validation_errors))
    except AtifError as exc:
        parser.error(str(exc))
        return 2
    summary = {
        "manifest": str(manifest_path),
        "documents": len(documents),
        "schema_version": SCHEMA_VERSION,
        "harbor_commit": HARBOR_COMMIT,
        "paths": [item.get("path") for item in manifest.get("documents", [])],
    }
    if args.pretty:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
