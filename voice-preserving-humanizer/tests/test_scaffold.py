"""Scaffold smoke tests (plan §8, §11.1; DR-02, DR-05, DR-19)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from humanize import HumanizeError, review_code_for_proposal, validate_consent_tuple  # noqa: E402
from profile import ProfileError, assert_revision_allowed, hypothesis_enforceable  # noqa: E402
from codes import REJECTION_CODES, SCHEMA_VERSIONS  # noqa: E402
from verify import memorization_overlaps, normalize_for_overlap  # noqa: E402
from style_metrics import sentence_median_report  # noqa: E402


class LayoutTests(unittest.TestCase):
    def test_plan_layout_exists(self):
        required = [
            "SKILL.md",
            "README.md",
            "THIRD_PARTY_NOTICES.md",
            "references/ai-patterns.md",
            "references/candidate-provenance.md",
            "references/harness-privacy.md",
            "references/high-register-editing.md",
            "references/profile-schema.md",
            "references/verification-rubric.md",
            "scripts/humanize.py",
            "scripts/profile.py",
            "scripts/protect.py",
            "scripts/style_metrics.py",
            "scripts/verify.py",
            "templates/consent.json",
            "templates/edit-proposal.json",
            "templates/edit-set.json",
            "templates/handoff-manifest.json",
            "templates/prepared-state.json",
            "templates/profile.yaml",
            "templates/review-approval.json",
            "templates/route-resolution.json",
            "templates/audit.json",
            "tests/test_scaffold.py",
        ]
        for rel in required:
            self.assertTrue((ROOT / rel).is_file(), rel)


class ProfileGateTests(unittest.TestCase):
    def test_diagnose_only_without_profile(self):
        assert_revision_allowed(None, "diagnose-only")

    def test_revision_requires_profile(self):
        with self.assertRaises(ProfileError) as ctx:
            assert_revision_allowed(None, "conservative")
        self.assertEqual(ctx.exception.code, "PROFILE_REQUIRED_FOR_REVISION")

    def test_hypothesis_enforceable(self):
        good = {
            "applicability": "enforceable",
            "evidence": ["a", "b"],
            "genericity_check": {
                "acceptable_contrast": "other ok phrasing",
                "quality_inversion": False,
                "user_confirmed_author_specific": True,
            },
        }
        self.assertTrue(hypothesis_enforceable(good))
        bad = dict(good)
        bad["evidence"] = ["only-one"]
        self.assertFalse(hypothesis_enforceable(bad))


class ReviewPrecedenceTests(unittest.TestCase):
    def test_low_confidence_wins(self):
        self.assertEqual(review_code_for_proposal(0.5, True), "LOW_CONFIDENCE_PROPOSAL")

    def test_model_requested_review(self):
        self.assertEqual(review_code_for_proposal(0.9, True), "MODEL_REQUESTED_REVIEW")

    def test_no_review(self):
        self.assertIsNone(review_code_for_proposal(0.9, False))


class ConsentTests(unittest.TestCase):
    def test_backend_mismatch(self):
        consent = {
            "schema_version": SCHEMA_VERSIONS["voice-consent"],
            "harness": "hermes",
            "provider_route": "r1",
            "resolved_backend_model": "a",
            "data_class": "raw_private",
            "dynamic_route": False,
        }
        route = {
            "schema_version": SCHEMA_VERSIONS["route-resolution"],
            "harness": "hermes",
            "provider_route": "r1",
            "resolved_backend_model": "b",
            "dynamic_route": False,
        }
        with self.assertRaises(HumanizeError) as ctx:
            validate_consent_tuple(consent, route)
        self.assertEqual(ctx.exception.code, "CONSENT_BACKEND_MISMATCH")

    def test_dynamic_raw_blocked(self):
        consent = {
            "schema_version": SCHEMA_VERSIONS["voice-consent"],
            "harness": "hermes",
            "provider_route": "r1",
            "resolved_backend_model": "a",
            "data_class": "raw_private",
            "dynamic_route": True,
            "dynamic_route_acknowledged": True,
        }
        route = {
            "schema_version": SCHEMA_VERSIONS["route-resolution"],
            "harness": "hermes",
            "provider_route": "r1",
            "resolved_backend_model": "a",
            "dynamic_route": True,
        }
        with self.assertRaises(HumanizeError) as ctx:
            validate_consent_tuple(consent, route)
        self.assertEqual(ctx.exception.code, "CONSENT_INVALID")


class VerifyHelperTests(unittest.TestCase):
    def test_normalize_tokens(self):
        toks = normalize_for_overlap("Epistemic-risk isn't trivial.")
        self.assertEqual(toks, ["epistemic", "risk", "isn't", "trivial"])

    def test_memorization_overlap(self):
        source = "alpha beta gamma"
        changed = "one two three four five six seven"
        sample = "one two three four five six zz"
        hits = memorization_overlaps(changed, {"s1": sample}, source, n=6)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["review_code"], "PROFILE_MEMORIZATION_OVERLAP")


class StyleMetricTests(unittest.TestCase):
    def test_insufficient_sample(self):
        r = sentence_median_report("Hi.", "Hello there.", [10.0, 12.0])
        self.assertFalse(r.sample_sufficient)
        self.assertEqual(r.note, "insufficient_sample")


class CLITests(unittest.TestCase):
    def test_prepare_diagnose_only(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src = td_path / "draft.md"
            src.write_text("A short draft for diagnose-only.\n", encoding="utf-8")
            out = td_path / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "humanize.py"),
                    "prepare",
                    "--source",
                    str(src),
                    "--mode",
                    "diagnose-only",
                    "--outdir",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            prepared = json.loads((out / "prepared-state.json").read_text(encoding="utf-8"))
            self.assertEqual(prepared["schema_version"], SCHEMA_VERSIONS["prepared-state"])
            self.assertEqual(prepared["mode"], "diagnose-only")

    def test_prepare_revision_without_profile_fails(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src = td_path / "draft.md"
            src.write_text("Needs a profile.\n", encoding="utf-8")
            out = td_path / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "humanize.py"),
                    "prepare",
                    "--source",
                    str(src),
                    "--mode",
                    "conservative",
                    "--outdir",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
            self.assertIn("PROFILE_REQUIRED_FOR_REVISION", audit["rejection_codes"])


class CodesTests(unittest.TestCase):
    def test_core_codes_present(self):
        for code in (
            "PROFILE_REQUIRED_FOR_REVISION",
            "LOW_CONFIDENCE_PROPOSAL",
            "MODEL_REQUESTED_REVIEW",
            "SENTINEL_ORDER_CHANGED",
            "PROFILE_MEMORIZATION_OVERLAP",
        ):
            self.assertIn(code, REJECTION_CODES)


if __name__ == "__main__":
    unittest.main()
