#!/usr/bin/env python3
"""CLI smoke for session-eval history against synthetic SKILL.md files.

Creates local skill files and canonical receipts, invokes ``history.py``, and
prints a machine-readable result.  No live transcripts or provider calls.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).with_name("history.py")
UNKNOWN = "unknown"
SCHEMA = "styrir-session-eval/v0"
CATALOG = "session-eval-check-catalog/v1"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


def check(check_id: str, status: str, channel: str = "behavior") -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "class": "hard_fail",
        "kind": "code",
        "channel": channel,
        "observed": status,
        "error": None,
        "evidence": [],
    }


def run_record(
    native_id: str,
    checks: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    *,
    parser_version: str = "1.0.0",
    tokens: dict[str, Any] | None = None,
    cost: Any = 1.0,
) -> dict[str, Any]:
    return {
        "id": f"claude:{native_id}",
        "harness": "claude",
        "native_identity": {"id": native_id, "kind": "session_id", "source": "sessionId"},
        "display_name": native_id,
        "parser": "claude-jsonl-adapter",
        "parser_version": parser_version,
        "source_path": f"/tmp/{native_id}.jsonl",
        "source_snapshot": {"sha256": "snap", "files": []},
        "started_at": "2026-09-13T09:00:00Z",
        "ended_at": "2026-09-13T10:00:00Z",
        "cwd": UNKNOWN,
        "model": "test",
        "tokens": tokens
        or {"input": 3, "output": 1, "cache_read": 0, "cache_create": 0, "total": 4},
        "cost_usd": cost,
        "usage_provenance": [],
        "skills": skills,
        "lineage": {},
        "turns": [],
        "checks": checks,
        "lifecycle": {"state": "terminal", "evidence": []},
    }


def receipt(
    runs: list[dict[str, Any]],
    *,
    generated_at: str,
    hard_pass: bool = True,
    catalog_id: str = CATALOG,
    schema: str = SCHEMA,
    empty: bool = False,
) -> dict[str, Any]:
    ids = []
    seen: set[str] = set()
    for item in runs:
        for row in item.get("checks") or []:
            if row["id"] not in seen:
                seen.add(row["id"])
                ids.append({"id": row["id"], "class": row.get("class"), "kind": row.get("kind"), "channel": row.get("channel")})
    return {
        "schema": schema,
        "catalog_id": catalog_id,
        "generated_at": generated_at,
        "since": UNKNOWN,
        "harnesses_requested": ["claude"],
        "harnesses_found": ["claude"],
        "coverage": {
            "sessions_ingested": len(runs),
            "empty": empty,
            "missing_requested_inputs": [],
            "applicable_hard_fail_unknown": 0,
        },
        "hard_pass": hard_pass,
        "infra_ok": True,
        "redaction": {"policy": "default-local", "applied": True},
        "approvals": [],
        "runs": runs,
        "skills": [],
        "checks": ids,
        "comparisons": [],
        "recommendations": [],
        "parse_errors": 0,
        "proof_gaps": [],
        "provenance": {"parser": "session-eval-ingest", "parser_version": "1.0.0", "snapshots": []},
    }


def invoke(receipt_path: Path, out: Path, skill_root: Path, first_party: Path, extra: list[str] | None = None) -> dict[str, Any]:
    command = [
        sys.executable,
        str(SCRIPT),
        str(receipt_path),
        "--out",
        str(out),
        "--skill-root",
        str(skill_root),
        "--first-party-root",
        str(first_party),
        "--history-root",
        str(out / "history"),
    ]
    if extra:
        command.extend(extra)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"CLI failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    summary = json.loads(result.stdout)
    written = Path(summary["receipt"])
    return json.loads(written.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="session-eval-history-smoke-") as temporary:
        root = Path(temporary)
        first_party = root / "first-party"
        host = root / "host-skills"
        external = root / "external"
        (first_party / "demo").mkdir(parents=True)
        (host / "demo").mkdir(parents=True)
        (host / "vendor").mkdir(parents=True)
        (host / "unused").mkdir(parents=True)
        (external / "vendor").mkdir(parents=True)
        demo = first_party / "demo" / "SKILL.md"
        demo.write_text("---\nname: demo\nversion: 1.0.0\n---\noriginal\n", encoding="utf-8")
        os.symlink(demo, host / "demo" / "SKILL.md")
        (external / "vendor" / "SKILL.md").write_text("---\nname: vendor\n---\nthird-party\n", encoding="utf-8")
        os.symlink(external / "vendor" / "SKILL.md", host / "vendor" / "SKILL.md")
        (host / "unused" / "SKILL.md").write_text("---\nname: unused\n---\nidle\n", encoding="utf-8")
        demo_skill = {
            "name": "demo",
            "path": str(host / "demo" / "SKILL.md"),
            "digest": "sha256:historical-demo",
            "source": "grok.prompt_context",
            "confidence": "high",
        }
        mention = {
            "name": "demo",
            "path": str(host / "demo" / "SKILL.md"),
            "digest": UNKNOWN,
            "source": "claude.tool_or_text",
            "confidence": "low",
        }
        vendor_skill = {
            "name": "vendor",
            "path": str(host / "vendor" / "SKILL.md"),
            "digest": "sha256:historical-vendor",
            "source": "claude.tool_or_text",
            "confidence": "low",
        }
        missing_skill = {
            "name": "gone",
            "path": str(host / "gone" / "SKILL.md"),
            "digest": "sha256:historical-gone",
            "source": "grok.prompt_context",
            "confidence": "high",
        }
        unknown_tokens = {field: UNKNOWN for field in ("input", "output", "cache_read", "cache_create", "total")}

        candidate_doc = receipt(
            [
                run_record(
                    "sess-1",
                    [check("tool.unpaired", "pass"), check("ingest.parse_error", "pass", "infra")],
                    [demo_skill, mention, vendor_skill, missing_skill],
                    tokens=unknown_tokens,
                    cost=UNKNOWN,
                )
            ],
            generated_at="2026-09-13T16:00:00+00:00",
        )
        candidate_path = root / "candidate.json"
        write_json(candidate_path, candidate_doc)

        out = root / "out"
        enriched = invoke(candidate_path, out, host, first_party)
        def by_name_digest(rows: list[dict[str, Any]], name: str, digest: str | None = None) -> dict[str, Any]:
            matches = [item for item in rows if item.get("name") == name]
            if digest is None:
                return matches[0]
            return next(item for item in matches if item.get("historical_loaded_digest") == digest)

        demo_row = by_name_digest(enriched["skills"], "demo", "sha256:historical-demo")
        assert demo_row["activation_kind"] == "authoritative"
        assert demo_row["ownership"] == "first_party"
        assert demo_row["digest"] == "sha256:historical-demo"
        assert demo_row["current_on_disk_digest"] != "sha256:historical-demo"
        assert demo_row.get("version") == "1.0.0"
        assert demo_row.get("resolved_via_symlink") is True
        vendor_row = by_name_digest(enriched["skills"], "vendor", "sha256:historical-vendor")
        assert vendor_row["ownership"] == "external"
        gone_row = by_name_digest(enriched["skills"], "gone", "sha256:historical-gone")
        assert gone_row["missing"] is True
        unused_row = by_name_digest(enriched["skills"], "unused", UNKNOWN)
        assert unused_row["activation_kind"] == "absent"
        assert any(gap.get("kind") == "skill.missing" for gap in enriched["proof_gaps"])
        assert any(gap.get("kind") == "usage.unknown" for gap in enriched["proof_gaps"])
        assert any(gap.get("kind") == "skill.absent_usage" for gap in enriched["proof_gaps"])
        mention_row = next(item for item in enriched["runs"][0]["skills"] if item["source"] == "claude.tool_or_text" and item["name"] == "demo")
        assert mention_row["activation_kind"] == "mention"
        assert mention_row["digest"] == UNKNOWN
        assert candidate_path.read_text(encoding="utf-8")

        demo.write_text("---\nname: demo\nversion: 2.0.0\n---\nedited\n", encoding="utf-8")
        edited_out = root / "out-edited"
        edited = invoke(candidate_path, edited_out, host, first_party)
        demo_after = next(
            item
            for item in edited["skills"]
            if item["name"] == "demo" and item["historical_loaded_digest"] == "sha256:historical-demo"
        )
        assert demo_after["historical_loaded_digest"] == "sha256:historical-demo"
        assert demo_after["digest"] == "sha256:historical-demo"
        assert demo_after["current_on_disk_digest"] != demo_row["current_on_disk_digest"]

        baseline = receipt(
            [
                run_record(
                    "sess-1",
                    [check("tool.unpaired", "fail"), check("ingest.parse_error", "fail", "infra")],
                    [demo_skill],
                    tokens=unknown_tokens,
                    cost=UNKNOWN,
                )
            ],
            generated_at="2026-09-13T15:00:00+00:00",
        )
        incomplete = receipt(
            [
                run_record(
                    "sess-1",
                    [check("tool.unpaired", "fail"), check("ingest.parse_error", "fail", "infra")],
                    [demo_skill],
                )
            ],
            generated_at="2026-09-13T15:30:00+00:00",
            hard_pass=False,
            empty=True,
        )
        parser_mismatch = receipt(
            [
                run_record(
                    "sess-1",
                    [check("tool.unpaired", "fail"), check("ingest.parse_error", "fail", "infra")],
                    [demo_skill],
                    parser_version="9.9.9",
                )
            ],
            generated_at="2026-09-13T15:40:00+00:00",
        )
        schema_mismatch = receipt(
            [run_record("sess-1", [check("tool.unpaired", "fail")], [demo_skill])],
            generated_at="2026-09-13T15:41:00+00:00",
            schema="styrir-session-eval/v1",
        )
        catalog_mismatch = receipt(
            [run_record("sess-1", [check("tool.unpaired", "fail")], [demo_skill])],
            generated_at="2026-09-13T15:42:00+00:00",
            catalog_id="session-eval-check-catalog/v0",
        )
        baseline_path = root / "baseline.json"
        incomplete_path = root / "incomplete.json"
        parser_path = root / "parser.json"
        schema_path = root / "schema.json"
        catalog_path = root / "catalog.json"
        write_json(baseline_path, baseline)
        write_json(incomplete_path, incomplete)
        write_json(parser_path, parser_mismatch)
        write_json(schema_path, schema_mismatch)
        write_json(catalog_path, catalog_mismatch)

        compared = invoke(
            candidate_path,
            root / "out-compare",
            host,
            first_party,
            extra=["--baseline", str(baseline_path)],
        )
        comparison = compared["comparisons"][0]
        assert comparison["compatible"] is True
        assert comparison["counts"]["improved"] == 1
        assert comparison["infra_counts"]["improved"] == 1
        assert comparison["usage"]["unmeasurable"] is True
        assert comparison["pairing"] == "identity"
        assert isinstance(comparison["cohort"]["skill_digests"], list)
        assert "sha256:historical-demo" in comparison["cohort"]["skill_digests"]

        named = invoke(
            candidate_path,
            root / "out-incomplete",
            host,
            first_party,
            extra=["--baseline", str(incomplete_path)],
        )
        assert named["comparisons"][0]["baseline_qualification"]["label"] == "named_incomplete"
        assert named["comparisons"][0]["quality_delta_allowed"] is False

        for label, path in (("parser", parser_path), ("schema", schema_path), ("catalog", catalog_path)):
            result = invoke(candidate_path, root / f"out-{label}", host, first_party, extra=["--baseline", str(path)])
            row = result["comparisons"][0]
            assert row["compatible"] is False, label
            assert row["counts"]["improved"] == 0, label
            assert row["counts"]["regressed"] == 0, label
            assert row["counts"]["equal"] == 0, label
            assert row["counts"]["unmeasurable"] == 1, label
            assert row["infra_counts"]["unmeasurable"] in {0, 1}, label
            assert row["usage"]["unmeasurable"] is True, label

        two_digest = receipt(
            [
                run_record(
                    "sess-a",
                    [check("tool.unpaired", "pass")],
                    [{"name": "demo", "path": str(host / "demo" / "SKILL.md"), "digest": "sha256:rev-a", "source": "grok.prompt_context", "confidence": "high"}],
                ),
                run_record(
                    "sess-b",
                    [check("tool.unpaired", "pass")],
                    [{"name": "demo", "path": str(host / "demo" / "SKILL.md"), "digest": "sha256:rev-b", "source": "grok.prompt_context", "confidence": "high"}],
                ),
            ],
            generated_at="2026-09-13T16:30:00+00:00",
        )
        two_digest["skills"] = []
        two_path = root / "two-digest.json"
        write_json(two_path, two_digest)
        two_out = invoke(two_path, root / "out-two-digest", host, first_party)
        two_hist = {item["historical_loaded_digest"] for item in two_out["skills"] if item["name"] == "demo"}
        assert two_hist == {"sha256:rev-a", "sha256:rev-b"}

        first_history = list((root / "out-compare" / "history").glob("*.json"))
        assert len(first_history) == 1
        original = first_history[0].read_bytes()
        repeat = invoke(candidate_path, root / "out-compare", host, first_party, extra=["--baseline", str(baseline_path)])
        still = list((root / "out-compare" / "history").glob("*.json"))
        assert len(still) == 1
        assert still[0].read_bytes() == original

        default_root = root / "out-default"
        first_default = invoke(candidate_path, default_root, host, first_party)
        assert first_default["comparisons"] == [] or first_default["provenance"]["history"]["baseline_label"] != "qualified_champion" or first_default["provenance"]["history"].get("evaluation_identity")
        first_default_files = list((default_root / "history").glob("*.json"))
        assert len(first_default_files) == 1
        second_default = invoke(candidate_path, default_root, host, first_party)
        second_default_files = list((default_root / "history").glob("*.json"))
        assert len(second_default_files) == 1
        assert second_default_files[0].read_bytes() == first_default_files[0].read_bytes()
        assert second_default["provenance"]["history"]["baseline_label"] == "none"
        assert second_default["comparisons"] == []

        composed_root = root / "composed"
        composed_history = composed_root / "history"
        ingest_doc = receipt([run_record("sess-composed", [], [demo_skill])], generated_at="2026-09-13T17:00:00+00:00")
        ingest_doc["checks"] = []
        ingest_path = composed_root / "ingest.json"
        write_json(ingest_path, ingest_doc)
        registry_doc = invoke(ingest_path, composed_root / "registry", host, first_party, extra=["--history-root", str(composed_history)])
        stale = "older-unevaluated-registry"
        evaluated_doc = json.loads(json.dumps(registry_doc))
        evaluated_doc["runs"][0]["checks"] = [check("tool.unpaired", "pass")]
        evaluated_doc["checks"] = [{"id": "tool.unpaired", "class": "hard_fail", "kind": "code", "channel": "behavior"}]
        evaluated_doc.setdefault("provenance", {}).setdefault("history", {})["evaluation_identity"] = stale
        evaluated_path = composed_root / "evaluated.json"
        write_json(evaluated_path, evaluated_doc)
        eval_first = invoke(evaluated_path, composed_root / "eval-1", host, first_party, extra=["--history-root", str(composed_history)])
        eval_id = eval_first["provenance"]["history"]["evaluation_identity"]
        assert eval_id != stale
        composed_files = sorted(path.name for path in composed_history.glob("*.json"))
        assert len(composed_files) == 2
        eval_repeat = invoke(evaluated_path, composed_root / "eval-2", host, first_party, extra=["--history-root", str(composed_history)])
        assert eval_repeat["provenance"]["history"]["evaluation_identity"] == eval_id
        assert sorted(path.name for path in composed_history.glob("*.json")) == composed_files
        changed_doc = json.loads(json.dumps(evaluated_doc))
        changed_doc["runs"][0]["checks"][0]["status"] = "fail"
        changed_doc["hard_pass"] = False
        changed_doc.setdefault("provenance", {}).setdefault("history", {})["evaluation_identity"] = stale
        changed_path = composed_root / "changed.json"
        write_json(changed_path, changed_doc)
        eval_changed = invoke(changed_path, composed_root / "eval-changed", host, first_party, extra=["--history-root", str(composed_history)])
        assert eval_changed["provenance"]["history"]["evaluation_identity"] not in {stale, eval_id}
        assert len(list(composed_history.glob("*.json"))) == 3

        print(
            json.dumps(
                {
                    "ok": True,
                    "scenarios": [
                        "authoritative load vs mention",
                        "missing skill",
                        "edited skill old digest unchanged",
                        "first-party symlink vs external",
                        "absent usage",
                        "unknown usage",
                        "incompatible catalog/parser/schema partitioned denominators",
                        "two historical skill digests same path",
                        "qualified vs incomplete baseline",
                        "immutable repeated history",
                        "default rerun reuses history not self-compare",
                        "composed ingest-history-evaluate-history identity",
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
