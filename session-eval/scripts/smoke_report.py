#!/usr/bin/env python3
"""Self-contained smoke for session-eval report HTML.

Generates normal, empty, malformed, markup-secret, and baseline receipts and
renders them through report.render_report. Checks required section ids, stable
row ids, HTML escaping, secret absence, unmeasurable token trends, incompatible
comparisons (no quality delta, both skill digests), and source-hash presence.

Does not ingest live sessions, open raw payloads, call providers, or require
sibling judge/recommend modules. Parent runs this after integration.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import report as report_mod

SCHEMA = "styrir-session-eval/v0"
CATALOG = "session-eval-check-catalog/v1"
UNKNOWN = "unknown"
REQUIRED_IDS = (
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
SECRET = "sk-abcdefghijklmnopqrstuvwxyz012345"
MARKUP = '<script>alert("xss")</script>'
FULL_MD_MARKER = "FULLMD-SHOULD-NEVER-APPEAR-IN-REPORT-9f3c"
SNAP_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SNAP_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
HIST_DIGEST = "sha256:hist111111111111111111111111111111111111111111111111111111111111"
DISK_DIGEST = "sha256:disk222222222222222222222222222222222222222222222222222222222222"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def evidence(source: str, snapshot: str, start: int = 1, end: int = 2) -> dict[str, Any]:
    return {
        "source_path": source,
        "snapshot_hash": snapshot,
        "parser_version": "1.0.0",
        "event_range": {"start_line": start, "end_line": end},
        "evidence_hash": "sha256:ev" + snapshot[:8],
    }


def check_row(check_id: str, status: str, *, channel: str = "behavior", observed: str | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "class": "hard_fail" if check_id.startswith("tool.") or check_id.startswith("session.") else "expected_behavior",
        "kind": "code",
        "channel": channel,
        "observed": observed or status,
        "error": None,
        "evidence": [evidence("/tmp/session.jsonl", SNAP_A, 10, 12)],
    }


def run_record(
    native_id: str,
    *,
    display_name: str | None = None,
    tokens: Any = None,
    checks: list[dict[str, Any]] | None = None,
    parse_errors: list[Any] | None = None,
    started_at: str = "2026-09-13T09:00:00Z",
    snapshot: str = SNAP_A,
    unpaired: bool = False,
    live: bool = False,
    source_path: str | None = None,
) -> dict[str, Any]:
    path = source_path if source_path is not None else f"/tmp/{native_id}.jsonl"
    if unpaired:
        tool_calls = [{"id": "call-1", "name": "read", "status": "unpaired"}]
        lifecycle_state = "terminal"
    elif live:
        tool_calls = [{"id": "call-1", "name": "read", "status": "pending"}]
        lifecycle_state = "live"
    else:
        tool_calls = [
            {
                "id": "call-1",
                "name": "read",
                "status": "ok",
                "result_source_line": 2,
                "result_source_path": path,
            }
        ]
        lifecycle_state = "terminal"
    return {
        "id": f"claude:{native_id}",
        "harness": "claude",
        "native_identity": {"id": native_id, "kind": "session_id", "source": "sessionId"},
        "display_name": display_name if display_name is not None else native_id,
        "parser": "claude-jsonl-adapter",
        "parser_version": "1.0.0",
        "source_path": path,
        "source_snapshot": {
            "sha256": snapshot,
            "files": [{"path": path, "role": "primary", "sha256": snapshot}],
        },
        "started_at": started_at,
        "ended_at": "2026-09-13T10:00:00Z" if lifecycle_state == "terminal" else UNKNOWN,
        "cwd": UNKNOWN,
        "model": "test-model",
        "tokens": tokens
        if tokens is not None
        else {"input": 3, "output": 1, "cache_read": 0, "cache_create": 0, "total": 4},
        "cost_usd": UNKNOWN,
        "usage_provenance": [],
        "skills": [
            {
                "name": "example",
                "path": "/Users/brooks/Code/skills/example/SKILL.md",
                "digest": HIST_DIGEST,
                "source": "prompt_context",
                "confidence": "high",
            }
        ],
        "lineage": {
            "parent": UNKNOWN,
            "children": [],
            "attempt": {"id": "a1", "number": 1},
            "continuation_of": UNKNOWN,
            "continued_by": UNKNOWN,
        },
        "turns": [{"id": "t1", "role": "assistant", "tool_calls": tool_calls, "errors": [], "source_line": 4, "lineage": {"parent": UNKNOWN}}],
        "checks": checks
        or [
            check_row("tool.unpaired", "pass"),
            check_row("session.incomplete", "pass"),
        ],
        "lifecycle": {
            "state": lifecycle_state,
            "evidence": [evidence(path, snapshot, 20, 20)],
        },
        "parse_errors": parse_errors or [],
    }


def receipt(
    runs: list[dict[str, Any]],
    *,
    empty: bool = False,
    parse_errors: int = 0,
    hard_pass: bool = False,
    infra_ok: bool = True,
    catalog_id: str = CATALOG,
    comparisons: list[dict[str, Any]] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    skills: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if skills is None:
        skills = [
            {
                "name": "example",
                "path": "/Users/brooks/Code/skills/example/SKILL.md",
                "digest": HIST_DIGEST,
                "version": "1.2.0",
                "activations": [{"source": "prompt_context", "confidence": "high", "count": 1}],
                "hard_fail_count": 1 if any(_failed(run) for run in runs) else 0,
                "last_seen": "2026-09-13T10:00:00Z",
                "historical_loaded_digest": HIST_DIGEST,
                "current_on_disk_digest": DISK_DIGEST,
                "ownership": "first_party",
                "activation_kind": "authoritative",
            }
        ]
    if recommendations is None:
        if empty or not runs:
            recommendations = [
                {
                    "id": "rec-empty",
                    "target": None,
                    "action": None,
                    "rationale": None,
                    "evidence": [],
                    "verification": None,
                    "confidence": "none",
                    "limitation": "coverage.empty; no sessions ingested; no patch invented",
                }
            ]
        else:
            recommendations = [
                {
                    "id": "rec-001",
                    "target": {
                        "kind": "skill",
                        "path": "/Users/brooks/Code/skills/example/SKILL.md",
                        "digest": HIST_DIGEST,
                        "name": "example",
                    },
                    "action": "State unpaired tools after terminal evidence as failure.",
                    "rationale": "Recurring tool.unpaired on this digest.",
                    "evidence": [dict(evidence("/tmp/alpha.jsonl", SNAP_A, 10, 40), check_id="tool.unpaired")],
                    "verification": "Re-run a comparable session; preserve the original snapshot.",
                    "confidence": "high",
                    "limitation": None,
                }
            ]
    snapshots = []
    for run in runs:
        snapshots.append(
            {
                "native_identity": (run.get("native_identity") or {}).get("id"),
                "source_path": run.get("source_path"),
                "sha256": (run.get("source_snapshot") or {}).get("sha256"),
                "parser": run.get("parser"),
                "parser_version": run.get("parser_version"),
            }
        )
    return {
        "schema": SCHEMA,
        "catalog_id": catalog_id,
        "generated_at": "2026-09-14T00:00:00Z",
        "since": "all",
        "harnesses_requested": ["claude"],
        "harnesses_found": ["claude"] if runs else [],
        "coverage": {
            "sessions_ingested": len(runs),
            "sessions_malformed": 1 if parse_errors else 0,
            "applicable_hard_fail_decided": 1 if runs else 0,
            "applicable_hard_fail_unknown": 0,
            "missing_requested_inputs": [] if runs else [{"harness": "claude", "kind": "coverage_gap"}],
            "empty": empty or not runs,
        },
        "hard_pass": hard_pass and not empty and bool(runs),
        "infra_ok": infra_ok,
        "feedback_outcome": None,
        "redaction": {"policy": "default-local", "applied": True},
        "approvals": [],
        "runs": runs,
        "skills": skills,
        "checks": [],
        "comparisons": comparisons or [],
        "recommendations": recommendations,
        "parse_errors": parse_errors,
        "proof_gaps": [] if runs else [{"kind": "comparison.no_eligible_baseline", "reason": "no_eligible_champion"}],
        "provenance": {
            "parser": "session-eval-ingest",
            "parser_version": "1.0.0",
            "snapshots": snapshots,
        },
    }


def _failed(run: dict[str, Any]) -> bool:
    return any(item.get("status") == "fail" for item in run.get("checks") or [])


def comparison(*, compatible: bool, catalog_candidate: str = CATALOG) -> dict[str, Any]:
    counts = (
        {"improved": 1, "regressed": 0, "equal": 2, "unmeasurable": 0}
        if compatible
        else {"improved": 0, "regressed": 0, "equal": 0, "unmeasurable": 4}
    )
    return {
        "baseline_receipt": "history/baseline.json",
        "candidate_receipt": "receipt.json",
        "cohort": {
            "harnesses": ["claude"],
            "skill_digests": [HIST_DIGEST, DISK_DIGEST],
            "compatible": compatible,
        },
        "catalog": {
            "baseline": CATALOG,
            "candidate": catalog_candidate,
            "compatible": compatible,
        },
        "measurement": {
            "baseline_schema": SCHEMA,
            "candidate_schema": SCHEMA,
            "parsers": [
                {
                    "harness": "claude",
                    "baseline": {"name": "claude-jsonl-adapter", "version": "1.0.0"},
                    "candidate": {"name": "claude-jsonl-adapter", "version": "1.0.0"},
                }
            ],
            "compatible": compatible,
        },
        "redaction_policy": {
            "baseline": "default-local",
            "candidate": "default-local",
            "compatible": True,
        },
        "counts": counts,
        "unmeasurable_reasons": [] if compatible else ["catalog_mismatch"],
        "quality_delta_allowed": compatible,
        "compatible": compatible,
    }


def required_ids_present(html: str) -> None:
    for ident in REQUIRED_IDS:
        if not re.search(rf'id="{re.escape(ident)}"', html):
            raise AssertionError(f"missing required section id={ident}")


EVENT_ATTR = re.compile(r"^on[a-z]+$", re.I)
CSS_FETCH = re.compile(
    r"""(?ix)
    @import\s+(?:url\s*\(\s*)?['"]?([^'")\s]+)
    | url\s*\(\s*['"]?([^'")]+)
    """
)
URL_ATTRS = {
    "src",
    "srcset",
    "href",
    "poster",
    "data",
    "action",
    "formaction",
    "xlink:href",
    "cite",
    "background",
    "codebase",
}


def _url_kind(value: str) -> str:
    text = str(value or "").strip()
    if not text or text.startswith("#"):
        return "local"
    lowered = text.lower()
    if lowered.startswith("javascript:") or lowered.startswith("vbscript:"):
        return "javascript"
    if lowered.startswith("data:"):
        return "data"
    if lowered.startswith("//") or lowered.startswith(("http:", "https:", "ftp:")):
        return "external"
    return "local"


def _css_fetched_urls(text: str) -> list[str]:
    found: list[str] = []
    for match in CSS_FETCH.finditer(text or ""):
        url = match.group(1) or match.group(2) or ""
        if url:
            found.append(url)
    return found


def _srcset_urls(value: str) -> list[str]:
    urls: list[str] = []
    for item in str(value or "").split(","):
        token = item.strip().split(" ", 1)[0].strip()
        if token:
            urls.append(token)
    return urls


class _ActiveContentParser(HTMLParser):
    """Inspect tags/CSS for active or fetching content. Ignores inert prose."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.defects: list[str] = []
        self._style_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect_tag(tag, attrs)
        if tag.lower() == "style":
            self._style_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style" and self._style_depth:
            self._style_depth -= 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect_tag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self._inspect_css(data, "style element")

    def _inspect_css(self, text: str, where: str) -> None:
        for url in _css_fetched_urls(text):
            kind = _url_kind(url)
            if kind != "local":
                self.defects.append(f"{where} fetches {kind} url")

    def _inspect_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        mapping = {(key or "").lower(): value or "" for key, value in attrs}
        if name == "script":
            self.defects.append("active script element")
        if name == "meta" and mapping.get("http-equiv", "").lower() == "refresh":
            content = mapping.get("content", "")
            if re.search(r"url\s*=", content, re.I):
                target = re.split(r"url\s*=", content, maxsplit=1, flags=re.I)[-1].strip(" '\"")
                kind = _url_kind(target)
                if kind != "local":
                    self.defects.append(f"meta refresh {kind} url")
        for key, value in mapping.items():
            if EVENT_ATTR.match(key):
                self.defects.append(f"event handler {key}")
            if key == "style":
                self._inspect_css(value, "style attribute")
            if key not in URL_ATTRS:
                continue
            urls = _srcset_urls(value) if key == "srcset" else [value]
            for url in urls:
                kind = _url_kind(url)
                if kind != "local":
                    self.defects.append(f"{name} {key} {kind} url")


def assert_no_active_content(html: str, label: str = "html") -> None:
    parser = _ActiveContentParser()
    parser.feed(html)
    parser.close()
    if parser.defects:
        raise AssertionError(f"{label}: active content {parser.defects}")


def _checker_self_test() -> None:
    """Wording is not a network action; live tags, handlers, and fetches are."""

    assert_no_active_content(
        "<footer>No network, no JavaScript, no CDN. https://example.com is prose.</footer>",
        "inert prose",
    )
    assert_no_active_content("<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>", "escaped script text")
    dirty = {
        "script": "<script>alert(1)</script>",
        "handler": '<p onclick="x()">x</p>',
        "javascript-url": '<a href="javascript:alert(1)">x</a>',
        "img-src": '<img src="https://cdn.example/x.png" alt="">',
        "link-href": '<link rel="stylesheet" href="https://cdn.example/x.css">',
        "css-import": '<style>@import url("https://cdn.example/x.css");</style>',
        "css-url": '<div style="background:url(https://cdn.example/x.png)"></div>',
    }
    for name, sample in dirty.items():
        try:
            assert_no_active_content(sample, name)
        except AssertionError:
            continue
        raise AssertionError(f"active-content checker missed {name}")

def render_case(root: Path, name: str, payload: Any) -> tuple[Path, str]:
    out = root / name
    out.mkdir(parents=True, exist_ok=True)
    receipt_path = out / "receipt.json"
    if isinstance(payload, (dict, list)):
        write_json(receipt_path, payload)
    else:
        receipt_path.write_text(str(payload), encoding="utf-8")
    written = report_mod.render_report(payload if isinstance(payload, dict) else report_mod.coerce_receipt(payload), out=out)
    html = written.read_text(encoding="utf-8")
    required_ids_present(html)
    assert_no_active_content(html, name)
    if FULL_MD_MARKER in html:
        raise AssertionError("full.md marker leaked into HTML")
    return written, html


def assert_contains(html: str, token: str, label: str) -> None:
    if token not in html:
        raise AssertionError(f"{label}: expected {token!r} in HTML")


def assert_absent(html: str, token: str, label: str) -> None:
    if token in html:
        raise AssertionError(f"{label}: forbidden {token!r} present")


def main() -> int:
    parser = argparse.ArgumentParser(prog="session-eval-smoke-report")
    parser.add_argument(
        "--out",
        default=None,
        help="durable directory for smoke HTML cases (default: temp, deleted on exit)",
    )
    args = parser.parse_args()
    temporary = None
    if args.out:
        root = Path(args.out).expanduser()
        root.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="session-eval-report-smoke-")
        root = Path(temporary.name)
    try:
        _checker_self_test()
        planted = root / "stages" / "build" / "full.md"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(FULL_MD_MARKER + "\n", encoding="utf-8")

        normal_run = run_record(
            "alpha",
            checks=[check_row("tool.unpaired", "fail"), check_row("session.incomplete", "pass")],
            unpaired=True,
        )
        unknown_usage_run = run_record(
            "beta",
            tokens={"input": UNKNOWN, "output": UNKNOWN, "cache_read": UNKNOWN, "cache_create": UNKNOWN, "total": UNKNOWN},
            started_at="2026-09-14T09:00:00Z",
            snapshot=SNAP_B,
            checks=[check_row("tokens.unknown_not_zero", "pass")],
        )
        normal = receipt(
            [normal_run, unknown_usage_run],
            hard_pass=False,
            comparisons=[comparison(compatible=True)],
        )
        normal_path, normal_html = render_case(root, "normal", normal)
        assert_contains(normal_html, 'id="session-claude:alpha"', "normal session id")
        assert_contains(normal_html, 'id="check-tool.unpaired"', "normal failure id")
        assert_contains(normal_html, 'id="skill-', "normal skill id")
        assert_contains(normal_html, 'id="rec-', "normal recommendation id")
        assert_contains(normal_html, 'id="compare-1"', "normal comparison id")
        assert_contains(normal_html, SNAP_A, "normal source hash A")
        assert_contains(normal_html, SNAP_B, "normal source hash B")
        assert_contains(normal_html, HIST_DIGEST, "normal historical digest")
        assert_contains(normal_html, DISK_DIGEST, "normal on-disk digest")
        assert_contains(normal_html, "unmeasurable", "normal unknown usage marked")
        assert_absent(normal_html, FULL_MD_MARKER, "normal full.md")
        assert_contains(normal_html, "status=unpaired", "terminal unpaired status")
        assert_contains(normal_html, "(missing)", "terminal unpaired missing marker")
        assert_contains(normal_html, "status=ok", "resolved ok status")
        assert_contains(normal_html, "result_source_line", "canonical result pointer")
        assert_contains(normal_html, "(paired)", "resolved paired marker")
        assert_absent(normal_html, "result=unknown (unpaired)", "invented result_id unpaired")
        if "Tokens / day" in normal_html and "unmeasurable" not in normal_html:
            raise AssertionError("token chart missing unmeasurable marking")

        empty = receipt([], empty=True, hard_pass=False)
        empty_path, empty_html = render_case(root, "empty", empty)
        assert_contains(empty_html, "coverage.empty=true", "empty verdict")
        assert_contains(empty_html, "hard_pass=false", "empty hard_pass")
        assert_contains(empty_html, "limitation", "empty limitation")
        assert_contains(empty_html, "No observations", "empty trends")

        malformed_run = run_record(
            "gamma",
            parse_errors=[{"line": 3, "kind": "json"}],
            checks=[check_row("ingest.parse_error", "fail", channel="infra")],
        )
        malformed = receipt([malformed_run], parse_errors=2, hard_pass=False, infra_ok=False)
        malformed_path, malformed_html = render_case(root, "malformed", malformed)
        assert_contains(malformed_html, "parse_errors=2", "malformed count")
        assert_contains(malformed_html, "counted, not dropped", "malformed counted")

        garbage_path, garbage_html = render_case(root, "malformed-object", report_mod.coerce_receipt("not-json"))
        required_ids_present(garbage_html)
        assert_contains(garbage_html, "hard_pass=false", "garbage honest verdict")

        secret_run = run_record(
            "delta",
            display_name=f"{MARKUP} {SECRET} ok",
        )
        secret_receipt = receipt([secret_run], hard_pass=True)
        secret_path, secret_html = render_case(root, "markup-secret", secret_receipt)
        assert_absent(secret_html, SECRET, "secret token")
        assert_absent(secret_html, "<script>", "raw script element from label")
        assert_contains(secret_html, "&lt;script&gt;", "escaped markup")
        assert_contains(secret_html, "[REDACTED]", "redacted secret")

        baseline = receipt(
            [normal_run],
            hard_pass=False,
            comparisons=[
                comparison(compatible=True),
                comparison(compatible=False, catalog_candidate="session-eval-check-catalog/other"),
            ],
        )
        baseline_path, baseline_html = render_case(root, "baseline", baseline)
        assert_contains(baseline_html, 'id="compare-1"', "baseline compare 1")
        assert_contains(baseline_html, 'id="compare-2"', "baseline compare 2")
        assert_contains(baseline_html, "No quality delta", "incompatible hides delta")
        assert_contains(baseline_html, HIST_DIGEST, "baseline historical digest")
        assert_contains(baseline_html, DISK_DIGEST, "baseline current digest")
        incompatible_start = baseline_html.find('id="compare-2"')
        chunk = baseline_html[incompatible_start:].split("</article>", 1)[0]
        if "<th>improved</th>" in chunk:
            raise AssertionError("incompatible comparison emitted quality delta table")

        live_html = report_mod.render_html(receipt([run_record("liveone", live=True)]))
        assert_contains(live_html, "status=pending", "live pending status")
        assert_contains(live_html, "(unresolved)", "live unresolved not failure")
        error_run = run_record("errone")
        error_run["turns"][0]["tool_calls"][0]["status"] = "error"
        error_html = report_mod.render_html(receipt([error_run]))
        assert_contains(error_html, "status=error", "error result paired")
        assert_contains(error_html, "(paired)", "error still paired")

        vacuous = {
            "schema": "unexpected/v1",
            "coverage": {
                "empty": False,
                "applicable_hard_fail_decided": 0,
                "applicable_hard_fail_unknown": 0,
            },
            "hard_pass": True,
            "infra_ok": True,
            "runs": [],
        }
        vacuous_html = report_mod.render_html(vacuous)
        assert_contains(vacuous_html, "hard_pass=false", "vacuous fail closed")
        assert_contains(vacuous_html, "Unsupported or malformed", "vacuous unknown verdict")
        assert_contains(vacuous_html, "limitation", "vacuous limitation")
        if "banner pass" in vacuous_html:
            raise AssertionError("vacuous receipt rendered green PASS")
        valid_pass = receipt([run_record("passok")], hard_pass=True)
        valid_html = report_mod.render_html(valid_pass)
        if "banner pass" not in valid_html:
            raise AssertionError("valid pass receipt lost PASS class")
        uncertain_run = run_record("unc")
        uncertain = receipt([uncertain_run], hard_pass=True)
        uncertain["coverage"]["applicable_hard_fail_decided"] = 0
        uncertain["coverage"]["applicable_hard_fail_unknown"] = 2
        uncertain["coverage"]["empty"] = False
        uncertain_html = report_mod.render_html(uncertain)
        if "banner pass" in uncertain_html:
            raise AssertionError("undecided receipt rendered green PASS")
        if "hard_pass=false because coverage.empty=true" in uncertain_html:
            raise AssertionError("nonempty uncertain coverage marked empty")

        def comparison_html(comp: dict[str, Any]) -> str:
            return report_mod.render_html(receipt([run_record("cmp")], comparisons=[comp]))

        present_true = comparison_html(comparison(compatible=True))
        if "<th>improved</th>" not in present_true:
            raise AssertionError("all-true gates hid quality delta")
        meas_false = comparison(compatible=True)
        del meas_false["compatible"]
        del meas_false["quality_delta_allowed"]
        meas_false["measurement"]["compatible"] = False
        meas_false["counts"] = {"improved": 3, "regressed": 0, "equal": 0, "unmeasurable": 0}
        meas_html = comparison_html(meas_false)
        if "<th>improved</th>" in meas_html:
            raise AssertionError("measurement false with absent top flags still scored")
        missing_gate = comparison(compatible=True)
        del missing_gate["compatible"]
        del missing_gate["quality_delta_allowed"]
        del missing_gate["measurement"]
        missing_html = comparison_html(missing_gate)
        if "<th>improved</th>" in missing_html:
            raise AssertionError("missing measurement gate still scored")
        contradict = comparison(compatible=True)
        contradict["compatible"] = True
        contradict["quality_delta_allowed"] = True
        contradict["measurement"]["compatible"] = False
        contradict["counts"]["improved"] = 3
        contradict_html = comparison_html(contradict)
        if "<th>improved</th>" in contradict_html:
            raise AssertionError("top true nested false still scored")

        hostile_html = report_mod.render_html(
            receipt([run_record("hostile", source_path="javascript:document.body.textContent='executed'")])
        )
        lowered_hostile = hostile_html.lower()
        if 'href="javascript:' in lowered_hostile or "href='javascript:" in lowered_hostile:
            raise AssertionError("javascript source_path became a clickable href")
        for unsafe in (
            "https://example.invalid/x",
            "http://example.invalid/x",
            "data:text/html,hi",
            "//cdn.example/x",
        ):
            unsafe_html = report_mod.render_html(receipt([run_record("u", source_path=unsafe)]))
            if f'href="{unsafe}"' in unsafe_html or f"href='{unsafe}'" in unsafe_html:
                raise AssertionError(f"unsafe source_path linked: {unsafe}")
        reserved_html = report_mod.render_html(receipt([run_record("hashy", source_path="/tmp/a#b.jsonl")]))
        if "file:///tmp/a%23b.jsonl" not in reserved_html:
            raise AssertionError("reserved # in local path was not encoded")
        if 'href="/tmp/a#b.jsonl"' in reserved_html:
            raise AssertionError("raw # path used as href fragment")
        space_html = report_mod.render_html(receipt([run_record("spc", source_path="/tmp/a b.jsonl")]))
        if "file:///tmp/a%20b.jsonl" not in space_html:
            raise AssertionError("space in local path was not encoded")
        query_html = report_mod.render_html(receipt([run_record("qry", source_path="/tmp/a?b.jsonl")]))
        if "file:///tmp/a%3Fb.jsonl" not in query_html:
            raise AssertionError("question mark in local path was not encoded")
        pct_html = report_mod.render_html(receipt([run_record("pct", source_path="/tmp/a%b.jsonl")]))
        if "file:///tmp/a%25b.jsonl" not in pct_html:
            raise AssertionError("percent in local path was not encoded")

        many_runs = [
            run_record(f"s{index}", snapshot=f"{index:064x}", checks=[check_row("session.incomplete", "pass")])
            for index in range(120)
        ]
        many_html = report_mod.render_html(receipt(many_runs, hard_pass=False))
        for index in range(120):
            digest = f"{index:064x}"
            if digest not in many_html:
                raise AssertionError(f"snapshot hash truncated: {digest}")
        footer_html = many_html[many_html.find('id="footer"') :]
        if "#provenance" not in footer_html and "not exhaustive" not in footer_html:
            raise AssertionError("footer omitted provenance pointer after compacting")

        # CLI path: malformed file still renders.
        cli_dir = root / "cli-malformed"
        cli_dir.mkdir()
        bad_receipt = cli_dir / "receipt.json"
        bad_receipt.write_text("{not json", encoding="utf-8")
        import subprocess

        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "report.py"), "--receipt", str(bad_receipt), "--out", str(cli_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(f"report CLI failed on malformed receipt: {completed.stderr}")
        cli_summary = json.loads(completed.stdout)
        cli_html = Path(cli_summary["report"]).read_text(encoding="utf-8")
        required_ids_present(cli_html)

        # Same bytes reuse, different bytes do not overwrite.
        first = report_mod.render_report(normal, out=root / "immutable")
        second = report_mod.render_report(normal, out=root / "immutable")
        if first != second:
            raise AssertionError("identical report bytes must reuse the path")
        third = report_mod.render_report(empty, out=root / "immutable")
        if third == first:
            raise AssertionError("changed report overwrote immutable path")
        if first.read_text(encoding="utf-8") != normal_html and SNAP_A not in first.read_text(encoding="utf-8"):
            raise AssertionError("former report bytes were mutated")

        print(
            json.dumps(
                {
                    "ok": True,
                    "cases": {
                        "normal": str(normal_path),
                        "empty": str(empty_path),
                        "malformed": str(malformed_path),
                        "malformed_object": str(garbage_path),
                        "markup_secret": str(secret_path),
                        "baseline": str(baseline_path),
                    },
                },
                indent=2,
            )
        )
    finally:
        if temporary is not None:
            temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
