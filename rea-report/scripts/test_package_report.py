"""Run with: uv run --with reportlab==5.1.0 python test_package_report.py"""

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from package_report import package


class ReportCheck(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.identity = "ev_" + "a" * 64
        # Synthetic shape fixture, deliberately not presented as authenticated REA Evidence.
        self.record = {
            "evidence_id": self.identity,
            "subject": {"name": "demo", "digest": {"sha256": "b" * 64}},
            "provider": {"id": "test-only"}, "operation": "fixture_inspection",
            "normalized_result": {"coverage": {"omitted": 3}, "unexplored_branches": ["native analysis"]},
            "confidence": "observed", "authority": "shipped-artifact",
            "limitations": ["Only the selected fixture was examined."],
        }
        self.report = {
            "title": "REA report check",
            "summary": "Literal <img src='https://example.invalid/secret'> and Unicode: café, naïve.",
            "scope": "Synthetic static Evidence; no target execution.",
            "findings": [{"kind": "observed", "text": "Fixture metadata was supplied.", "evidence_ids": [self.identity]}],
            "limitations": ["Omitted observations: 3; native analysis remains unknown."],
        }
        self.report_path = self.root / "findings.json"
        self.evidence_path = self.root / "evidence.json"
        self.output = self.root / "output"

    def run_package(self, document=None):
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        self.evidence_path.write_text(json.dumps(document or self.record), encoding="utf-8")
        return package(self.report_path, [self.evidence_path], self.output)

    def test_preserves_bundle_unknowns_and_renders_text(self):
        bundle = {"records": [self.record], "unknowns": [{"text": "Unanswered", "revision": 2}]}
        self.run_package(bundle)
        saved = json.loads((self.output / "report.json").read_text())
        self.assertEqual(saved["evidence_sources"][0]["document"], bundle)
        self.assertEqual(saved["report"], self.report)
        self.assertIn("Omitted observations", (self.output / "report.md").read_text())
        self.assertTrue((self.output / "report.pdf").read_bytes().startswith(b"%PDF-"))
        if shutil.which("pdftotext"):
            pdf_text = subprocess.check_output(["pdftotext", str(self.output / "report.pdf"), "-"], text=True)
            self.assertIn(self.identity, "".join(pdf_text.split()))
            self.assertIn("café", pdf_text)
            self.assertIn("naïve", pdf_text)
            self.assertIn("<img", pdf_text)  # Content stays literal, never fetched or interpreted as HTML.

    def test_unknowns_allowed_but_claims_need_supplied_citations(self):
        self.report["findings"][0]["evidence_ids"] = []
        with self.assertRaisesRegex(ValueError, "require evidence"):
            self.run_package()
        self.assertFalse(self.output.exists())
        self.report["findings"][0]["evidence_ids"] = ["ev_" + "c" * 64]
        with self.assertRaisesRegex(ValueError, "absent"):
            self.run_package()
        self.report["findings"][0].update(kind="unknown", evidence_ids=[])
        self.run_package()

    def test_incomplete_or_conflicting_evidence_rejected(self):
        partial = copy.deepcopy(self.record)
        del partial["normalized_result"]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.run_package(partial)
        conflicting = copy.deepcopy(self.record)
        conflicting["limitations"] = ["Changed payload under same ID"]
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            self.run_package({"records": [self.record, conflicting]})
        self.assertFalse(self.output.exists())

    def test_existing_output_and_symlink_are_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "report.md"
        sentinel.write_text("Keep me")
        with self.assertRaises(FileExistsError):
            self.run_package()
        self.assertEqual(sentinel.read_text(), "Keep me")
        sentinel.unlink()
        self.output.rmdir()
        self.output.symlink_to(self.root / "absent")
        with self.assertRaises(FileExistsError):
            self.run_package()
        self.assertTrue(self.output.is_symlink())

    def test_bad_json_and_budget_fail_without_output(self):
        self.report_path.write_text('{"title":"one","title":"two"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            package(self.report_path, [self.evidence_path], self.output)
        self.report_path.write_text('{"bad":NaN}')
        with self.assertRaisesRegex(ValueError, "Non-JSON"):
            package(self.report_path, [self.evidence_path], self.output)
        self.report_path.write_text(" " * (1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "budget"):
            package(self.report_path, [self.evidence_path], self.output, 1)
        self.assertFalse(self.output.exists())

    def test_failed_pdf_does_not_publish_partial_report(self):
        self.report["summary"] = "Unsupported glyph: 😀"
        with self.assertRaisesRegex(ValueError, "font lacks"):
            self.run_package()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".rea-report-*")), [])


if __name__ == "__main__":
    unittest.main()
