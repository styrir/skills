#!/usr/bin/env python3
"""First-party skill/adapter recommendations from session-eval findings.

Consumes a ``styrir-session-eval/v0`` receipt (typically after evaluate) and
emits evidence-bound ``recommendations[]``.  This module does not ingest
sessions, run checks, render HTML, call providers, or mutate sources, skills,
or adapters.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import ingest as ingest_mod

UNKNOWN = ingest_mod.UNKNOWN
RECEIPT_SCHEMA = "styrir-session-eval/v0"
RECOMMENDER_VERSION = "1.0.0"
RECOMMENDER_STAGE = "session-eval-recommend"
DEFAULT_FIRST_PARTY_ROOT = Path.home() / "Code" / "skills"
AUTHORITATIVE_SOURCES = (
    "grok.prompt_context",
    "claude.skill_path",
    "claude.skills",
)
DIGEST_HEX = re.compile(r"^[0-9a-fA-F]{64}$")
PARSER_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,31}$")
SECRET_RE = re.compile(r"(?i)(?:sk|pk|token|secret|key)[-_][A-Za-z0-9._=-]{6,}")

SKILL_CHECK_IDS = {
    "tool.unpaired",
    "tool.repeat_loop",
    "tool.secret_pattern",
    "claim.command_outcome",
    "skill.registry_unreadable",
    "session.identity_missing",
    "judge.completeness",
    "judge.grounding",
    "judge.tool_selection",
    "judge.friction",
}
ADAPTER_CHECK_IDS = {
    "ingest.parse_error",
    "ingest.sidecar_not_stream",
    "tokens.unknown_not_zero",
    "session.clock_skew",
}
UNKNOWN_LIMITATION_IDS = {
    "claim.completion": "recommend.unknown_completion_outcome",
    "claim.command_outcome": "recommend.unknown_command_outcome",
}
POLICY_GAP = "claim.historical_policy_unavailable"
POINTER_KEYS = ("source_path", "snapshot_hash", "parser_version", "event_range", "evidence_hash")

ACTIONS = {
    "tool.unpaired": (
        "State that tool_use without a paired result after explicit terminal evidence is a failure.",
        "Run a new comparable session with the revised skill and verify explicit terminal evidence plus paired tool results. Preserve the original snapshot and its failing result; re-ingesting it must not rewrite history.",
    ),
    "tool.repeat_loop": (
        "State that four or more consecutive same-tool same-normalized-args invocations without a progress marker is a failure.",
        "Run a new comparable session with the revised skill and verify a same-tool sequence resets on a progress marker or stays below four. Preserve the original snapshot; re-ingesting it must not rewrite history.",
    ),
    "tool.secret_pattern": (
        "State that session and tool payloads must not contain key/token secret patterns, and that matches are recorded as hash plus range only.",
        "Run a new comparable session with the revised skill and verify tool.secret_pattern passes without exporting secret text. Preserve the original snapshot pointers.",
    ),
    "claim.command_outcome": (
        "State that a claimed command success is a failure when the identified command's final recorded outcome contradicts the claim.",
        "Run a new comparable session with the revised skill and verify claim.command_outcome matches the recorded final outcome. Preserve the original snapshot; do not consult the live checkout as historical truth.",
    ),
    "skill.registry_unreadable": (
        "Ensure the recorded SKILL.md path exists and includes name: frontmatter.",
        "Re-evaluate a new session that lists the skill path and verify skill.registry_unreadable passes. Preserve the original snapshot.",
    ),
    "session.identity_missing": (
        "State that a session record must carry native identity or the documented fallback source stem.",
        "Re-ingest a new comparable session and verify session.identity_missing passes. Preserve the original snapshot identity.",
    ),
    "judge.completeness": (
        "State that unmet user requests must be fulfilled or explicitly disclosed before terminal.",
        "Run a new comparable session with the revised skill and verify judge.completeness against the same evidence-pointer schema without provider calls from this stage. Preserve the original snapshot.",
    ),
    "judge.grounding": (
        "State that claims about files, commands, or tests must not contradict evidence this session actually recorded.",
        "Run a new comparable session with the revised skill and verify judge.grounding using recorded snapshot evidence only. Preserve the original snapshot.",
    ),
    "judge.tool_selection": (
        "State that the selected tool must be appropriate for the stated step among tools actually recorded in the session.",
        "Run a new comparable session with the revised skill and verify judge.tool_selection against the recorded inventory. Preserve the original snapshot.",
    ),
    "judge.friction": (
        "State that the assistant must not cause avoidable user re-prompting by ignoring stated constraints or omitting required disclosure.",
        "Run a new comparable session with the revised skill and verify judge.friction has no avoidable re-prompt evidence. Preserve the original snapshot.",
    ),
    "ingest.parse_error": (
        "Repair the associated first-party adapter so non-object JSONL/JSON records are counted as parse failures and never treated as a behavioral pass.",
        "After that adapter repair, re-ingest the original snapshot and verify ingest.parse_error is pass, parse_errors remain counted, and source bytes are unchanged.",
    ),
    "ingest.sidecar_not_stream": (
        "Repair the associated first-party adapter so the primary stream stays authoritative when a sidecar exists; use the sidecar only to enrich.",
        "After that adapter repair, re-ingest the original snapshot and verify ingest.sidecar_not_stream is pass while the primary stream remains the source. Preserve original bytes.",
    ),
    "tokens.unknown_not_zero": (
        "Repair the associated first-party adapter so absent usage stays unknown rather than writing zero.",
        "After that adapter repair, re-ingest the original snapshot and verify tokens.unknown_not_zero is pass with unknown usage, not a fabricated zero. Preserve original bytes.",
    ),
    "session.clock_skew": (
        "Repair the associated first-party adapter so mixed epoch-seconds and ISO timestamps in one Grok session normalize to a single scale.",
        "After that adapter repair, re-ingest the original snapshot and verify session.clock_skew is pass with one timestamp scale. Preserve original bytes.",
    ),
}


class RecommendError(Exception):
    """An expected local-input error suitable for a concise CLI message."""


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _is_unknown(value: Any) -> bool:
    return value in (None, "", UNKNOWN)


def _canonical(value: Any) -> str:
    return ingest_mod._canonical(value)


def _label(value: Any, limit: int = 240) -> str:
    return ingest_mod._safe_label(value, limit=limit)


def _export_path(value: Any) -> str:
    text = str(value or "")
    if not text:
        return UNKNOWN
    return ingest_mod._export_source_path(text)


def _absolute(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _lexical(path: str | Path) -> Path:
    value = Path(path).expanduser()
    if not value.is_absolute():
        value = Path.cwd() / value
    return Path(os.path.normpath(str(value)))


def _under(path: Path, root: Path | None) -> bool:
    if root is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _looks_sensitive(value: Any) -> bool:
    text = str(value or "")
    if not text:
        return False
    if SECRET_RE.search(text):
        return True
    if "<" in text or ">" in text:
        return True
    return False


def _hash_hex(value: Any) -> str | None:
    """Return lowercase 64-hex when the value is a canonical hash; never echo invalid text."""

    if _is_unknown(value):
        return None
    text = str(value).strip()
    if _looks_sensitive(text):
        return None
    if text.startswith("sha256:"):
        text = text[7:]
    if DIGEST_HEX.fullmatch(text):
        return text.lower()
    return None


def _export_hash(value: Any, *, allow_unknown: bool = False) -> str | None:
    if allow_unknown and value == UNKNOWN:
        return UNKNOWN
    hex_part = _hash_hex(value)
    if hex_part is None:
        return None
    text = str(value).strip()
    if text.startswith("sha256:"):
        return f"sha256:{hex_part}"
    return hex_part


def _export_digest(value: Any) -> str | None:
    hex_part = _hash_hex(value)
    if hex_part is None:
        return None
    return f"sha256:{hex_part}"


def _parser_version_ok(value: Any) -> bool:
    if _is_unknown(value):
        return False
    text = str(value).strip()
    if _looks_sensitive(text):
        return False
    return bool(PARSER_VERSION_RE.fullmatch(text))


def _file_digest(path: Path) -> str:
    try:
        exported = _export_digest(ingest_mod.sha256_file(path))
        return exported or UNKNOWN
    except OSError:
        return UNKNOWN


def _activation_kind(confidence: Any, source: Any) -> str:
    source_text = str(source or "")
    if confidence == "high" or source_text in AUTHORITATIVE_SOURCES or source_text.endswith("prompt_context"):
        return "authoritative"
    if confidence in {"medium", "low"} or source_text:
        return "mention"
    return "absent"


def _historical_digest(skill: dict[str, Any]) -> str:
    for key in ("historical_loaded_digest", "digest"):
        exported = _export_digest(skill.get(key))
        if exported is not None:
            return exported
    return UNKNOWN


def _current_digest(skill: dict[str, Any]) -> str:
    exported = _export_digest(skill.get("current_on_disk_digest"))
    return exported if exported is not None else UNKNOWN


def _resolve_existing_file(path_text: Any, roots: Sequence[Path]) -> Path | None:
    if _is_unknown(path_text):
        return None
    raw = Path(str(path_text)).expanduser()
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(_lexical(raw))
        for root in roots:
            candidates.append(root / raw)
            if raw.parts and raw.parts[0] == root.name:
                candidates.append(root.parent / raw)
    seen: set[str] = set()
    for candidate in candidates:
        marker = str(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def _ownership(resolved: Path | None, first_party_root: Path | None) -> str:
    if resolved is None:
        return "unresolved"
    if first_party_root is None:
        return "unresolved"
    return "first_party" if _under(resolved, first_party_root) else "external"


def _event_range(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if "start_line" not in value:
        return None
    start = value.get("start_line")
    end = value.get("end_line", start)
    if start in (None, UNKNOWN) or end in (None, UNKNOWN):
        return None
    try:
        start_line = int(start)
        end_line = int(end)
    except (TypeError, ValueError):
        return None
    if start_line < 1 or end_line < start_line:
        return None
    return {"start_line": start_line, "end_line": end_line}


def _path_aliases(path_text: Any) -> set[str]:
    if _is_unknown(path_text):
        return set()
    raw = str(path_text)
    aliases = {raw}
    try:
        expanded = str(Path(raw).expanduser())
        aliases.add(expanded)
        candidate = Path(raw).expanduser()
        if candidate.exists():
            aliases.add(str(candidate.resolve()))
    except OSError:
        pass
    return aliases


def _run_source_paths(run: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    paths |= _path_aliases(run.get("source_path"))
    snapshot = run.get("source_snapshot") if isinstance(run.get("source_snapshot"), dict) else {}
    files = snapshot.get("files") if isinstance(snapshot.get("files"), list) else []
    for item in files:
        if isinstance(item, dict):
            paths |= _path_aliases(item.get("path"))
    return paths


def _source_in_run(source_path: Any, run: dict[str, Any]) -> bool:
    return bool(_path_aliases(source_path) & _run_source_paths(run))


def _run_snapshot_hex(run: dict[str, Any]) -> str | None:
    snapshot = run.get("source_snapshot") if isinstance(run.get("source_snapshot"), dict) else {}
    return _hash_hex(snapshot.get("sha256"))


def _pointer(check_id: str, item: dict[str, Any], run: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    if any(key not in item for key in POINTER_KEYS):
        return None
    source_path = item.get("source_path")
    if _is_unknown(source_path):
        return None
    snapshot_export = _export_hash(item.get("snapshot_hash"), allow_unknown=False)
    item_hex = _hash_hex(item.get("snapshot_hash"))
    run_hex = _run_snapshot_hex(run)
    if snapshot_export is None or item_hex is None or run_hex is None or item_hex != run_hex:
        return None
    parser_version = item.get("parser_version")
    run_parser = run.get("parser_version")
    if not _parser_version_ok(parser_version) or not _parser_version_ok(run_parser):
        return None
    if str(parser_version).strip() != str(run_parser).strip():
        return None
    event_range = _event_range(item.get("event_range"))
    if event_range is None:
        return None
    evidence_value = item.get("evidence_hash")
    if evidence_value == UNKNOWN:
        evidence_export: str | None = UNKNOWN
    else:
        evidence_export = _export_hash(evidence_value, allow_unknown=False)
        if evidence_export is None:
            return None
    if not _source_in_run(source_path, run):
        return None
    return {
        "check_id": str(check_id),
        "source_path": _export_path(source_path),
        "snapshot_hash": snapshot_export,
        "parser_version": str(parser_version).strip(),
        "event_range": event_range,
        "evidence_hash": evidence_export,
    }


def _complete_pointers(check: dict[str, Any], run: dict[str, Any]) -> list[dict[str, Any]] | None:
    """All recorded evidence items must be complete and belong to this run."""

    check_id = str(check.get("id") or UNKNOWN)
    evidence = check.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return None
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in evidence:
        pointer = _pointer(check_id, item, run) if isinstance(item, dict) else None
        if pointer is None:
            return None
        key = _canonical(pointer)
        if key in seen:
            continue
        seen.add(key)
        rows.append(pointer)
    return rows or None


def _safe_pointers(check: dict[str, Any], run: dict[str, Any]) -> list[dict[str, Any]]:
    """Valid pointers only; incomplete/stale/sensitive items are dropped, never copied."""

    check_id = str(check.get("id") or UNKNOWN)
    evidence = check.get("evidence") if isinstance(check.get("evidence"), list) else []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in evidence:
        pointer = _pointer(check_id, item, run) if isinstance(item, dict) else None
        if pointer is None:
            continue
        key = _canonical(pointer)
        if key in seen:
            continue
        seen.add(key)
        rows.append(pointer)
    return rows


def _skill_name(skill: dict[str, Any], resolved: Path | None) -> str:
    name = skill.get("name")
    if not _is_unknown(name):
        return _label(name)
    if resolved is not None:
        parts = [part for part in resolved.parts if part]
        if parts and parts[-1].casefold() == "skill.md" and len(parts) > 1:
            return _label(parts[-2])
        return _label(resolved.stem)
    return UNKNOWN


def _classify_skill(skill: dict[str, Any], first_party_root: Path) -> dict[str, Any]:
    recorded = skill.get("path")
    resolved = _resolve_existing_file(recorded, [first_party_root])
    ownership = _ownership(resolved, first_party_root)
    kind = _activation_kind(skill.get("confidence"), skill.get("source"))
    historical = _historical_digest(skill)
    current = _current_digest(skill)
    if current == UNKNOWN and resolved is not None:
        current = _file_digest(resolved)
    return {
        "skill": skill,
        "recorded_path": recorded,
        "resolved": resolved,
        "ownership": ownership,
        "activation_kind": kind,
        "historical": historical,
        "current": current,
        "name": _skill_name(skill, resolved),
    }


def _run_skills(run: dict[str, Any], first_party_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    skills = run.get("skills") if isinstance(run.get("skills"), list) else []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        classified = _classify_skill(skill, first_party_root)
        key = _canonical(
            {
                "path": str(classified["resolved"] or classified["recorded_path"] or UNKNOWN),
                "historical": classified["historical"],
                "source": skill.get("source"),
                "kind": classified["activation_kind"],
            }
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(classified)
    return rows


def _authoritative_candidates(skills: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        item
        for item in skills
        if item["activation_kind"] == "authoritative"
        and item["ownership"] == "first_party"
        and item["resolved"] is not None
        and item["historical"] != UNKNOWN
    ]
    rows.sort(key=lambda item: (str(item["resolved"]), item["historical"], item["name"]))
    return rows


def _unique_skills(skills: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in skills:
        key = (str(item["resolved"]), item["historical"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _skill_bound_by_evidence(skill: dict[str, Any], pointers: Sequence[dict[str, Any]]) -> bool:
    aliases = _path_aliases(skill.get("resolved")) | _path_aliases(skill.get("recorded_path"))
    for pointer in pointers:
        if _path_aliases(pointer.get("source_path")) & aliases:
            return True
    return False


def _skill_bind_limitation(skills: Sequence[dict[str, Any]]) -> str:
    if not skills:
        return "recommend.missing_target_attribution"
    kinds = {item["activation_kind"] for item in skills}
    ownerships = {item["ownership"] for item in skills}
    if "authoritative" in kinds:
        authoritative = [item for item in skills if item["activation_kind"] == "authoritative"]
        if any(item["ownership"] == "external" for item in authoritative) and not any(
            item["ownership"] == "first_party" and item["resolved"] is not None for item in authoritative
        ):
            return "recommend.external_target"
        if any(item["ownership"] == "unresolved" or item["resolved"] is None for item in authoritative) and not any(
            item["ownership"] == "first_party" and item["resolved"] is not None for item in authoritative
        ):
            return "recommend.unresolved_target"
        if any(item["historical"] == UNKNOWN for item in authoritative):
            return "recommend.historical_digest_unknown"
    if kinds <= {"mention", "absent"} or "authoritative" not in kinds:
        if ownerships == {"external"}:
            return "recommend.external_target"
        if ownerships <= {"unresolved", "external"} and "unresolved" in ownerships:
            return "recommend.unresolved_target"
        return "recommend.mention_only"
    return "recommend.missing_target_attribution"


def _choose_skill(
    skills: Sequence[dict[str, Any]],
    pointers: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    """Bind one first-party skill, or a null limitation independent of list order."""

    candidates = _unique_skills(_authoritative_candidates(skills))
    bound = _unique_skills([item for item in candidates if _skill_bound_by_evidence(item, pointers)])
    if len(bound) == 1:
        return bound[0], None
    if len(bound) > 1:
        return None, "recommend.ambiguous_target"
    if len(candidates) == 1:
        return candidates[0], None
    if len(candidates) > 1:
        return None, "recommend.ambiguous_target"
    return None, _skill_bind_limitation(skills)


def _explicit_adapter_path(_run: dict[str, Any], _receipt: dict[str, Any]) -> Path | None:
    """Ingest/evaluate do not record adapter filesystem paths. Do not invent one."""

    return None


def _skill_target(bound: dict[str, Any]) -> dict[str, Any]:
    resolved: Path = bound["resolved"]
    return {
        "kind": "skill",
        "path": _export_path(str(resolved)),
        "digest": bound["historical"],
        "name": bound["name"],
    }


def _rationale(check_id: str, target: dict[str, Any], recurring: bool) -> str:
    digest = target.get("digest") or UNKNOWN
    kind = target.get("kind") or "skill"
    if recurring:
        return f"Recurring {check_id} fails on this first-party {kind} digest {digest}."
    return f"{check_id} failed on this first-party {kind} digest {digest}."


def _action_fields(check_id: str, target: dict[str, Any], recurring: bool) -> tuple[str, str, str]:
    action, verification = ACTIONS.get(
        check_id,
        (
            f"Record an evidence-bound correction on this first-party {target.get('kind')} for {check_id}.",
            "Run a new comparable session against the revised first-party target and verify the original snapshot still records the failing result.",
        ),
    )
    return action, _rationale(check_id, target, recurring), verification


def _coverage_empty(receipt: dict[str, Any]) -> bool:
    coverage = receipt.get("coverage") if isinstance(receipt.get("coverage"), dict) else {}
    if coverage.get("empty") is True:
        return True
    runs = receipt.get("runs") if isinstance(receipt.get("runs"), list) else []
    return not any(isinstance(run, dict) for run in runs)


def _has_policy_gap(receipt: dict[str, Any], check: dict[str, Any]) -> bool:
    if str(check.get("id") or "") not in {"claim.completion", "claim.command_outcome"}:
        return False
    gaps = receipt.get("proof_gaps") if isinstance(receipt.get("proof_gaps"), list) else []
    for item in gaps:
        if not isinstance(item, dict):
            if item == POLICY_GAP:
                return True
            continue
        token = item.get("claim") or item.get("id") or item.get("kind") or item.get("code")
        if token == POLICY_GAP:
            return True
        serialized = _canonical(item)
        if POLICY_GAP in serialized:
            return True
    observed = str(check.get("observed") or "")
    return "historical_policy" in observed or observed in {"acceptance_set_unknown", "outcome_unknown"}


def _is_material_unknown(check: dict[str, Any]) -> bool:
    if str(check.get("status") or "") != "unknown":
        return False
    return True


def _unknown_limitation_token(check_id: str) -> str:
    return UNKNOWN_LIMITATION_IDS.get(check_id, "recommend.unknown_finding")


def _limitation_row(
    limitation: str,
    evidence: Sequence[dict[str, Any]],
    sort_key: tuple[Any, ...],
) -> dict[str, Any]:
    return {
        "target": None,
        "action": None,
        "rationale": None,
        "evidence": list(evidence),
        "verification": None,
        "confidence": "none",
        "limitation": limitation,
        "_sort": sort_key,
    }


def _action_row(
    target: dict[str, Any],
    check_id: str,
    evidence: Sequence[dict[str, Any]],
    recurring: bool,
    sort_key: tuple[Any, ...],
) -> dict[str, Any]:
    action, rationale, verification = _action_fields(check_id, target, recurring)
    return {
        "target": target,
        "action": action,
        "rationale": rationale,
        "evidence": list(evidence),
        "verification": verification,
        "confidence": "high" if recurring else "medium",
        "limitation": None,
        "_sort": sort_key,
    }


def _merge_evidence(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        key = _canonical(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(
        key=lambda row: (
            str(row.get("check_id") or ""),
            str(row.get("source_path") or ""),
            int((row.get("event_range") or {}).get("start_line") or 0),
            str(row.get("snapshot_hash") or ""),
        )
    )
    return merged


def _iter_run_checks(receipt: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    runs = receipt.get("runs") if isinstance(receipt.get("runs"), list) else []
    for run in runs:
        if not isinstance(run, dict):
            continue
        checks = run.get("checks") if isinstance(run.get("checks"), list) else []
        for check in checks:
            if isinstance(check, dict):
                yield run, check


def _observation_id(run: dict[str, Any], check_id: str) -> tuple[str, str, str]:
    return (
        str(run.get("id") or UNKNOWN),
        _run_snapshot_hex(run) or "",
        check_id,
    )


def _actionable_fail(check: dict[str, Any]) -> bool:
    status = str(check.get("status") or "")
    if status != "fail":
        return False
    check_id = str(check.get("id") or "")
    if check_id in SKILL_CHECK_IDS or check_id in ADAPTER_CHECK_IDS:
        return True
    return str(check.get("kind") or "") == "llm"


def _build_recommendations(
    receipt: dict[str, Any],
    first_party_root: Path,
    adapter_root: Path | None,
) -> list[dict[str, Any]]:
    del adapter_root  # Ownership root only; never a filename guess or implicit target.
    actions: dict[tuple[Any, ...], dict[str, Any]] = {}
    limitations: dict[tuple[Any, ...], dict[str, Any]] = {}

    def add_action(
        key: tuple[Any, ...],
        row: dict[str, Any],
        extra_evidence: Sequence[dict[str, Any]],
        observation: tuple[str, str, str],
    ) -> None:
        existing = actions.get(key)
        if existing is None:
            row["evidence"] = _merge_evidence(row["evidence"])
            row["_observations"] = {observation}
            actions[key] = row
            return
        existing["evidence"] = _merge_evidence(list(existing["evidence"]) + list(extra_evidence))
        observations = set(existing.get("_observations") or set())
        observations.add(observation)
        existing["_observations"] = observations
        recurring = len(observations) >= 2
        existing["confidence"] = "high" if recurring else "medium"
        check_id = str((existing["evidence"][0].get("check_id") if existing["evidence"] else "") or key[0])
        _action, rationale, _verification = _action_fields(check_id, existing["target"], recurring)
        existing["rationale"] = rationale

    def add_limitation(key: tuple[Any, ...], limitation: str, evidence: Sequence[dict[str, Any]]) -> None:
        existing = limitations.get(key)
        if existing is None:
            limitations[key] = _limitation_row(limitation, _merge_evidence(evidence), key)
            return
        existing["evidence"] = _merge_evidence(list(existing["evidence"]) + list(evidence))

    if _coverage_empty(receipt):
        add_limitation(("empty",), "recommend.empty_evaluation", [])

    for run, check in _iter_run_checks(receipt):
        check_id = str(check.get("id") or UNKNOWN)
        status = str(check.get("status") or UNKNOWN)
        if status == "not_applicable":
            continue
        if status == "unknown":
            if not _is_material_unknown(check):
                continue
            token = _unknown_limitation_token(check_id)
            add_limitation((token, check_id), token, _safe_pointers(check, run))
            if _has_policy_gap(receipt, check):
                add_limitation(
                    ("recommend.historical_policy_unavailable", check_id),
                    "recommend.historical_policy_unavailable",
                    _safe_pointers(check, run),
                )
            continue
        if not _actionable_fail(check):
            continue

        evidence = _complete_pointers(check, run)
        if evidence is None:
            add_limitation(
                ("recommend.insufficient_evidence", check_id),
                "recommend.insufficient_evidence",
                _safe_pointers(check, run),
            )
            continue

        if check_id in ADAPTER_CHECK_IDS:
            if _explicit_adapter_path(run, receipt) is None:
                add_limitation(
                    ("recommend.unresolved_target", check_id),
                    "recommend.unresolved_target",
                    evidence,
                )
            continue

        skills = _run_skills(run, first_party_root)
        bound, limitation = _choose_skill(skills, evidence)
        if bound is None:
            add_limitation((limitation or "recommend.missing_target_attribution", check_id), limitation or "recommend.missing_target_attribution", evidence)
            continue
        target = _skill_target(bound)
        key = (check_id, "skill", target["path"], target["digest"])
        add_action(
            key,
            _action_row(target, check_id, evidence, False, key),
            evidence,
            _observation_id(run, check_id),
        )

    if not actions and not limitations:
        add_limitation(("recommend.insufficient_evidence",), "recommend.insufficient_evidence", [])

    rows: list[dict[str, Any]] = []
    for item in list(actions.values()) + list(limitations.values()):
        observations = item.pop("_observations", None)
        recurring = bool(observations) and len(observations) >= 2
        if item.get("limitation") is None:
            item["confidence"] = "high" if recurring else "medium"
            check_id = str((item["evidence"][0].get("check_id") if item.get("evidence") else "") or "")
            if check_id and item.get("target"):
                item["rationale"] = _rationale(check_id, item["target"], recurring)
        rows.append(item)

    rows.sort(key=lambda row: row.get("_sort") or ())
    numbered: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        item.pop("_sort", None)
        numbered.append({"id": f"rec-{index:03d}", **item})
    return numbered


def load_receipt(path: str | Path) -> dict[str, Any]:
    candidate = _lexical(path)
    if candidate.is_dir():
        candidate = candidate / "receipt.json"
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RecommendError(f"missing receipt: {candidate}") from exc
    except OSError as exc:
        raise RecommendError(f"unreadable receipt: {candidate}") from exc
    except json.JSONDecodeError as exc:
        raise RecommendError(f"invalid receipt JSON: {candidate}") from exc
    if not isinstance(payload, dict):
        raise RecommendError("receipt must be an object")
    return payload


def recommend_receipt(
    receipt: dict[str, Any],
    *,
    out: str | Path | None = None,
    first_party_root: str | Path | None = None,
    adapter_root: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Pure recommendation enrichment. Never mutates sources, skills, or adapters."""

    if not isinstance(receipt, dict):
        raise RecommendError("recommend_receipt requires a receipt object")
    if receipt.get("schema") not in (None, RECEIPT_SCHEMA):
        raise RecommendError(f"unsupported receipt schema: {receipt.get('schema')}")

    party = _absolute(first_party_root) if first_party_root is not None else DEFAULT_FIRST_PARTY_ROOT
    adapters = _lexical(adapter_root) if adapter_root is not None else None
    document = _copy(receipt)
    recommendations = _build_recommendations(document, party, adapters)

    provenance = document.get("provenance") if isinstance(document.get("provenance"), dict) else {}
    provenance = dict(provenance)
    provenance["recommend"] = {
        "stage": RECOMMENDER_STAGE,
        "version": RECOMMENDER_VERSION,
        "first_party_root": str(party),
        "adapter_root": str(adapters.resolve()) if adapters is not None and adapters.exists() else (str(adapters) if adapters is not None else None),
        "provider_calls": 0,
    }
    document["schema"] = RECEIPT_SCHEMA
    document["recommendations"] = recommendations
    document["provenance"] = provenance
    if "proof_gaps" not in document or not isinstance(document.get("proof_gaps"), list):
        document["proof_gaps"] = list(receipt.get("proof_gaps") or []) if isinstance(receipt.get("proof_gaps"), list) else []

    if out is not None:
        out_dir = ingest_mod._output_root(out)
    else:
        out_dir = ingest_mod._output_root(ingest_mod._default_output_dir() / "recommend")
    ingest_mod._secure_dir(out_dir)
    ingest_mod._secure_dir(out_dir / "receipts")
    immutable_id = ingest_mod.sha256_text(_canonical(document))
    ingest_mod._write_immutable_json(out_dir / "receipts" / f"{immutable_id}.json", document)
    requested_path = out_dir / "receipt.json"
    payload = _canonical(document).encode("utf-8")
    if requested_path.exists() and requested_path.read_bytes() != payload:
        requested_path = ingest_mod._write_immutable_json(out_dir / f"receipt-{immutable_id}.json", document)
    else:
        requested_path = ingest_mod._write_immutable_json(requested_path, document)
    return document, requested_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval-recommend",
        description="Propose first-party skill/adapter corrections from a canonical session-eval receipt. Never writes sources, skills, or adapters and never calls providers.",
    )
    parser.add_argument("receipt", nargs="?", help="canonical styrir-session-eval/v0 receipt.json (or directory)")
    parser.add_argument("--receipt", dest="receipt_flag", help="canonical receipt path (alternative to positional)")
    parser.add_argument("--out", "--output", default=None, help="output directory for the enriched immutable receipt")
    parser.add_argument("--first-party-root", default=None, help="resolved first-party ownership root (default: ~/Code/skills)")
    parser.add_argument("--adapter-root", default=None, help="first-party adapter ownership root; unused as a filename guess")
    parser.add_argument("--pretty", action="store_true", help="pretty-print the command summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    receipt_path = args.receipt_flag or args.receipt
    if not receipt_path:
        parser.error("recommend requires --receipt")
        return 2
    try:
        loaded = load_receipt(receipt_path)
        receipt, path = recommend_receipt(
            loaded,
            out=args.out,
            first_party_root=args.first_party_root,
            adapter_root=args.adapter_root,
        )
    except (RecommendError, ingest_mod.IngestError) as exc:
        parser.error(str(exc))
        return 2
    rows = receipt.get("recommendations") or []
    summary = {
        "receipt": str(path),
        "recommendation_count": len(rows),
        "actionable": sum(1 for row in rows if row.get("limitation") is None),
        "limitations": sum(1 for row in rows if row.get("limitation") is not None),
        "provider_calls": 0,
    }
    if args.pretty:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
