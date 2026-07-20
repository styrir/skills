"""Protected-span detection and sentinel helpers (plan §7.1; DR-06, DR-07, DR-08)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


SENTINEL_RE = re.compile(r"VP_SENTINEL_(\d{4})")


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str
    text: str


def make_sentinel_id(source: str, index: int, salt: bytes = b"") -> str:
    """Source-derived per-index sentinel material (DR-07)."""
    h = hashlib.sha256()
    h.update(salt)
    h.update(str(index).encode("ascii"))
    h.update(b"\0")
    h.update(source.encode("utf-8"))
    n = int.from_bytes(h.digest()[:2], "big") % 10000
    return f"VP_SENTINEL_{n:04d}"


def find_urls(text: str) -> list[Span]:
    """Minimal URL detector placeholder; full multi-extractor order is plan §7.1."""
    spans: list[Span] = []
    pattern = re.compile(r"https?://[^\s<>\]\)]+")
    for m in pattern.finditer(text):
        prefix = text[: m.start()].encode("utf-8")
        matched = m.group(0).encode("utf-8")
        start = len(prefix)
        end = start + len(matched)
        spans.append(Span(start=start, end=end, kind="url", text=m.group(0)))
    return spans


def validate_sentinel_order(original_ids: list[str], restored_text: str) -> str | None:
    """Return rejection code if sentinel relative order changes (DR-08)."""
    found = SENTINEL_RE.findall(restored_text)
    found_ids = [f"VP_SENTINEL_{n}" for n in found]
    wanted = [s for s in found_ids if s in set(original_ids)]
    expected = [s for s in original_ids if s in set(wanted)]
    if wanted != expected:
        return "SENTINEL_ORDER_CHANGED"
    return None
