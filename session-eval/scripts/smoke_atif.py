#!/usr/bin/env python3
"""Ingest then export Claude and Grok synthetic sessions to pinned ATIF-v1.8.

This is an executable smoke scenario for SE-EXPORT-001.  It does not replace
Harbor's Pydantic models; it validates against the pinned independent schema
and official field/reference rules in ``atif.validate_atif``.  Optional
``HARBOR_SRC`` enables the upstream Trajectory model.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
INGEST = SCRIPTS / "ingest.py"
ATIF = SCRIPTS / "atif.py"
EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / ".styrir"
    / "runs"
    / "session-eval-implementation"
    / "skills-2ol.10"
)
SECRET = "SMOKE_SECRET_7f4c9e"
MARKUP = "<script>alert('smoke')</script>"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from atif import (  # noqa: E402
    HARBOR_COMMIT,
    SCHEMA_VERSION,
    load_official_schema,
    load_schema_provenance,
    to_atif,
    validate_atif,
    validate_with_harbor,
)


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


def run_cli(script: Path, args: list[str]) -> dict[str, Any]:
    command = [sys.executable, str(script), *args]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    stdout = completed.stdout.strip()
    if not stdout:
        raise AssertionError(f"{script.name} produced no stdout")
    return json.loads(stdout.splitlines()[-1])


def one_run(receipt: dict[str, Any], harness: str, native_id: str) -> dict[str, Any]:
    matches = []
    for run in receipt.get("runs", []):
        if run.get("harness") != harness:
            continue
        identity = run.get("native_identity")
        found = identity.get("id") if isinstance(identity, dict) else identity
        if found == native_id:
            matches.append(run)
    if len(matches) != 1:
        raise AssertionError(f"expected one {harness} run {native_id}, got {len(matches)}")
    return matches[0]


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_redacted(blob: str, label: str) -> None:
    if SECRET in blob:
        raise AssertionError(f"{label} leaked synthetic secret")
    if MARKUP in blob or "<script" in blob.lower():
        raise AssertionError(f"{label} leaked synthetic markup")


def assert_official(document: dict[str, Any], label: str) -> None:
    errors = validate_atif(document)
    if errors:
        raise AssertionError(f"{label} failed pinned ATIF constraints: {errors}")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise AssertionError(f"{label} schema_version is not {SCHEMA_VERSION}")
    steps = document["steps"]
    ids = [step["step_id"] for step in steps]
    if ids != list(range(1, len(steps) + 1)):
        raise AssertionError(f"{label} step_id chronology is {ids}")
    harbor_src = os.environ.get("HARBOR_SRC")
    if harbor_src:
        harbor_errors = validate_with_harbor(document, harbor_src)
        if harbor_errors:
            raise AssertionError(f"{label} failed Harbor Trajectory validation: {harbor_errors}")


def unknown_run() -> dict[str, Any]:
    lineage = {
        "parent": "unknown",
        "children": "unknown",
        "attempt": "unknown",
        "continuation_of": "unknown",
        "continued_by": "unknown",
    }
    return {
        "id": "claude:unknown-usage",
        "harness": "claude",
        "native_identity": {"id": "unknown-usage", "kind": "session_id", "source": "sessionId"},
        "display_name": "unknown-usage",
        "parser": "claude-jsonl-adapter",
        "parser_version": "1.0.0",
        "source_path": "/tmp/unknown-usage.jsonl",
        "source_snapshot": {
            "sha256": "abc",
            "files": [{"path": "/tmp/unknown-usage.jsonl", "role": "primary", "sha256": "def"}],
        },
        "started_at": "unknown",
        "ended_at": "unknown",
        "cwd": "unknown",
        "model": "unknown",
        "tokens": {
            "input": "unknown",
            "output": "unknown",
            "cache_read": "unknown",
            "cache_create": "unknown",
            "total": "unknown",
        },
        "cost_usd": "unknown",
        "usage_provenance": [],
        "skills": [],
        "lineage": lineage,
        "turns": [
            {
                "id": "t1",
                "role": "user",
                "tool_calls": [],
                "errors": [],
                "source_line": 1,
                "source_path": "/tmp/unknown-usage.jsonl",
                "lineage": lineage,
            }
        ],
        "checks": [],
        "lifecycle": {"state": "unknown", "evidence": []},
    }


def run_with_tokens(run_id: str, tokens: dict[str, Any], cost: Any = "unknown") -> dict[str, Any]:
    run = unknown_run()
    run["id"] = f"claude:{run_id}"
    run["native_identity"] = {"id": run_id, "kind": "session_id", "source": "sessionId"}
    run["display_name"] = run_id
    run["tokens"] = tokens
    run["cost_usd"] = cost
    return run


def assert_omitted_prompt_total(document: dict[str, Any], label: str) -> None:
    metrics = document.get("final_metrics") or {}
    if "total_prompt_tokens" in metrics:
        raise AssertionError(f"{label} exported total_prompt_tokens={metrics['total_prompt_tokens']!r} with unknown cache")
    if metrics.get("total_prompt_tokens") == 0:
        raise AssertionError(f"{label} zeroed unknown prompt total")
    basis = (metrics.get("extra") or {}).get("prompt_token_basis")
    if basis != "omitted_unknown_prompt_component":
        raise AssertionError(f"{label} prompt_token_basis {basis!r}")


def build_samples(root: Path) -> tuple[Path, Path, Path]:
    claude = root / "claude" / "session.jsonl"
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
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "claude-call-1",
                            "name": "Bash",
                            "input": {"secret": SECRET},
                        }
                    ],
                },
            },
            {
                "sessionId": "claude-1",
                "timestamp": "2026-09-13T10:00:01Z",
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "claude-call-1",
                            "is_error": False,
                            "content": MARKUP,
                        }
                    ],
                },
            },
            {
                "sessionId": "claude-1",
                "timestamp": "2026-09-13T10:00:02Z",
                "type": "result",
                "result": MARKUP,
                "total_cost_usd": 0.12,
            },
        ],
    )
    claude_cache = root / "claude-cache" / "session.jsonl"
    write_jsonl(
        claude_cache,
        [
            {
                "sessionId": "claude-cache",
                "timestamp": "2026-09-13T11:00:00Z",
                "cwd": str(root),
                "type": "assistant",
                "message": {
                    "id": "claude-cache-message",
                    "role": "assistant",
                    "model": "claude-test",
                    "usage": {
                        "input_tokens": 2,
                        "output_tokens": 3,
                        "cache_read_input_tokens": 5,
                        "cache_creation_input_tokens": 1,
                    },
                    "content": [{"type": "text", "text": "ok"}],
                },
            }
        ],
    )
    grok.mkdir(parents=True)
    write_jsonl(
        grok / "chat_history.jsonl",
        [
            {
                "type": "assistant",
                "id": "grok-message",
                "content": MARKUP,
                "tool_calls": [{"id": "grok-call", "name": "shell", "arguments": {"secret": SECRET}}],
            },
            {"type": "tool_result", "tool_call_id": "grok-call", "is_error": False, "content": SECRET},
        ],
    )
    write_jsonl(
        grok / "events.jsonl",
        [
            {
                "type": "turn_started",
                "ts": "2026-09-13T10:05:00Z",
                "params": {"sessionId": "grok-primary", "turnId": "grok-turn", "modelId": "grok-model"},
            },
            {"type": "heartbeat", "ts": 1726221900},
        ],
    )
    write_jsonl(
        grok / "updates.jsonl",
        [
            {
                "timestamp": 1726221901,
                "method": "session/update",
                "params": {
                    "sessionId": "grok-primary",
                    "update": {
                        "sessionUpdate": {
                            "type": "tool_call",
                            "toolCallId": "grok-update-call",
                            "title": "shell",
                            "turnId": "grok-turn",
                        }
                    },
                },
            },
            {
                "timestamp": 1726221902,
                "method": "session/update",
                "params": {
                    "sessionId": "grok-primary",
                    "update": {
                        "sessionUpdate": {
                            "type": "tool_call_update",
                            "toolCallId": "grok-update-call",
                            "status": "completed",
                            "turnId": "grok-turn",
                        }
                    },
                },
            },
            {
                "timestamp": 1726221903,
                "method": "session/update",
                "params": {
                    "sessionId": "grok-primary",
                    "update": {
                        "sessionUpdate": {
                            "type": "turn_completed",
                            "inputTokens": 5,
                            "outputTokens": 2,
                            "totalTokens": 7,
                            "turnId": "grok-turn",
                        }
                    },
                },
                "_meta": {"totalTokens": 30},
            },
        ],
    )
    write_json(
        grok / "summary.json",
        {
            "info": {
                "id": "grok-stale",
                "cwd": str(root),
                "current_model_id": "grok-stale-model",
                "created_at": "2026-09-13T10:05:00Z",
                "ended_at": "2026-09-13T10:05:03Z",
            },
            "session_summary": MARKUP,
        },
    )
    write_json(
        grok / "usage.json",
        {
            "sessionId": "grok-stale",
            "session": {"inputTokens": 999, "outputTokens": 999, "totalTokens": 999},
            "turns": [{"inputTokens": 999, "outputTokens": 999}],
        },
    )
    write_json(grok / "prompt_context.json", {"skills": [{"path": "demo/SKILL.md", "digest": "sha256:historical"}]})
    return claude, claude_cache, grok


def document_for_run(manifest: dict[str, Any], run_id: str) -> dict[str, Any]:
    listing = next(item for item in manifest["documents"] if item.get("run_id") == run_id)
    return load_json(listing["path"])


def main() -> int:
    schema = load_official_schema()
    provenance = load_schema_provenance()
    assert provenance["commit"] == HARBOR_COMMIT
    assert provenance["observed_spec"] == SCHEMA_VERSION
    assert schema["required"] == ["schema_version", "agent", "steps"]
    assert "ATIF-v1.8" in schema["properties"]["schema_version"]["enum"]

    unknown_doc = to_atif(unknown_run())
    assert_official(unknown_doc, "unknown-usage")
    metrics = unknown_doc.get("final_metrics") or {}
    for field in ("total_prompt_tokens", "total_completion_tokens", "total_cached_tokens", "total_cost_usd"):
        if field in metrics:
            raise AssertionError(f"unknown usage exported {field}={metrics[field]!r}")
    if metrics.get("total_steps") != 1:
        raise AssertionError("unknown-usage total_steps missing")
    coverage = (metrics.get("extra") or {}).get("token_coverage") or {}
    if set(coverage.values()) != {"unknown"}:
        raise AssertionError(f"unknown usage coverage was {coverage}")
    assert_redacted(_canonical_blob(unknown_doc), "unknown-usage")

    unknown_cache_doc = to_atif(
        run_with_tokens(
            "unknown-cache",
            {
                "input": 2,
                "output": 3,
                "cache_read": "unknown",
                "cache_create": "unknown",
                "total": 5,
            },
        )
    )
    assert_official(unknown_cache_doc, "unknown-cache")
    assert_omitted_prompt_total(unknown_cache_doc, "unknown-cache")
    unknown_cache_metrics = unknown_cache_doc.get("final_metrics") or {}
    if unknown_cache_metrics.get("total_completion_tokens") != 3:
        raise AssertionError("unknown-cache dropped known completion tokens")
    if "total_cached_tokens" in unknown_cache_metrics:
        raise AssertionError("unknown-cache invented cached tokens")
    if unknown_cache_metrics.get("extra", {}).get("observed_input_tokens") != 2:
        raise AssertionError("unknown-cache did not retain observed input separately")

    known_cache_doc = to_atif(
        run_with_tokens(
            "known-cache",
            {
                "input": 10,
                "output": 3,
                "cache_read": 4,
                "cache_create": 2,
                "total": 19,
            },
        )
    )
    assert_official(known_cache_doc, "known-cache")
    known_cache_metrics = known_cache_doc.get("final_metrics") or {}
    if known_cache_metrics.get("total_prompt_tokens") != 16:
        raise AssertionError(f"known-cache prompt total {known_cache_metrics.get('total_prompt_tokens')!r}")
    if known_cache_metrics.get("total_cached_tokens") != 4:
        raise AssertionError("known-cache missing cache hits")
    if known_cache_metrics.get("extra", {}).get("prompt_token_basis") != "summed_components":
        raise AssertionError("known-cache should sum disjoint prompt components")

    inclusive_doc = to_atif(
        run_with_tokens(
            "inclusive-cache",
            {
                "input": 16,
                "output": 3,
                "cache_read": 4,
                "cache_create": 2,
                "total": 19,
            },
        )
    )
    assert_official(inclusive_doc, "inclusive-cache")
    inclusive_metrics = inclusive_doc.get("final_metrics") or {}
    if inclusive_metrics.get("total_prompt_tokens") != 16:
        raise AssertionError(f"inclusive-cache double-counted cache: {inclusive_metrics.get('total_prompt_tokens')!r}")
    if inclusive_metrics.get("extra", {}).get("prompt_token_basis") != "inclusive_input":
        raise AssertionError("inclusive-cache should keep harness-inclusive input")

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="session-eval-atif-smoke-", dir=EVIDENCE) as temporary:
        root = Path(temporary)
        claude, claude_cache, grok = build_samples(root / "input")
        ingest_out = root / "ingest"
        atif_out = root / "atif"
        repeat_out = root / "atif-repeat"
        ingest_summary = run_cli(
            INGEST,
            [
                "--since",
                "all",
                "--out",
                str(ingest_out),
                "--harness",
                "claude",
                "--path",
                str(claude),
                "--harness",
                "claude",
                "--path",
                str(claude_cache),
                "--harness",
                "grok",
                "--path",
                str(grok),
            ],
        )
        receipt_path = Path(ingest_summary["receipt"])
        receipt = load_json(receipt_path)
        claude_run = one_run(receipt, "claude", "claude-1")
        cache_run = one_run(receipt, "claude", "claude-cache")
        grok_run = one_run(receipt, "grok", "grok-primary")
        assert_redacted(json.dumps(receipt, ensure_ascii=False), "receipt")

        atif_summary = run_cli(
            ATIF,
            ["--receipt", str(receipt_path), "--out", str(atif_out), "--validate"],
        )
        assert atif_summary["schema_version"] == SCHEMA_VERSION
        assert atif_summary["harbor_commit"] == HARBOR_COMMIT
        assert atif_summary["documents"] == 3
        manifest = load_json(atif_summary["manifest"])
        claude_doc = document_for_run(manifest, claude_run["id"])
        cache_doc = document_for_run(manifest, cache_run["id"])
        grok_doc = document_for_run(manifest, grok_run["id"])
        assert_official(claude_doc, "claude")
        assert_official(cache_doc, "claude-cache")
        assert_official(grok_doc, "grok")
        assert_redacted(json.dumps(claude_doc, ensure_ascii=False), "claude ATIF")
        assert_redacted(json.dumps(cache_doc, ensure_ascii=False), "claude-cache ATIF")
        assert_redacted(json.dumps(grok_doc, ensure_ascii=False), "grok ATIF")
        assert_redacted(Path(atif_summary["manifest"]).read_text(encoding="utf-8"), "manifest")

        if claude_doc["session_id"] != "claude-1":
            raise AssertionError(f"claude session_id {claude_doc['session_id']!r}")
        if claude_doc["trajectory_id"] != claude_run["id"]:
            raise AssertionError("claude trajectory_id does not match run.id")
        if claude_doc["agent"]["name"] != "claude" or claude_doc["agent"]["version"] != claude_run["parser_version"]:
            raise AssertionError("claude agent identity mismatch")
        if claude_doc["extra"]["source"]["native_identity"]["id"] != "claude-1":
            raise AssertionError("claude native identity not preserved")
        claude_calls = [
            call
            for step in claude_doc["steps"]
            for call in step.get("tool_calls") or []
        ]
        if not any(call["tool_call_id"] == "claude-call-1" for call in claude_calls):
            raise AssertionError("claude tool call identity missing")
        claude_obs = [
            result.get("source_call_id")
            for step in claude_doc["steps"]
            for result in (step.get("observation") or {}).get("results") or []
        ]
        if "claude-call-1" not in claude_obs:
            raise AssertionError("claude paired observation missing")
        if any(call.get("arguments") for call in claude_calls):
            raise AssertionError("claude tool arguments were not empty")
        claude_metrics = claude_doc.get("final_metrics") or {}
        if claude_run["tokens"].get("cache_read") != "unknown" or claude_run["tokens"].get("cache_create") != "unknown":
            raise AssertionError("claude-1 fixture must leave cache unknown")
        assert_omitted_prompt_total(claude_doc, "claude-1")
        if claude_metrics.get("total_completion_tokens") != 3:
            raise AssertionError(f"claude known completion missing: {claude_metrics}")
        if "total_cached_tokens" in claude_metrics:
            raise AssertionError("claude-1 invented cached tokens")
        if claude_metrics.get("total_cost_usd") != 0.12:
            raise AssertionError("claude known cost missing")
        cache_metrics = cache_doc.get("final_metrics") or {}
        if cache_run["tokens"].get("input") != 2 or cache_run["tokens"].get("cache_read") != 5 or cache_run["tokens"].get("cache_create") != 1:
            raise AssertionError(f"claude-cache ingest tokens {cache_run['tokens']}")
        if cache_metrics.get("total_prompt_tokens") != 8:
            raise AssertionError(f"claude-cache Harbor prompt total {cache_metrics.get('total_prompt_tokens')!r}")
        if cache_metrics.get("total_cached_tokens") != 5:
            raise AssertionError("claude-cache missing cache hits")
        if cache_metrics.get("total_completion_tokens") != 3:
            raise AssertionError("claude-cache missing completion")
        if cache_metrics.get("extra", {}).get("prompt_token_basis") != "summed_components":
            raise AssertionError("claude-cache should sum disjoint prompt components")

        if grok_doc["session_id"] != "grok-primary":
            raise AssertionError(f"grok session_id {grok_doc['session_id']!r}")
        if grok_doc["trajectory_id"] != grok_run["id"]:
            raise AssertionError("grok trajectory_id does not match run.id")
        if grok_doc["extra"]["source"]["native_identity"]["id"] != "grok-primary":
            raise AssertionError("grok native identity not preserved")
        grok_calls = [
            call
            for step in grok_doc["steps"]
            for call in step.get("tool_calls") or []
        ]
        grok_ids = {call["tool_call_id"] for call in grok_calls}
        if "grok-call" not in grok_ids:
            raise AssertionError(f"grok paired call missing: {grok_ids}")
        grok_obs = {
            result.get("source_call_id")
            for step in grok_doc["steps"]
            for result in (step.get("observation") or {}).get("results") or []
        }
        if "grok-call" not in grok_obs:
            raise AssertionError("grok paired observation missing")
        grok_metrics = grok_doc.get("final_metrics") or {}
        grok_extra = grok_metrics.get("extra") or {}
        if grok_run["tokens"]["total"] == "unknown":
            if "total_tokens" in grok_extra:
                raise AssertionError("grok unknown total became a metric")
        else:
            if grok_extra.get("total_tokens") != grok_run["tokens"]["total"]:
                raise AssertionError("grok known total tokens not preserved")
        grok_tokens = grok_run.get("tokens") or {}
        if any(grok_tokens.get(field) == "unknown" for field in ("input", "cache_read", "cache_create")):
            assert_omitted_prompt_total(grok_doc, "grok")
        if grok_tokens.get("output") == "unknown" and "total_completion_tokens" in grok_metrics:
            raise AssertionError("grok unknown output exported as completion")
        if grok_tokens.get("cache_read") == "unknown" and "total_cached_tokens" in grok_metrics:
            raise AssertionError("grok unknown cache_read exported as cached tokens")

        repeat = run_cli(
            ATIF,
            ["--receipt", str(receipt_path), "--out", str(repeat_out), "--validate"],
        )
        first_docs = {Path(path).name: Path(path).read_bytes() for path in atif_summary["paths"]}
        repeat_docs = {Path(path).name: Path(path).read_bytes() for path in repeat["paths"]}
        if first_docs.keys() != repeat_docs.keys():
            raise AssertionError("repeat export changed document set")
        for name, payload in first_docs.items():
            if payload != repeat_docs[name]:
                raise AssertionError(f"repeat export changed {name}")
        second = run_cli(
            ATIF,
            ["--receipt", str(receipt_path), "--out", str(atif_out), "--validate"],
        )
        if second["paths"] != atif_summary["paths"]:
            raise AssertionError("repeat export into the same out directory changed history paths")
        for path in second["paths"]:
            if Path(path).read_bytes() != first_docs[Path(path).name]:
                raise AssertionError(f"repeat export overwrote {path}")

        result = {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "harbor_commit": HARBOR_COMMIT,
            "receipt": str(receipt_path),
            "manifest": atif_summary["manifest"],
            "documents": atif_summary["paths"],
            "claude_session_id": claude_doc["session_id"],
            "grok_session_id": grok_doc["session_id"],
            "steps": {
                "claude": [step["step_id"] for step in claude_doc["steps"]],
                "claude_cache": [step["step_id"] for step in cache_doc["steps"]],
                "grok": [step["step_id"] for step in grok_doc["steps"]],
            },
        }
        write_json(EVIDENCE / "smoke-result.json", result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0


def _canonical_blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
