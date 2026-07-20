#!/usr/bin/env python3
"""Deterministic prepare/resolve/finalize orchestrator (plan §5.4, §7; DR-02).

Scaffold: validates core gates and owns CLI entrypoints. Full protection,
pattern recomputation, and edit application land in subsequent tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from codes import (  # noqa: E402
    CONFIDENCE_REVIEW_THRESHOLD,
    MODES,
    REASON_CATEGORIES,
    SCHEMA_VERSIONS,
)
from profile import ProfileError, assert_revision_allowed  # noqa: E402


class HumanizeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HumanizeError("MALFORMED_EDIT_PROPOSAL", f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise HumanizeError("MALFORMED_EDIT_PROPOSAL", "JSON root must be an object")
    return data


def _require_schema(data: dict[str, Any], expected: str) -> None:
    got = data.get("schema_version")
    if got != expected:
        raise HumanizeError(
            "MALFORMED_EDIT_PROPOSAL",
            f"expected schema_version {expected}, got {got!r}",
        )


def review_code_for_proposal(confidence: float, requires_review: bool) -> str | None:
    """Deterministic review precedence (DR-19)."""
    if confidence < CONFIDENCE_REVIEW_THRESHOLD:
        return "LOW_CONFIDENCE_PROPOSAL"
    if requires_review:
        return "MODEL_REQUESTED_REVIEW"
    return None


def validate_consent_tuple(consent: dict, route: dict) -> None:
    _require_schema(consent, SCHEMA_VERSIONS["voice-consent"])
    _require_schema(route, SCHEMA_VERSIONS["route-resolution"])
    pairs = (
        ("harness", consent.get("harness"), route.get("harness")),
        ("provider_route", consent.get("provider_route"), route.get("provider_route")),
        (
            "resolved_backend_model",
            consent.get("resolved_backend_model"),
            route.get("resolved_backend_model"),
        ),
    )
    for name, c, r in pairs:
        if not c or not r:
            raise HumanizeError("BACKEND_RESOLUTION_REQUIRED", f"missing {name}")
        if c != r:
            if name == "resolved_backend_model":
                raise HumanizeError("CONSENT_BACKEND_MISMATCH", f"{name} mismatch")
            raise HumanizeError("CONSENT_INVALID", f"{name} mismatch")
    dynamic = bool(route.get("dynamic_route"))
    data_class = consent.get("data_class")
    if dynamic and data_class == "raw_private":
        raise HumanizeError(
            "CONSENT_INVALID",
            "dynamic routes cannot carry raw_private data",
        )


def cmd_prepare(args: argparse.Namespace) -> int:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    source = Path(args.source)
    if not source.is_file():
        print(f"error: source not found: {source}", file=sys.stderr)
        return 2
    mode = args.mode
    if mode not in MODES:
        print(f"error: invalid mode {mode!r}", file=sys.stderr)
        return 2

    profile_obj = None
    if args.profile:
        p = Path(args.profile)
        if not p.is_file():
            print(f"error: profile not found: {p}", file=sys.stderr)
            return 2
        profile_obj = {"_path": str(p)}

    try:
        assert_revision_allowed(profile_obj, mode)
    except ProfileError as e:
        audit = {
            "schema_version": SCHEMA_VERSIONS["voice-audit"],
            "document_id": args.document_id or source.stem,
            "status": "rejected",
            "source_sha256": _sha256_file(source),
            "output_sha256": None,
            "edit_ids": [],
            "evidence_by_edit": [],
            "verifier": {},
            "review_findings": [],
            "review_approval_ids": [],
            "voice_metric_warnings": [],
            "warnings": [],
            "rejection_codes": [e.code],
        }
        (outdir / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(f"rejected: {e.code}")
        return 1

    consent = _load_json(Path(args.consent)) if args.consent else None
    route = _load_json(Path(args.route_resolution)) if args.route_resolution else None
    if mode != "diagnose-only":
        if not consent or not route:
            print(
                "error: consent and route-resolution required for revision modes",
                file=sys.stderr,
            )
            return 2
        try:
            validate_consent_tuple(consent, route)
        except HumanizeError as e:
            print(f"rejected: {e.code}: {e}", file=sys.stderr)
            return 1

    source_text = source.read_text(encoding="utf-8")
    source_sha = _sha256_text(source_text)
    prepared = {
        "schema_version": SCHEMA_VERSIONS["prepared-state"],
        "run_id": args.run_id or "run-scaffold",
        "document_id": args.document_id or source.stem,
        "mode": mode,
        "profile_id": (consent or {}).get("profile_id") if consent else None,
        "source_sha256": source_sha,
        "protected_source_sha256": source_sha,
        "passage_map": [
            {
                "passage_id": "document-001",
                "start_byte": 0,
                "end_byte": len(source_text.encode("utf-8")),
                "sha256": source_sha,
            }
        ],
        "sentinels": [],
        "consent_sha256": _sha256_text(json.dumps(consent, sort_keys=True, default=str))
        if consent
        else None,
        "route_resolution_sha256": _sha256_text(json.dumps(route, sort_keys=True, default=str))
        if route
        else None,
    }
    (outdir / "prepared-state.json").write_text(
        json.dumps(prepared, indent=2) + "\n", encoding="utf-8"
    )
    (outdir / "protected-source.txt").write_text(source_text, encoding="utf-8")
    if mode == "diagnose-only":
        audit = {
            "schema_version": SCHEMA_VERSIONS["voice-audit"],
            "document_id": prepared["document_id"],
            "status": "accepted",
            "source_sha256": source_sha,
            "output_sha256": None,
            "edit_ids": [],
            "evidence_by_edit": [],
            "verifier": {"note": "diagnose-only scaffold; no revision emitted"},
            "review_findings": [],
            "review_approval_ids": [],
            "voice_metric_warnings": [],
            "warnings": ["diagnose_only_scaffold"],
            "rejection_codes": [],
        }
        (outdir / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"prepared: {outdir / 'prepared-state.json'}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    try:
        prepared = _load_json(Path(args.prepared))
        _require_schema(prepared, SCHEMA_VERSIONS["prepared-state"])
        proposal = _load_json(Path(args.proposal))
        _require_schema(proposal, SCHEMA_VERSIONS["edit-proposal"])
    except HumanizeError as e:
        print(f"rejected: {e.code}: {e}", file=sys.stderr)
        return 1

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    review_findings = []
    for item in proposal.get("proposals") or []:
        if not isinstance(item, dict):
            print("rejected: MALFORMED_EDIT_PROPOSAL", file=sys.stderr)
            return 1
        conf = float(item.get("confidence", 0))
        req = bool(item.get("requires_review", False))
        code = review_code_for_proposal(conf, req)
        rc = item.get("reason_category")
        if rc not in REASON_CATEGORIES:
            print(
                f"rejected: MALFORMED_EDIT_PROPOSAL invalid reason_category {rc!r}",
                file=sys.stderr,
            )
            return 1
        if code:
            review_findings.append(
                {
                    "proposal_id": item.get("proposal_id"),
                    "review_code": code,
                    "confidence": conf,
                    "requires_review": req,
                }
            )

    if args.route_resolution:
        try:
            route = _load_json(Path(args.route_resolution))
            _require_schema(route, SCHEMA_VERSIONS["route-resolution"])
        except HumanizeError as e:
            print(f"rejected: {e.code}: {e}", file=sys.stderr)
            return 1

    result = {
        "schema_version": "resolve-scaffold.v1",
        "prepared_source_sha256": prepared.get("source_sha256"),
        "proposal_document_id": proposal.get("document_id"),
        "review_findings": review_findings,
        "status": "review_required" if review_findings else "awaiting_verifier",
        "note": "scaffold resolve does not yet apply edits; full engine pending",
    }
    (outdir / "resolve-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(f"resolve: {outdir / 'resolve-result.json'}")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    print(
        "finalize: scaffold only — full verification/restore/emit path not yet implemented",
        file=sys.stderr,
    )
    return 2


def cmd_approve(args: argparse.Namespace) -> int:
    print(
        "approve: interactive user-only gate not yet implemented (DR-16)",
        file=sys.stderr,
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="humanize.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare", help="Validate consent/profile and emit prepared state")
    prep.add_argument("--source", required=True)
    prep.add_argument("--profile")
    prep.add_argument("--consent")
    prep.add_argument("--route-resolution")
    prep.add_argument("--mode", default="conservative")
    prep.add_argument("--document-id")
    prep.add_argument("--run-id")
    prep.add_argument("--outdir", required=True)
    prep.set_defaults(func=cmd_prepare)

    res = sub.add_parser("resolve", help="Validate proposals and stage candidate (scaffold)")
    res.add_argument("--prepared", required=True)
    res.add_argument("--proposal", required=True)
    res.add_argument("--route-resolution")
    res.add_argument("--outdir", required=True)
    res.set_defaults(func=cmd_resolve)

    fin = sub.add_parser("finalize", help="Verify and emit accepted output")
    fin.add_argument("--prepared", required=True)
    fin.add_argument("--candidate", required=True)
    fin.add_argument("--verifier", required=True)
    fin.add_argument("--outdir", required=True)
    fin.set_defaults(func=cmd_finalize)

    appr = sub.add_parser("approve", help="User-only review approval")
    appr.add_argument("--audit", required=True)
    appr.add_argument("--finding", required=True)
    appr.add_argument("--profile-dir", required=True)
    appr.set_defaults(func=cmd_approve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
