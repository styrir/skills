#!/usr/bin/env python3
"""Render a self-contained offline session-eval HTML report from a redacted receipt.

Consumes the canonical ``styrir-session-eval/v0`` receipt only. Never opens
raw session files, ``full.md``, or other source payloads. All source-derived
labels are redacted then HTML-escaped. Missing or malformed receipts still
emit every required section with an honest verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote, unquote, urlparse

RECEIPT_SCHEMA = "styrir-session-eval/v0"
CATALOG_ID = "session-eval-check-catalog/v1"
GENERATOR = "session-eval-report"
GENERATOR_VERSION = "1.0.0"
UNKNOWN = "unknown"
REQUIRED_SECTION_IDS = (
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
TOKEN_FIELDS = ("input", "output", "cache_read", "cache_create", "total")
SECRET_PATTERN = re.compile(
    r"(?i)(?:(?:api[_-]?key|secret(?:[_-]?key)?|password|passwd|access[_-]?token|auth[_-]?token|"
    r"private[_-]?key)\s*[\"']?\s*[:=]\s*[\"']?[^\s,\"']{8,}"
    r"|sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?:sk|pk|token|secret|key)[-_][A-Za-z0-9._=-]{6,}"
    r"|bearer\s+[A-Za-z0-9._=-]{8,})"
)
RAW_KEYS = {
    "prompt",
    "prompts",
    "payload",
    "payloads",
    "arguments",
    "args",
    "input",
    "output",
    "stdout",
    "stderr",
    "terminal",
    "transcript",
    "content",
    "text",
    "body",
    "message",
    "messages",
    "full_md",
    "full.md",
}
CSS = """
:root{
  --paper:#f3efe6;
  --surface:#fffcf6;
  --ink:#1a1612;
  --muted:#4e463c;
  --line:#d7d0c3;
  --pass-bg:#dcefe0;
  --pass-ink:#0d4a24;
  --fail-bg:#f8dede;
  --fail-ink:#7a1212;
  --warn-bg:#f6ead0;
  --warn-ink:#6a4a00;
  --info-bg:#dde7f4;
  --info-ink:#143a6b;
  --th:#ece6d8;
}
*{box-sizing:border-box}
html{font-size:16px;max-width:100%}
body{
  margin:0;
  padding:1.25rem 1.1rem 2.5rem;
  background:var(--paper);
  color:var(--ink);
  font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  max-width:100%;
}
a.skip{
  position:absolute;left:-999px;top:auto;width:1px;height:1px;overflow:hidden;
}
a.skip:focus{
  position:static;width:auto;height:auto;padding:.35rem .6rem;
  background:var(--info-bg);color:var(--info-ink);
}
header{margin:0 0 1.35rem}
h1{
  font-size:1.35rem;
  font-weight:650;
  letter-spacing:-0.02em;
  margin:0 0 .35rem;
  max-width:28ch;
}
.lede{
  margin:0;
  color:var(--muted);
  max-width:70ch;
}
section,footer{
  background:var(--surface);
  border:1px solid var(--line);
  padding:.85rem 1rem 1rem;
  margin:0 0 1.15rem;
  max-width:100%;
  min-width:0;
}
h2{
  font-size:1.05rem;
  font-weight:650;
  letter-spacing:-0.015em;
  margin:0 0 .55rem;
}
h3{font-size:.95rem;font-weight:650;margin:.85rem 0 .35rem}
p{margin:.35rem 0}
.note{color:var(--muted);max-width:70ch}
dl.facts{
  display:grid;
  grid-template-columns:minmax(8rem,14rem) 1fr;
  gap:.2rem .9rem;
  margin:.35rem 0 0;
  max-width:100%;
}
dl.facts dt{font-weight:650;color:var(--muted)}
dl.facts dd{margin:0;min-width:0;overflow-wrap:anywhere;word-break:break-word}
.banner{
  margin:0 0 .65rem;
  padding:.55rem .7rem;
  font-weight:650;
  border:1px solid var(--line);
}
.pass{background:var(--pass-bg);color:var(--pass-ink);border-color:#9ec9a8}
.fail{background:var(--fail-bg);color:var(--fail-ink);border-color:#e2a0a0}
.warn{background:var(--warn-bg);color:var(--warn-ink);border-color:#e0c48a}
.info{background:var(--info-bg);color:var(--info-ink);border-color:#a0bce2}
.table-wrap{overflow-x:auto;margin:.4rem 0;max-width:100%;min-width:0}
table{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}
th,td{border:1px solid var(--line);padding:.32rem .5rem;text-align:left;vertical-align:top}
th{background:var(--th);font-weight:650}
td.mono,th.mono,code,.mono{
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:12px;
  word-break:break-all;
}
.charts{
  display:flex;
  flex-wrap:wrap;
  gap:1rem;
  align-items:flex-start;
}
figure{margin:0;max-width:100%}
figcaption{font-size:12px;color:var(--muted);margin:.25rem 0 0;max-width:36ch}
svg{max-width:100%;height:auto}
svg text{fill:var(--ink);font:11px ui-sans-serif,system-ui,sans-serif}
details{margin:.4rem 0 0;border-top:1px solid var(--line);padding-top:.35rem}
summary{cursor:pointer;font-weight:650;color:var(--ink)}
summary:focus{outline:2px solid var(--info-ink);outline-offset:2px}
ul.compact{margin:.25rem 0;padding-left:1.1rem}
a{color:var(--info-ink)}
a:focus{outline:2px solid var(--info-ink);outline-offset:2px}
footer{color:var(--muted);font-size:12.5px}
#provenance dd,#footer p{min-width:0;overflow-wrap:anywhere;word-break:break-word}
@media (max-width:720px){
  body{padding:.85rem .7rem 1.8rem}
  dl.facts{grid-template-columns:1fr}
  .charts{flex-direction:column}
  h1{font-size:1.2rem}
}
@media print{
  @page{margin:14mm}
  body{background:#fff;color:#111;padding:0;font-size:11pt}
  section,footer{break-inside:avoid;border-color:#bbb;background:#fff}
  a{color:inherit;text-decoration:none}
  .banner{print-color-adjust:exact;-webkit-print-color-adjust:exact}
  header{margin-bottom:.8rem}
}
""".strip()


class ReportError(Exception):
    """Expected local-input error suitable for a concise CLI message."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _is_unknown(value: Any) -> bool:
    return value in (None, "", UNKNOWN)


def _copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy(item) for item in value]
    return value


def _redact_text(value: Any, limit: int = 240) -> str:
    """Structural label: strip NULs, redact secrets, never emit matched secret text."""

    if value is None:
        return UNKNOWN
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value).replace("\x00", "")
    text = SECRET_PATTERN.sub("[REDACTED]", text)
    text = " ".join(text.split())
    if not text:
        return UNKNOWN
    return text[:limit]


def _esc(value: Any, limit: int = 240) -> str:
    return html.escape(_redact_text(value, limit), quote=True)


def _attr(value: Any, limit: int = 240) -> str:
    return _esc(value, limit)


def _html_id(prefix: str, raw: Any) -> str:
    text = _redact_text(raw, 120)
    slug = re.sub(r"[^A-Za-z0-9_.:-]+", "-", text).strip("-_.")
    if not slug:
        slug = "unknown"
    return f"{prefix}-{slug}"


def _digest8(value: Any) -> str:
    text = _redact_text(value, 128)
    if text.lower().startswith("sha256:"):
        text = text[7:]
    text = re.sub(r"[^A-Za-z0-9]", "", text)
    return (text[:8] or "unknown")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default


def _output_root(path: str | Path) -> Path:
    value = Path(path).expanduser()
    if not value.is_absolute():
        value = Path.cwd().resolve() / value
    return Path(os.path.normpath(str(value)))


def _write_immutable(path: Path, payload: bytes) -> Path:
    """Owner-only write. Same bytes are reused; different bytes never overwrite."""

    path = _output_root(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(payload)[:16]
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    parent_fd = os.open(str(path.parent), os.O_RDONLY | nofollow)
    try:
        info = os.fstat(parent_fd)
        if not stat.S_ISDIR(info.st_mode):
            raise ReportError(f"output parent is not a directory: {path.parent}")
        candidate_index = 0
        while True:
            if candidate_index == 0:
                candidate = path
            else:
                suffix = f"-{digest}" if candidate_index == 1 else f"-{digest}-{candidate_index}"
                candidate = path.with_name(path.stem + suffix + path.suffix)
            try:
                existing_fd = os.open(candidate.name, os.O_RDONLY | nofollow, dir_fd=parent_fd)
            except FileNotFoundError:
                existing_fd = None
            if existing_fd is not None:
                try:
                    existing = b""
                    while True:
                        chunk = os.read(existing_fd, 1024 * 1024)
                        if not chunk:
                            break
                        existing += chunk
                finally:
                    os.close(existing_fd)
                if existing == payload:
                    return candidate
                candidate_index += 1
                continue
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow
            try:
                fd = os.open(candidate.name, flags, 0o600, dir_fd=parent_fd)
            except FileExistsError:
                candidate_index += 1
                continue
            failed = True
            try:
                os.fchmod(fd, 0o600)
                view = memoryview(payload)
                while view:
                    written = os.write(fd, view)
                    view = view[written:]
                failed = False
            except OSError as exc:
                raise ReportError(f"cannot write {candidate}: {exc}") from exc
            finally:
                os.close(fd)
                if failed:
                    try:
                        os.unlink(candidate.name, dir_fd=parent_fd)
                    except OSError:
                        pass
            if not failed:
                return candidate
    finally:
        os.close(parent_fd)


def _malformed_envelope(reason: str, parse_errors: int = 1) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "catalog_id": CATALOG_ID,
        "generated_at": UNKNOWN,
        "since": UNKNOWN,
        "harnesses_requested": [],
        "harnesses_found": [],
        "coverage": {
            "sessions_ingested": 0,
            "sessions_malformed": 0,
            "applicable_hard_fail_decided": 0,
            "applicable_hard_fail_unknown": 0,
            "missing_requested_inputs": [],
            "empty": True,
        },
        "hard_pass": False,
        "infra_ok": False,
        "feedback_outcome": None,
        "redaction": {"policy": "default-local", "applied": True},
        "approvals": [],
        "runs": [],
        "skills": [],
        "checks": [],
        "comparisons": [],
        "recommendations": [
            {
                "id": "rec-malformed-receipt",
                "target": None,
                "action": None,
                "rationale": None,
                "evidence": [],
                "verification": None,
                "confidence": "none",
                "limitation": reason,
            }
        ],
        "parse_errors": parse_errors,
        "proof_gaps": [{"kind": "receipt.malformed", "reason": reason}],
        "provenance": {
            "parser": UNKNOWN,
            "parser_version": UNKNOWN,
            "snapshots": [],
            "report": {"generator": GENERATOR, "malformed": True, "reason": reason},
        },
    }


def coerce_receipt(receipt: Any) -> dict[str, Any]:
    """Normalize a receipt for rendering. Never invent success from garbage."""

    if not isinstance(receipt, dict):
        return _malformed_envelope("receipt_not_object")
    document = _copy(receipt)
    for key in (
        "runs",
        "skills",
        "checks",
        "comparisons",
        "recommendations",
        "proof_gaps",
        "approvals",
        "harnesses_requested",
        "harnesses_found",
    ):
        if not isinstance(document.get(key), list):
            document[key] = []
    if not isinstance(document.get("provenance"), dict):
        document["provenance"] = {"parser": UNKNOWN, "parser_version": UNKNOWN, "snapshots": []}
    if not isinstance(document.get("redaction"), dict):
        document["redaction"] = {"policy": UNKNOWN, "applied": True}
    if not isinstance(document.get("parse_errors"), int) or isinstance(document.get("parse_errors"), bool):
        document["parse_errors"] = 0

    runs = [item for item in document["runs"] if isinstance(item, dict)]
    coverage = _as_dict(document.get("coverage"))
    decided = _int(coverage.get("applicable_hard_fail_decided"), 0)
    unknown_hard = _int(coverage.get("applicable_hard_fail_unknown"), 0)
    claimed_empty = coverage.get("empty")
    if not runs:
        coverage["empty"] = True
    elif decided > 0 or unknown_hard > 0:
        coverage["empty"] = False
    else:
        coverage["empty"] = True
    if "sessions_ingested" not in coverage:
        coverage["sessions_ingested"] = len(runs)
    document["coverage"] = coverage

    if not isinstance(document.get("hard_pass"), bool):
        document["hard_pass"] = False
    if not isinstance(document.get("infra_ok"), bool):
        document["infra_ok"] = False
    if document["parse_errors"] == 0:
        document["parse_errors"] = _int(coverage.get("sessions_malformed"), 0)

    schema_supported = document.get("schema") == RECEIPT_SCHEMA
    gaps = [item for item in document["proof_gaps"] if isinstance(item, dict)]
    if not schema_supported:
        gaps.append({"kind": "receipt.schema_unexpected", "schema": document.get("schema")})
    inconsistent = False
    if claimed_empty is False and not runs:
        inconsistent = True
    if document["hard_pass"] is True and (
        coverage["empty"] or not runs or decided == 0 or not schema_supported
    ):
        inconsistent = True
    if not schema_supported or inconsistent or coverage["empty"] or not runs or decided == 0:
        document["hard_pass"] = False
    if not schema_supported or inconsistent:
        recs = [item for item in document["recommendations"] if isinstance(item, dict)]
        if not any(item.get("limitation") for item in recs):
            recs.append(
                {
                    "id": "rec-malformed-receipt",
                    "target": None,
                    "action": None,
                    "rationale": None,
                    "evidence": [],
                    "verification": None,
                    "confidence": "none",
                    "limitation": "unsupported or inconsistent receipt; verdict is unknown, not success",
                }
            )
        document["recommendations"] = recs
        if inconsistent and not any(item.get("kind") == "receipt.inconsistent" for item in gaps):
            gaps.append({"kind": "receipt.inconsistent", "reason": "boolean_or_schema_mismatch"})
    document["proof_gaps"] = gaps
    return document


def _receipt_unreliable(receipt: dict[str, Any]) -> bool:
    if receipt.get("schema") != RECEIPT_SCHEMA:
        return True
    for item in _as_list(receipt.get("proof_gaps")):
        if isinstance(item, dict) and item.get("kind") in {
            "receipt.malformed",
            "receipt.schema_unexpected",
            "receipt.inconsistent",
        }:
            return True
    report_meta = _as_dict(_as_dict(receipt.get("provenance")).get("report"))
    return bool(report_meta.get("malformed"))


def _native_label(native: Any) -> str:
    if _is_unknown(native):
        return UNKNOWN
    if isinstance(native, dict):
        identity = native.get("id")
        if _is_unknown(identity):
            return UNKNOWN
        return _redact_text(identity)
    return _redact_text(native)


def _native_kind(native: Any) -> str:
    if isinstance(native, dict):
        return _redact_text(native.get("kind") or UNKNOWN)
    return UNKNOWN


def _token_display(tokens: Any) -> str:
    mapping = _as_dict(tokens)
    if not mapping:
        return UNKNOWN
    total = mapping.get("total")
    if _is_unknown(total):
        return UNKNOWN
    return _redact_text(total)


def _usage_known(tokens: Any) -> bool:
    mapping = _as_dict(tokens)
    if not mapping:
        return False
    total = mapping.get("total")
    return not _is_unknown(total) and isinstance(total, (int, float)) and not isinstance(total, bool)


def _day_key(value: Any) -> str | None:
    if _is_unknown(value):
        return None
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        candidate = text[:10]
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
        except ValueError:
            return None
        return candidate
    return None


def _run_day(run: dict[str, Any]) -> str | None:
    for key in ("started_at", "ended_at"):
        day = _day_key(run.get(key))
        if day:
            return day
    return None


def _run_hard_fail(run: dict[str, Any]) -> bool:
    for check in _as_list(run.get("checks")):
        if not isinstance(check, dict):
            continue
        if check.get("class") == "hard_fail" and check.get("status") == "fail" and check.get("channel") != "infra":
            return True
    return False


def _failed_checks(run: dict[str, Any]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for check in _as_list(run.get("checks")):
        if isinstance(check, dict) and check.get("status") == "fail":
            failed.append(check)
    return failed


def _facts(pairs: Sequence[tuple[str, Any]]) -> str:
    rows: list[str] = []
    for key, value in pairs:
        rows.append(f"<dt>{_esc(key)}</dt><dd>{_esc(value, 8000)}</dd>")
    return f'<dl class="facts">{"".join(rows)}</dl>'


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]], *, row_ids: Sequence[str] | None = None) -> str:
    head = "".join(f"<th>{cell}</th>" for cell in headers)
    body: list[str] = []
    for index, row in enumerate(rows):
        ident = ""
        if row_ids is not None and index < len(row_ids) and row_ids[index]:
            ident = f' id="{_attr(row_ids[index])}"'
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        body.append(f"<tr{ident}>{cells}</tr>")
    if not body:
        empty = f'<tr><td colspan="{len(headers)}">None recorded.</td></tr>'
        body.append(empty)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _pointer_cell(item: dict[str, Any]) -> str:
    event_range = _as_dict(item.get("event_range"))
    start = event_range.get("start_line", UNKNOWN)
    end = event_range.get("end_line", UNKNOWN)
    parts = [
        f"path={_esc(item.get('source_path') or UNKNOWN)}",
        f"snapshot={_esc(item.get('snapshot_hash') or UNKNOWN)}",
        f"parser={_esc(item.get('parser_version') or UNKNOWN)}",
        f"lines={_esc(start)}–{_esc(end)}",
        f"hash={_esc(item.get('evidence_hash') or UNKNOWN)}",
    ]
    if item.get("check_id"):
        parts.insert(0, f"check={_esc(item.get('check_id'))}")
    return '<span class="mono">' + "; ".join(parts) + "</span>"


def _safe_local_href(path_value: Any) -> str | None:
    """Return an encoded file URL for an absolute local path, else None."""

    if path_value is None:
        return None
    text = str(path_value).replace("\x00", "").strip()
    if not text or text == UNKNOWN:
        return None
    if "\n" in text or "\r" in text:
        return None
    lowered = text.casefold()
    if lowered.startswith(("javascript:", "vbscript:", "data:", "http:", "https:", "ftp:", "blob:")):
        return None
    if text.startswith("//"):
        return None
    if lowered.startswith("file:"):
        parsed = urlparse(text)
        if parsed.scheme.casefold() != "file":
            return None
        if parsed.netloc not in ("", "localhost"):
            return None
        path = unquote(parsed.path or "")
        if parsed.query:
            path = f"{path}?{unquote(parsed.query)}"
        if parsed.fragment:
            path = f"{path}#{unquote(parsed.fragment)}"
        if not path.startswith("/"):
            return None
        return "file://" + quote(path, safe="/")
    if not text.startswith("/"):
        return None
    return "file://" + quote(text, safe="/")


def _source_link(path_value: Any) -> str:
    label = _redact_text(path_value, 320)
    if label == UNKNOWN:
        return _esc(UNKNOWN)
    href = _safe_local_href(path_value)
    if href is None:
        return f'<span class="mono">{_esc(label, 320)}</span>'
    return f'<a class="mono" href="{html.escape(href, quote=True)}">{_esc(label, 320)}</a>'


def _lineage_block(lineage: Any) -> str:
    mapping = lineage if isinstance(lineage, dict) else {"parent": UNKNOWN, "children": UNKNOWN, "attempt": UNKNOWN, "continuation_of": UNKNOWN, "continued_by": UNKNOWN}
    attempt = mapping.get("attempt")
    if isinstance(attempt, dict):
        attempt_label = f"id={_redact_text(attempt.get('id'))} number={_redact_text(attempt.get('number'))}"
    elif _is_unknown(attempt):
        attempt_label = UNKNOWN
    else:
        attempt_label = _redact_text(attempt)

    def rel(value: Any) -> str:
        if _is_unknown(value):
            return UNKNOWN
        if isinstance(value, list):
            if not value:
                return "[]"
            return ", ".join(_redact_text(item) for item in value)
        return _redact_text(value)

    return _facts(
        [
            ("parent", rel(mapping.get("parent", UNKNOWN))),
            ("children", rel(mapping.get("children", UNKNOWN))),
            ("attempt", attempt_label),
            ("continuation_of", rel(mapping.get("continuation_of", UNKNOWN))),
            ("continued_by", rel(mapping.get("continued_by", UNKNOWN))),
        ]
    )


def _pairing_block(run: dict[str, Any]) -> str:
    rows: list[str] = []
    lifecycle = _as_dict(run.get("lifecycle"))
    terminal = lifecycle.get("state") == "terminal"
    for turn in _as_list(run.get("turns")):
        if not isinstance(turn, dict):
            continue
        for call in _as_list(turn.get("tool_calls")):
            if not isinstance(call, dict):
                continue
            call_id = call.get("id") or call.get("call_id") or UNKNOWN
            status = call.get("status") or UNKNOWN
            result_line = call.get("result_source_line")
            result_path = call.get("result_source_path")
            has_result = result_line is not None or (isinstance(result_path, str) and result_path and result_path != UNKNOWN)
            if status in {"ok", "error"} or (has_result and status not in {"unpaired", "pending"}):
                marker = "paired"
                detail = (
                    f"status={_esc(status)} "
                    f"result_source_line={_esc(UNKNOWN if result_line is None else result_line)} "
                    f"result_source_path={_esc(result_path or UNKNOWN)}"
                )
            elif status == "unpaired" or (status not in {"pending", "ok", "error"} and terminal and not has_result):
                marker = "missing"
                detail = f"status={_esc(status if status != UNKNOWN else 'unpaired')}"
            else:
                marker = "unresolved"
                detail = f"status={_esc(status if status != UNKNOWN else 'pending')}"
            rows.append(
                "<li>"
                f'<span class="mono">call={_esc(call_id)}</span> '
                f'<span class="mono">{detail}</span> '
                f"({_esc(marker)})"
                "</li>"
            )
    if not rows:
        return '<p class="note">No tool pairing records on this run.</p>'
    return f'<ul class="compact">{"".join(rows)}</ul>'


def _lifecycle_block(run: dict[str, Any]) -> str:
    lifecycle = _as_dict(run.get("lifecycle"))
    state = lifecycle.get("state") or UNKNOWN
    pointers = [_pointer_cell(item) for item in _as_list(lifecycle.get("evidence")) if isinstance(item, dict)]
    evidence = "<br>".join(pointers) if pointers else _esc("none")
    return f"<p>state: <strong>{_esc(state)}</strong></p><p>{evidence}</p>"


def _svg_chart(title: str, points: Sequence[tuple[str, float | None]], unit: str) -> str:
    width, height = 320, 148
    left, right, top, bottom = 36, 12, 18, 36
    plot_w = width - left - right
    plot_h = height - top - bottom
    known = [value for _, value in points if value is not None]
    caption = _esc(title)
    if not points:
        body = (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" '
            f'aria-label="{caption}: no observations">'
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fffcf6" stroke="#d7d0c3"/>'
            f'<text x="{width/2:.0f}" y="{height/2:.0f}" text-anchor="middle">No observations</text>'
            "</svg>"
        )
        return f"<figure>{body}<figcaption>{caption}. No observations.</figcaption></figure>"
    max_value = max(known) if known else None
    if max_value is None:
        body = (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" '
            f'aria-label="{caption}: unmeasurable">'
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fffcf6" stroke="#d7d0c3"/>'
            '<pattern id="unm" width="6" height="6" patternUnits="userSpaceOnUse">'
            '<path d="M0,6 L6,0" stroke="#6a4a00" stroke-width="1"/></pattern>'
            f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="url(#unm)" opacity="0.45"/>'
            f'<text x="{width/2:.0f}" y="{height/2:.0f}" text-anchor="middle">unmeasurable</text>'
            "</svg>"
        )
        return (
            f"<figure>{body}<figcaption>{caption} is unmeasurable; unknown usage is not charted as zero."
            "</figcaption></figure>"
        )
    scale = max_value if max_value > 0 else 1.0
    count = max(len(points), 1)
    gap = 4
    bar_w = max((plot_w / count) - gap, 4)
    bars: list[str] = []
    for index, (label, value) in enumerate(points):
        x = left + index * (bar_w + gap)
        tick = _esc(label[-5:] if len(label) > 5 else label, 16)
        if value is None:
            bars.append(
                f'<rect x="{x:.1f}" y="{top:.1f}" width="{bar_w:.1f}" height="{plot_h:.1f}" '
                f'fill="#f6ead0" stroke="#6a4a00"/>'
                f'<text x="{x + bar_w/2:.1f}" y="{top + plot_h/2:.1f}" text-anchor="middle">?</text>'
            )
        else:
            bar_h = (float(value) / scale) * plot_h
            y = top + plot_h - bar_h
            bars.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(bar_h, 1):.1f}" '
                f'fill="#143a6b"/>'
            )
        bars.append(
            f'<text x="{x + bar_w/2:.1f}" y="{height - 8}" text-anchor="middle">{tick}</text>'
        )
    axis = (
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#1a1612"/>'
        f'<line x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}" stroke="#1a1612"/>'
        f'<text x="4" y="{top + 8}">{_esc(f"{scale:g}")}</text>'
        f'<text x="4" y="{top + plot_h}">{_esc("0")}</text>'
    )
    unmeasurable = any(value is None for _, value in points)
    note = f"{caption} ({_esc(unit)})."
    if unmeasurable:
        note += " Hatched or marked days are unmeasurable, not zero."
    aria = caption + ("; includes unmeasurable days" if unmeasurable else "")
    body = (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{aria}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fffcf6" stroke="#d7d0c3"/>'
        f"{axis}{''.join(bars)}</svg>"
    )
    return f"<figure>{body}<figcaption>{note}</figcaption></figure>"


def _trend_points(runs: Sequence[dict[str, Any]]) -> tuple[list[tuple[str, float | None]], list[tuple[str, float | None]], list[tuple[str, float | None]]]:
    days: dict[str, dict[str, Any]] = {}
    undated = 0
    for run in runs:
        if not isinstance(run, dict):
            continue
        day = _run_day(run)
        if day is None:
            undated += 1
            continue
        bucket = days.setdefault(day, {"sessions": 0, "hard_fail": 0, "tokens": 0.0, "token_unknown": False})
        bucket["sessions"] += 1
        if _run_hard_fail(run):
            bucket["hard_fail"] += 1
        if _usage_known(run.get("tokens")):
            bucket["tokens"] += float(_as_dict(run.get("tokens")).get("total"))
        else:
            bucket["token_unknown"] = True
    labels = sorted(days)
    sessions = [(day, float(days[day]["sessions"])) for day in labels]
    hard_fail = [(day, float(days[day]["hard_fail"])) for day in labels]
    tokens: list[tuple[str, float | None]] = []
    for day in labels:
        if days[day]["token_unknown"]:
            tokens.append((day, None))
        else:
            tokens.append((day, float(days[day]["tokens"])))
    if undated and not labels:
        # Dated axis absent: do not invent a zero series.
        return [], [], []
    return sessions, hard_fail, tokens


def _verdict_class(receipt: dict[str, Any]) -> str:
    coverage = _as_dict(receipt.get("coverage"))
    if _receipt_unreliable(receipt) or coverage.get("empty") or _int(receipt.get("parse_errors")):
        return "warn"
    if _bool(receipt.get("hard_pass")) and _bool(receipt.get("infra_ok")):
        return "pass"
    return "fail"


def _verdict_text(receipt: dict[str, Any]) -> str:
    coverage = _as_dict(receipt.get("coverage"))
    empty = _bool(coverage.get("empty"))
    hard_pass = _bool(receipt.get("hard_pass"))
    infra_ok = _bool(receipt.get("infra_ok"))
    parse_errors = _int(receipt.get("parse_errors"))
    runs = len([item for item in _as_list(receipt.get("runs")) if isinstance(item, dict)])
    if _receipt_unreliable(receipt):
        return (
            f"hard_pass=false. Unsupported or malformed receipt. Honest unknown verdict. "
            f"infra_ok={str(infra_ok).lower()}. runs={runs}. parse_errors={parse_errors}. "
            "Limitation recorded. Not success."
        )
    if empty:
        return (
            f"hard_pass=false because coverage.empty=true. infra_ok={str(infra_ok).lower()}. "
            f"runs={runs}. parse_errors={parse_errors}. Empty coverage is not success."
        )
    return (
        f"hard_pass={str(hard_pass).lower()}. infra_ok={str(infra_ok).lower()}. "
        f"runs={runs}. parse_errors={parse_errors}."
    )


def _section_verdict(receipt: dict[str, Any]) -> str:
    coverage = _as_dict(receipt.get("coverage"))
    runs = [item for item in _as_list(receipt.get("runs")) if isinstance(item, dict)]
    banner = _verdict_text(receipt)
    return (
        '<section id="verdict">'
        "<h2>Verdict</h2>"
        f'<p class="banner {_verdict_class(receipt)}">{_esc(banner, 480)}</p>'
        + _facts(
            [
                ("hard_pass", _bool(receipt.get("hard_pass"))),
                ("coverage.empty", _bool(coverage.get("empty"))),
                ("infra_ok", _bool(receipt.get("infra_ok"))),
                ("run count", len(runs)),
                ("parse_errors", _int(receipt.get("parse_errors"))),
                (
                    "behavioral decided",
                    coverage.get("applicable_hard_fail_decided", UNKNOWN),
                ),
                (
                    "hard gates unknown",
                    coverage.get("applicable_hard_fail_unknown", UNKNOWN),
                ),
            ]
        )
        + "</section>"
    )


def _section_coverage(receipt: dict[str, Any]) -> str:
    coverage = _as_dict(receipt.get("coverage"))
    requested = [_redact_text(item) for item in _as_list(receipt.get("harnesses_requested"))]
    found = [_redact_text(item) for item in _as_list(receipt.get("harnesses_found"))]
    missing = coverage.get("missing_requested_inputs")
    if not isinstance(missing, list):
        missing = []
    gap_labels = []
    for item in missing:
        if isinstance(item, dict):
            gap_labels.append(_redact_text(item.get("harness") or item.get("reason") or item))
        else:
            gap_labels.append(_redact_text(item))
    usage_unknown = False
    for run in _as_list(receipt.get("runs")):
        if isinstance(run, dict) and not _usage_known(run.get("tokens")):
            usage_unknown = True
            break
    usage_note = "Usage/cost is unknown for at least one run and is not treated as zero." if usage_unknown else "No unknown usage flagged on ingested runs."
    if _bool(coverage.get("empty")):
        usage_note = "Coverage is empty. Unknown usage stays unknown; no totals were invented."
    return (
        '<section id="coverage">'
        "<h2>Coverage</h2>"
        + _facts(
            [
                ("harnesses requested", ", ".join(requested) if requested else UNKNOWN),
                ("harnesses found", ", ".join(found) if found else UNKNOWN),
                ("sessions ingested", coverage.get("sessions_ingested", len(_as_list(receipt.get("runs"))))),
                ("sessions malformed", coverage.get("sessions_malformed", receipt.get("parse_errors"))),
                ("missing requested inputs", ", ".join(gap_labels) if gap_labels else "none"),
                ("empty", _bool(coverage.get("empty"))),
            ]
        )
        + f'<p class="note">{_esc(usage_note, 400)}</p>'
        + "</section>"
    )


def _section_trends(receipt: dict[str, Any]) -> str:
    runs = [item for item in _as_list(receipt.get("runs")) if isinstance(item, dict)]
    sessions, hard_fail, tokens = _trend_points(runs)
    if not runs:
        charts = (
            _svg_chart("Sessions / day", [], "sessions")
            + _svg_chart("Hard-fail / day", [], "runs")
            + _svg_chart("Tokens / day", [], "tokens")
        )
        note = '<p class="note">No runs to chart. Trends remain present and unmeasurable rather than zero.</p>'
    elif not sessions:
        charts = (
            _svg_chart("Sessions / day", [], "sessions")
            + _svg_chart("Hard-fail / day", [], "runs")
            + _svg_chart("Tokens / day", [(UNKNOWN, None)], "tokens")
        )
        note = '<p class="note">Run timestamps are unknown. Token usage is marked unmeasurable, never zero.</p>'
    else:
        charts = (
            _svg_chart("Sessions / day", sessions, "sessions")
            + _svg_chart("Hard-fail / day", hard_fail, "runs")
            + _svg_chart("Tokens / day", tokens, "tokens")
        )
        note = '<p class="note">Token series omit unknown observations. Unmeasurable days are marked, not plotted as zero.</p>'
    return f'<section id="trends"><h2>Trends</h2><div class="charts">{charts}</div>{note}</section>'


def _activation_cell(entry: dict[str, Any]) -> str:
    rows = []
    for item in _as_list(entry.get("activations")):
        if not isinstance(item, dict):
            rows.append(_esc(item))
            continue
        rows.append(
            f"{_esc(item.get('source') or UNKNOWN)} / {_esc(item.get('confidence') or UNKNOWN)}"
            f" × {_esc(item.get('count') if item.get('count') is not None else 1)}"
        )
    kind = entry.get("activation_kind")
    if kind:
        rows.append(f"kind={_esc(kind)}")
    return "<br>".join(rows) if rows else _esc("none")


def _section_skills(receipt: dict[str, Any]) -> str:
    headers = [
        "name",
        "digest",
        "version",
        "activations",
        "hard fails",
        "ownership",
        "historical digest",
        "on-disk digest",
    ]
    rows: list[list[str]] = []
    ids: list[str] = []
    used: set[str] = set()
    for index, entry in enumerate(_as_list(receipt.get("skills"))):
        if not isinstance(entry, dict):
            continue
        historical = entry.get("historical_loaded_digest") or entry.get("digest") or UNKNOWN
        current = entry.get("current_on_disk_digest") or UNKNOWN
        digest8 = _digest8(historical if not _is_unknown(historical) else current)
        ident = _html_id("skill", digest8)
        if ident in used:
            ident = _html_id("skill", f"{digest8}-{index}")
        used.add(ident)
        ids.append(ident)
        ownership = entry.get("ownership") or UNKNOWN
        opaque = ownership in {"external", "third_party", "unresolved"}
        own_label = _esc(ownership)
        if opaque:
            own_label += " <strong>opaque third-party</strong>"
        version = entry.get("version")
        rows.append(
            [
                _esc(entry.get("name") or UNKNOWN),
                f'<span class="mono">{_esc(entry.get("digest") or historical)}</span>',
                _esc(version) if not _is_unknown(version) else _esc("—"),
                _activation_cell(entry),
                _esc(entry.get("hard_fail_count", 0)),
                own_label,
                f'<span class="mono">{_esc(historical)}</span>',
                f'<span class="mono">{_esc(current)}</span>',
            ]
        )
    note = '<p class="note">Historical loaded digest is distinct from current on-disk digest. Display names are not identity.</p>'
    if not rows:
        note = '<p class="note">No skill registry rows. Section remains for empty evaluations.</p>' + note
    return f'<section id="skills"><h2>Skills</h2>{_table(headers, rows, row_ids=ids)}{note}</section>'


def _section_sessions(receipt: dict[str, Any]) -> str:
    headers = ["run.id", "harness", "native id", "display name", "model", "tokens", "checks failed", "source"]
    rows: list[list[str]] = []
    ids: list[str] = []
    details: list[str] = []
    used: set[str] = set()
    for index, run in enumerate(_as_list(receipt.get("runs"))):
        if not isinstance(run, dict):
            continue
        run_id = run.get("id") or f"run-{index}"
        ident = _html_id("session", run_id)
        if ident in used:
            ident = _html_id("session", f"{run_id}-{index}")
        used.add(ident)
        ids.append(ident)
        failed = _failed_checks(run)
        fail_ids = ", ".join(_redact_text(item.get("id") or UNKNOWN) for item in failed) or "none"
        rows.append(
            [
                f'<span class="mono">{_esc(run_id)}</span>',
                _esc(run.get("harness") or UNKNOWN),
                f'<span class="mono">{_esc(_native_label(run.get("native_identity")))}</span>',
                _esc(run.get("display_name") or UNKNOWN),
                _esc(run.get("model") or UNKNOWN),
                _esc(_token_display(run.get("tokens"))),
                _esc(fail_ids, 320),
                _source_link(run.get("source_path")),
            ]
        )
        evidence_rows = []
        for check in failed:
            for pointer in _as_list(check.get("evidence")):
                if isinstance(pointer, dict):
                    evidence_rows.append(_pointer_cell({**pointer, "check_id": check.get("id")}))
        evidence_html = "<br>".join(evidence_rows) if evidence_rows else _esc("none")
        details.append(
            f'<details><summary>Structural drilldown {_esc(run_id)}</summary>'
            "<h3>Lineage</h3>"
            + _lineage_block(run.get("lineage"))
            + "<h3>Tool pairing</h3>"
            + _pairing_block(run)
            + "<h3>Lifecycle</h3>"
            + _lifecycle_block(run)
            + "<h3>Evidence pointers</h3>"
            + f"<p>{evidence_html}</p>"
            + '<p class="note">Drilldown is structural metadata only. Transcripts, prompts, payloads, and terminal output are omitted.</p>'
            + "</details>"
        )
    parse_note = ""
    parse_errors = _int(receipt.get("parse_errors"))
    if parse_errors:
        parse_note = f'<p class="note">parse_errors={_esc(parse_errors)} counted, not dropped.</p>'
    if not rows:
        parse_note += '<p class="note">No sessions ingested.</p>'
    return (
        f'<section id="sessions"><h2>Sessions</h2>{_table(headers, rows, row_ids=ids)}'
        + "".join(details)
        + parse_note
        + "</section>"
    )


def _section_failures(receipt: dict[str, Any]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in _as_list(receipt.get("runs")):
        if not isinstance(run, dict):
            continue
        for check in _failed_checks(run):
            check_id = str(check.get("id") or UNKNOWN)
            grouped.setdefault(check_id, []).append({"run": run, "check": check})
    for check in _as_list(receipt.get("checks")):
        if not isinstance(check, dict) or check.get("status") != "fail":
            continue
        check_id = str(check.get("id") or UNKNOWN)
        grouped.setdefault(check_id, [])
    parts = ['<section id="failures"><h2>Failures</h2>']
    if not grouped:
        parts.append('<p class="note">No failing checks recorded.</p>')
    for check_id in sorted(grouped):
        ident = _html_id("check", check_id)
        items = grouped[check_id]
        rows = []
        row_ids = []
        for offset, item in enumerate(items):
            run = _as_dict(item.get("run"))
            check = _as_dict(item.get("check"))
            pointers = [_pointer_cell(ptr) for ptr in _as_list(check.get("evidence")) if isinstance(ptr, dict)]
            rows.append(
                [
                    f'<span class="mono">{_esc(run.get("id") or UNKNOWN)}</span>',
                    _esc(check.get("class") or UNKNOWN),
                    _esc(check.get("channel") or UNKNOWN),
                    _esc(check.get("observed") or UNKNOWN),
                    "<br>".join(pointers) if pointers else _esc("none"),
                ]
            )
            row_ids.append(f"{ident}-{offset}")
        parts.append(f'<h3 id="{_attr(ident)}">{_esc(check_id)}</h3>')
        parts.append(
            _table(
                ["run", "class", "channel", "observed", "evidence"],
                rows,
                row_ids=row_ids,
            )
        )
    parts.append("</section>")
    return "".join(parts)


def _quality_delta_allowed(comparison: dict[str, Any]) -> bool:
    catalog = _as_dict(comparison.get("catalog"))
    cohort = _as_dict(comparison.get("cohort"))
    redaction = _as_dict(comparison.get("redaction_policy"))
    measurement = _as_dict(comparison.get("measurement"))
    gates = (
        catalog.get("compatible") is True,
        cohort.get("compatible") is True,
        redaction.get("compatible") is True,
        measurement.get("compatible") is True,
    )
    if not all(gates):
        return False
    if "quality_delta_allowed" in comparison and comparison.get("quality_delta_allowed") is not True:
        return False
    if "compatible" in comparison and comparison.get("compatible") is not True:
        return False
    return True


def _skill_digest_pair(receipt: dict[str, Any], comparison: dict[str, Any]) -> str:
    cohort = _as_dict(comparison.get("cohort"))
    listed = [_redact_text(item) for item in _as_list(cohort.get("skill_digests"))]
    historical: list[str] = []
    current: list[str] = []
    for entry in _as_list(receipt.get("skills")):
        if not isinstance(entry, dict):
            continue
        historical.append(_redact_text(entry.get("historical_loaded_digest") or entry.get("digest") or UNKNOWN))
        current.append(_redact_text(entry.get("current_on_disk_digest") or UNKNOWN))
    bits = []
    if listed:
        bits.append("cohort digests: " + ", ".join(listed))
    bits.append("historical: " + (", ".join(historical) if historical else UNKNOWN))
    bits.append("current on-disk: " + (", ".join(current) if current else UNKNOWN))
    return "; ".join(bits)


def _section_comparisons(receipt: dict[str, Any]) -> str:
    parts = ['<section id="comparisons"><h2>Comparisons</h2>']
    comparisons = [item for item in _as_list(receipt.get("comparisons")) if isinstance(item, dict)]
    if not comparisons:
        parts.append('<p class="note">No eligible baseline. Quality delta is not inferred.</p>')
        parts.append("</section>")
        return "".join(parts)
    for index, comparison in enumerate(comparisons, start=1):
        ident = _html_id("compare", index)
        allowed = _quality_delta_allowed(comparison)
        compatible = allowed
        catalog = _as_dict(comparison.get("catalog"))
        cohort = _as_dict(comparison.get("cohort"))
        redaction = _as_dict(comparison.get("redaction_policy"))
        measurement = _as_dict(comparison.get("measurement"))
        counts = _as_dict(comparison.get("counts"))
        reasons = comparison.get("unmeasurable_reasons") or []
        if not isinstance(reasons, list):
            reasons = [reasons]
        parts.append(f'<article id="{_attr(ident)}"><h3>Comparison {index}</h3>')
        parts.append(
            _facts(
                [
                    ("compatible", compatible),
                    ("quality delta allowed", allowed),
                    ("catalog baseline", catalog.get("baseline", UNKNOWN)),
                    ("catalog candidate", catalog.get("candidate", UNKNOWN)),
                    ("cohort harnesses", ", ".join(_redact_text(item) for item in _as_list(cohort.get("harnesses"))) or UNKNOWN),
                    ("redaction baseline", redaction.get("baseline", UNKNOWN)),
                    ("redaction candidate", redaction.get("candidate", UNKNOWN)),
                    ("measurement compatible", measurement.get("compatible", UNKNOWN)),
                    ("skill digests", _skill_digest_pair(receipt, comparison)),
                    ("unmeasurable reasons", ", ".join(_redact_text(item) for item in reasons) or "none"),
                ]
            )
        )
        if allowed:
            parts.append(
                _table(
                    ["improved", "regressed", "equal", "unmeasurable"],
                    [
                        [
                            _esc(counts.get("improved", 0)),
                            _esc(counts.get("regressed", 0)),
                            _esc(counts.get("equal", 0)),
                            _esc(counts.get("unmeasurable", 0)),
                        ]
                    ],
                )
            )
        else:
            parts.append(
                '<p class="banner warn">No quality delta. Incompatible or incomplete comparison '
                "is not scored. Historical and current skill digests are listed above.</p>"
            )
        parts.append("</article>")
    parts.append("</section>")
    return "".join(parts)


def _section_recommendations(receipt: dict[str, Any]) -> str:
    parts = ['<section id="recommendations"><h2>Recommendations</h2>']
    rows = [item for item in _as_list(receipt.get("recommendations")) if isinstance(item, dict)]
    coverage = _as_dict(receipt.get("coverage"))
    if not rows:
        if _bool(coverage.get("empty")):
            parts.append(
                '<p class="note">No recommendation rows on an empty evaluation. '
                "A limitation is required by contract; none was supplied. No patch was invented.</p>"
            )
        else:
            parts.append('<p class="note">No recommendation rows.</p>')
        parts.append("</section>")
        return "".join(parts)
    used: set[str] = set()
    for index, item in enumerate(rows, start=1):
        raw_id = str(item.get("id") or f"{index:03d}")
        slug = raw_id[4:] if raw_id.startswith("rec-") else raw_id
        contract_id = _html_id("rec", slug)
        if contract_id in used:
            contract_id = _html_id("rec", f"{index:03d}")
        used.add(contract_id)
        limitation = item.get("limitation")
        target = item.get("target")
        target_label = UNKNOWN
        if isinstance(target, dict):
            target_label = (
                f"{_redact_text(target.get('kind') or UNKNOWN)} "
                f"{_redact_text(target.get('name') or UNKNOWN)} "
                f"{_redact_text(target.get('path') or UNKNOWN)} "
                f"digest={_redact_text(target.get('digest') or UNKNOWN)}"
            )
        elif target is None and limitation:
            target_label = "none (limitation)"
        evidence = [
            _pointer_cell(ptr)
            for ptr in _as_list(item.get("evidence"))
            if isinstance(ptr, dict)
        ]
        parts.append(f'<article id="{_attr(contract_id)}">')
        if limitation and item.get("action") in (None, UNKNOWN):
            parts.append(f"<h3>Limitation {_esc(item.get('id') or index)}</h3>")
            parts.append(_facts([("limitation", limitation), ("confidence", item.get("confidence") or "none")]))
            parts.append('<p class="note">Insufficient evidence. No invented patch.</p>')
        else:
            parts.append(f"<h3>{_esc(item.get('id') or f'rec-{index:03d}')}</h3>")
            parts.append(
                _facts(
                    [
                        ("target", target_label),
                        ("action", item.get("action") or UNKNOWN),
                        ("rationale", item.get("rationale") or UNKNOWN),
                        ("verification", item.get("verification") or UNKNOWN),
                        ("confidence", item.get("confidence") or UNKNOWN),
                    ]
                )
            )
        if evidence:
            parts.append("<p>" + "<br>".join(evidence) + "</p>")
        parts.append("</article>")
    parts.append("</section>")
    return "".join(parts)


def _snapshot_records(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(native: Any, path: Any, digest: Any, parser: Any, version: Any) -> None:
        sha = _redact_text(digest or UNKNOWN, 128)
        source = _redact_text(path or UNKNOWN, 8000)
        key = (sha, source)
        if key in seen:
            return
        seen.add(key)
        records.append(
            {
                "native_identity": native if not _is_unknown(native) else UNKNOWN,
                "source_path": path if not _is_unknown(path) else UNKNOWN,
                "sha256": digest if not _is_unknown(digest) else UNKNOWN,
                "parser": parser if not _is_unknown(parser) else UNKNOWN,
                "parser_version": version if not _is_unknown(version) else UNKNOWN,
            }
        )

    provenance = _as_dict(receipt.get("provenance"))
    for item in _as_list(provenance.get("snapshots")):
        if isinstance(item, dict):
            add(
                item.get("native_identity"),
                item.get("source_path"),
                item.get("sha256"),
                item.get("parser"),
                item.get("parser_version"),
            )
        else:
            add(UNKNOWN, UNKNOWN, item, UNKNOWN, UNKNOWN)
    for run in _as_list(receipt.get("runs")):
        if not isinstance(run, dict):
            continue
        snapshot = _as_dict(run.get("source_snapshot"))
        add(
            run.get("id") or _native_label(run.get("native_identity")),
            run.get("source_path"),
            snapshot.get("sha256"),
            run.get("parser"),
            run.get("parser_version"),
        )
    return records


def _provenance_pairs(receipt: dict[str, Any]) -> list[tuple[str, Any]]:
    provenance = _as_dict(receipt.get("provenance"))
    redaction = _as_dict(receipt.get("redaction"))
    snapshots = _snapshot_records(receipt)
    return [
        ("generator", f"{GENERATOR} {GENERATOR_VERSION}"),
        ("catalog_id", receipt.get("catalog_id") or CATALOG_ID),
        ("schema", receipt.get("schema") or UNKNOWN),
        ("parser", provenance.get("parser") or UNKNOWN),
        ("parser_version", provenance.get("parser_version") or UNKNOWN),
        ("redaction", redaction.get("policy") or UNKNOWN),
        ("redaction applied", redaction.get("applied", True)),
        ("snapshot count", len(snapshots)),
    ]


def _section_provenance(receipt: dict[str, Any]) -> str:
    notice = (
        "Redacted local report. No raw prompts, tool payloads, secrets, or terminal output. "
        "WorkGraph stages/**/full.md is never inlined. Evidence is source path, snapshot hash, "
        "parser version, line range, and evidence hash. Each consumed snapshot keeps its full hash."
    )
    snapshots = _snapshot_records(receipt)
    rows = [
        [
            _esc(item.get("native_identity"), 240),
            f'<span class="mono">{_esc(item.get("source_path"), 8000)}</span>',
            f'<span class="mono">{_esc(item.get("sha256"), 128)}</span>',
            _esc(f"{item.get('parser')}/{item.get('parser_version')}", 240),
        ]
        for item in snapshots
    ]
    table = _table(
        ["native / run", "source path", "sha256", "parser"],
        rows,
    )
    return (
        '<section id="provenance"><h2>Provenance</h2>'
        + _facts(_provenance_pairs(receipt))
        + table
        + f'<p class="note">{_esc(notice, 480)}</p>'
        + "</section>"
    )


def _section_footer(receipt: dict[str, Any]) -> str:
    pairs = _provenance_pairs(receipt)
    compact = " · ".join(f"{key}: {_redact_text(value, 240)}" for key, value in pairs)
    compact += " · full snapshot identities in Provenance (#provenance); footer is not exhaustive"
    return (
        f'<footer id="footer"><p>{_esc(compact, 800)}</p>'
        '<p>Offline file. No network, no JavaScript, no CDN.</p></footer>'
    )


def render_html(receipt: Any) -> str:
    document = coerce_receipt(receipt)
    title = "Session evaluation"
    coverage = _as_dict(document.get("coverage"))
    if _bool(coverage.get("empty")):
        title = "Session evaluation — empty coverage"
    elif _int(document.get("parse_errors")):
        title = "Session evaluation — malformed records counted"
    sections = [
        _section_verdict(document),
        _section_coverage(document),
        _section_trends(document),
        _section_skills(document),
        _section_sessions(document),
        _section_failures(document),
        _section_comparisons(document),
        _section_recommendations(document),
        _section_provenance(document),
        _section_footer(document),
    ]
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<a class="skip" href="#verdict">Skip to verdict</a>\n'
        "<header><h1>Session evaluation</h1>"
        '<p class="lede">Compact verdict and coverage, then table-led evidence. Structural drilldown only.</p>'
        "</header>\n"
        + "\n".join(sections)
        + "\n</body>\n</html>\n"
    )


def render_report(receipt: Any, *, out: str | Path) -> Path:
    """Write an immutable standalone ``report.html``. Returns the actual path."""

    if out is None:
        raise ReportError("out is required")
    html_text = render_html(receipt)
    payload = html_text.encode("utf-8")
    out_dir = _output_root(out)
    if out_dir.suffix.lower() == ".html":
        requested = out_dir
    else:
        requested = out_dir / "report.html"
    return _write_immutable(requested, payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval-report",
        description="Render a self-contained offline HTML report from a redacted session-eval receipt.",
    )
    parser.add_argument("--receipt", required=True, help="path to styrir-session-eval/v0 receipt.json")
    parser.add_argument("--out", required=True, help="output directory or report.html path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = Path(args.receipt).expanduser()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        parser.error(f"unreadable receipt: {path}: {exc}")
        return 2
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = _malformed_envelope("receipt_unparseable")
    try:
        written = render_report(payload, out=args.out)
    except ReportError as exc:
        parser.error(str(exc))
        return 2
    print(json.dumps({"report": str(written)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
