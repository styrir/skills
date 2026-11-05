#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["reportlab==5.1.0"]
# ///
"""Package analyst findings and saved morluto/rea Evidence; never run a target."""

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty plain text")
    return value


def strings(value):
    if not isinstance(value, list):
        raise ValueError("Expected an array of strings")
    return [text(item) for item in value]


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path, remaining):
    with path.open("rb") as stream:
        raw = stream.read(remaining + 1)
    if len(raw) > remaining:
        raise ValueError("Input budget exceeded; increase --max-input-mib deliberately")
    def reject_constant(value):
        raise ValueError(f"Non-JSON number: {value}")

    data = json.loads(raw, object_pairs_hook=no_duplicate_keys, parse_constant=reject_constant)
    return raw, data


def evidence_records(document):
    if not isinstance(document, dict):
        raise ValueError("Expected a complete REA Evidence record or canonical bundle")
    records = document.get("records") if "records" in document else [document]
    if not isinstance(records, list) or not records:
        raise ValueError("Evidence must contain at least one complete record")
    for record in records:
        if not isinstance(record, dict) or not re.fullmatch(r"ev_[0-9a-f]{64}", str(record.get("evidence_id"))):
            raise ValueError("Missing or malformed REA evidence_id; do not use summaries/envelopes")
        required = {"subject", "provider", "operation", "normalized_result", "confidence", "authority", "limitations"}
        if not required <= record.keys():
            raise ValueError("Incomplete Evidence record; save complete CLI JSON or MCP structuredContent")
        text(record["operation"])
        text(record["authority"])
        strings(record["limitations"])
        if record["confidence"] not in {"observed", "derived", "inferred"}:
            raise ValueError("Invalid Evidence confidence")
        if not isinstance(record["provider"], dict) or not isinstance(record["subject"], (dict, type(None))):
            raise ValueError("Invalid Evidence provider or subject")
    return records


def markdown_text(value):
    return re.sub(r"([\\`*_{}\[\]()<>#+.!|~-])", r"\\\1", value)


def sections(report, records):
    yield 1, report["title"]
    yield 0, report["summary"]
    yield 2, "Scope"
    yield 0, report["scope"]
    yield 2, "Findings"
    for finding in report["findings"]:
        yield 3, finding["kind"].capitalize()
        yield 0, finding["text"]
        yield 0, "Evidence: " + (", ".join(finding["evidence_ids"]) or "None; unresolved question.")
    yield 2, "Limitations and unknowns"
    for limitation in report["limitations"]:
        yield 0, limitation
    yield 0, "Packaging checks record shape and citation membership only. It does not authenticate REA evidence IDs, verify analyst conclusions, or rerun analysis. Source coverage, authority and limitations remain those of the saved records. Complete input documents are retained in report.json."
    yield 2, "Evidence index"
    for record in records.values():
        yield 3, record["operation"]
        yield 0, record["evidence_id"]
        yield 0, f"Confidence: {record['confidence']}; authority: {record['authority']}"
        yield 0, "Subject: " + json.dumps(record["subject"], ensure_ascii=False)
        for limitation in record["limitations"]:
            yield 0, "Source limitation: " + limitation


def write_pdf(path, content):
    fonts = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("Report", str(fonts / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("ReportBold", str(fonts / "VeraBd.ttf")))
    body = ParagraphStyle("ReportBody", fontName="Report", fontSize=9, leading=14, spaceAfter=8)
    styles_by_level = {0: body}
    for level, size in [(1, 21), (2, 14), (3, 10)]:
        styles_by_level[level] = ParagraphStyle(
            f"ReportH{level}", parent=body, fontName="ReportBold", fontSize=size,
            leading=size + 5, spaceBefore=12, keepWithNext=True,
            textColor=colors.HexColor("#183b56"))
    story = []
    for level, value in content:
        font = pdfmetrics.getFont("ReportBold" if level else "Report")
        unsupported = {char for char in value if not char.isspace() and ord(char) not in font.face.charToGlyph}
        if unsupported:
            raise ValueError(f"PDF font lacks characters: {''.join(sorted(unsupported))!r}; use supported text")
        story.append(Paragraph(escape(value).replace("\n", "<br/>"), styles_by_level[level]))
    story.append(Spacer(1, 8))

    def footer(canvas, doc):
        canvas.setFont("Report", 8)
        canvas.setFillColor(colors.HexColor("#52616b"))
        canvas.drawString(0.7 * inch, 0.4 * inch, "REA evidence report")
        canvas.drawRightString(doc.pagesize[0] - 0.7 * inch, 0.4 * inch, str(doc.page))

    SimpleDocTemplate(str(path), title=content[0][1], author="REA report",
                      leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                      topMargin=0.6 * inch, bottomMargin=0.65 * inch).build(
                          story, onFirstPage=footer, onLaterPages=footer)


def package(report_path, evidence_paths, output, max_input_mib=64):
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    if max_input_mib < 1:
        raise ValueError("--max-input-mib must be positive")
    # ponytail: whole-document JSON, 64 MiB default; raise explicitly or stream if real reports need more.
    remaining = max_input_mib * 1024 * 1024
    raw, report = read_json(report_path, remaining)
    remaining -= len(raw)
    if not isinstance(report, dict):
        raise ValueError("Report must be a JSON object")
    for key in ("title", "summary", "scope"):
        text(report[key])
    if "\n" in report["title"]:
        raise ValueError("Report title must be one line")
    strings(report["limitations"])
    if not isinstance(report["findings"], list) or not report["findings"]:
        raise ValueError("Provide at least one finding or explicit unknown")
    sources, records = [], {}
    for source in evidence_paths:
        raw, document = read_json(source, remaining)
        remaining -= len(raw)
        for record in evidence_records(document):
            identity = record["evidence_id"]
            if identity in records and records[identity] != record:
                raise ValueError(f"Conflicting records for {identity}")
            records[identity] = record
        sources.append({"file": source.name, "sha256": hashlib.sha256(raw).hexdigest(), "document": document})
    for finding in report["findings"]:
        if not isinstance(finding, dict) or finding.get("kind") not in {"observed", "derived", "inferred", "unknown"}:
            raise ValueError("Finding kind must be observed, derived, inferred or unknown")
        text(finding["text"])
        refs = strings(finding["evidence_ids"])
        if not refs and finding["kind"] != "unknown":
            raise ValueError("Findings require evidence IDs; use unknown for unanswered questions")
        if set(refs) - records.keys():
            raise ValueError("Finding cites an evidence ID absent from supplied records")
    content = list(sections(report, records))
    output = output.absolute()
    with tempfile.TemporaryDirectory(prefix=".rea-report-", dir=output.parent) as tmp:
        stage = Path(tmp)
        (stage / "report.json").write_text(json.dumps(
            {"schema": "rea-report/1", "report": report, "evidence_sources": sources},
            ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (stage / "report.md").write_text("\n\n".join(
            ("#" * level + " " if level else "") + markdown_text(value)
            for level, value in content) + "\n", encoding="utf-8")
        write_pdf(stage / "report.pdf", content)
        output.mkdir(mode=0o700)  # Refuse existing files, directories and symlinks.
        for source in stage.iterdir():
            source.rename(output / source.name)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="Analyst-authored report JSON")
    parser.add_argument("--evidence", type=Path, action="append", required=True, help="Complete record or canonical bundle; repeatable")
    parser.add_argument("--output", type=Path, required=True, help="New directory under an existing parent")
    parser.add_argument("--max-input-mib", type=int, default=64, help="Combined input byte budget (default: 64 MiB)")
    args = parser.parse_args()
    try:
        output = package(args.report, args.evidence, args.output, args.max_input_mib)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"rea-report: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
