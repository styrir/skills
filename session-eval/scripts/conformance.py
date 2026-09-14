#!/usr/bin/env python3
"""End-to-end session-eval conformance runner (skills-2ol.9).

Generates a synthetic five-harness corpus, invokes the shared local CLI
pinned by the parallel-wave contract, and writes a requirement-by-requirement
evidence record under ``--out``. This script is execution machinery, not a
passing receipt. Parent integrates, runs this runner, and performs the
offline browser / authorized-judge observations this lane cannot claim.

Never invents a second CLI. Never requests or invokes unapproved providers.
Never treats absent judge proof as pass. Never greps HTML source as a
substitute for opening the real report offline.

Usage:
    python3 session-eval/scripts/conformance.py --out OUT [--cli PATH] [--judge-evidence RECEIPT]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

CANONICAL_REVISION = "31de9458f85e8ad9755fa8e9262a770f8c7c8a1c"
RECEIPT_SCHEMA = "styrir-session-eval/v0"
CATALOG_ID = "session-eval-check-catalog/v1"
HARNESSES = ("claude", "codex", "pi", "omp", "grok")
REQUIRED_IDS = (
    "SE-DOC-001",
    "SE-PORT-001",
    "SE-INGEST-001",
    "SE-INGEST-002",
    "SE-EVIDENCE-001",
    "SE-PRIVACY-001",
    "SE-USAGE-001",
    "SE-CHECK-001",
    "SE-CHECK-002",
    "SE-JUDGE-001",
    "SE-SKILL-001",
    "SE-TREND-001",
    "SE-REPORT-001",
    "SE-CORRECT-001",
    "SE-VERIFY-001",
)
OPTIONAL_IDS = ("SE-WORKGRAPH-001", "SE-EXPORT-001")
REQUIRED_HTML_IDS = (
    "verdict",
    "coverage",
    "trends",
    "skills",
    "sessions",
    "failures",
    "comparisons",
    "recommendations",
    "provenance",
    "footer",
)
SECRET_TOKEN = "CONFORMANCE_SECRET_7f4c9e2b"
MARKUP_TOKEN = "<script>alert('conformance')</script>"
SK_TOKEN = "sk-conformanceAAAAAAAAAAAAAAAA"
WORKGRAPH_BIN = Path("/Users/brooks/Code/agent-ops/bin/workgraph-eval-score")
WORKGRAPH_EVIDENCE = Path("/Users/brooks/Code/agent-ops/tests/workgraph-eval/fixtures/red-baseline")
WORKGRAPH_MANIFEST = Path("/Users/brooks/Code/agent-ops/tests/workgraph-eval/fixtures/acceptance-manifest.json")
WORKGRAPH_ALLOWLIST = Path("/Users/brooks/Code/agent-ops/tests/workgraph-eval/fixtures/mutation-allowlist.json")
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parent

# Finding snapshot_hash is the aggregate run.source_snapshot.sha256
# (root-contract-decision). File bytes belong only on source_snapshot.files[].sha256.


class ConformanceError(Exception):
    """Expected local-input error suitable for a concise CLI message."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_json(path: Path, value: Any, *, pretty: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        payload = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    else:
        payload = _canonical(value) + "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_jsonl(path: Path, rows: list[Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if isinstance(row, str):
                handle.write(row)
                if not row.endswith("\n"):
                    handle.write("\n")
            else:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _git_revision(root: Path) -> dict[str, Any]:
    recorded = {"canonical": CANONICAL_REVISION, "worktree": None, "error": None}
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        recorded["error"] = str(exc)
        return recorded
    if completed.returncode != 0:
        recorded["error"] = (completed.stderr or completed.stdout or "git rev-parse failed").strip()
        return recorded
    recorded["worktree"] = (completed.stdout or "").strip() or None
    return recorded


def default_cli_path() -> Path:
    return SCRIPT_DIR / "session_eval.py"


# ---------------------------------------------------------------------------
# Synthetic corpus
# ---------------------------------------------------------------------------


def omp_session(session_id: str, rows: list[Any], *, cwd: str | None = None) -> list[Any]:
    header: dict[str, Any] = {
        "type": "session",
        "version": 3,
        "id": session_id,
        "timestamp": "2026-09-13T10:00:00Z",
    }
    if cwd is not None:
        header["cwd"] = cwd
    return [header, *rows]


def tool_call(
    call_id: str,
    name: str,
    arguments: dict[str, Any],
    *,
    parent_id: str | None = None,
    child_id: str | None = None,
    attempt: dict[str, Any] | None = None,
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
    if parent_id is not None:
        row["parentId"] = parent_id
    if child_id is not None:
        row["childId"] = child_id
    if attempt is not None:
        row["attempt"] = attempt
    if timestamp is not None:
        row["timestamp"] = timestamp
    return row


def tool_result(
    call_id: str,
    is_error: bool,
    content: Any,
    *,
    parent_id: str | None = None,
    child_id: str | None = None,
    attempt: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "type": "message",
        "id": f"res-{call_id}",
        "message": {"role": "toolResult", "toolCallId": call_id, "isError": is_error, "content": content},
    }
    if parent_id is not None:
        row["parentId"] = parent_id
    if child_id is not None:
        row["childId"] = child_id
    if attempt is not None:
        row["attempt"] = attempt
    if timestamp is not None:
        row["timestamp"] = timestamp
    return row


def assistant_text(turn_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": turn_id,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def user_text(turn_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": turn_id,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def session_end() -> dict[str, Any]:
    return {"type": "custom", "customType": "session_end", "timestamp": "2026-09-13T10:09:00Z"}


def session_live() -> dict[str, Any]:
    return {"type": "custom", "customType": "live", "timestamp": "2026-09-13T10:09:00Z"}


def write_skill(path: Path, name: str, version: str, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\nversion: {version}\n---\n\n{body}\n", encoding="utf-8")
    return path


def write_grok_session(
    path: Path,
    session_id: str,
    *,
    skill_entries: list[dict[str, Any]] | None = None,
    mention_paths: list[str] | None = None,
    unpaired: bool = False,
    title: str | None = None,
    ended: bool = True,
    cwd: str | None = None,
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    chat: list[Any] = [{"type": "user", "id": f"{session_id}-u1", "content": "do the work"}]
    if mention_paths:
        chat.append(
            {
                "type": "assistant",
                "id": f"{session_id}-mention",
                "content": "consider " + " ".join(mention_paths),
            }
        )
    if unpaired:
        chat.append(
            {
                "type": "assistant",
                "id": f"{session_id}-tool",
                "content": "working",
                "tool_calls": [{"id": f"{session_id}-call", "name": "shell", "arguments": {"command": "status"}}],
            }
        )
    else:
        chat.append(
            {
                "type": "assistant",
                "id": f"{session_id}-tool",
                "content": "ok",
                "tool_calls": [{"id": f"{session_id}-call", "name": "shell", "arguments": {"command": "true"}}],
            }
        )
        chat.append({"type": "tool_result", "tool_call_id": f"{session_id}-call", "is_error": False, "content": "ok"})
    write_jsonl(path / "chat_history.jsonl", chat)
    write_jsonl(
        path / "events.jsonl",
        [
            {
                "type": "turn_started",
                "ts": "2026-09-13T10:05:00Z",
                "params": {"sessionId": session_id, "turnId": f"{session_id}-turn", "modelId": "grok-model"},
            }
        ],
    )
    write_jsonl(path / "updates.jsonl", [])
    info: dict[str, Any] = {
        "id": session_id,
        "cwd": cwd or str(path.parent),
        "current_model_id": "grok-model",
        "created_at": "2026-09-13T10:05:00Z",
    }
    if ended:
        info["ended_at"] = "2026-09-13T10:09:00Z"
    if title is not None:
        info["title"] = title
    _write_json(path / "summary.json", {"info": info})
    if skill_entries:
        _write_json(path / "prompt_context.json", {"skills": skill_entries})
    return path


def generate_corpus(root: Path) -> dict[str, Any]:
    """Write a durable synthetic corpus under ``root``. Returns a path index."""

    corpus = root / "corpus"
    if corpus.exists():
        shutil.rmtree(corpus)
    corpus.mkdir(parents=True)

    cwd = str(corpus)
    index: dict[str, Any] = {"root": str(corpus), "cases": {}}

    # --- five-harness normal (plus unknown-schema + malformed lines) ---
    five = corpus / "five-harness"
    claude = five / "claude" / "session.jsonl"
    write_jsonl(
        claude,
        [
            {
                "sessionId": "claude-1",
                "timestamp": "2026-09-13T10:00:00Z",
                "cwd": cwd,
                "type": "assistant",
                "title": f"normal {MARKUP_TOKEN}",
                "future_schema": {"note": "unknown-field-retained-privately"},
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
                            "input": {"command": "true", "api_key": SECRET_TOKEN},
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
                            "content": MARKUP_TOKEN,
                        }
                    ],
                },
            },
            {
                "sessionId": "claude-1",
                "timestamp": "2026-09-13T10:00:02Z",
                "type": "result",
                "result": "ok",
                "total_cost_usd": 0.12,
            },
            "{malformed-claude",
        ],
    )
    codex = five / "codex" / "rollout-001.jsonl"
    write_jsonl(
        codex,
        [
            {
                "timestamp": "2026-09-13T10:01:00Z",
                "ordinal": 1,
                "type": "session_meta",
                "payload": {
                    "session_id": "codex-1",
                    "cwd": cwd,
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
                "payload": {
                    "type": "custom_tool_call",
                    "id": "codex-item",
                    "call_id": "codex-call",
                    "name": "shell",
                    "parentId": "parent-turn",
                    "input": {"command": "true"},
                },
            },
            {
                "timestamp": "2026-09-13T10:01:03Z",
                "ordinal": 4,
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": "codex-call",
                    "is_error": False,
                    "output": "ok",
                },
            },
            {
                "timestamp": "2026-09-13T10:01:04Z",
                "ordinal": 5,
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {"total_token_usage": {"input_tokens": 10, "output_tokens": 4}},
                },
            },
            {
                "timestamp": "2026-09-13T10:01:05Z",
                "ordinal": 6,
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {"total_token_usage": {"input_tokens": 10, "output_tokens": 4}},
                },
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
    pi = five / "pi" / "session.jsonl"
    write_jsonl(
        pi,
        [
            {"type": "session", "version": 3, "id": "pi-1", "timestamp": "2026-09-13T10:02:00Z", "cwd": cwd},
            {"type": "model_change", "provider": "test", "modelId": "pi-model"},
            {
                "type": "message",
                "id": "pi-message",
                "timestamp": "2026-09-13T10:02:01Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "toolCall", "id": "pi-call", "name": "read", "arguments": {"path": "README.md"}}],
                },
            },
            {
                "type": "message",
                "id": "pi-result",
                "timestamp": "2026-09-13T10:02:02Z",
                "message": {"role": "toolResult", "toolCallId": "pi-call", "isError": False, "content": "ok"},
            },
        ],
    )
    omp_ended = five / "omp" / "ended.jsonl"
    write_jsonl(
        omp_ended,
        omp_session(
            "omp-ended",
            [
                {
                    "type": "custom",
                    "customType": "tool_execution_start",
                    "data": {"toolCallId": "omp-call", "toolName": "shell", "args": {"command": "true"}},
                },
                tool_call("omp-call", "shell", {"command": "true"}),
                tool_result("omp-call", False, "ok"),
                session_end(),
            ],
            cwd=cwd,
        ),
    )
    omp_unpaired = five / "omp" / "unpaired.jsonl"
    write_jsonl(
        omp_unpaired,
        omp_session(
            "omp-unpaired",
            [tool_call("omp-unpaired-call", "shell", {"command": "true"}), session_end()],
            cwd=cwd,
        ),
    )
    omp_live = five / "omp" / "live.jsonl"
    write_jsonl(
        omp_live,
        omp_session(
            "omp-live",
            [tool_call("omp-live-call", "shell", {"command": "true"}), session_live()],
            cwd=cwd,
        ),
    )
    grok = five / "grok" / "session-1"
    grok.mkdir(parents=True)
    write_jsonl(
        grok / "chat_history.jsonl",
        [
            {
                "type": "assistant",
                "id": "grok-message",
                "content": "ok",
                "tool_calls": [{"id": "grok-call", "name": "shell", "arguments": {"command": "true"}}],
            },
            {"type": "tool_result", "tool_call_id": "grok-call", "is_error": False, "content": "ok"},
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
    (grok / "summary.json").write_text(
        json.dumps(
            {
                "info": {
                    "id": "grok-primary",
                    "cwd": cwd,
                    "current_model_id": "grok-model",
                    "created_at": "2026-09-13T10:05:00Z",
                    "ended_at": "2026-09-13T10:05:03Z",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (grok / "usage.json").write_text(
        json.dumps(
            {
                "sessionId": "grok-primary",
                "session": {"inputTokens": 5, "outputTokens": 2, "totalTokens": 7},
                "turns": [{"inputTokens": 5, "outputTokens": 2}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    skill_v1 = corpus / "skills" / "v1" / "demo" / "SKILL.md"
    skill_v2 = corpus / "skills" / "v2" / "demo" / "SKILL.md"
    write_skill(skill_v1, "demo", "1.0.0", "Historical loaded body.")
    write_skill(skill_v2, "demo", "2.0.0", "Edited current body. Mention pairing.")
    (grok / "prompt_context.json").write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "path": str(skill_v1),
                        "digest": sha256_file(skill_v1),
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    index["cases"]["five_harness"] = {
        "paths": [str(five / "claude"), str(five / "codex"), str(five / "pi"), str(five / "omp"), str(grok)],
        "harnesses": list(HARNESSES),
        "skill_roots": [str(corpus / "skills" / "v2")],
        "first_party_root": str(corpus / "skills" / "v2"),
    }

    # --- empty ---
    empty = corpus / "empty"
    empty.mkdir()
    index["cases"]["empty"] = {"paths": [str(empty)], "harnesses": ["omp"]}

    # --- malformed-only ---
    malformed = corpus / "malformed" / "omp" / "broken.jsonl"
    write_jsonl(
        malformed,
        omp_session(
            "malformed-1",
            [assistant_text("malformed-ok", "hello"), "{not-json", session_end()],
            cwd=cwd,
        ),
    )
    index["cases"]["malformed"] = {"paths": [str(malformed)], "harnesses": ["omp"]}

    # --- nested agents ---
    nested = corpus / "nested" / "omp" / "nested.jsonl"
    nested_args = {"command": "ls /tmp", "nonce": "same"}
    nested_error = {"exit_code": 1, "output": "same-error"}
    nested_rows: list[Any] = [
        {"type": "agent_start", "id": "agent-a", "parentId": "omp-nested", "timestamp": "2026-09-13T10:06:00Z"},
        {"type": "agent_start", "id": "agent-b", "parentId": "omp-nested", "timestamp": "2026-09-13T10:06:01Z"},
    ]
    for index_n in range(3):
        call_id = f"nested-a-{index_n}"
        nested_rows.append(tool_call(call_id, "shell", nested_args, parent_id="agent-a"))
        nested_rows.append(tool_result(call_id, True, nested_error, parent_id="agent-a"))
    nested_rows.append(tool_call("nested-b-0", "shell", nested_args, parent_id="agent-b"))
    nested_rows.append(tool_result("nested-b-0", True, nested_error, parent_id="agent-b"))
    nested_rows.append(session_end())
    write_jsonl(nested, omp_session("omp-nested", nested_rows, cwd=cwd))
    index["cases"]["nested"] = {"paths": [str(nested)], "harnesses": ["omp"]}

    # --- ended unpaired vs live unpaired ---
    ended_unpaired = corpus / "ended-unpaired" / "omp" / "ended.jsonl"
    write_jsonl(
        ended_unpaired,
        omp_session(
            "ended-unpaired",
            [tool_call("ended-call", "shell", {"command": "ls"}), session_end()],
            cwd=cwd,
        ),
    )
    live_unpaired = corpus / "live-unpaired" / "omp" / "live.jsonl"
    write_jsonl(
        live_unpaired,
        omp_session(
            "live-unpaired",
            [tool_call("live-call", "shell", {"command": "ls"}), session_live()],
            cwd=cwd,
        ),
    )
    eof_unpaired = corpus / "eof-unpaired" / "omp" / "eof.jsonl"
    write_jsonl(
        eof_unpaired,
        omp_session(
            "eof-unpaired",
            [tool_call("eof-call", "shell", {"command": "ls"})],
            cwd=cwd,
        ),
    )
    index["cases"]["ended_unpaired"] = {"paths": [str(ended_unpaired)], "harnesses": ["omp"]}
    index["cases"]["live_unpaired"] = {"paths": [str(live_unpaired)], "harnesses": ["omp"]}
    index["cases"]["eof_unpaired"] = {"paths": [str(eof_unpaired)], "harnesses": ["omp"]}

    # --- usage absent (Pi) and repeated aggregate (Codex already has this; dedicated stream) ---
    usage_absent = corpus / "usage-absent" / "pi" / "session.jsonl"
    write_jsonl(
        usage_absent,
        [
            {"type": "session", "version": 3, "id": "pi-usage-absent", "timestamp": "2026-09-13T10:02:00Z", "cwd": cwd},
            assistant_text("pi-u", "no usage fields"),
            session_end(),
        ],
    )
    index["cases"]["usage_absent"] = {"paths": [str(usage_absent)], "harnesses": ["pi"]}

    # --- secret / markup ---
    secret = corpus / "secret-markup" / "claude" / "session.jsonl"
    write_jsonl(
        secret,
        [
            {
                "sessionId": "claude-secret",
                "timestamp": "2026-09-13T10:00:00Z",
                "cwd": cwd,
                "type": "assistant",
                "title": MARKUP_TOKEN,
                "message": {
                    "id": "secret-msg",
                    "role": "assistant",
                    "model": "claude-test",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "secret-call",
                            "name": "Bash",
                            "input": {"command": "echo", "password": SECRET_TOKEN, "token": SK_TOKEN},
                        }
                    ],
                },
            },
            {
                "sessionId": "claude-secret",
                "timestamp": "2026-09-13T10:00:01Z",
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "secret-call",
                            "is_error": False,
                            "content": f"leaked {SECRET_TOKEN} {MARKUP_TOKEN}",
                        }
                    ],
                },
            },
            {
                "sessionId": "claude-secret",
                "timestamp": "2026-09-13T10:00:02Z",
                "type": "result",
                "result": SECRET_TOKEN,
                "total_cost_usd": 0.01,
            },
        ],
    )
    index["cases"]["secret_markup"] = {"paths": [str(secret)], "harnesses": ["claude"]}

    # --- skill unchanged / edited / mention / missing ---
    v1_digest = sha256_file(skill_v1)
    v2_digest = sha256_file(skill_v2)
    skill_v1_root = str(corpus / "skills" / "v1")
    skill_v2_root = str(corpus / "skills" / "v2")
    unchanged_session = write_grok_session(
        corpus / "skill-unchanged" / "grok" / "session",
        "skill-unchanged",
        skill_entries=[{"path": str(skill_v1), "digest": v1_digest}],
        title="unchanged demo",
        cwd=cwd,
    )
    index["cases"]["skill_unchanged"] = {
        "paths": [str(unchanged_session)],
        "harnesses": ["grok"],
        "skill_roots": [skill_v1_root],
        "first_party_root": skill_v1_root,
    }
    edited_session = write_grok_session(
        corpus / "skill-edited" / "grok" / "session",
        "skill-edited",
        skill_entries=[{"path": str(skill_v2), "digest": v1_digest}],
        title="edited demo",
        cwd=cwd,
    )
    index["cases"]["skill_edited"] = {
        "paths": [str(edited_session)],
        "harnesses": ["grok"],
        "skill_roots": [skill_v2_root],
        "first_party_root": skill_v2_root,
    }
    mention_session = write_grok_session(
        corpus / "skill-mention" / "grok" / "session",
        "skill-mention",
        mention_paths=[str(skill_v2)],
        title="mention demo",
        cwd=cwd,
    )
    index["cases"]["skill_mention"] = {
        "paths": [str(mention_session)],
        "harnesses": ["grok"],
        "skill_roots": [skill_v2_root],
        "first_party_root": skill_v2_root,
    }
    missing_path = str(corpus / "skills" / "missing" / "gone" / "SKILL.md")
    missing_digest = sha256_bytes(b"conformance-missing-historical-digest")
    missing_session = write_grok_session(
        corpus / "skill-missing" / "grok" / "session",
        "skill-missing",
        skill_entries=[{"path": missing_path, "digest": missing_digest}],
        title="missing demo",
        cwd=cwd,
    )
    index["cases"]["skill_missing"] = {
        "paths": [str(missing_session)],
        "harnesses": ["grok"],
        "skill_roots": [skill_v2_root],
        "first_party_root": skill_v2_root,
    }

    # --- checks: loop, ordinary error, contradict, completion unknown ---
    loop_fail = corpus / "loop-fail" / "omp" / "loop.jsonl"
    loop_rows: list[Any] = []
    for index_n in range(4):
        call_id = f"loop-{index_n}"
        loop_rows.append(tool_call(call_id, "shell", {"command": "ls /tmp", "nonce": "same"}))
        loop_rows.append(tool_result(call_id, True, {"exit_code": 1, "output": "retry"}))
    loop_rows.append(session_end())
    write_jsonl(loop_fail, omp_session("loop-fail", loop_rows, cwd=cwd))
    index["cases"]["loop_fail"] = {"paths": [str(loop_fail)], "harnesses": ["omp"]}

    ordinary = corpus / "ordinary-error" / "omp" / "ordinary.jsonl"
    write_jsonl(
        ordinary,
        omp_session(
            "ordinary-error",
            [
                tool_call("err-1", "shell", {"command": "ls /missing"}),
                tool_result("err-1", True, {"exit_code": 1, "output": "missing"}),
                session_end(),
            ],
            cwd=cwd,
        ),
    )
    index["cases"]["ordinary_error"] = {"paths": [str(ordinary)], "harnesses": ["omp"]}

    contradict = corpus / "claim-contradict" / "omp" / "contradict.jsonl"
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
            cwd=cwd,
        ),
    )
    index["cases"]["claim_contradict"] = {"paths": [str(contradict)], "harnesses": ["omp"]}

    completion = corpus / "claim-completion" / "omp" / "complete.jsonl"
    write_jsonl(
        completion,
        omp_session(
            "completion-unknown",
            [assistant_text("done-1", "The task is complete."), session_end()],
            cwd=cwd,
        ),
    )
    index["cases"]["claim_completion"] = {"paths": [str(completion)], "harnesses": ["omp"]}

    recurring = corpus / "recurring-unpaired"
    recurring_paths: list[str] = []
    for n in range(3):
        session_dir = write_grok_session(
            recurring / f"run-{n}",
            f"recurring-{n}",
            skill_entries=[{"path": str(skill_v2), "digest": v2_digest}],
            unpaired=True,
            title=f"recurring {n}",
            cwd=cwd,
        )
        recurring_paths.append(str(session_dir))
    index["cases"]["recurring_unpaired"] = {
        "paths": recurring_paths,
        "harnesses": ["grok"],
        "skill_roots": [skill_v2_root],
        "first_party_root": skill_v2_root,
    }

    # --- missing requested harness ---
    index["cases"]["missing_harness"] = {
        "paths": [str(pi)],
        "harnesses": ["claude", "pi"],
    }

    # --- change-history: copy of claude for mutation after first ingest ---
    change_src = corpus / "change-history" / "claude" / "session.jsonl"
    shutil.copytree(five / "claude", change_src.parent, dirs_exist_ok=True)
    index["cases"]["change_history"] = {"paths": [str(change_src.parent)], "harnesses": ["claude"]}

    index["skills"] = {"v1": str(skill_v1), "v2": str(skill_v2)}
    index["immutable_sources"] = [str(skill_v1), str(skill_v2)]
    index["workgraph"] = {
        "evidence": str(WORKGRAPH_EVIDENCE),
        "manifest": str(WORKGRAPH_MANIFEST),
        "allowlist": str(WORKGRAPH_ALLOWLIST),
        "bin": str(WORKGRAPH_BIN),
        "present": {
            "evidence": WORKGRAPH_EVIDENCE.is_dir(),
            "manifest": WORKGRAPH_MANIFEST.is_file(),
            "allowlist": WORKGRAPH_ALLOWLIST.is_file(),
            "bin": WORKGRAPH_BIN.is_file(),
        },
    }
    _write_json(corpus / "index.json", index)
    return index


# ---------------------------------------------------------------------------
# Shared CLI invocation
# ---------------------------------------------------------------------------


def build_cli_command(
    cli: Path,
    *,
    paths: Sequence[str],
    harnesses: Sequence[str],
    out: Path,
    skill_roots: Sequence[str] | None = None,
    first_party_root: str | None = None,
    history_root: str | None = None,
    baseline: str | None = None,
    atif: bool = False,
    workgraph: Mapping[str, str] | None = None,
) -> list[str]:
    command = [sys.executable, str(cli), "--since", "all", "--out", str(out)]
    for path in paths:
        command.extend(["--path", path])
    for harness in harnesses:
        command.extend(["--harness", harness])
    for root in skill_roots or []:
        command.extend(["--skill-root", root])
    if first_party_root:
        command.extend(["--first-party-root", first_party_root])
    if history_root:
        command.extend(["--history-root", history_root])
    if baseline:
        command.extend(["--baseline", baseline])
    if atif:
        command.append("--atif")
    if workgraph:
        command.extend(
            [
                "--workgraph",
                workgraph["evidence"],
                "--workgraph-manifest",
                workgraph["manifest"],
                "--workgraph-allowlist",
                workgraph["allowlist"],
                "--workgraph-bin",
                workgraph["bin"],
            ]
        )
    return command


def invoke_shared_cli(command: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    """Run the pinned shared CLI. Never injects judge/provider flags."""

    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("JUDGE")}
    env["SESSION_EVAL_CONFORMANCE"] = "1"
    started = _now()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "started_at": started,
            "ended_at": _now(),
            "stdout_json": None,
            "error": f"shared CLI execution failed: {exc}",
            "missing_implementation": True,
        }
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    parsed: Any = None
    parse_error = None
    text = stdout.strip()
    if text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            for line in reversed(text.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        parsed = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
            if parsed is None:
                parse_error = "shared CLI stdout was not JSON"
    result = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "started_at": started,
        "ended_at": _now(),
        "stdout_json": parsed if isinstance(parsed, dict) else None,
        "error": parse_error,
        "missing_implementation": completed.returncode == 127
        or "No such file" in stderr
        or "not found" in stderr.lower()
        or "missing implementation" in (stdout + stderr).lower(),
    }
    if completed.returncode != 0 and result["error"] is None:
        result["error"] = (stderr or stdout or f"exit {completed.returncode}").strip()[:500]
    return result


def load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def resolve_cli_artifact(invocation: dict[str, Any], key: str, out: Path) -> Path | None:
    payload = invocation.get("stdout_json") if isinstance(invocation.get("stdout_json"), dict) else {}
    raw = payload.get(key) if isinstance(payload, dict) else None
    if isinstance(raw, str) and raw:
        candidate = Path(raw)
        if candidate.is_file():
            return candidate
    fallback = out / ("receipt.json" if key == "receipt" else "report.html")
    if fallback.is_file():
        return fallback
    return None


def file_identity(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": None, "exists": False, "sha256": None, "bytes": None}
    exists = path.is_file()
    return {
        "path": str(path),
        "exists": exists,
        "sha256": sha256_file(path) if exists else None,
        "bytes": path.stat().st_size if exists else None,
    }


def walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


def public_contains(value: Any, token: str) -> bool:
    for text in walk_strings(value):
        if token in text:
            return True
    return False


def html_contains(path: Path | None, token: str) -> bool:
    if path is None or not path.is_file():
        return False
    try:
        return token in path.read_text(encoding="utf-8")
    except OSError:
        return False


def html_has_id(path: Path | None, element_id: str) -> bool:
    if path is None or not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    needle = f'id="{element_id}"'
    alt = f"id='{element_id}'"
    return needle in text or alt in text


def runs_for(receipt: dict[str, Any] | None, harness: str | None = None) -> list[dict[str, Any]]:
    if not receipt:
        return []
    runs = [item for item in (receipt.get("runs") or []) if isinstance(item, dict)]
    if harness is None:
        return runs
    return [item for item in runs if item.get("harness") == harness]


def one_run(receipt: dict[str, Any] | None, harness: str, native: str | None = None) -> dict[str, Any] | None:
    candidates = runs_for(receipt, harness)
    if native is not None:
        matched = []
        for run in candidates:
            identity = run.get("native_identity")
            if identity == native:
                matched.append(run)
            elif isinstance(identity, dict) and identity.get("id") == native:
                matched.append(run)
        candidates = matched
    return candidates[0] if candidates else None


def native_id(run: dict[str, Any] | None) -> str | None:
    if not run:
        return None
    identity = run.get("native_identity")
    if isinstance(identity, dict):
        value = identity.get("id")
        return str(value) if value not in (None, "", "unknown") else None
    if isinstance(identity, str) and identity not in ("", "unknown"):
        return identity
    return None


def snapshot_hash(run: dict[str, Any] | None) -> str | None:
    if not run:
        return None
    snapshot = run.get("source_snapshot")
    if isinstance(snapshot, dict):
        value = snapshot.get("sha256")
        return str(value) if value not in (None, "", "unknown") else None
    return None


def check_row(run: dict[str, Any] | None, check_id: str) -> dict[str, Any] | None:
    if not run:
        return None
    for item in run.get("checks") or []:
        if isinstance(item, dict) and item.get("id") == check_id:
            return item
    return None


def rollup_row(receipt: dict[str, Any] | None, check_id: str) -> dict[str, Any] | None:
    if not receipt:
        return None
    for item in receipt.get("checks") or []:
        if isinstance(item, dict) and item.get("id") == check_id:
            return item
    return None


def finding_snapshot_ok(run: dict[str, Any] | None) -> tuple[bool, list[str], int]:
    """Root contract: finding evidence.snapshot_hash is aggregate run.source_snapshot.sha256.

    Missing/unknown snapshot_hash fails. Binding snapshot_hash to files[].sha256 fails
    unless that file hash is identical to the aggregate (then it is the aggregate).
    Runs with no evidence items are not a pass by themselves; the caller requires a
    positive evidence count across exercised scenarios.
    """

    if not run:
        return False, ["no run"], 0
    expected = snapshot_hash(run)
    if not expected:
        return False, ["run.source_snapshot.sha256 missing"], 0
    snapshot = run.get("source_snapshot") if isinstance(run.get("source_snapshot"), dict) else {}
    file_hashes = {
        str(item.get("sha256"))
        for item in (snapshot.get("files") or [])
        if isinstance(item, dict) and item.get("sha256") not in (None, "", "unknown")
    }
    problems: list[str] = []
    evidence_count = 0
    for check in run.get("checks") or []:
        if not isinstance(check, dict):
            continue
        for item in check.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            evidence_count += 1
            check_id = check.get("id")
            observed = item.get("snapshot_hash")
            if observed in (None, "", "unknown"):
                problems.append(f"{check_id}: evidence.snapshot_hash missing")
                continue
            observed_s = str(observed)
            if observed_s != expected:
                if observed_s in file_hashes:
                    problems.append(
                        f"{check_id}: evidence.snapshot_hash={observed_s} is files[].sha256, not aggregate {expected}"
                    )
                else:
                    problems.append(f"{check_id}: evidence.snapshot_hash={observed_s} != aggregate {expected}")
    return (not problems), problems, evidence_count


def native_sid(run: dict[str, Any] | None) -> str | None:
    if not run:
        return None
    ident = run.get("native_identity")
    if isinstance(ident, dict):
        value = ident.get("id")
        return str(value) if value not in (None, "") else None
    return str(ident) if ident not in (None, "") else None


def compact_run_by_native(
    scenario: Mapping[str, Any], native: str, harness: str | None = None
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for item in scenario.get("runs") or []:
        if not isinstance(item, dict):
            continue
        if harness is not None and item.get("harness") != harness:
            continue
        if native_sid(item) == native:
            matches.append(item)
    return matches[0] if len(matches) == 1 else None


def scenario_finding_gate(scenario: Mapping[str, Any]) -> tuple[bool, int]:
    runs = [item for item in (scenario.get("runs") or []) if isinstance(item, dict)]
    if not runs:
        return False, 0
    ok = all(item.get("finding_snapshot_hash_ok") is True for item in runs)
    count = sum(int(item.get("evidence_count") or 0) for item in runs)
    return ok, count


def token_unknown(run: dict[str, Any] | None, field: str) -> bool:
    if not run:
        return False
    tokens = run.get("tokens")
    if not isinstance(tokens, dict):
        return True
    value = tokens.get(field)
    return value in (None, "unknown")


def token_zero(run: dict[str, Any] | None, field: str) -> bool:
    if not run:
        return False
    tokens = run.get("tokens")
    if not isinstance(tokens, dict):
        return False
    return tokens.get(field) == 0


def status_of(check: dict[str, Any] | None) -> str | None:
    if not check:
        return None
    value = check.get("status")
    return str(value) if value is not None else None


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------


def run_scenario(
    name: str,
    cli: Path,
    out_root: Path,
    case: Mapping[str, Any],
    *,
    atif: bool = False,
    workgraph: Mapping[str, str] | None = None,
    history_root: Path | None = None,
    baseline: str | None = None,
    extra_env_note: str | None = None,
) -> dict[str, Any]:
    dest = out_root / "runs" / name
    dest.mkdir(parents=True, exist_ok=True)
    command = build_cli_command(
        cli,
        paths=list(case.get("paths") or []),
        harnesses=list(case.get("harnesses") or HARNESSES),
        out=dest,
        skill_roots=list(case.get("skill_roots") or []),
        first_party_root=case.get("first_party_root"),
        history_root=str(history_root) if history_root is not None else None,
        baseline=baseline,
        atif=atif,
        workgraph=workgraph,
    )
    invocation = invoke_shared_cli(command, cwd=REPO_ROOT)
    receipt_path = resolve_cli_artifact(invocation, "receipt", dest)
    report_path = resolve_cli_artifact(invocation, "report", dest)
    receipt = load_json(receipt_path)
    input_files = []
    for raw in case.get("paths") or []:
        path = Path(raw)
        if path.is_file():
            input_files.append(file_identity(path))
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file():
                    input_files.append(file_identity(child))
    record = {
        "name": name,
        "command": command,
        "invocation": {
            "returncode": invocation.get("returncode"),
            "error": invocation.get("error"),
            "missing_implementation": invocation.get("missing_implementation"),
            "started_at": invocation.get("started_at"),
            "ended_at": invocation.get("ended_at"),
            "stdout_sha256": sha256_text(str(invocation.get("stdout") or "")),
            "stderr_sha256": sha256_text(str(invocation.get("stderr") or "")),
            "stdout_json": invocation.get("stdout_json"),
        },
        "note": extra_env_note,
        "inputs": input_files,
        "out": str(dest),
        "receipt": file_identity(receipt_path),
        "report": file_identity(report_path),
        "receipt_schema": None if receipt is None else receipt.get("schema"),
        "hard_pass": None if receipt is None else receipt.get("hard_pass"),
        "infra_ok": None if receipt is None else receipt.get("infra_ok"),
        "coverage": None if receipt is None else receipt.get("coverage"),
        "harnesses_requested": None if receipt is None else receipt.get("harnesses_requested"),
        "harnesses_found": None if receipt is None else receipt.get("harnesses_found"),
        "parse_errors": None if receipt is None else receipt.get("parse_errors"),
        "catalog_id": None if receipt is None else receipt.get("catalog_id"),
        "recommendations_count": None if receipt is None else len(receipt.get("recommendations") or []),
        "comparisons_count": None if receipt is None else len(receipt.get("comparisons") or []),
        "approvals_count": None if receipt is None else len(receipt.get("approvals") or []),
        "provider_calls": None
        if receipt is None
        else (receipt.get("provenance") or {}).get("provider_calls"),
        "workgraph_invoked": None
        if receipt is None
        else (receipt.get("provenance") or {}).get("workgraph_invoked")
        or ((receipt.get("provenance") or {}).get("workgraph") or {}).get("invoked"),
        "secret_in_receipt": public_contains(receipt, SECRET_TOKEN) if receipt else None,
        "secret_in_report": html_contains(report_path, SECRET_TOKEN),
        "sk_in_receipt": public_contains(receipt, SK_TOKEN) if receipt else None,
        "sk_in_report": html_contains(report_path, SK_TOKEN),
        "markup_in_receipt": public_contains(receipt, MARKUP_TOKEN) if receipt else None,
        "markup_unescaped_in_report": html_contains(report_path, MARKUP_TOKEN),
        "html_ids": {element_id: html_has_id(report_path, element_id) for element_id in REQUIRED_HTML_IDS},
        "runs": [],
        "atif": None,
        "history": None,
    }
    if receipt is not None:
        for run in runs_for(receipt):
            ok, problems, evidence_count = finding_snapshot_ok(run)
            snapshot = run.get("source_snapshot") if isinstance(run.get("source_snapshot"), dict) else {}
            record["runs"].append(
                {
                    "id": run.get("id"),
                    "harness": run.get("harness"),
                    "native_identity": run.get("native_identity"),
                    "display_name": run.get("display_name"),
                    "parser": run.get("parser"),
                    "parser_version": run.get("parser_version"),
                    "lifecycle": (run.get("lifecycle") or {}).get("state")
                    if isinstance(run.get("lifecycle"), dict)
                    else None,
                    "snapshot_sha256": snapshot_hash(run),
                    "file_sha256s": [
                        str(item.get("sha256"))
                        for item in (snapshot.get("files") or [])
                        if isinstance(item, dict) and item.get("sha256") not in (None, "", "unknown")
                    ],
                    "tokens": run.get("tokens"),
                    "cost_usd": run.get("cost_usd"),
                    "lineage": run.get("lineage"),
                    "skills": run.get("skills"),
                    "checks": [
                        {
                            "id": item.get("id"),
                            "status": item.get("status"),
                            "class": item.get("class"),
                            "kind": item.get("kind"),
                            "channel": item.get("channel"),
                            "observed": item.get("observed"),
                        }
                        for item in (run.get("checks") or [])
                        if isinstance(item, dict)
                    ],
                    "evidence_count": evidence_count,
                    "finding_snapshot_hash_ok": ok,
                    "finding_snapshot_hash_problems": problems,
                }
            )
        atif_dir = dest / "atif"
        atif_manifest = dest / "atif-manifest.json"
        if atif_manifest.is_file() or atif_dir.is_dir():
            documents = []
            if atif_dir.is_dir():
                for child in sorted(atif_dir.glob("*.json")):
                    documents.append(file_identity(child))
            record["atif"] = {
                "manifest": file_identity(atif_manifest if atif_manifest.is_file() else None),
                "documents": documents,
                "secret_in_atif": any(
                    public_contains(load_json(Path(item["path"])), SECRET_TOKEN)
                    for item in documents
                    if item.get("path")
                ),
            }
        history_dir = Path(history_root) if history_root is not None else dest / "history"
        if history_dir.is_dir():
            entries = [file_identity(child) for child in sorted(history_dir.glob("*.json")) if child.is_file()]
            record["history"] = {"root": str(history_dir), "entries": entries, "count": len(entries)}
        record["skills"] = receipt.get("skills")
        record["recommendations"] = [
            {
                "id": item.get("id"),
                "target": item.get("target"),
                "action": item.get("action"),
                "rationale": item.get("rationale"),
                "verification": item.get("verification"),
                "evidence": item.get("evidence"),
                "limitation": item.get("limitation"),
                "confidence": item.get("confidence"),
            }
            for item in (receipt.get("recommendations") or [])
            if isinstance(item, dict)
        ]
        record["comparisons"] = receipt.get("comparisons")
        record["proof_gaps"] = receipt.get("proof_gaps")
        record["redaction"] = receipt.get("redaction")
        provenance = receipt.get("provenance") if isinstance(receipt.get("provenance"), dict) else {}
        record["provenance_workgraph"] = provenance.get("workgraph")
        record["private_snapshots"] = (dest / ".private" / "snapshots").is_dir()
    _write_json(dest / "scenario.json", {k: v for k, v in record.items() if k != "recommendations"})
    # Keep invocation stderr/stdout hashes only in scenario.json; raw streams stay on disk.
    _write_text(dest / "stdout.txt", str(invocation.get("stdout") or ""))
    _write_text(dest / "stderr.txt", str(invocation.get("stderr") or ""))
    return record


def mutate_change_history(corpus: Mapping[str, Any]) -> None:
    target = Path(corpus["cases"]["change_history"]["paths"][0]) / "session.jsonl"
    if not target.is_file():
        return
    text = target.read_text(encoding="utf-8")
    target.write_text(text.replace('"claude-1"', '"claude-1"') + '{"sessionId":"claude-1","type":"assistant","message":{"role":"assistant","content":[]}}\n', encoding="utf-8")


def inspect_judge_evidence(path: Path | None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": str(path) if path is not None else None,
        "present": False,
        "schema": None,
        "approvals": [],
        "judge_rows": [],
        "provider_calls": None,
        "pass_claimed": False,
        "status": "unknown",
        "limitation": "No --judge-evidence supplied. Opt-in judge execution remains unknown/blocked; never pass.",
    }
    if path is None:
        return record
    payload = load_json(path)
    if payload is None:
        record["limitation"] = f"judge evidence path is unreadable: {path}"
        record["status"] = "unknown"
        return record
    record["present"] = True
    record["schema"] = payload.get("schema")
    record["approvals"] = payload.get("approvals") or []
    record["provider_calls"] = (payload.get("provenance") or {}).get("provider_calls")
    rows = []
    for run in runs_for(payload):
        for item in run.get("checks") or []:
            if isinstance(item, dict) and str(item.get("id") or "").startswith("judge."):
                rows.append(
                    {
                        "run_id": run.get("id"),
                        "id": item.get("id"),
                        "status": item.get("status"),
                        "kind": item.get("kind"),
                        "observed": item.get("observed"),
                        "error": item.get("error"),
                        "approval_id": (item.get("judge") or {}).get("approval_id")
                        if isinstance(item.get("judge"), dict)
                        else None,
                    }
                )
    record["judge_rows"] = rows
    granted = [
        item
        for item in record["approvals"]
        if isinstance(item, dict) and item.get("granted") is True
    ]
    decided = [item for item in rows if item.get("status") in {"pass", "fail"}]
    if not granted:
        record["status"] = "unknown"
        record["limitation"] = (
            "Judge evidence present but no granted approval object. Status remains unknown; never pass."
        )
        return record
    if not decided:
        record["status"] = "unknown"
        record["limitation"] = (
            "Granted approval recorded but no decided judge.pass/fail rows. Missing-evidence/provider-error stays unknown."
        )
        return record
    record["pass_claimed"] = any(item.get("status") == "pass" for item in decided)
    record["status"] = "observed"
    record["limitation"] = (
        "Separately produced approved judge evidence accepted as observation only. "
        "This runner did not invoke a provider."
    )
    return record


# ---------------------------------------------------------------------------
# Requirement evaluation
# ---------------------------------------------------------------------------


UNKNOWN_DIGESTS = {None, "", "unknown"}


def _skill_rows(scenario: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [item for item in (scenario.get("skills") or []) if isinstance(item, dict)]


def _skill_with_kind(scenario: Mapping[str, Any], kind: str, name: str | None = None) -> dict[str, Any] | None:
    for item in _skill_rows(scenario):
        if item.get("activation_kind") == kind and (name is None or item.get("name") == name):
            return item
    return None


def _missing_skill_row(scenario: Mapping[str, Any]) -> dict[str, Any] | None:
    for item in _skill_rows(scenario):
        if item.get("missing") is True:
            return item
    return None


def _is_actionable(row: Mapping[str, Any]) -> bool:
    target = row.get("target")
    evidence = row.get("evidence")
    return (
        row.get("limitation") in (None, "")
        and isinstance(target, dict)
        and bool(target.get("path"))
        and bool(row.get("action"))
        and bool(row.get("rationale"))
        and bool(row.get("verification"))
        and isinstance(evidence, list)
        and len(evidence) > 0
    )


def _result(req_id: str, expected: str, observed: str, status: str, *, scenarios: list[str], limits: list[str], parent: str | None = None) -> dict[str, Any]:
    return {
        "id": req_id,
        "expected": expected,
        "observed": observed,
        "status": status,
        "scenarios": scenarios,
        "limitations": limits,
        "parent_observation": parent,
    }


def evaluate_requirements(
    *,
    scenarios: Mapping[str, dict[str, Any]],
    cli: Path,
    revision: Mapping[str, Any],
    judge: Mapping[str, Any],
    docs_ok: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    five = scenarios.get("five_harness") or {}
    empty = scenarios.get("empty") or {}
    malformed = scenarios.get("malformed") or {}
    nested = scenarios.get("nested") or {}
    ended = scenarios.get("ended_unpaired") or {}
    live = scenarios.get("live_unpaired") or {}
    eof = scenarios.get("eof_unpaired") or {}
    usage = scenarios.get("usage_absent") or {}
    secret = scenarios.get("secret_markup") or {}
    mention = scenarios.get("skill_mention") or {}
    missing_skill = scenarios.get("skill_missing") or {}
    unchanged_skill = scenarios.get("skill_unchanged") or {}
    edited_skill = scenarios.get("skill_edited") or {}
    loop = scenarios.get("loop_fail") or {}
    ordinary = scenarios.get("ordinary_error") or {}
    contradict = scenarios.get("claim_contradict") or {}
    completion = scenarios.get("claim_completion") or {}
    recurring = scenarios.get("recurring_unpaired") or {}
    missing_h = scenarios.get("missing_harness") or {}
    repeat = scenarios.get("repeat_ingest") or {}
    changed = scenarios.get("changed_ingest") or {}
    atif = scenarios.get("atif_export") or {}
    workgraph = scenarios.get("workgraph") or {}
    trend = scenarios.get("trend_revisions") or {}

    cli_exists = cli.is_file()
    any_missing = any(
        (item.get("invocation") or {}).get("missing_implementation") for item in scenarios.values()
    )
    any_receipt = any((item.get("receipt") or {}).get("exists") for item in scenarios.values())

    # SE-DOC-001
    rows.append(
        _result(
            "SE-DOC-001",
            "Indexed canonical store with source dossiers, decisions, stable IDs and task links; conflicting instructions block.",
            docs_ok.get("observed") or "documentation walk not recorded",
            "pass" if docs_ok.get("ok") else "fail",
            scenarios=["docs_walk"],
            limits=list(docs_ok.get("limits") or []),
            parent="Fresh-reader walk of conflicting-instruction blocking is a human review; runner only checks ID/link presence.",
        )
    )

    # SE-PORT-001
    port_status = "fail"
    port_obs = f"cli_exists={cli_exists} any_receipt={any_receipt} missing_implementation={any_missing}"
    if not cli_exists:
        port_status = "fail"
        port_obs = f"shared CLI missing at {cli}; missing implementation dependency failed explicitly"
    elif any_missing and not any_receipt:
        port_status = "fail"
    elif any_receipt:
        port_status = "pass"
    rows.append(
        _result(
            "SE-PORT-001",
            "Skill + shared CLI usable without OMP native workflow or Grok server; missing dependencies fail explicitly.",
            port_obs,
            port_status,
            scenarios=["five_harness", "empty", "malformed"],
            limits=["Pi-derived formats are feature-detected by ingest, not by this runner inventing a second parser."],
        )
    )

    # SE-INGEST-001
    found = five.get("harnesses_found") or []
    ingest_limits = []
    ingest_status = "fail"
    if not five.get("receipt", {}).get("exists"):
        ingest_status = "not_evaluated"
        ingest_limits.append("five_harness produced no receipt")
    else:
        have = set(found)
        missing = [name for name in HARNESSES if name not in have]
        parse_errors = five.get("parse_errors") or 0
        malformed_ok = (malformed.get("parse_errors") or 0) > 0 or (
            (malformed.get("coverage") or {}).get("sessions_malformed") or 0
        ) > 0
        if missing:
            ingest_limits.append("missing harnesses in five_harness: " + ", ".join(missing))
        if parse_errors <= 0:
            ingest_limits.append("five_harness parse_errors was not > 0 despite malformed lines")
        if missing_h.get("receipt", {}).get("exists"):
            missing_inputs = (missing_h.get("coverage") or {}).get("missing_requested_inputs") or []
            if not missing_inputs:
                ingest_limits.append("requested missing harness did not appear as coverage gap")
        if not missing and parse_errors > 0 and malformed_ok:
            ingest_status = "pass"
        elif five.get("receipt", {}).get("exists"):
            ingest_status = "fail"
    rows.append(
        _result(
            "SE-INGEST-001",
            "Discover/normalize Claude/Codex/Pi/OMP/Grok; missing requested harness is a coverage gap; malformed counted; unknown fields private.",
            f"harnesses_found={found} parse_errors={five.get('parse_errors')} malformed_parse={malformed.get('parse_errors')}",
            ingest_status,
            scenarios=["five_harness", "malformed", "missing_harness"],
            limits=ingest_limits,
        )
    )

    # SE-INGEST-002
    ended_state = None
    live_state = None
    eof_state = None
    ended_unpaired = None
    live_unpaired = None
    eof_unpaired = None
    lineage = None
    if ended.get("runs"):
        ended_state = ended["runs"][0].get("lifecycle")
        ended_unpaired = next((c.get("status") for c in ended["runs"][0].get("checks") or [] if c.get("id") == "tool.unpaired"), None)
    if live.get("runs"):
        live_state = live["runs"][0].get("lifecycle")
        live_unpaired = next((c.get("status") for c in live["runs"][0].get("checks") or [] if c.get("id") == "tool.unpaired"), None)
    if eof.get("runs"):
        eof_state = eof["runs"][0].get("lifecycle")
        eof_unpaired = next((c.get("status") for c in eof["runs"][0].get("checks") or [] if c.get("id") == "tool.unpaired"), None)
    if nested.get("runs"):
        lineage = nested["runs"][0].get("lineage")
    ingest2_ok = (
        ended_state == "terminal"
        and ended_unpaired == "fail"
        and live_state == "live"
        and live_unpaired in {"not_applicable", None}
        and eof_state in {"unknown", "live"}
        and eof_unpaired != "fail"
    )
    rows.append(
        _result(
            "SE-INGEST-002",
            "Preserve order, pairing, observed lineage; ended unpaired fails; live/EOF unpaired is not terminal-inferred.",
            f"ended={ended_state}/{ended_unpaired} live={live_state}/{live_unpaired} eof={eof_state}/{eof_unpaired} lineage={lineage}",
            "pass" if ingest2_ok else ("not_evaluated" if not ended.get("receipt", {}).get("exists") else "fail"),
            scenarios=["ended_unpaired", "live_unpaired", "eof_unpaired", "nested", "five_harness"],
            limits=["Runner does not invent lineage; observed parent/child must come from ingest."],
        )
    )

    # SE-EVIDENCE-001
    first_snaps = [item.get("snapshot_sha256") for item in (five.get("runs") or [])]
    repeat_snaps = [item.get("snapshot_sha256") for item in (repeat.get("runs") or [])]
    first_receipt = (five.get("receipt") or {}).get("sha256")
    repeat_receipt = (repeat.get("receipt") or {}).get("sha256")
    changed_receipt = (changed.get("receipt") or {}).get("sha256")
    five_find_ok, five_ev = scenario_finding_gate(five)
    ended_find_ok, ended_ev = scenario_finding_gate(ended)
    recur_find_ok, recur_ev = scenario_finding_gate(recurring)
    evidence_n = five_ev + ended_ev + recur_ev
    finding_ok = five_find_ok and ended_find_ok and recur_find_ok and evidence_n >= 1
    same_snap = bool(first_snaps) and first_snaps == repeat_snaps
    first_claude = compact_run_by_native(five, "claude-1", "claude")
    changed_claude = compact_run_by_native(changed, "claude-1", "claude")
    first_claude_snap = None if first_claude is None else first_claude.get("snapshot_sha256")
    changed_claude_snap = None if changed_claude is None else changed_claude.get("snapshot_sha256")
    new_snap = bool(first_claude_snap and changed_claude_snap and first_claude_snap != changed_claude_snap)
    former_kept = bool((five.get("receipt") or {}).get("exists"))
    history_kept = False
    if changed.get("history") and (changed["history"].get("count") or 0) >= 1:
        history_kept = True
    if repeat.get("history") and (repeat["history"].get("count") or 0) >= 1:
        history_kept = True
    evidence_status = (
        "pass"
        if finding_ok and same_snap and new_snap and former_kept
        else ("not_evaluated" if not (five.get("receipt") or {}).get("exists") else "fail")
    )
    rows.append(
        _result(
            "SE-EVIDENCE-001",
            "Findings identify source path, aggregate snapshot hash, parser version, range, evidence hash. Repeat ingest retains snapshot; changed bytes cannot overwrite former receipt.",
            (
                f"same_snap={same_snap} new_snap={new_snap} finding_snapshot_ok={finding_ok} "
                f"evidence_n={evidence_n} first_claude={first_claude_snap} changed_claude={changed_claude_snap} "
                f"first_receipt={first_receipt} repeat_receipt={repeat_receipt} changed_receipt={changed_receipt} "
                f"former_kept={former_kept} history_kept={history_kept}"
            ),
            evidence_status,
            scenarios=["five_harness", "repeat_ingest", "changed_ingest", "ended_unpaired", "recurring_unpaired"],
            limits=[
                "evidence.snapshot_hash must equal run.source_snapshot.sha256 (aggregate). File bytes hash only files[].sha256.",
                "changed_ingest new snapshot is native claude-1 vs five_harness claude-1, not a different-length run list.",
                "Receipt hash of a different corpus is not a substitute for a new snapshot.",
            ],
        )
    )

    # SE-PRIVACY-001
    leaked = any(
        [
            secret.get("secret_in_receipt"),
            secret.get("secret_in_report"),
            secret.get("sk_in_receipt"),
            secret.get("sk_in_report"),
            five.get("secret_in_receipt"),
            five.get("secret_in_report"),
        ]
    )
    markup_exec = secret.get("markup_unescaped_in_report")
    privacy_status = "pass"
    if not secret.get("receipt", {}).get("exists"):
        privacy_status = "not_evaluated"
    elif leaked or markup_exec:
        privacy_status = "fail"
    rows.append(
        _result(
            "SE-PRIVACY-001",
            "No raw prompts/tool payloads/secrets/terminal output in exported receipts/HTML; markup escaped; provider approval binds snapshot pairs.",
            f"secret_leaked={leaked} markup_unescaped={markup_exec} judge_provider_calls_in_default={five.get('provider_calls')}",
            privacy_status,
            scenarios=["secret_markup", "five_harness"],
            limits=[
                "Public evidence report omits raw secret tokens.",
                "Provider approval binding is observed via --judge-evidence only; this runner never grants approval.",
            ],
        )
    )

    # SE-USAGE-001
    pi_run = None
    for item in usage.get("runs") or []:
        if item.get("harness") == "pi":
            pi_run = item
            break
    if pi_run is None:
        for item in five.get("runs") or []:
            if item.get("harness") == "pi":
                pi_run = item
                break
    codex_run = next((item for item in (five.get("runs") or []) if item.get("harness") == "codex"), None)
    usage_unknown = token_unknown(pi_run, "total") if pi_run else False
    usage_zeroed = token_zero(pi_run, "total") if pi_run else False
    codex_input = (codex_run or {}).get("tokens") or {}
    usage_status = "pass" if usage_unknown and not usage_zeroed else (
        "not_evaluated" if not (usage.get("receipt", {}).get("exists") or five.get("receipt", {}).get("exists")) else "fail"
    )
    rows.append(
        _result(
            "SE-USAGE-001",
            "Unknown usage/cost remains unknown, never zero; overlapping aggregate records are not double-counted.",
            f"pi_tokens={None if pi_run is None else pi_run.get('tokens')} zeroed={usage_zeroed} codex_tokens={codex_input}",
            usage_status,
            scenarios=["usage_absent", "five_harness"],
            limits=["Double-count check is observational against Codex repeated token_count rows (expected input=10, not 20)."],
        )
    )

    # SE-CHECK-001
    parse_status = None
    if malformed.get("runs"):
        parse_status = next((c.get("status") for c in malformed["runs"][0].get("checks") or [] if c.get("id") == "ingest.parse_error"), None)
    loop_status = None
    if loop.get("runs"):
        loop_status = next((c.get("status") for c in loop["runs"][0].get("checks") or [] if c.get("id") == "tool.repeat_loop"), None)
    ordinary_loop = None
    ordinary_err = None
    if ordinary.get("runs"):
        ordinary_loop = next((c.get("status") for c in ordinary["runs"][0].get("checks") or [] if c.get("id") == "tool.repeat_loop"), None)
        ordinary_err = next((c.get("status") for c in ordinary["runs"][0].get("checks") or [] if c.get("id") == "tool.result_error"), None)
    empty_hard = empty.get("hard_pass")
    check1_ok = (
        parse_status == "fail"
        and loop_status == "fail"
        and ordinary_err == "fail"
        and ordinary_loop in {"pass", "not_applicable"}
        and empty_hard is False
    )
    rows.append(
        _result(
            "SE-CHECK-001",
            "Versioned catalog; infra/parse failure is not behavioral pass; empty coverage cannot establish success.",
            f"parse={parse_status} loop={loop_status} ordinary_error={ordinary_err} ordinary_loop={ordinary_loop} empty_hard_pass={empty_hard} catalog={five.get('catalog_id')}",
            "pass" if check1_ok else ("not_evaluated" if not malformed.get("receipt", {}).get("exists") else "fail"),
            scenarios=["malformed", "loop_fail", "ordinary_error", "empty", "five_harness"],
            limits=[],
        )
    )

    # SE-CHECK-002
    contradict_status = None
    if contradict.get("runs"):
        contradict_status = next((c.get("status") for c in contradict["runs"][0].get("checks") or [] if c.get("id") == "claim.command_outcome"), None)
    completion_status = None
    if completion.get("runs"):
        completion_status = next((c.get("status") for c in completion["runs"][0].get("checks") or [] if c.get("id") == "claim.completion"), None)
    gaps = completion.get("proof_gaps") or []
    gap_ok = any(
        (isinstance(item, dict) and (item.get("id") == "claim.historical_policy_unavailable" or "historical_policy" in str(item)))
        for item in gaps
    )
    check2_ok = contradict_status == "fail" and completion_status == "unknown"
    rows.append(
        _result(
            "SE-CHECK-002",
            "Command-outcome contradiction vs completion-without-acceptance-set unknown; never waive unknown as not_applicable; no checkout mutation.",
            f"command_outcome={contradict_status} completion={completion_status} historical_gap={gap_ok}",
            "pass" if check2_ok else ("not_evaluated" if not contradict.get("receipt", {}).get("exists") else "fail"),
            scenarios=["claim_contradict", "claim_completion"],
            limits=["WorkGraph scoring is a separate optional adjunct, not implied by claim checks."],
        )
    )

    # SE-JUDGE-001
    default_calls = five.get("provider_calls")
    default_approvals = five.get("approvals_count")
    judge_status = "unknown"
    judge_limits = [
        "This runner never passes --judge-provider/--judge-model/--judge-recipient/--judge-auth-env.",
        "Absent separately produced approved evidence, judge remains unknown/blocked, never pass.",
    ]
    if default_calls not in (0, None) and five.get("receipt", {}).get("exists"):
        judge_status = "fail"
        judge_limits.append("Default five_harness recorded provider_calls != 0")
    elif not judge.get("present"):
        judge_status = "unknown"
    elif judge.get("status") == "observed":
        judge_status = "pass" if not judge.get("pass_claimed") or judge.get("approvals") else "unknown"
        # Actual authorized judgment may pass only when evidence shows granted approval + decided rows.
        if judge.get("approvals") and judge.get("judge_rows"):
            judge_status = "pass"
    else:
        judge_status = "unknown"
    rows.append(
        _result(
            "SE-JUDGE-001",
            "Opt-out zero provider calls; authorized judgment only with approval; missing evidence/provider-error stay unknown never pass.",
            f"default_provider_calls={default_calls} default_approvals={default_approvals} judge_evidence={judge.get('status')} rows={len(judge.get('judge_rows') or [])}",
            judge_status,
            scenarios=["five_harness", "judge_evidence"],
            limits=judge_limits,
            parent="Authorized live judge remains parent-owned. Runner only consumes --judge-evidence.",
        )
    )

    # SE-SKILL-001
    unchanged_row = _skill_with_kind(unchanged_skill, "authoritative", "demo")
    edited_row = _skill_with_kind(edited_skill, "authoritative", "demo")
    mention_row = _skill_with_kind(mention, "mention")
    missing_row = _missing_skill_row(missing_skill)
    unchanged_hist = None if unchanged_row is None else (unchanged_row.get("historical_loaded_digest") or unchanged_row.get("digest"))
    unchanged_cur = None if unchanged_row is None else unchanged_row.get("current_on_disk_digest")
    edited_hist = None if edited_row is None else (edited_row.get("historical_loaded_digest") or edited_row.get("digest"))
    edited_cur = None if edited_row is None else edited_row.get("current_on_disk_digest")
    unchanged_ok = (
        unchanged_row is not None
        and unchanged_row.get("activation_kind") == "authoritative"
        and unchanged_row.get("digest_relation") == "historical_matches_current"
        and unchanged_hist not in UNKNOWN_DIGESTS
        and unchanged_cur == unchanged_hist
        and unchanged_row.get("missing") is False
    )
    edited_ok = (
        edited_row is not None
        and edited_row.get("activation_kind") == "authoritative"
        and edited_row.get("digest_relation") == "historical_differs_from_current"
        and edited_hist not in UNKNOWN_DIGESTS
        and edited_cur not in UNKNOWN_DIGESTS
        and edited_hist != edited_cur
    )
    mention_ok = (
        mention_row is not None
        and mention_row.get("activation_kind") == "mention"
        and mention_row.get("activation_kind") != "authoritative"
    )
    missing_ok = (
        missing_row is not None
        and missing_row.get("missing") is True
        and (missing_row.get("historical_loaded_digest") or missing_row.get("digest")) not in UNKNOWN_DIGESTS
        and missing_row.get("current_on_disk_digest") in UNKNOWN_DIGESTS
    )
    skill_ok = unchanged_ok and edited_ok and mention_ok and missing_ok
    skill_receipts = all(
        (item.get("receipt") or {}).get("exists")
        for item in (unchanged_skill, edited_skill, mention, missing_skill)
    )
    rows.append(
        _result(
            "SE-SKILL-001",
            "Registry records identity/path/digest; exercise unchanged, edited, missing, and low-confidence mention separately; never attribute current bytes to a past load.",
            (
                f"unchanged={unchanged_ok} edited={edited_ok} mention={mention_ok} missing={missing_ok} "
                f"unchanged_row={unchanged_row} edited_row={edited_row} mention_row={mention_row} missing_row={missing_row}"
            ),
            "pass" if skill_ok else ("not_evaluated" if not skill_receipts else "fail"),
            scenarios=["skill_unchanged", "skill_edited", "skill_mention", "skill_missing"],
            limits=["Low-confidence mentions must not be treated as authoritative loads."],
        )
    )

    # SE-TREND-001
    comparisons = trend.get("comparisons") or five.get("comparisons") or []
    trend_status = "not_evaluated"
    if trend.get("receipt", {}).get("exists") or five.get("receipt", {}).get("exists"):
        if comparisons:
            incompatible = [item for item in comparisons if isinstance(item, dict) and item.get("compatible") is False]
            measurable = [item for item in comparisons if isinstance(item, dict) and item.get("compatible") is True]
            trend_status = "pass" if (measurable or incompatible) else "fail"
        else:
            trend_status = "fail"
            if (five.get("comparisons_count") == 0) and not trend.get("receipt", {}).get("exists"):
                trend_status = "not_evaluated"
    rows.append(
        _result(
            "SE-TREND-001",
            "Immutable receipts support baseline/candidate comparisons; incompatible catalog/parser/cohort cannot silently yield a quality delta.",
            f"comparisons={comparisons}",
            trend_status,
            scenarios=["trend_revisions", "five_harness", "repeat_ingest"],
            limits=["Missing usage must remain unmeasurable, never a zero delta."],
        )
    )

    # SE-REPORT-001
    report_exists = (five.get("report") or {}).get("exists") and (empty.get("report") or {}).get("exists") and (malformed.get("report") or {}).get("exists")
    ids_ok = all((five.get("html_ids") or {}).values()) if five.get("html_ids") else False
    rows.append(
        _result(
            "SE-REPORT-001",
            "Redacted receipt.json + self-contained offline report.html with required sections for empty/malformed/normal.",
            f"reports_exist={report_exists} html_ids={five.get('html_ids')} empty_hard_pass={empty.get('hard_pass')}",
            "pass" if report_exists and ids_ok else ("not_evaluated" if not five.get("report", {}).get("exists") else "fail"),
            scenarios=["five_harness", "empty", "malformed", "secret_markup"],
            limits=[
                "Opening the real report offline is parent-owned. Runner does not treat HTML-source grep as visual PASS.",
            ],
            parent="Parent supplies/verifies offline browser evidence. Provisional skills-2ol.3 browser-initial is not final PASS.",
        )
    )

    # SE-CORRECT-001
    recs = [item for item in (recurring.get("recommendations") or []) if isinstance(item, dict)]
    empty_recs = [item for item in (empty.get("recommendations") or []) if isinstance(item, dict)]
    actionable = [item for item in recs if _is_actionable(item)]
    empty_limits = [
        item
        for item in empty_recs
        if item.get("limitation") and item.get("action") is None and item.get("target") is None
    ]
    sources_unchanged = recurring.get("source_bytes_unchanged") is True
    correct_ok = bool(actionable) and bool(empty_limits) and sources_unchanged
    correct_status = "pass" if correct_ok else (
        "not_evaluated" if not recurring.get("receipt", {}).get("exists") else "fail"
    )
    rows.append(
        _result(
            "SE-CORRECT-001",
            "Actionable findings may yield a concrete first-party proposal; insufficient evidence yields an explicit limitation; no source mutation.",
            (
                f"actionable={len(actionable)} empty_limitations={len(empty_limits)} "
                f"source_bytes_unchanged={recurring.get('source_bytes_unchanged')} "
                f"recurring_recommendations={recs} empty_recommendations={empty_recs}"
            ),
            correct_status,
            scenarios=["recurring_unpaired", "empty"],
            limits=["A limitation-only recurring row is not actionable proof. Generating recommendations must not write skills or session sources."],
        )
    )

    # SE-VERIFY-001
    covered = [row["id"] for row in rows]
    required_without_verify = [row for row in rows if row["id"] != "SE-VERIFY-001"]
    enumerated = {row["id"] for row in required_without_verify} == set(REQUIRED_IDS) - {"SE-VERIFY-001"}
    unevaluated = [row["id"] for row in required_without_verify if row["status"] == "not_evaluated"]
    verify_limits = [
        "This record is produced by the runner. Parent must still execute it against integrated siblings and retain evidence under .styrir/runs/.",
        "Partial execution is not completion. Failed sibling rows stay on those rows; this id records complete evaluation, not epic PASS.",
        f"canonical_revision={revision.get('canonical')} worktree={revision.get('worktree')}",
    ]
    verify_status = "fail"
    if enumerated and any_receipt and not unevaluated:
        verify_status = "pass"
    elif not any_receipt:
        verify_status = "not_evaluated"
    rows.append(
        _result(
            "SE-VERIFY-001",
            "End-to-end conformance identifies the canonical revision and evidence for all Required rows; unexecuted paths documented.",
            f"required_rows_enumerated={len(covered) + 1} unevaluated={unevaluated} any_receipt={any_receipt} cli={cli}",
            verify_status,
            scenarios=["five_harness", "empty", "malformed", "repeat_ingest", "changed_ingest", "skill_unchanged", "skill_edited", "recurring_unpaired"],
            limits=verify_limits,
            parent="Epic audit and final closeout are Main/CLOSEOUT, not a claimed build PASS.",
        )
    )

    # SE-WORKGRAPH-001
    wg_invoked = workgraph.get("workgraph_invoked")
    wg_result = workgraph.get("provenance_workgraph") or {}
    wg_status = "not_evaluated"
    if workgraph.get("receipt", {}).get("exists"):
        attached = wg_result.get("result") if isinstance(wg_result, dict) else None
        if wg_invoked and isinstance(attached, dict) and attached.get("hard_pass") is False:
            wg_status = "pass"
        elif wg_invoked:
            wg_status = "pass" if attached is not None else "fail"
        else:
            wg_status = "fail"
    rows.append(
        _result(
            "SE-WORKGRAPH-001",
            "Requested adjunct invokes existing workgraph-eval-score and records result/errors without duplicating publication rules.",
            f"invoked={wg_invoked} attached={wg_result}",
            wg_status,
            scenarios=["workgraph"],
            limits=[
                "Uses /Users/brooks/Code/agent-ops/bin/workgraph-eval-score and tests/workgraph-eval/fixtures/red-baseline.",
                "Does not launch or stop WorkGraph runs. Does not read stages/**/full.md into reports.",
            ],
        )
    )

    # SE-EXPORT-001
    atif_info = atif.get("atif") or {}
    export_status = "not_evaluated"
    if atif.get("receipt", {}).get("exists"):
        docs = atif_info.get("documents") or []
        export_status = "pass" if docs and not atif_info.get("secret_in_atif") else "fail"
    rows.append(
        _result(
            "SE-EXPORT-001",
            "One ATIF document per normalized session against pinned ATIF-v1.8; Claude and Grok chronology/identity; no Phoenix/OTel server.",
            f"atif={atif_info}",
            export_status,
            scenarios=["atif_export"],
            limits=["Optional; does not block core completion. Harbor Pydantic validation remains parent-optional."],
        )
    )
    return rows


def walk_docs() -> dict[str, Any]:
    spec = SKILL_DIR / "docs" / "specification.md"
    index = SKILL_DIR / "docs" / "index.md"
    decisions = SKILL_DIR / "docs" / "decisions.md"
    reqmap = SKILL_DIR / "docs" / "requirement-map.md"
    missing = [str(path) for path in (spec, index, decisions, reqmap) if not path.is_file()]
    text = spec.read_text(encoding="utf-8") if spec.is_file() else ""
    present = [req_id for req_id in REQUIRED_IDS + OPTIONAL_IDS if req_id in text]
    return {
        "ok": not missing and len(present) == len(REQUIRED_IDS) + len(OPTIONAL_IDS),
        "observed": f"missing_files={missing} spec_ids={present}",
        "limits": [] if not missing else [f"missing {path}" for path in missing],
        "paths": {
            "specification": file_identity(spec),
            "index": file_identity(index),
            "decisions": file_identity(decisions),
            "requirement_map": file_identity(reqmap),
        },
    }


def public_scrub(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SECRET_TOKEN, "[redacted-synthetic]").replace(SK_TOKEN, "[redacted-synthetic]")
    if isinstance(value, dict):
        return {key: public_scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [public_scrub(item) for item in value]
    return value


def render_markdown(record: Mapping[str, Any]) -> str:
    lines = [
        "# Session-eval conformance evidence",
        "",
        "This is an execution record, not a claim that the epic passed. Missing evidence is `not_evaluated` or `unknown`, never pass.",
        "",
        f"- Task: `skills-2ol.9`",
        f"- Canonical revision: `{record.get('canonical_revision')}`",
        f"- Worktree revision: `{record.get('worktree_revision')}`",
        f"- Generated at: `{record.get('generated_at')}`",
        f"- CLI: `{record.get('cli')}`",
        "",
        "## Requirements",
        "",
        "| Requirement | Expected behavior | Observed evidence | Result | Limitations |",
        "|---|---|---|---|---|",
    ]
    for row in record.get("requirements") or []:
        limits = "; ".join(row.get("limitations") or []) or "—"
        observed = str(row.get("observed") or "").replace("|", "/")
        expected = str(row.get("expected") or "").replace("|", "/")
        if len(observed) > 240:
            observed = observed[:237] + "..."
        lines.append(
            f"| {row.get('id')} | {expected} | {observed} | `{row.get('status')}` | {limits} |"
        )
    lines.extend(
        [
            "",
            "## Parent-owned observations",
            "",
            "- Offline browser open of `report.html` for empty/malformed/normal/markup-secret.",
            "- Authorized live judge under interactive approval.",
            "- Epic audit and CLOSEOUT publication.",
            "",
            "## Commands",
            "",
        ]
    )
    for scenario in record.get("scenarios") or []:
        command = " ".join(str(part) for part in (scenario.get("command") or []))
        lines.append(f"- `{scenario.get('name')}`: `{command}`")
        lines.append(
            f"  returncode={scenario.get('invocation', {}).get('returncode')} receipt={(scenario.get('receipt') or {}).get('sha256')} report={(scenario.get('report') or {}).get('sha256')}"
        )
    lines.extend(["", "## Limits", ""])
    for item in record.get("limits") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def run(out: Path, cli: Path, judge_evidence: Path | None) -> dict[str, Any]:
    out = out.expanduser()
    out.mkdir(parents=True, exist_ok=True)
    fixtures = out / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    corpus = generate_corpus(fixtures)
    # Durable copy lives under --out/fixtures; never a disappearing tempfile.
    before_sources = {path: sha256_file(Path(path)) for path in corpus.get("immutable_sources") or []}
    revision = _git_revision(REPO_ROOT)
    docs = walk_docs()
    judge = inspect_judge_evidence(judge_evidence)

    scenarios: dict[str, dict[str, Any]] = {}
    history_root = out / "history"

    def go(name: str, case_name: str, **kwargs: Any) -> dict[str, Any]:
        case = corpus["cases"][case_name]
        record = run_scenario(name, cli, out, case, history_root=history_root, **kwargs)
        scenarios[name] = record
        return record

    if cli.is_file():
        go("five_harness", "five_harness")
        go("repeat_ingest", "five_harness")
        mutate_change_history(corpus)
        go("changed_ingest", "change_history")
        go("empty", "empty")
        go("malformed", "malformed")
        go("nested", "nested")
        go("ended_unpaired", "ended_unpaired")
        go("live_unpaired", "live_unpaired")
        go("eof_unpaired", "eof_unpaired")
        go("usage_absent", "usage_absent")
        go("secret_markup", "secret_markup")
        go("skill_unchanged", "skill_unchanged")
        go("skill_edited", "skill_edited")
        go("skill_mention", "skill_mention")
        go("skill_missing", "skill_missing")
        go("loop_fail", "loop_fail")
        go("ordinary_error", "ordinary_error")
        go("claim_contradict", "claim_contradict")
        go("claim_completion", "claim_completion")
        go("recurring_unpaired", "recurring_unpaired")
        go("missing_harness", "missing_harness")
        go("atif_export", "five_harness", atif=True)
        wg = corpus.get("workgraph") or {}
        present = wg.get("present") or {}
        if all(present.get(key) for key in ("evidence", "manifest", "allowlist", "bin")):
            go(
                "workgraph",
                "five_harness",
                workgraph={
                    "evidence": wg["evidence"],
                    "manifest": wg["manifest"],
                    "allowlist": wg["allowlist"],
                    "bin": wg["bin"],
                },
            )
        else:
            scenarios["workgraph"] = {
                "name": "workgraph",
                "command": [],
                "invocation": {
                    "returncode": None,
                    "error": "workgraph-eval-score fixtures or binary missing",
                    "missing_implementation": True,
                },
                "receipt": {"path": None, "exists": False, "sha256": None},
                "report": {"path": None, "exists": False, "sha256": None},
                "runs": [],
                "limitations": [f"present={present}"],
            }
        baseline = (scenarios.get("five_harness") or {}).get("receipt") or {}
        go(
            "trend_revisions",
            "skill_mention",
            baseline=baseline.get("path"),
        )
    else:
        missing = {
            "name": "cli_missing",
            "command": [sys.executable, str(cli), "--since", "all", "--out", str(out / "runs" / "cli_missing")],
            "invocation": {
                "returncode": None,
                "error": f"shared CLI not found: {cli}",
                "missing_implementation": True,
            },
            "receipt": {"path": None, "exists": False, "sha256": None},
            "report": {"path": None, "exists": False, "sha256": None},
            "runs": [],
        }
        scenarios["five_harness"] = dict(missing, name="five_harness")

    after_sources = {path: sha256_file(Path(path)) for path in corpus.get("immutable_sources") or []}
    if "recurring_unpaired" in scenarios:
        scenarios["recurring_unpaired"]["source_bytes_unchanged"] = before_sources == after_sources
        scenarios["recurring_unpaired"]["source_hash_before"] = before_sources
        scenarios["recurring_unpaired"]["source_hash_after"] = after_sources

    requirements = evaluate_requirements(
        scenarios=scenarios,
        cli=cli,
        revision=revision,
        judge=judge,
        docs_ok=docs,
    )
    limits = [
        "Runner does not claim epic PASS. Parent integrates sibling modules then executes this script.",
        "Offline browser inspection of report.html is parent-owned and must not be faked with HTML-source grep.",
        "Judge pass requires separately produced approved evidence via --judge-evidence; otherwise unknown/blocked.",
        "This runner never requests or invokes providers and never passes judge provider flags.",
        "Finding evidence.snapshot_hash is aggregate run.source_snapshot.sha256; file bytes belong on files[].sha256.",
        "WorkGraph adjunct delegates to existing workgraph-eval-score; it does not duplicate publication rules.",
        "Synthetic corpus only; no live session transcripts or live secrets.",
        f"Pinned shared CLI: python3 session-eval/scripts/session_eval.py (resolved {cli})",
        f"Canonical base revision {CANONICAL_REVISION}",
    ]
    coverage = {
        "runner_covers": [
            "SE-DOC-001 file/ID presence",
            "SE-PORT-001 shared CLI invocation / explicit missing-dep failure",
            "SE-INGEST-001 five harnesses + malformed + missing harness",
            "SE-INGEST-002 nested / ended / live / EOF unpaired",
            "SE-EVIDENCE-001 repeat vs changed snapshot identity + finding snapshot_hash contract",
            "SE-PRIVACY-001 synthetic secret/markup absence in receipt/HTML",
            "SE-USAGE-001 unknown usage and repeated aggregate",
            "SE-CHECK-001 parse/loop/ordinary-error/empty",
            "SE-CHECK-002 contradicted command vs completion unknown",
            "SE-JUDGE-001 default zero calls; consume --judge-evidence only",
            "SE-SKILL-001 unchanged/edited/mention/missing as separate controls",
            "SE-TREND-001 baseline/candidate comparison fields",
            "SE-REPORT-001 artifact presence + required section ids (not visual open)",
            "SE-CORRECT-001 actionable recurring proposal plus empty limitation; sources unchanged",
            "SE-VERIFY-001 enumeration of every Required row",
            "SE-WORKGRAPH-001 real workgraph-eval-score delegation",
            "SE-EXPORT-001 --atif documents",
        ],
        "parent_must_observe": [
            "SE-REPORT-001 open real report.html offline (normal/empty/malformed/markup-secret)",
            "SE-JUDGE-001 authorized live provider judgment under interactive approval",
            "SE-PRIVACY-001 approval binding across changed snapshot bytes with a real provider",
            "SE-VERIFY-001 epic audit after sibling integration",
            "Visual confirmation that escaped markup is not executable in a browser",
        ],
    }
    record = {
        "schema": "session-eval-conformance/v1",
        "task": "skills-2ol.9",
        "generated_at": _now(),
        "canonical_revision": CANONICAL_REVISION,
        "worktree_revision": revision.get("worktree"),
        "revision": revision,
        "cli": str(cli),
        "cli_exists": cli.is_file(),
        "out": str(out),
        "corpus": str(fixtures / "corpus"),
        "judge_evidence": judge,
        "docs": docs,
        "requirements": requirements,
        "scenarios": [
            {
                "name": item.get("name"),
                "command": item.get("command"),
                "invocation": item.get("invocation"),
                "receipt": item.get("receipt"),
                "report": item.get("report"),
                "hard_pass": item.get("hard_pass"),
                "infra_ok": item.get("infra_ok"),
                "coverage": item.get("coverage"),
                "harnesses_found": item.get("harnesses_found"),
                "parse_errors": item.get("parse_errors"),
                "secret_in_receipt": item.get("secret_in_receipt"),
                "secret_in_report": item.get("secret_in_report"),
                "runs": item.get("runs"),
                "atif": item.get("atif"),
                "history": item.get("history"),
                "recommendations": item.get("recommendations"),
                "comparisons": item.get("comparisons"),
                "skills": item.get("skills"),
                "proof_gaps": item.get("proof_gaps"),
                "source_bytes_unchanged": item.get("source_bytes_unchanged"),
                "source_hash_before": item.get("source_hash_before"),
                "source_hash_after": item.get("source_hash_after"),
            }
            for item in scenarios.values()
        ],
        "coverage_matrix": coverage,
        "limits": limits,
        "statuses": {
            row["id"]: row["status"] for row in requirements
        },
    }
    public = public_scrub(record)
    evidence_json = _write_json(out / "evidence" / "requirements.json", public)
    evidence_md = _write_text(out / "evidence" / "requirements.md", render_markdown(public))
    _write_json(out / "evidence" / "coverage-matrix.json", coverage)
    _write_json(
        out / "evidence" / "summary.json",
        {
            "task": "skills-2ol.9",
            "canonical_revision": CANONICAL_REVISION,
            "cli": str(cli),
            "cli_exists": cli.is_file(),
            "statuses": public["statuses"],
            "evidence": {"json": str(evidence_json), "markdown": str(evidence_md)},
            "note": "Not a fabricated PASS. Parent executes and audits.",
        },
    )
    return public


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval-conformance",
        description="Generate a synthetic corpus, invoke the shared session-eval CLI, and write requirement evidence.",
    )
    parser.add_argument("--out", required=True, help="durable output directory for corpus, runs, and evidence")
    parser.add_argument(
        "--cli",
        default=None,
        help="path to session_eval.py (default: session-eval/scripts/session_eval.py beside this runner)",
    )
    parser.add_argument(
        "--judge-evidence",
        default=None,
        help="separately produced approved judge receipt; absent proof remains unknown/blocked",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cli = Path(args.cli).expanduser() if args.cli else default_cli_path()
    judge_path = Path(args.judge_evidence).expanduser() if args.judge_evidence else None
    if judge_path is not None and judge_path.is_dir():
        candidate = judge_path / "receipt.json"
        judge_path = candidate if candidate.is_file() else judge_path
    try:
        record = run(Path(args.out), cli, judge_path)
    except ConformanceError as exc:
        parser.error(str(exc))
        return 2
    summary = {
        "out": record.get("out"),
        "cli": record.get("cli"),
        "cli_exists": record.get("cli_exists"),
        "canonical_revision": record.get("canonical_revision"),
        "statuses": record.get("statuses"),
        "note": "conformance evidence written; not an epic PASS",
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
