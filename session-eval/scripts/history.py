#!/usr/bin/env python3
"""Skill registry, trend comparison, champion selection, and immutable history.

This module enriches an existing ``styrir-session-eval/v0`` receipt.  It does
not ingest sessions, run checks, render HTML, call providers, or mutate
sources, skills, or prior receipts.  Historical loaded bytes stay as recorded;
current on-disk bytes are hashed separately and never copied onto an old
activation.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ingest import (  # noqa: E402
    IngestError,
    UNKNOWN,
    _canonical,
    _write_immutable_json,
    sha256_bytes,
    sha256_text,
)

RECEIPT_SCHEMA = "styrir-session-eval/v0"
HISTORY_STAGE = "session-eval-history"
TOKEN_FIELDS = ("input", "output", "cache_read", "cache_create", "total")
DECIDED_STATUSES = {"pass", "fail", "not_applicable"}
AUTHORITATIVE_SOURCES = (
    "grok.prompt_context",
    "claude.skill_path",
    "claude.skills",
)
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.DOTALL)


class HistoryError(IngestError):
    """Expected local-input error suitable for a concise CLI message."""


def _label(value: Any, limit: int = 240) -> str:
    if value is None:
        return UNKNOWN
    text = str(value).replace("\x00", "")
    text = text.replace("<", "[").replace(">", "]")
    text = " ".join(text.split())
    return text[:limit] if text else UNKNOWN


def _is_unknown(value: Any) -> bool:
    return value in (None, "", UNKNOWN)


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _absolute(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _lexical(path: str | Path) -> Path:
    value = Path(path).expanduser()
    if not value.is_absolute():
        value = Path.cwd() / value
    return Path(os.path.normpath(str(value)))


def _output_path(path: str | Path) -> Path:
    """Resolve existing prefix so the ingest writer can open a no-follow chain."""

    return _lexical(path).resolve()


def _under(path: Path, root: Path | None) -> bool:
    if root is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _default_first_party_root() -> Path:
    return Path.home() / "Code" / "skills"


def _default_skill_roots(first_party_root: Path | None = None) -> list[Path]:
    roots = [
        first_party_root or _default_first_party_root(),
        Path.home() / ".claude" / "skills",
        Path.home() / ".codex" / "skills",
        Path.home() / ".pi" / "agent" / "skills",
        Path.home() / ".omp" / "agent" / "skills",
        Path.home() / ".grok" / "skills",
    ]
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            roots.extend(
                candidate / relative
                for relative in (".claude/skills", ".pi/skills", ".omp/skills")
            )
            break
    return [root for root in roots if root.is_dir()]


def _default_output_dir() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            current = candidate
            break
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return current / ".styrir" / "runs" / f"{stamp}-session-eval-history"


def load_receipt(path: str | Path) -> dict[str, Any]:
    candidate = _lexical(path)
    if candidate.is_dir():
        candidate = candidate / "receipt.json"
    try:
        payload = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        raise HistoryError(f"cannot read receipt {candidate}: {exc}") from exc
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HistoryError(f"receipt is not JSON: {candidate}: {exc}") from exc
    if not isinstance(value, dict):
        raise HistoryError(f"receipt is not an object: {candidate}")
    return value


def parse_skill_frontmatter(text: str) -> dict[str, Any]:
    """Parse optional SKILL.md name/version without a YAML runtime."""

    name: str | None = None
    version: str | None = None
    match = _FRONTMATTER.match(text)
    if match:
        block = match.group(1)
    else:
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                break
            if ":" not in line or stripped.startswith("#") or stripped.startswith("```"):
                break
            lines.append(line)
        block = "\n".join(lines)
    current_parent: str | None = None
    for raw in block.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indented = raw[0] in " \t"
        if not indented and ":" in raw:
            key, _, remainder = raw.partition(":")
            key = key.strip()
            remainder = remainder.strip().strip("'\"")
            current_parent = key
            if key == "name" and remainder:
                name = remainder
            elif key == "version" and remainder:
                version = remainder
            elif key == "metadata.version" and remainder:
                version = version or remainder
            elif key == "metadata" and not remainder:
                continue
            else:
                current_parent = key if not remainder else None
        elif indented and current_parent == "metadata" and ":" in raw:
            key, _, remainder = raw.strip().partition(":")
            if key.strip() == "version" and remainder.strip():
                version = version or remainder.strip().strip("'\"")
    return {"name": name, "version": version}


def _skill_name_from_path(path: str | Path) -> str:
    parts = [part for part in str(path).replace("\\", "/").split("/") if part]
    if parts and parts[-1].casefold() == "skill.md":
        return parts[-2] if len(parts) > 1 else UNKNOWN
    return Path(str(path)).stem or UNKNOWN


def _read_skill_file(path: Path) -> tuple[str | None, dict[str, Any]]:
    try:
        data = path.read_bytes()
    except OSError:
        return None, {}
    digest = sha256_bytes(data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", "replace")
    meta = parse_skill_frontmatter(text)
    return digest, meta


def iter_skill_files(roots: Sequence[str | Path]) -> list[Path]:
    """Discover SKILL.md files, following file/dir symlinks with loop protection."""

    found: list[Path] = []
    seen: set[tuple[int, int]] = set()
    stack = [_lexical(root) for root in roots]
    while stack:
        directory = stack.pop()
        try:
            info = directory.stat()
        except OSError:
            continue
        key = (info.st_dev, info.st_ino)
        if key in seen:
            continue
        seen.add(key)
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            try:
                if name.casefold() == "skill.md" and entry.is_file():
                    found.append(entry)
                    continue
                if entry.is_dir():
                    stack.append(entry)
            except OSError:
                continue
    found.sort(key=lambda item: str(item))
    return found


def _resolve_skill_file(path_text: Any, skill_roots: Sequence[Path]) -> Path | None:
    if _is_unknown(path_text):
        return None
    raw = Path(str(path_text)).expanduser()
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(_lexical(raw))
        for root in skill_roots:
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


def _activation_kind(confidence: Any, source: Any) -> str:
    source_text = str(source or "")
    if confidence == "high" or source_text in AUTHORITATIVE_SOURCES or source_text.endswith("prompt_context"):
        return "authoritative"
    if confidence in {"medium", "low"} or source_text:
        return "mention"
    return "absent"


def _native_id(run: dict[str, Any]) -> str | None:
    native = run.get("native_identity")
    if _is_unknown(native):
        return None
    if isinstance(native, dict):
        ident = native.get("id")
        if _is_unknown(ident):
            return None
        return str(ident)
    return str(native)


def _run_timestamp(run: dict[str, Any]) -> str:
    for key in ("ended_at", "started_at"):
        value = run.get(key)
        if not _is_unknown(value):
            return str(value)
    return UNKNOWN


def _check_ids(receipt: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for check in receipt.get("checks") or []:
        if isinstance(check, dict) and not _is_unknown(check.get("id")):
            ids.add(str(check["id"]))
    for run in receipt.get("runs") or []:
        if not isinstance(run, dict):
            continue
        for check in run.get("checks") or []:
            if isinstance(check, dict) and not _is_unknown(check.get("id")):
                ids.add(str(check["id"]))
    return ids


def _unknown_hard_gate_count(receipt: dict[str, Any]) -> int:
    coverage = receipt.get("coverage") if isinstance(receipt.get("coverage"), dict) else {}
    recorded = coverage.get("applicable_hard_fail_unknown")
    if isinstance(recorded, int):
        return recorded
    count = 0
    for run in receipt.get("runs") or []:
        if not isinstance(run, dict):
            continue
        for check in run.get("checks") or []:
            if not isinstance(check, dict):
                continue
            if (
                check.get("class") == "hard_fail"
                and check.get("channel") == "behavior"
                and check.get("status") == "unknown"
            ):
                count += 1
    return count


def is_qualified_champion(receipt: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if receipt.get("hard_pass") is not True:
        reasons.append("hard_pass_not_true")
    if receipt.get("infra_ok") is not True:
        reasons.append("infra_ok_not_true")
    coverage = receipt.get("coverage") if isinstance(receipt.get("coverage"), dict) else {}
    if coverage.get("empty") is not False:
        reasons.append("coverage_empty_or_unknown")
    missing = coverage.get("missing_requested_inputs") or []
    if missing:
        reasons.append("missing_requested_inputs")
    if _unknown_hard_gate_count(receipt):
        reasons.append("unknown_hard_gates")
    return not reasons, reasons


def _digest_relation(historical: Any, current: Any) -> str:
    hist_unknown = _is_unknown(historical)
    curr_unknown = _is_unknown(current)
    if hist_unknown:
        return "historical_unknown"
    if curr_unknown:
        return "observed_load"
    if historical == current:
        return "historical_matches_current"
    return "historical_differs_from_current"


def _registry_key(name: str, path: str, historical: Any) -> tuple[str, str, str]:
    digest = UNKNOWN if _is_unknown(historical) else str(historical)
    return (name, path, digest)


def _iter_activation_entries(receipt: dict[str, Any]) -> Iterable[tuple[dict[str, Any] | None, dict[str, Any]]]:
    seen_from_runs = False
    for run in receipt.get("runs") or []:
        if not isinstance(run, dict):
            continue
        for skill in run.get("skills") or []:
            if isinstance(skill, dict):
                seen_from_runs = True
                yield run, skill
    if seen_from_runs:
        return
    for skill in receipt.get("skills") or []:
        if isinstance(skill, dict):
            yield None, skill


def enrich_registry(
    receipt: dict[str, Any],
    skill_roots: Sequence[str | Path] | None = None,
    first_party_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build the skill registry from activations plus current SKILL.md files.

    Current bytes are hashed only into ``current_on_disk_digest``.  Historical
    ``digest`` / ``historical_loaded_digest`` values from the receipt are
    preserved even when the file has been edited or is missing.
    """

    enriched = _copy(receipt)
    party = _absolute(first_party_root) if first_party_root is not None else _default_first_party_root()
    roots = [_absolute(root) for root in skill_roots] if skill_roots is not None else _default_skill_roots(party)
    discovered = iter_skill_files(roots)
    disk_by_resolved: dict[str, dict[str, Any]] = {}
    for file_path in discovered:
        try:
            resolved = file_path.resolve()
        except OSError:
            continue
        digest, meta = _read_skill_file(file_path)
        if digest is None:
            continue
        name = _label(meta.get("name") or _skill_name_from_path(resolved))
        version = meta.get("version")
        disk_by_resolved[str(resolved)] = {
            "name": name,
            "path": str(resolved),
            "lexical_path": str(file_path),
            "digest": digest,
            "version": _label(version) if version else None,
            "ownership": _ownership(resolved, party),
            "symlink": file_path.is_symlink(),
        }

    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}

    def bucket_for(name: str, path: str, resolved: Path | None, historical: Any) -> dict[str, Any]:
        identity_path = str(resolved) if resolved is not None else path
        key = _registry_key(name, identity_path, historical)
        existing = buckets.get(key)
        if existing is not None:
            return existing
        entry = {
            "name": name,
            "path": identity_path,
            "digest": UNKNOWN if _is_unknown(historical) else historical,
            "activations": [],
            "hard_fail_count": 0,
            "last_seen": UNKNOWN,
            "historical_loaded_digest": UNKNOWN if _is_unknown(historical) else historical,
            "current_on_disk_digest": UNKNOWN,
            "ownership": _ownership(resolved, party),
            "missing": resolved is None,
            "activation_kind": "absent",
            "digest_relation": "historical_unknown",
        }
        buckets[key] = entry
        return entry

    def add_activation_row(entry: dict[str, Any], source: str, confidence: str) -> None:
        source_label = _label(source)
        confidence_label = confidence if confidence in CONFIDENCE_RANK else "low"
        for row in entry["activations"]:
            if row["source"] == source_label and row["confidence"] == confidence_label:
                row["count"] += 1
                return
        entry["activations"].append(
            {"source": source_label, "confidence": confidence_label, "count": 1}
        )
        kinds = {_activation_kind(item["confidence"], item["source"]) for item in entry["activations"]}
        if "authoritative" in kinds:
            entry["activation_kind"] = "authoritative"
        elif "mention" in kinds:
            entry["activation_kind"] = "mention"

    def note_last_seen(entry: dict[str, Any], run: dict[str, Any] | None) -> None:
        if run is None:
            return
        stamp = _run_timestamp(run)
        current = entry.get("last_seen", UNKNOWN)
        if _is_unknown(current) or (not _is_unknown(stamp) and stamp > str(current)):
            entry["last_seen"] = stamp

    def note_hard_fails(entry: dict[str, Any], run: dict[str, Any] | None) -> None:
        if run is None:
            return
        seen = entry.setdefault("_hard_fail_runs", set())
        marker = run.get("id") or id(run)
        if marker in seen:
            return
        seen.add(marker)
        fails = 0
        for check in run.get("checks") or []:
            if not isinstance(check, dict):
                continue
            if check.get("class") == "hard_fail" and check.get("status") == "fail":
                fails += 1
        entry["hard_fail_count"] = int(entry.get("hard_fail_count") or 0) + fails

    for run, skill in _iter_activation_entries(enriched):
        recorded_path = str(skill.get("path") or UNKNOWN)
        resolved = _resolve_skill_file(recorded_path, roots)
        disk = disk_by_resolved.get(str(resolved)) if resolved is not None else None
        name = _label(skill.get("name") or (disk["name"] if disk else _skill_name_from_path(recorded_path)))
        historical = skill.get("digest")
        if _is_unknown(historical):
            historical = skill.get("historical_loaded_digest", UNKNOWN)
        if _is_unknown(historical):
            historical = UNKNOWN
        entry = bucket_for(name, recorded_path, resolved, historical)
        if not _is_unknown(historical):
            # Preserve the recorded load identity.  Never replace it with current bytes.
            entry["historical_loaded_digest"] = historical
            entry["digest"] = historical
        current = None if disk is None else disk["digest"]
        if current is None and resolved is not None:
            hashed, meta = _read_skill_file(resolved)
            current = hashed
            if meta.get("version") and not entry.get("version"):
                entry["version"] = _label(meta["version"])
        if current is not None:
            entry["current_on_disk_digest"] = current
            entry["missing"] = False
            if disk:
                if disk.get("version"):
                    entry["version"] = disk["version"]
                entry["ownership"] = disk["ownership"]
                if disk.get("symlink"):
                    entry["resolved_via_symlink"] = True
                if disk.get("name") and entry["name"] in {UNKNOWN, _skill_name_from_path(recorded_path)}:
                    entry["name"] = disk["name"]
        else:
            if resolved is None:
                entry["missing"] = True
                entry["current_on_disk_digest"] = UNKNOWN
        entry["digest_relation"] = _digest_relation(
            entry.get("historical_loaded_digest"),
            entry.get("current_on_disk_digest"),
        )
        # Activation digest stays historical/unknown. Current bytes never fill it.
        add_activation_row(entry, str(skill.get("source") or UNKNOWN), str(skill.get("confidence") or "low"))
        note_last_seen(entry, run)
        note_hard_fails(entry, run)
        if run is not None:
            own_historical = skill.get("digest")
            if _is_unknown(own_historical):
                own_historical = UNKNOWN
            skill["current_on_disk_digest"] = entry.get("current_on_disk_digest", UNKNOWN)
            skill["historical_loaded_digest"] = own_historical
            skill["digest"] = own_historical
            skill["digest_relation"] = _digest_relation(
                own_historical, skill.get("current_on_disk_digest")
            )
            skill["ownership"] = entry["ownership"]
            skill["missing"] = bool(entry["missing"])
            skill["activation_kind"] = _activation_kind(skill.get("confidence"), skill.get("source"))

    occupied_paths = {entry.get("path") for entry in buckets.values()}
    for resolved_text, disk in disk_by_resolved.items():
        if disk["path"] in occupied_paths or resolved_text in occupied_paths:
            continue
        key = _registry_key(disk["name"], disk["path"], UNKNOWN)
        if key in buckets:
            continue
        buckets[key] = {
            "name": disk["name"],
            "path": disk["path"],
            "digest": disk["digest"],
            "activations": [],
            "hard_fail_count": 0,
            "last_seen": UNKNOWN,
            "historical_loaded_digest": UNKNOWN,
            "current_on_disk_digest": disk["digest"],
            "ownership": disk["ownership"],
            "missing": False,
            "activation_kind": "absent",
            "digest_relation": "historical_unknown",
        }
        if disk.get("version"):
            buckets[key]["version"] = disk["version"]
        if disk.get("symlink"):
            buckets[key]["resolved_via_symlink"] = True

    registry = []
    for entry in buckets.values():
        entry.pop("_hard_fail_runs", None)
        if entry.get("version") is None:
            entry.pop("version", None)
        entry["activations"] = sorted(
            entry["activations"],
            key=lambda row: (row["source"], row["confidence"]),
        )
        registry.append(entry)
    registry.sort(key=lambda item: (item.get("name") or "", item.get("path") or "", item.get("digest") or ""))
    enriched["skills"] = registry

    gaps = list(enriched.get("proof_gaps") or [])

    def add_gap(kind: str, **fields: Any) -> None:
        item = {"kind": kind, **fields}
        if item not in gaps:
            gaps.append(item)

    for entry in registry:
        if entry.get("missing") and entry.get("activation_kind") != "absent":
            add_gap("skill.missing", name=entry["name"], path=entry["path"])
        if entry.get("digest_relation") == "historical_differs_from_current":
            add_gap(
                "skill.digest_drift",
                name=entry["name"],
                historical_loaded_digest=entry.get("historical_loaded_digest"),
                current_on_disk_digest=entry.get("current_on_disk_digest"),
            )
        if entry.get("ownership") == "unresolved" and entry.get("activation_kind") != "absent":
            add_gap("skill.unresolved_ownership", name=entry["name"], path=entry["path"])
        if entry.get("activation_kind") == "absent":
            add_gap("skill.absent_usage", name=entry["name"], path=entry["path"])
    usage_unknown = False
    for run in enriched.get("runs") or []:
        if not isinstance(run, dict):
            continue
        tokens = run.get("tokens") if isinstance(run.get("tokens"), dict) else {}
        if any(_is_unknown(tokens.get(field)) for field in TOKEN_FIELDS) or _is_unknown(run.get("cost_usd")):
            usage_unknown = True
    if usage_unknown:
        add_gap("usage.unknown", reason="token_or_cost_unknown")
    enriched["proof_gaps"] = gaps
    provenance = dict(enriched.get("provenance") or {})
    provenance["history_stage"] = HISTORY_STAGE
    provenance["first_party_root"] = str(party)
    enriched["provenance"] = provenance
    return enriched


def _harness_population(baseline: dict[str, Any], candidate: dict[str, Any], cohort: dict[str, Any] | None) -> tuple[list[str], bool, str | None]:
    explicit = list(cohort.get("harnesses") or []) if isinstance(cohort, dict) else []
    base_req = [str(item) for item in (baseline.get("harnesses_requested") or [])]
    cand_req = [str(item) for item in (candidate.get("harnesses_requested") or [])]
    base_found = [str(item) for item in (baseline.get("harnesses_found") or [])]
    cand_found = [str(item) for item in (candidate.get("harnesses_found") or [])]
    if explicit:
        population = [item for item in explicit if item]
        if not population:
            return [], False, "empty_explicit_cohort"
        return population, True, None
    if base_req and cand_req and base_req == cand_req:
        found = [item for item in base_found if item in cand_found]
        if found:
            return found, True, None
        if not base_found and not cand_found:
            return list(base_req), True, None
        return list(base_req), True, None
    intersection = [item for item in base_found if item in cand_found]
    if intersection:
        return intersection, True, None
    return [], False, "empty_harness_intersection"


def _skill_digests(receipt: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()

    def add(digest: Any) -> None:
        if _is_unknown(digest):
            return
        text = str(digest)
        if text in seen:
            return
        seen.add(text)
        values.append(text)

    def from_skill(skill: dict[str, Any]) -> None:
        historical = skill.get("historical_loaded_digest")
        if not _is_unknown(historical):
            add(historical)
            return
        if skill.get("activation_kind") == "absent":
            return
        add(skill.get("digest"))

    for skill in receipt.get("skills") or []:
        if isinstance(skill, dict):
            from_skill(skill)
    for run in receipt.get("runs") or []:
        if not isinstance(run, dict):
            continue
        for skill in run.get("skills") or []:
            if isinstance(skill, dict):
                from_skill(skill)
    return values


def _union_skill_digests(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for digest in _skill_digests(baseline) + _skill_digests(candidate):
        if digest in seen:
            continue
        seen.add(digest)
        values.append(digest)
    return values


def _parsers_by_harness(receipt: dict[str, Any], harnesses: Sequence[str]) -> dict[str, set[tuple[Any, Any]]]:
    result: dict[str, set[tuple[Any, Any]]] = {harness: set() for harness in harnesses}
    allowed = set(harnesses)
    for run in receipt.get("runs") or []:
        if not isinstance(run, dict):
            continue
        harness = run.get("harness")
        if harness not in allowed:
            continue
        result.setdefault(str(harness), set()).add((run.get("parser"), run.get("parser_version")))
    return result


def _redaction_policy(receipt: dict[str, Any]) -> Any:
    redaction = receipt.get("redaction")
    if isinstance(redaction, dict):
        return redaction.get("policy")
    return None


def compatibility_gates(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    cohort: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate catalog, check-id, cohort, redaction, schema, and parser gates."""

    population, cohort_ok, cohort_reason = _harness_population(baseline, candidate, cohort)
    base_catalog = baseline.get("catalog_id")
    cand_catalog = candidate.get("catalog_id")
    catalog_ok = not _is_unknown(base_catalog) and base_catalog == cand_catalog
    if _is_unknown(base_catalog) and _is_unknown(cand_catalog):
        catalog_ok = False
    if base_catalog == cand_catalog and not _is_unknown(base_catalog):
        catalog_ok = True
    base_ids = _check_ids(baseline)
    cand_ids = _check_ids(candidate)
    check_ids_ok = base_ids == cand_ids
    base_schema = baseline.get("schema")
    cand_schema = candidate.get("schema")
    schema_ok = base_schema == cand_schema and not _is_unknown(base_schema)
    base_redaction = _redaction_policy(baseline)
    cand_redaction = _redaction_policy(candidate)
    redaction_ok = base_redaction == cand_redaction and not _is_unknown(base_redaction)
    parsers_base = _parsers_by_harness(baseline, population)
    parsers_cand = _parsers_by_harness(candidate, population)
    parser_rows: list[dict[str, Any]] = []
    parsers_ok = True
    if not population:
        parsers_ok = False
    for harness in population:
        base_set = parsers_base.get(harness) or set()
        cand_set = parsers_cand.get(harness) or set()
        base_pair = next(iter(base_set)) if len(base_set) == 1 else None
        cand_pair = next(iter(cand_set)) if len(cand_set) == 1 else None
        row_ok = (
            base_pair is not None
            and cand_pair is not None
            and base_pair == cand_pair
            and not _is_unknown(base_pair[0])
            and not _is_unknown(base_pair[1])
        )
        if not row_ok:
            parsers_ok = False
        parser_rows.append(
            {
                "harness": harness,
                "baseline": (
                    {"name": base_pair[0], "version": base_pair[1]} if base_pair is not None else UNKNOWN
                ),
                "candidate": (
                    {"name": cand_pair[0], "version": cand_pair[1]} if cand_pair is not None else UNKNOWN
                ),
            }
        )
        if len(base_set) > 1 or len(cand_set) > 1:
            parsers_ok = False
    compatible = catalog_ok and check_ids_ok and cohort_ok and redaction_ok and schema_ok and parsers_ok
    reasons: list[str] = []
    if not catalog_ok:
        reasons.append("catalog_mismatch")
    if not check_ids_ok:
        reasons.append("check_id_set_mismatch")
    if not cohort_ok:
        reasons.append(cohort_reason or "cohort_incompatible")
    if not redaction_ok:
        reasons.append("redaction_mismatch")
    if not schema_ok:
        reasons.append("schema_mismatch")
    if not parsers_ok:
        reasons.append("parser_mismatch")
    return {
        "compatible": compatible,
        "reasons": reasons,
        "population": population,
        "catalog": {
            "baseline": base_catalog if base_catalog is not None else UNKNOWN,
            "candidate": cand_catalog if cand_catalog is not None else UNKNOWN,
            "compatible": catalog_ok,
        },
        "check_ids": {
            "baseline": sorted(base_ids),
            "candidate": sorted(cand_ids),
            "compatible": check_ids_ok,
        },
        "cohort": {
            "harnesses": population,
            "skill_digests": _union_skill_digests(baseline, candidate),
            "compatible": cohort_ok,
        },
        "measurement": {
            "baseline_schema": base_schema if base_schema is not None else UNKNOWN,
            "candidate_schema": cand_schema if cand_schema is not None else UNKNOWN,
            "parsers": parser_rows,
            "compatible": schema_ok and parsers_ok,
        },
        "redaction_policy": {
            "baseline": base_redaction if base_redaction is not None else UNKNOWN,
            "candidate": cand_redaction if cand_redaction is not None else UNKNOWN,
            "compatible": redaction_ok,
        },
    }


def _observations(receipt: dict[str, Any], population: Sequence[str]) -> list[dict[str, Any]]:
    allowed = set(population)
    rows: list[dict[str, Any]] = []
    for run in receipt.get("runs") or []:
        if not isinstance(run, dict):
            continue
        harness = run.get("harness")
        if allowed and harness not in allowed:
            continue
        native = _native_id(run)
        for check in run.get("checks") or []:
            if not isinstance(check, dict):
                continue
            check_id = check.get("id")
            pairable = native is not None and not _is_unknown(check_id)
            rows.append(
                {
                    "subject": ("run", str(harness or UNKNOWN), native or UNKNOWN, str(check_id or UNKNOWN)),
                    "pairable": pairable,
                    "check_id": check_id,
                    "status": check.get("status"),
                    "class": check.get("class"),
                    "kind": check.get("kind"),
                    "channel": check.get("channel") or "behavior",
                }
            )
        tokens = run.get("tokens") if isinstance(run.get("tokens"), dict) else {}
        usage_unknown = any(_is_unknown(tokens.get(field)) for field in TOKEN_FIELDS) or _is_unknown(
            run.get("cost_usd")
        )
        rows.append(
            {
                "subject": ("usage", str(harness or UNKNOWN), native or UNKNOWN, "tokens_cost"),
                "pairable": native is not None,
                "check_id": "usage.tokens_cost",
                "status": "unknown" if usage_unknown else "pass",
                "class": "expected_behavior",
                "kind": "code",
                "channel": "usage",
            }
        )
    return rows


def _index_observations(rows: Sequence[dict[str, Any]]) -> dict[tuple[Any, ...], dict[str, Any]]:
    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        if not row.get("pairable"):
            continue
        indexed[tuple(row["subject"])] = row
    return indexed


def _transition(before: str | None, after: str | None) -> str:
    if before == "unknown" or after == "unknown" or _is_unknown(before) or _is_unknown(after):
        return "unmeasurable"
    if before == after and before in DECIDED_STATUSES:
        return "equal"
    if before == "fail" and after == "pass":
        return "improved"
    if before == "pass" and after == "fail":
        return "regressed"
    return "unmeasurable"


def _row_channel(row: dict[str, Any]) -> str:
    channel = row.get("channel")
    if channel in {"infra", "usage"}:
        return str(channel)
    return "behavior"


def _identity_keys(rows: Sequence[dict[str, Any]]) -> list[tuple[Any, ...]]:
    keys: list[tuple[Any, ...]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        key = tuple(row["subject"])
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _channel_rows(rows: Sequence[dict[str, Any]], channel: str) -> list[dict[str, Any]]:
    return [row for row in rows if _row_channel(row) == channel]


def _tally_channel(
    base_rows: Sequence[dict[str, Any]],
    cand_rows: Sequence[dict[str, Any]],
    channel: str,
    compatible: bool,
) -> tuple[dict[str, int], str]:
    base = _channel_rows(base_rows, channel)
    cand = _channel_rows(cand_rows, channel)
    counts = {"improved": 0, "regressed": 0, "equal": 0, "unmeasurable": 0}
    all_keys = set(_identity_keys(base)) | set(_identity_keys(cand))
    base_index = _index_observations(base)
    cand_index = _index_observations(cand)
    pairable = set(base_index) | set(cand_index)
    if not compatible:
        counts["unmeasurable"] = len(all_keys)
        return counts, "none"
    if not pairable:
        counts["unmeasurable"] = len(all_keys)
        return counts, "aggregate"
    for key in sorted(all_keys):
        left = base_index.get(key)
        right = cand_index.get(key)
        if left is None or right is None:
            counts["unmeasurable"] += 1
            continue
        counts[_transition(left.get("status"), right.get("status"))] += 1
    return counts, "identity"


def _tally_usage(
    base_rows: Sequence[dict[str, Any]],
    cand_rows: Sequence[dict[str, Any]],
    compatible: bool,
) -> dict[str, Any]:
    base = _channel_rows(base_rows, "usage")
    cand = _channel_rows(cand_rows, "usage")
    if not base and not cand:
        return {"comparable": False, "unmeasurable": False, "reason": None}
    if not compatible:
        return {"comparable": False, "unmeasurable": True, "reason": "incompatible_measurement"}
    base_index = _index_observations(base)
    cand_index = _index_observations(cand)
    keys = set(_identity_keys(base)) | set(_identity_keys(cand))
    unknown = False
    comparable = False
    for key in keys:
        left = base_index.get(key)
        right = cand_index.get(key)
        if left is None or right is None:
            unknown = True
            continue
        if left.get("status") == "unknown" or right.get("status") == "unknown":
            unknown = True
        else:
            comparable = True
    if unknown:
        return {"comparable": comparable, "unmeasurable": True, "reason": "absent_or_unknown"}
    return {"comparable": comparable, "unmeasurable": False, "reason": None}


def compare_receipts(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    cohort: dict[str, Any] | None = None,
    baseline_path: str | Path | None = None,
    candidate_path: str | Path | None = None,
    baseline_qualification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare explicit subject/check identities.  No invented causality."""

    gates = compatibility_gates(baseline, candidate, cohort)
    population = gates["population"]
    base_rows = _observations(baseline, population)
    cand_rows = _observations(candidate, population)
    counts, pairing = _tally_channel(base_rows, cand_rows, "behavior", gates["compatible"])
    infra_counts, _infra_pairing = _tally_channel(base_rows, cand_rows, "infra", gates["compatible"])
    usage = _tally_usage(base_rows, cand_rows, gates["compatible"])
    if not gates["compatible"]:
        pairing = "none"

    qualification = baseline_qualification or {}
    quality_delta_allowed = bool(gates["compatible"]) and qualification.get("qualified", True) is True
    if qualification.get("qualified") is False and qualification.get("policy") == "named":
        quality_delta_allowed = False

    reasons = list(gates["reasons"])
    if not quality_delta_allowed and "baseline_incomplete" not in reasons and qualification.get("qualified") is False:
        reasons.append("baseline_incomplete")
    if usage["unmeasurable"] and usage["reason"] and usage["reason"] not in reasons:
        reasons.append("usage_unmeasurable")

    return {
        "baseline_receipt": str(baseline_path) if baseline_path is not None else "inline",
        "candidate_receipt": str(candidate_path) if candidate_path is not None else "inline",
        "cohort": gates["cohort"],
        "catalog": gates["catalog"],
        "check_ids": gates["check_ids"],
        "measurement": gates["measurement"],
        "redaction_policy": gates["redaction_policy"],
        "counts": counts,
        "infra_counts": infra_counts,
        "usage": usage,
        "pairing": pairing,
        "unmeasurable_reasons": reasons,
        "quality_delta_allowed": quality_delta_allowed,
        "baseline_qualification": qualification,
        "compatible": gates["compatible"],
    }


def _history_json_paths(history_root: Path) -> list[Path]:
    if not history_root.is_dir():
        return []
    try:
        entries = list(history_root.iterdir())
    except OSError:
        return []
    paths = [item for item in entries if item.is_file() and item.suffix == ".json"]
    paths.sort(key=lambda item: item.name)
    return paths


def _generated_at(receipt: dict[str, Any], path: Path) -> str:
    value = receipt.get("generated_at")
    if not _is_unknown(value):
        return str(value)
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return path.name


def evaluation_identity(receipt: dict[str, Any]) -> str:
    """Hash the current receipt. Never trust inherited provenance.history identity."""

    runs_payload: list[dict[str, Any]] = []
    for run in receipt.get("runs") or []:
        if not isinstance(run, dict):
            continue
        skills = []
        for skill in run.get("skills") or []:
            if not isinstance(skill, dict):
                continue
            digest = skill.get("historical_loaded_digest")
            if _is_unknown(digest):
                digest = skill.get("digest")
            skills.append(
                {
                    "name": skill.get("name"),
                    "path": skill.get("path"),
                    "digest": UNKNOWN if _is_unknown(digest) else digest,
                }
            )
        checks = []
        for check in run.get("checks") or []:
            if not isinstance(check, dict):
                continue
            checks.append(
                {
                    "id": check.get("id"),
                    "status": check.get("status"),
                    "channel": check.get("channel") or "behavior",
                }
            )
        snapshot = run.get("source_snapshot") if isinstance(run.get("source_snapshot"), dict) else {}
        runs_payload.append(
            {
                "id": run.get("id"),
                "harness": run.get("harness"),
                "native_identity": run.get("native_identity"),
                "snapshot": snapshot.get("sha256"),
                "parser": run.get("parser"),
                "parser_version": run.get("parser_version"),
                "checks": checks,
                "skills": skills,
            }
        )
    payload = {
        "schema": receipt.get("schema"),
        "catalog_id": receipt.get("catalog_id"),
        "redaction": _redaction_policy(receipt),
        "hard_pass": receipt.get("hard_pass"),
        "infra_ok": receipt.get("infra_ok"),
        "runs": runs_payload,
    }
    return sha256_text(_canonical(payload))


def _receipt_evaluation_identity(receipt: dict[str, Any]) -> str:
    """Stored identity is authoritative only on immutable history snapshots."""

    stored = ((receipt.get("provenance") or {}).get("history") or {}).get("evaluation_identity")
    if isinstance(stored, str) and stored:
        return stored
    return evaluation_identity(receipt)


def select_baseline(
    history_root: str | Path | None,
    candidate: dict[str, Any],
    named_baseline: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pick a named baseline or the latest older distinct qualified champion."""

    candidate_id = evaluation_identity(candidate)
    if named_baseline is not None:
        if isinstance(named_baseline, dict):
            receipt = _copy(named_baseline)
            path = None
        else:
            path = _lexical(named_baseline)
            receipt = load_receipt(path)
        named_id = evaluation_identity(receipt)
        qualified, reasons = is_qualified_champion(receipt)
        gates = compatibility_gates(receipt, candidate)
        label = "named_complete"
        extra: list[str] = []
        if named_id == candidate_id:
            label = "named_same_evaluation"
            extra.append("same_evaluation_identity")
        elif not gates["compatible"]:
            label = "named_incompatible"
            extra.extend(gates["reasons"])
        elif not qualified:
            label = "named_incomplete"
        return {
            "policy": "named",
            "receipt": receipt,
            "path": str(path) if path is not None else None,
            "qualified": qualified and gates["compatible"] and named_id != candidate_id,
            "label": label,
            "reasons": reasons + extra,
        }

    root = _output_path(history_root) if history_root is not None else None
    champions: list[tuple[str, Path, dict[str, Any]]] = []
    if root is not None:
        for path in _history_json_paths(root):
            try:
                receipt = load_receipt(path)
            except HistoryError:
                continue
            if receipt.get("schema") != RECEIPT_SCHEMA:
                continue
            if _receipt_evaluation_identity(receipt) == candidate_id:
                continue
            qualified, _reasons = is_qualified_champion(receipt)
            if not qualified:
                continue
            gates = compatibility_gates(receipt, candidate)
            if not gates["compatible"]:
                continue
            champions.append((_generated_at(receipt, path), path, receipt))
    if not champions:
        return {
            "policy": "none",
            "receipt": None,
            "path": None,
            "qualified": False,
            "label": "none",
            "reasons": ["no_eligible_champion"],
        }
    champions.sort(key=lambda item: (item[0], item[1].name))
    stamp, path, receipt = champions[-1]
    return {
        "policy": "champion",
        "receipt": receipt,
        "path": str(path),
        "qualified": True,
        "label": "qualified_champion",
        "reasons": [],
        "generated_at": stamp,
    }


def write_history(receipt: dict[str, Any], history_root: str | Path) -> Path:
    """Write an immutable history snapshot.  Same bytes are reused, never overwritten."""

    root = _output_path(history_root)
    digest = sha256_text(_canonical(receipt))
    path = root / f"{digest}.json"
    return _write_immutable_json(path, receipt)


def history(
    receipt: str | Path | dict[str, Any],
    out: str | Path | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    first_party_root: str | Path | None = None,
    history_root: str | Path | None = None,
    baseline: str | Path | dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    """Enrich a canonical receipt, compare against a baseline, and record history."""

    if isinstance(receipt, dict):
        loaded = _copy(receipt)
        source_path = None
    else:
        source_path = _lexical(receipt)
        loaded = load_receipt(source_path)
    if loaded.get("schema") != RECEIPT_SCHEMA:
        # Still enrich; comparison reports the schema gate rather than inventing a second schema.
        pass
    out_path = _output_path(out) if out is not None else _output_path(_default_output_dir())
    hist_root = _output_path(history_root) if history_root is not None else out_path / "history"
    enriched = enrich_registry(loaded, skill_roots=skill_roots, first_party_root=first_party_root)
    identity = evaluation_identity(enriched)
    provenance = dict(enriched.get("provenance") or {})
    history_meta = dict(provenance.get("history") or {})
    history_meta["evaluation_identity"] = identity
    provenance["history"] = history_meta
    enriched["provenance"] = provenance
    selection = select_baseline(hist_root, enriched, named_baseline=baseline)
    comparisons: list[dict[str, Any]] = []
    gaps = list(enriched.get("proof_gaps") or [])
    if selection["receipt"] is None:
        gaps.append(
            {
                "kind": "comparison.no_eligible_baseline",
                "reason": "no_eligible_champion" if selection["policy"] == "none" else selection["label"],
            }
        )
    else:
        comparison = compare_receipts(
            selection["receipt"],
            enriched,
            baseline_path=selection.get("path"),
            candidate_path=source_path,
            baseline_qualification={
                "policy": selection["policy"],
                "qualified": selection["qualified"],
                "label": selection["label"],
                "reasons": selection.get("reasons") or [],
            },
        )
        comparisons.append(comparison)
        if not comparison.get("compatible"):
            gaps.append(
                {
                    "kind": "comparison.incompatible",
                    "reasons": comparison.get("unmeasurable_reasons") or [],
                }
            )
        if selection.get("label") == "named_same_evaluation":
            comparison["quality_delta_allowed"] = False
    enriched["comparisons"] = comparisons
    enriched["proof_gaps"] = gaps
    provenance = dict(enriched.get("provenance") or {})
    provenance["history"] = {
        "stage": HISTORY_STAGE,
        "baseline_policy": selection["policy"],
        "baseline_label": selection["label"],
        "baseline_path": selection.get("path"),
        "source_receipt": str(source_path) if source_path is not None else None,
        "history_root": str(hist_root),
        "evaluation_identity": identity,
    }
    enriched["provenance"] = provenance
    history_path = write_history(enriched, hist_root)
    requested = out_path / "receipt.json"
    written = _write_immutable_json(requested, enriched)
    # Annotate the in-memory document only; rewriting would create a second snapshot.
    history_meta = dict((enriched.get("provenance") or {}).get("history") or {})
    history_meta["entry"] = str(history_path)
    provenance = dict(enriched.get("provenance") or {})
    provenance["history"] = history_meta
    enriched["provenance"] = provenance
    return enriched, written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session-eval-history",
        description="Enrich a canonical session-eval receipt with skill registry, champion baseline, and immutable history.",
    )
    parser.add_argument("receipt", nargs="?", help="canonical styrir-session-eval/v0 receipt.json (or directory)")
    parser.add_argument("--receipt", dest="receipt_flag", help="canonical receipt path (alternative to positional)")
    parser.add_argument("--out", "--output", default=None, help="output directory for the enriched receipt")
    parser.add_argument("--history-root", default=None, help="immutable history directory (default: OUT/history)")
    parser.add_argument("--skill-root", action="append", default=[], help="skill root used to hash current SKILL.md bytes (repeatable)")
    parser.add_argument("--first-party-root", default=None, help="resolved first-party ownership root (default: ~/Code/skills)")
    parser.add_argument("--baseline", default=None, help="optional named baseline receipt; labeled if incomplete or incompatible")
    parser.add_argument("--pretty", action="store_true", help="pretty-print the command summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    receipt = args.receipt_flag or args.receipt
    if not receipt:
        parser.error("receipt path is required")
        return 2
    try:
        document, path = history(
            receipt,
            out=args.out,
            skill_roots=args.skill_root or None,
            first_party_root=args.first_party_root,
            history_root=args.history_root,
            baseline=args.baseline,
        )
    except (HistoryError, IngestError) as exc:
        parser.error(str(exc))
        return 2
    summary = {
        "receipt": str(path),
        "skills": len(document.get("skills") or []),
        "comparisons": len(document.get("comparisons") or []),
        "history_entry": (document.get("provenance") or {}).get("history", {}).get("entry"),
        "baseline_label": (document.get("provenance") or {}).get("history", {}).get("baseline_label"),
        "proof_gaps": len(document.get("proof_gaps") or []),
    }
    if args.pretty:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
