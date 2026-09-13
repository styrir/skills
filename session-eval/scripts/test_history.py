#!/usr/bin/env python3
"""Focused unit tests for session-eval history (skills-2ol.4).

Registry cases read real synthetic SKILL.md files.  Comparison/champion cases
may use synthetic canonical receipts.  This file does not ingest live
transcripts or mutate sources.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from history import (
    RECEIPT_SCHEMA,
    UNKNOWN,
    compare_receipts,
    compatibility_gates,
    enrich_registry,
    evaluation_identity,
    history,
    is_qualified_champion,
    parse_skill_frontmatter,
    select_baseline,
    write_history,
)


def _check(
    check_id: str,
    status: str,
    *,
    channel: str = "behavior",
    class_: str = "hard_fail",
) -> dict:
    return {
        "id": check_id,
        "status": status,
        "class": class_,
        "kind": "code",
        "channel": channel,
        "observed": status,
        "error": None,
        "evidence": [],
    }


def _run(
    native_id: str,
    checks: list[dict],
    *,
    harness: str = "claude",
    parser: str = "claude-jsonl-adapter",
    parser_version: str = "1.0.0",
    skills: list[dict] | None = None,
    tokens: dict | None = None,
    cost: object = 1.25,
    ended_at: str = "2026-09-13T10:00:00Z",
) -> dict:
    known_tokens = {
        "input": 10,
        "output": 4,
        "cache_read": 0,
        "cache_create": 0,
        "total": 14,
    }
    return {
        "id": f"{harness}:{native_id}",
        "harness": harness,
        "native_identity": {"id": native_id, "kind": "session_id", "source": "sessionId"},
        "display_name": native_id,
        "parser": parser,
        "parser_version": parser_version,
        "source_path": f"/tmp/{native_id}.jsonl",
        "source_snapshot": {"sha256": "abc", "files": []},
        "started_at": "2026-09-13T09:00:00Z",
        "ended_at": ended_at,
        "cwd": UNKNOWN,
        "model": "test-model",
        "tokens": known_tokens if tokens is None else tokens,
        "cost_usd": cost,
        "usage_provenance": [],
        "skills": skills or [],
        "lineage": {},
        "turns": [],
        "checks": checks,
        "lifecycle": {"state": "terminal", "evidence": []},
    }


def _receipt(
    runs: list[dict],
    *,
    catalog_id: str = "session-eval-check-catalog/v1",
    schema: str = RECEIPT_SCHEMA,
    generated_at: str = "2026-09-13T12:00:00+00:00",
    hard_pass: bool = True,
    infra_ok: bool = True,
    empty: bool = False,
    missing: list | None = None,
    unknown_hard: int = 0,
    harnesses: list[str] | None = None,
    redaction: str = "default-local",
    checks: list[dict] | None = None,
) -> dict:
    found = harnesses or sorted({run["harness"] for run in runs})
    rollup = checks
    if rollup is None:
        ids = []
        seen = set()
        for run in runs:
            for check in run.get("checks") or []:
                if check["id"] not in seen:
                    seen.add(check["id"])
                    ids.append({"id": check["id"], "class": check.get("class"), "kind": check.get("kind"), "channel": check.get("channel")})
        rollup = ids
    return {
        "schema": schema,
        "catalog_id": catalog_id,
        "generated_at": generated_at,
        "since": UNKNOWN,
        "harnesses_requested": list(found),
        "harnesses_found": list(found),
        "coverage": {
            "sessions_ingested": len(runs),
            "empty": empty,
            "missing_requested_inputs": missing or [],
            "applicable_hard_fail_unknown": unknown_hard,
        },
        "hard_pass": hard_pass,
        "infra_ok": infra_ok,
        "redaction": {"policy": redaction, "applied": True},
        "approvals": [],
        "runs": runs,
        "skills": [],
        "checks": rollup,
        "comparisons": [],
        "recommendations": [],
        "parse_errors": 0,
        "proof_gaps": [],
        "provenance": {"parser": "session-eval-ingest", "parser_version": "1.0.0", "snapshots": []},
    }


UNKNOWN_TOKENS = {field: UNKNOWN for field in ("input", "output", "cache_read", "cache_create", "total")}


class FrontmatterTests(unittest.TestCase):
    def test_yaml_frontmatter_name_and_version(self) -> None:
        meta = parse_skill_frontmatter("---\nname: demo\nversion: 1.2.0\n---\n# Demo\n")
        self.assertEqual(meta["name"], "demo")
        self.assertEqual(meta["version"], "1.2.0")

    def test_metadata_version_and_bare_keys(self) -> None:
        meta = parse_skill_frontmatter("name: demo\nmetadata:\n  version: 9\n\n# body\n")
        self.assertEqual(meta["name"], "demo")
        self.assertEqual(meta["version"], "9")


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="session-eval-history-")
        self.root = Path(self.temp.name)
        self.first_party = self.root / "first-party"
        self.host = self.root / "host-skills"
        self.external = self.root / "external"
        (self.first_party / "demo").mkdir(parents=True)
        (self.host / "demo").mkdir(parents=True)
        (self.host / "vendor").mkdir(parents=True)
        (self.external / "vendor").mkdir(parents=True)
        self.demo = self.first_party / "demo" / "SKILL.md"
        self.demo.write_text("---\nname: demo\nversion: 1.2.0\n---\nbody-a\n", encoding="utf-8")
        self.demo_digest = __import__("hashlib").sha256(self.demo.read_bytes()).hexdigest()
        os.symlink(self.demo, self.host / "demo" / "SKILL.md")
        (self.external / "vendor" / "SKILL.md").write_text(
            "---\nname: vendor\nversion: 0.1\n---\nvendor\n", encoding="utf-8"
        )
        os.symlink(self.external / "vendor" / "SKILL.md", self.host / "vendor" / "SKILL.md")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _enrich(self, skills: list[dict], runs_checks: list[dict] | None = None) -> dict:
        run = _run(
            "sess-1",
            runs_checks or [_check("tool.unpaired", "pass")],
            skills=skills,
        )
        receipt = _receipt([run])
        return enrich_registry(
            receipt,
            skill_roots=[self.host],
            first_party_root=self.first_party,
        )

    def test_authoritative_load_vs_mention(self) -> None:
        enriched = self._enrich(
            [
                {
                    "name": "demo",
                    "path": str(self.host / "demo" / "SKILL.md"),
                    "digest": "sha256:historical-demo",
                    "source": "grok.prompt_context",
                    "confidence": "high",
                },
                {
                    "name": "demo",
                    "path": str(self.host / "demo" / "SKILL.md"),
                    "digest": UNKNOWN,
                    "source": "claude.tool_or_text",
                    "confidence": "low",
                },
            ]
        )
        demos = [item for item in enriched["skills"] if item["name"] == "demo"]
        auth = next(item for item in demos if item["historical_loaded_digest"] == "sha256:historical-demo")
        unknown = next(item for item in demos if item["historical_loaded_digest"] == UNKNOWN)
        self.assertEqual(auth["activation_kind"], "authoritative")
        self.assertEqual(unknown["activation_kind"], "mention")
        mention = next(
            skill
            for skill in enriched["runs"][0]["skills"]
            if skill["source"] == "claude.tool_or_text"
        )
        self.assertEqual(mention["activation_kind"], "mention")
        self.assertEqual(mention["digest"], UNKNOWN)

    def test_missing_skill(self) -> None:
        missing_path = str(self.host / "gone" / "SKILL.md")
        enriched = self._enrich(
            [
                {
                    "name": "gone",
                    "path": missing_path,
                    "digest": "sha256:old-gone",
                    "source": "grok.prompt_context",
                    "confidence": "high",
                }
            ]
        )
        gone = next(item for item in enriched["skills"] if item["name"] == "gone")
        self.assertTrue(gone["missing"])
        self.assertEqual(gone["historical_loaded_digest"], "sha256:old-gone")
        self.assertEqual(gone["current_on_disk_digest"], UNKNOWN)
        self.assertEqual(gone["digest"], "sha256:old-gone")
        self.assertTrue(any(gap.get("kind") == "skill.missing" for gap in enriched["proof_gaps"]))

    def test_edited_skill_preserves_old_digest(self) -> None:
        enriched = self._enrich(
            [
                {
                    "name": "demo",
                    "path": str(self.host / "demo" / "SKILL.md"),
                    "digest": "sha256:historical-demo",
                    "source": "grok.prompt_context",
                    "confidence": "high",
                }
            ]
        )
        demo = next(item for item in enriched["skills"] if item["name"] == "demo")
        self.assertEqual(demo["historical_loaded_digest"], "sha256:historical-demo")
        self.assertEqual(demo["digest"], "sha256:historical-demo")
        self.assertEqual(demo["current_on_disk_digest"], self.demo_digest)
        self.assertNotEqual(demo["current_on_disk_digest"], demo["historical_loaded_digest"])
        self.assertEqual(demo["digest_relation"], "historical_differs_from_current")
        self.assertEqual(demo.get("version"), "1.2.0")
        run_skill = enriched["runs"][0]["skills"][0]
        self.assertEqual(run_skill["digest"], "sha256:historical-demo")
        self.demo.write_text("---\nname: demo\nversion: 1.3.0\n---\nbody-b\n", encoding="utf-8")
        again = self._enrich(
            [
                {
                    "name": "demo",
                    "path": str(self.host / "demo" / "SKILL.md"),
                    "digest": "sha256:historical-demo",
                    "source": "grok.prompt_context",
                    "confidence": "high",
                }
            ]
        )
        demo2 = next(item for item in again["skills"] if item["name"] == "demo")
        self.assertEqual(demo2["historical_loaded_digest"], "sha256:historical-demo")
        self.assertNotEqual(demo2["current_on_disk_digest"], self.demo_digest)

    def test_first_party_symlink_vs_external(self) -> None:
        enriched = self._enrich(
            [
                {
                    "name": "demo",
                    "path": str(self.host / "demo" / "SKILL.md"),
                    "digest": "sha256:historical-demo",
                    "source": "grok.prompt_context",
                    "confidence": "high",
                },
                {
                    "name": "vendor",
                    "path": str(self.host / "vendor" / "SKILL.md"),
                    "digest": "sha256:historical-vendor",
                    "source": "claude.tool_or_text",
                    "confidence": "low",
                },
            ]
        )
        demo = next(item for item in enriched["skills"] if item["name"] == "demo")
        vendor = next(item for item in enriched["skills"] if item["name"] == "vendor")
        self.assertEqual(demo["ownership"], "first_party")
        self.assertTrue(demo.get("resolved_via_symlink"))
        self.assertEqual(vendor["ownership"], "external")
        self.assertTrue(vendor.get("resolved_via_symlink"))

    def test_absent_usage_registry_only_skill(self) -> None:
        run = _run("sess-1", [_check("tool.unpaired", "pass")], skills=[])
        receipt = _receipt([run])
        enriched = enrich_registry(
            receipt,
            skill_roots=[self.host],
            first_party_root=self.first_party,
        )
        names = {item["name"] for item in enriched["skills"]}
        self.assertIn("demo", names)
        demo = next(item for item in enriched["skills"] if item["name"] == "demo")
        self.assertEqual(demo["activation_kind"], "absent")
        self.assertEqual(demo["historical_loaded_digest"], UNKNOWN)
        self.assertEqual(demo["digest"], demo["current_on_disk_digest"])
        self.assertTrue(any(gap.get("kind") == "skill.absent_usage" for gap in enriched["proof_gaps"]))

    def test_p1_two_historical_digests_same_path_and_run_level_discovery(self) -> None:
        # Parent fixture: two runs, same SKILL.md path, digests A then B, top-level skills [].
        path = str(self.host / "demo" / "SKILL.md")
        run_a = _run(
            "sess-a",
            [_check("tool.unpaired", "pass")],
            skills=[
                {
                    "name": "demo",
                    "path": path,
                    "digest": "sha256:rev-a",
                    "source": "grok.prompt_context",
                    "confidence": "high",
                }
            ],
        )
        run_b = _run(
            "sess-b",
            [_check("tool.unpaired", "pass")],
            skills=[
                {
                    "name": "demo",
                    "path": path,
                    "digest": "sha256:rev-b",
                    "source": "grok.prompt_context",
                    "confidence": "high",
                }
            ],
        )
        receipt = _receipt([run_a, run_b])
        receipt["skills"] = []
        enriched = enrich_registry(
            receipt,
            skill_roots=[self.host],
            first_party_root=self.first_party,
        )
        demos = [item for item in enriched["skills"] if item["name"] == "demo"]
        digests = {item["historical_loaded_digest"] for item in demos}
        self.assertEqual(digests, {"sha256:rev-a", "sha256:rev-b"})
        raw = _receipt([run_a])
        raw["skills"] = []
        gates = compatibility_gates(raw, enriched)
        self.assertIsInstance(gates["cohort"]["skill_digests"], list)
        self.assertEqual(set(gates["cohort"]["skill_digests"]), {"sha256:rev-a", "sha256:rev-b"})


class ComparisonTests(unittest.TestCase):
    def test_identity_improved_regressed_equal(self) -> None:
        baseline = _receipt(
            [
                _run(
                    "sess-1",
                    [
                        _check("tool.unpaired", "fail"),
                        _check("tool.repeat_loop", "pass"),
                        _check("session.identity_missing", "pass"),
                    ],
                )
            ]
        )
        candidate = _receipt(
            [
                _run(
                    "sess-1",
                    [
                        _check("tool.unpaired", "pass"),
                        _check("tool.repeat_loop", "fail"),
                        _check("session.identity_missing", "pass"),
                    ],
                )
            ]
        )
        result = compare_receipts(baseline, candidate)
        self.assertTrue(result["compatible"])
        self.assertEqual(result["pairing"], "identity")
        self.assertEqual(result["counts"]["improved"], 1)
        self.assertEqual(result["counts"]["regressed"], 1)
        self.assertEqual(result["counts"]["equal"], 1)
        self.assertTrue(result["quality_delta_allowed"])

    def test_unknown_and_unmatched_are_unmeasurable(self) -> None:
        baseline = _receipt(
            [
                _run(
                    "sess-1",
                    [
                        _check("tool.unpaired", "unknown"),
                        _check("tool.repeat_loop", "pass"),
                    ],
                )
            ]
        )
        candidate = _receipt(
            [
                _run(
                    "sess-1",
                    [
                        _check("tool.unpaired", "pass"),
                        _check("tool.repeat_loop", "pass"),
                        _check("session.identity_missing", "fail"),
                    ],
                )
            ]
        )
        result = compare_receipts(baseline, candidate)
        self.assertFalse(result["compatible"])
        self.assertIn("check_id_set_mismatch", result["unmeasurable_reasons"])
        self.assertEqual(result["counts"]["improved"], 0)
        self.assertEqual(result["counts"]["regressed"], 0)
        self.assertEqual(result["counts"]["equal"], 0)
        self.assertGreater(result["counts"]["unmeasurable"], 0)

        same_ids_base = _receipt([_run("sess-1", [_check("tool.unpaired", "unknown")])])
        same_ids_cand = _receipt([_run("sess-1", [_check("tool.unpaired", "pass")])])
        unknown = compare_receipts(same_ids_base, same_ids_cand)
        self.assertTrue(unknown["compatible"])
        self.assertEqual(unknown["counts"]["unmeasurable"], 1)
        unmatched_base = _receipt([_run("sess-a", [_check("tool.unpaired", "pass")])])
        unmatched_cand = _receipt([_run("sess-b", [_check("tool.unpaired", "fail")])])
        unmatched = compare_receipts(unmatched_base, unmatched_cand)
        self.assertTrue(unmatched["compatible"])
        self.assertGreaterEqual(unmatched["counts"]["unmeasurable"], 2)
        self.assertEqual(unmatched["counts"]["improved"], 0)
        self.assertEqual(unmatched["counts"]["regressed"], 0)

    def test_incompatible_catalog_cohort_parser_schema_redaction(self) -> None:
        base_run = _run("sess-1", [_check("tool.unpaired", "pass")])
        cand_run = _run("sess-1", [_check("tool.unpaired", "fail")])
        catalog = compare_receipts(
            _receipt([base_run], catalog_id="session-eval-check-catalog/v1"),
            _receipt([cand_run], catalog_id="session-eval-check-catalog/v2"),
        )
        self.assertFalse(catalog["compatible"])
        self.assertIn("catalog_mismatch", catalog["unmeasurable_reasons"])
        self.assertEqual(catalog["counts"]["improved"], 0)

        cohort = compare_receipts(
            _receipt([base_run], harnesses=["claude"]),
            _receipt([_run("sess-1", [_check("tool.unpaired", "fail")], harness="grok", parser="grok-session-adapter")], harnesses=["grok"]),
        )
        self.assertFalse(cohort["compatible"])
        self.assertTrue(any("cohort" in reason or "intersection" in reason for reason in cohort["unmeasurable_reasons"]))

        parser = compare_receipts(
            _receipt([base_run]),
            _receipt([_run("sess-1", [_check("tool.unpaired", "fail")], parser_version="2.0.0")]),
        )
        self.assertFalse(parser["compatible"])
        self.assertIn("parser_mismatch", parser["unmeasurable_reasons"])

        schema = compare_receipts(
            _receipt([base_run], schema=RECEIPT_SCHEMA),
            _receipt([cand_run], schema="styrir-session-eval/v1"),
        )
        self.assertFalse(schema["compatible"])
        self.assertIn("schema_mismatch", schema["unmeasurable_reasons"])

        redaction = compare_receipts(
            _receipt([base_run], redaction="default-local"),
            _receipt([cand_run], redaction="strict"),
        )
        self.assertFalse(redaction["compatible"])
        self.assertIn("redaction_mismatch", redaction["unmeasurable_reasons"])

    def test_infra_separated_and_usage_unknown(self) -> None:
        baseline = _receipt(
            [
                _run(
                    "sess-1",
                    [
                        _check("tool.unpaired", "fail"),
                        _check("ingest.parse_error", "fail", channel="infra"),
                    ],
                    tokens=UNKNOWN_TOKENS,
                    cost=UNKNOWN,
                )
            ]
        )
        candidate = _receipt(
            [
                _run(
                    "sess-1",
                    [
                        _check("tool.unpaired", "pass"),
                        _check("ingest.parse_error", "pass", channel="infra"),
                    ],
                    tokens=UNKNOWN_TOKENS,
                    cost=UNKNOWN,
                )
            ]
        )
        result = compare_receipts(baseline, candidate)
        self.assertTrue(result["compatible"])
        self.assertEqual(result["counts"]["improved"], 1)
        self.assertEqual(result["infra_counts"]["improved"], 1)
        self.assertTrue(result["usage"]["unmeasurable"])
        self.assertIn("usage_unmeasurable", result["unmeasurable_reasons"])

    def test_p1_incompatible_denominators_partition_channels(self) -> None:
        # Parent fixture: 1 behavior + 1 infra + usage, incompatible catalog.
        # Frozen code reported behavior unmeasurable=3 and infra=2.
        baseline = _receipt(
            [
                _run(
                    "sess-1",
                    [
                        _check("tool.unpaired", "pass"),
                        _check("ingest.parse_error", "pass", channel="infra"),
                    ],
                    tokens=UNKNOWN_TOKENS,
                    cost=UNKNOWN,
                )
            ]
        )
        candidate = _receipt(
            [
                _run(
                    "sess-1",
                    [
                        _check("tool.unpaired", "fail"),
                        _check("ingest.parse_error", "fail", channel="infra"),
                    ],
                    tokens=UNKNOWN_TOKENS,
                    cost=UNKNOWN,
                )
            ],
            catalog_id="incompatible-catalog",
        )
        result = compare_receipts(baseline, candidate)
        self.assertFalse(result["compatible"])
        self.assertEqual(result["counts"]["improved"], 0)
        self.assertEqual(result["counts"]["regressed"], 0)
        self.assertEqual(result["counts"]["equal"], 0)
        self.assertEqual(result["counts"]["unmeasurable"], 1)
        self.assertEqual(result["infra_counts"]["unmeasurable"], 1)
        self.assertEqual(result["infra_counts"]["improved"], 0)
        self.assertTrue(result["usage"]["unmeasurable"])


class ChampionHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="session-eval-history-champ-")
        self.root = Path(self.temp.name)
        self.history_root = self.root / "history"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_qualified_champion_vs_incomplete_named_baseline(self) -> None:
        candidate = _receipt(
            [_run("sess-1", [_check("tool.unpaired", "pass")])],
            generated_at="2026-09-13T14:00:00+00:00",
        )
        champion = _receipt(
            [_run("sess-1", [_check("tool.unpaired", "fail")])],
            generated_at="2026-09-13T13:00:00+00:00",
        )
        incomplete = _receipt(
            [_run("sess-1", [_check("tool.unpaired", "fail")])],
            generated_at="2026-09-13T13:30:00+00:00",
            hard_pass=False,
            empty=True,
        )
        write_history(champion, self.history_root)
        write_history(incomplete, self.history_root)
        selected = select_baseline(self.history_root, candidate)
        self.assertEqual(selected["label"], "qualified_champion")
        self.assertTrue(selected["qualified"])
        self.assertEqual(selected["receipt"]["generated_at"], champion["generated_at"])

        named = select_baseline(self.history_root, candidate, named_baseline=incomplete)
        self.assertEqual(named["label"], "named_incomplete")
        self.assertFalse(named["qualified"])
        comparison = compare_receipts(
            incomplete,
            candidate,
            baseline_qualification={
                "policy": "named",
                "qualified": False,
                "label": "named_incomplete",
                "reasons": named["reasons"],
            },
        )
        self.assertFalse(comparison["quality_delta_allowed"])
        self.assertIn("baseline_incomplete", comparison["unmeasurable_reasons"])

        ok, reasons = is_qualified_champion(incomplete)
        self.assertFalse(ok)
        self.assertIn("hard_pass_not_true", reasons)
        self.assertIn("coverage_empty_or_unknown", reasons)

    def test_immutable_repeated_and_changed_history(self) -> None:
        receipt = _receipt([_run("sess-1", [_check("tool.unpaired", "pass")])])
        first = write_history(receipt, self.history_root)
        second = write_history(receipt, self.history_root)
        self.assertEqual(first, second)
        original = first.read_bytes()
        changed = _receipt(
            [_run("sess-1", [_check("tool.unpaired", "fail")])],
            generated_at="2026-09-13T15:00:00+00:00",
        )
        third = write_history(changed, self.history_root)
        self.assertNotEqual(third, first)
        self.assertEqual(first.read_bytes(), original)
        self.assertNotEqual(third.read_bytes(), original)

    def test_history_orchestrator_does_not_mutate_source_receipt(self) -> None:
        source = self.root / "source.json"
        payload = _receipt([_run("sess-1", [_check("tool.unpaired", "pass")])])
        source.write_text(json.dumps(payload), encoding="utf-8")
        before = source.read_bytes()
        skills = self.root / "skills" / "demo"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: demo\nversion: 1\n---\n", encoding="utf-8")
        document, written = history(
            source,
            out=self.root / "out",
            skill_roots=[skills.parent],
            first_party_root=skills.parent,
            history_root=self.history_root,
        )
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue(written.is_file())
        self.assertEqual(document["schema"], RECEIPT_SCHEMA)
        self.assertTrue((self.root / "out" / "receipt.json").is_file())
        entries = list(self.history_root.glob("*.json"))
        self.assertEqual(len(entries), 1)

    def test_p1_default_rerun_reuses_history_not_self_compare(self) -> None:
        source = self.root / "source.json"
        payload = _receipt(
            [_run("sess-1", [_check("tool.unpaired", "pass")])],
            hard_pass=True,
            infra_ok=True,
            empty=False,
        )
        source.write_text(json.dumps(payload), encoding="utf-8")
        skills = self.root / "skills" / "demo"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: demo\nversion: 1\n---\n", encoding="utf-8")
        first, _written = history(
            source,
            out=self.root / "out1",
            skill_roots=[skills.parent],
            first_party_root=skills.parent,
            history_root=self.history_root,
        )
        first_files = sorted(path.name for path in self.history_root.glob("*.json"))
        self.assertEqual(len(first_files), 1)
        self.assertEqual(first["comparisons"], [])
        second, _again = history(
            source,
            out=self.root / "out2",
            skill_roots=[skills.parent],
            first_party_root=skills.parent,
            history_root=self.history_root,
        )
        second_files = sorted(path.name for path in self.history_root.glob("*.json"))
        self.assertEqual(second_files, first_files)
        self.assertEqual(second["comparisons"], [])
        self.assertEqual(
            (second.get("provenance") or {}).get("history", {}).get("baseline_label"),
            "none",
        )
        self.assertNotEqual(
            (second.get("provenance") or {}).get("history", {}).get("evaluation_identity"),
            None,
        )

    def test_p1_composed_evaluate_does_not_inherit_stale_identity(self) -> None:
        skills = self.root / "skills" / "demo"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: demo\nversion: 1\n---\n", encoding="utf-8")
        ingest_like = _receipt(
            [_run("sess-1", [])],
            hard_pass=True,
            infra_ok=True,
            empty=False,
        )
        ingest_like["checks"] = []
        registry, _written = history(
            ingest_like,
            out=self.root / "out-registry",
            skill_roots=[skills.parent],
            first_party_root=skills.parent,
            history_root=self.history_root,
        )
        stale = ((registry.get("provenance") or {}).get("history") or {}).get("evaluation_identity")
        self.assertTrue(isinstance(stale, str) and stale)

        evaluated = json.loads(json.dumps(registry))
        evaluated["runs"][0]["checks"] = [_check("tool.unpaired", "pass")]
        evaluated["checks"] = [
            {"id": "tool.unpaired", "class": "hard_fail", "kind": "code", "channel": "behavior"}
        ]
        evaluated["hard_pass"] = True
        evaluated["infra_ok"] = True
        evaluated.setdefault("provenance", {}).setdefault("history", {})["evaluation_identity"] = stale
        self.assertNotEqual(evaluation_identity(evaluated), stale)

        first, _path = history(
            evaluated,
            out=self.root / "out-eval-1",
            skill_roots=[skills.parent],
            first_party_root=skills.parent,
            history_root=self.history_root,
        )
        new_id = ((first.get("provenance") or {}).get("history") or {}).get("evaluation_identity")
        self.assertEqual(new_id, evaluation_identity(evaluated))
        self.assertNotEqual(new_id, stale)
        after_eval = sorted(path.name for path in self.history_root.glob("*.json"))
        self.assertEqual(len(after_eval), 2)

        second, _again = history(
            evaluated,
            out=self.root / "out-eval-2",
            skill_roots=[skills.parent],
            first_party_root=skills.parent,
            history_root=self.history_root,
        )
        self.assertEqual(
            ((second.get("provenance") or {}).get("history") or {}).get("evaluation_identity"),
            new_id,
        )
        self.assertEqual(sorted(path.name for path in self.history_root.glob("*.json")), after_eval)
        self.assertEqual(
            ((second.get("provenance") or {}).get("history") or {}).get("baseline_label"),
            "none",
        )
        self.assertEqual(second["comparisons"], [])

        changed = json.loads(json.dumps(evaluated))
        changed["runs"][0]["checks"][0]["status"] = "fail"
        changed["hard_pass"] = False
        changed.setdefault("provenance", {}).setdefault("history", {})["evaluation_identity"] = stale
        third, _changed_path = history(
            changed,
            out=self.root / "out-eval-changed",
            skill_roots=[skills.parent],
            first_party_root=skills.parent,
            history_root=self.history_root,
        )
        changed_id = ((third.get("provenance") or {}).get("history") or {}).get("evaluation_identity")
        self.assertNotEqual(changed_id, new_id)
        self.assertNotEqual(changed_id, stale)
        self.assertEqual(changed_id, evaluation_identity(changed))
        self.assertEqual(len(list(self.history_root.glob("*.json"))), 3)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
