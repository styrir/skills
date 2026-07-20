"""Profile loading and enforceability checks (plan §6; DR-05, DR-14)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ProfileError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def load_profile_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        text_stripped = text.lstrip()
        if text_stripped.startswith("{"):
            import json
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ProfileError("PROFILE_INVALID", "JSON profile root must be object")
            return data
        raise ProfileError(
            "PROFILE_INVALID",
            "PyYAML not installed; provide JSON profile content or install PyYAML",
        )
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ProfileError("PROFILE_INVALID", "profile must be a mapping")
    return data


def hypothesis_enforceable(h: dict) -> bool:
    if h.get("applicability") == "descriptive_only":
        return False
    evidence = h.get("evidence") or []
    if len(evidence) < 2:
        return False
    gc = h.get("genericity_check") or {}
    if not gc.get("acceptable_contrast"):
        return False
    if gc.get("quality_inversion") is not False:
        return False
    if gc.get("user_confirmed_author_specific") is not True:
        return False
    return True


def assert_revision_allowed(profile: dict | None, mode: str) -> None:
    if mode == "diagnose-only":
        return
    if not profile:
        raise ProfileError(
            "PROFILE_REQUIRED_FOR_REVISION",
            "revision modes require a resolvable validated voice profile",
        )


def collect_unenforceable_constraints(profile: dict, hypothesis_ids: list[str]) -> list[str]:
    by_id = {h.get("id"): h for h in profile.get("hypotheses") or [] if isinstance(h, dict)}
    bad = []
    for hid in hypothesis_ids:
        h = by_id.get(hid)
        if h is None or not hypothesis_enforceable(h):
            bad.append(hid)
    return bad
