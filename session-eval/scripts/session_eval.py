#!/usr/bin/env python3
"""Portable shared session-eval CLI: ingest through redacted HTML report.

Pipeline:
  ingest immutable snapshots
  → history.enrich_registry (no intermediate history write)
  → evaluate with exact ingest/.private/snapshots and registry
  → optional explicitly approved judge (imported only when selected)
  → recommendations
  → history comparisons/store
  → optional ATIF
  → render

Missing implementation dependencies fail explicitly. No fake fallbacks.
Judge module import/execution happens only when judge options are selected.
Default path makes no provider calls. Report consumes the redacted receipt only.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


class SessionEvalError(Exception):
    """Expected local-input or missing-dependency error."""


def _load_stage(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise SessionEvalError(f"missing implementation dependency: {name}") from exc


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _registry_argument(receipt: dict[str, Any]) -> dict[str, Any]:
    """evaluate.evaluate_receipt expects a dict; contract registry is receipt.skills."""

    skills = receipt.get("skills")
    if isinstance(skills, dict):
        return skills
    if isinstance(skills, list):
        return {"skills": skills}
    return {"skills": []}


def _parse_json_value(raw: str | None) -> Any:
    if raw is None or raw == "":
        return None
    text = str(raw)
    candidate = Path(text).expanduser()
    suffix = candidate.suffix.lower()
    if suffix == ".json" and candidate.is_file():
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SessionEvalError(f"unreadable --judge-evidence JSON: {candidate}: {exc}") from exc
        return payload
    if suffix in {".md", ".jsonl", ".txt"}:
        raise SessionEvalError("judge evidence must be redacted JSON, not a session or full.md file")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SessionEvalError(f"unreadable --judge-evidence JSON: {exc}") from exc


def _judge_selected(options: dict[str, Any] | None) -> bool:
    if not options:
        return False
    return any(
        options.get(key)
        for key in ("rubric_ids", "provider", "model", "recipient", "semantic_evidence", "auth_env")
    )


def _run_judge(
    receipt: dict[str, Any],
    *,
    out: Path,
    snapshot_root: Path,
    options: dict[str, Any],
) -> tuple[dict[str, Any], Path | None]:
    judge = _load_stage("judge")
    rubric_ids = list(options.get("rubric_ids") or [])
    provider = options.get("provider")
    model = options.get("model")
    recipient = options.get("recipient")
    missing = [
        name
        for name, value in (
            ("judge_rubric", rubric_ids),
            ("judge_provider", provider),
            ("judge_model", model),
            ("judge_recipient", recipient),
        )
        if not value
    ]
    if missing:
        raise SessionEvalError(
            "judge selected but incomplete; required: --judge-rubric, --judge-provider, "
            "--judge-model, --judge-recipient"
        )
    preview = judge.prepare_judge_request(
        receipt,
        snapshot_root=snapshot_root,
        rubric_ids=rubric_ids,
        provider=provider,
        model=model,
        recipient=recipient,
        semantic_evidence=options.get("semantic_evidence"),
    )
    approval = judge.approve_interactively(preview)
    if approval is None:
        return receipt, None
    judged, judged_path = judge.judge_receipt(
        receipt,
        out=out,
        snapshot_root=snapshot_root,
        rubric_ids=rubric_ids,
        provider=provider,
        model=model,
        recipient=recipient,
        approval=approval,
        semantic_evidence=options.get("semantic_evidence"),
        auth_env=options.get("auth_env"),
    )
    return judged, judged_path


def evaluate_sessions(
    *,
    paths: Sequence[str | Path] | None = None,
    harnesses: Sequence[str] | None = None,
    since: str | None = None,
    out: str | Path | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    first_party_root: str | Path | None = None,
    history_root: str | Path | None = None,
    baseline: str | Path | None = None,
    atif: bool = False,
    workgraph: str | Path | None = None,
    workgraph_manifest: str | Path | None = None,
    workgraph_allowlist: str | Path | None = None,
    workgraph_bin: str | Path | None = None,
    judge_options: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    """Run the portable pipeline. Returns (receipt, actual receipt path, actual report path)."""

    ingest_mod = _load_stage("ingest")
    history_mod = _load_stage("history")
    evaluate_mod = _load_stage("evaluate")
    report_mod = _load_stage("report")

    receipt, ingest_path = ingest_mod.ingest(
        paths=paths,
        harnesses=harnesses,
        out=out,
        skill_roots=skill_roots,
        since=since,
    )
    out_dir = ingest_path.parent
    snapshot_root = out_dir / ".private" / "snapshots"

    receipt = history_mod.enrich_registry(
        receipt,
        skill_roots=skill_roots,
        first_party_root=first_party_root,
    )

    receipt, eval_path = evaluate_mod.evaluate_receipt(
        receipt=receipt,
        receipt_path=ingest_path,
        snapshot_root=snapshot_root,
        out=out_dir,
        workgraph=workgraph,
        workgraph_manifest=workgraph_manifest,
        workgraph_allowlist=workgraph_allowlist,
        workgraph_bin=workgraph_bin,
        registry=_registry_argument(receipt),
        first_party_root=first_party_root,
        report_html=None,
    )
    receipt_path = eval_path

    if _judge_selected(judge_options):
        receipt, judged_path = _run_judge(
            receipt,
            out=out_dir,
            snapshot_root=snapshot_root,
            options=judge_options or {},
        )
        if judged_path is not None:
            receipt_path = judged_path

    recommend_mod = _load_stage("recommend")
    receipt, recommend_path = recommend_mod.recommend_receipt(
        receipt,
        out=out_dir,
        first_party_root=first_party_root,
        adapter_root=None,
    )
    receipt_path = recommend_path

    receipt, history_path = history_mod.history(
        receipt,
        out=out_dir,
        skill_roots=skill_roots,
        first_party_root=first_party_root,
        history_root=history_root,
        baseline=baseline,
    )
    receipt_path = history_path

    if atif:
        atif_mod = _load_stage("atif")
        atif_mod.export_atif(receipt, out_dir)

    report_path = report_mod.render_report(receipt, out=out_dir)
    return receipt, receipt_path, report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval",
        description="Portable session-eval CLI: local ingest through offline HTML report.",
    )
    parser.add_argument("--path", dest="paths", action="append", help="local session path (repeatable)")
    parser.add_argument("--harness", dest="harnesses", action="append", help="harness filter (repeatable)")
    parser.add_argument("--since", default=None, help="mtime bound: ISO-8601, days, or all (default: ingest 7 days)")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--skill-root", dest="skill_roots", action="append", help="skill root (repeatable)")
    parser.add_argument("--first-party-root", default=None, help="first-party skills root")
    parser.add_argument("--history-root", default=None, help="immutable history directory")
    parser.add_argument("--baseline", default=None, help="named baseline receipt path")
    parser.add_argument("--atif", action="store_true", help="opt-in ATIF export")
    parser.add_argument("--workgraph", default=None, help="workgraph run directory")
    parser.add_argument("--workgraph-manifest", default=None, help="workgraph score manifest")
    parser.add_argument("--workgraph-allowlist", default=None, help="workgraph mutation allowlist")
    parser.add_argument("--workgraph-bin", default=None, help="workgraph-eval-score binary")
    parser.add_argument("--judge-rubric", dest="judge_rubrics", action="append", help="opt-in judge rubric id (repeatable)")
    parser.add_argument("--judge-provider", default=None, help="opt-in judge provider")
    parser.add_argument("--judge-model", default=None, help="opt-in judge model")
    parser.add_argument("--judge-recipient", default=None, help="opt-in judge recipient endpoint")
    parser.add_argument("--judge-evidence", default=None, help="opt-in redacted semantic evidence JSON")
    parser.add_argument("--judge-auth-env", default=None, help="environment variable name for judge auth (never copied into the receipt)")
    return parser


def _judge_options_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    options = {
        "rubric_ids": list(args.judge_rubrics or []),
        "provider": args.judge_provider,
        "model": args.judge_model,
        "recipient": args.judge_recipient,
        "semantic_evidence": _parse_json_value(args.judge_evidence),
        "auth_env": args.judge_auth_env,
    }
    if not _judge_selected(options):
        return None
    return options


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        judge_options = _judge_options_from_args(args)
        receipt, receipt_path, report_path = evaluate_sessions(
            paths=args.paths,
            harnesses=args.harnesses,
            since=args.since,
            out=args.out,
            skill_roots=args.skill_roots,
            first_party_root=args.first_party_root,
            history_root=args.history_root,
            baseline=args.baseline,
            atif=args.atif,
            workgraph=args.workgraph,
            workgraph_manifest=args.workgraph_manifest,
            workgraph_allowlist=args.workgraph_allowlist,
            workgraph_bin=args.workgraph_bin,
            judge_options=judge_options,
        )
    except SessionEvalError as exc:
        print(f"session-eval: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Surface sibling expected errors without fabricating a second schema.
        name = type(exc).__name__
        if name.endswith("Error"):
            print(f"session-eval: {exc}", file=sys.stderr)
            return 1
        raise
    coverage = receipt.get("coverage") if isinstance(receipt.get("coverage"), dict) else {}
    summary = {
        "receipt": str(receipt_path),
        "report": str(report_path),
        "hard_pass": bool(receipt.get("hard_pass")),
        "infra_ok": bool(receipt.get("infra_ok")),
        "coverage": coverage,
        "parse_errors": receipt.get("parse_errors", 0),
        "schema": receipt.get("schema"),
        "catalog_id": receipt.get("catalog_id"),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
