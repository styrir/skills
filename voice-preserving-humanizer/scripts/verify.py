"""Deterministic verification helpers (plan §7.4, §9.3; DR-09, DR-11, DR-12)."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_for_overlap(text: str) -> list[str]:
    """Tokenize for six-token memorization scan (plan §9.3; DR-11)."""
    text = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            tokens.append("".join(buf))
            buf = []

    for ch in text:
        if ch in {"'", "’"} and buf:
            buf.append("'")
            continue
        if ch.isalnum():
            buf.append(ch)
        else:
            flush()
    flush()
    return [t for t in tokens if t and t != "'"]


def contiguous_ngrams(tokens: list[str], n: int = 6) -> set[tuple[str, ...]]:
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def memorization_overlaps(
    changed_region: str,
    profile_sample_texts: dict[str, str],
    source_text: str,
    n: int = 6,
) -> list[dict]:
    src_grams = contiguous_ngrams(normalize_for_overlap(source_text), n)
    region_grams = contiguous_ngrams(normalize_for_overlap(changed_region), n)
    hits = []
    for sample_id, sample in profile_sample_texts.items():
        sample_grams = contiguous_ngrams(normalize_for_overlap(sample), n)
        for gram in sorted(region_grams & sample_grams):
            if gram in src_grams:
                continue
            hits.append(
                {
                    "sample_id": sample_id,
                    "token_count": n,
                    "alignment_sha256": sha256_text(" ".join(gram)),
                    "review_code": "PROFILE_MEMORIZATION_OVERLAP",
                }
            )
    return hits


@dataclass(frozen=True)
class VerifierGate:
    protected_spans: str
    edit_locality: str
    semantic_fidelity: str

    @property
    def deterministic_pass(self) -> bool:
        return self.protected_spans == "pass" and self.edit_locality == "pass"


def combine_with_semantic(det: VerifierGate, semantic: str) -> str:
    if not det.deterministic_pass:
        return "rejected"
    if semantic == "fail":
        return "rejected"
    if semantic == "uncertain":
        return "review_required"
    if semantic == "pass" and det.semantic_fidelity == "pass":
        return "accepted"
    return "review_required"
