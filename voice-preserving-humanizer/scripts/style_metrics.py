"""Independent style metrics and corpus envelopes (plan §7.4, §9.5; DR-04)."""

from __future__ import annotations

import re
from dataclasses import dataclass


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[\w']+", re.UNICODE)


@dataclass(frozen=True)
class MetricReport:
    name: str
    source_value: float | None
    output_value: float | None
    corpus_median: float | None
    corpus_low: float | None
    corpus_high: float | None
    sample_sufficient: bool
    warn: bool
    note: str


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text.strip()) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def sentence_length_words(text: str) -> list[int]:
    return [len(words(s)) for s in sentences(text)]


def median(vals: list[float | int]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (float(s[mid - 1]) + float(s[mid])) / 2.0


def contraction_rate(text: str) -> float | None:
    ws = words(text)
    if len(ws) < 100:
        return None
    contractions = sum(1 for w in ws if "'" in w or "’" in w)
    return contractions / len(ws)


def sentence_median_report(source: str, output: str, corpus_vals: list[float]) -> MetricReport:
    s_lens = sentence_length_words(source)
    o_lens = sentence_length_words(output)
    sufficient = len(s_lens) >= 5 and len(o_lens) >= 5
    if not sufficient:
        return MetricReport(
            name="sentence_length_median",
            source_value=median(s_lens),
            output_value=median(o_lens),
            corpus_median=median(corpus_vals) if corpus_vals else None,
            corpus_low=min(corpus_vals) if corpus_vals else None,
            corpus_high=max(corpus_vals) if corpus_vals else None,
            sample_sufficient=False,
            warn=False,
            note="insufficient_sample",
        )
    s_med = median(s_lens)
    o_med = median(o_lens)
    c_med = median(corpus_vals) if corpus_vals else None
    c_low = min(corpus_vals) if corpus_vals else None
    c_high = max(corpus_vals) if corpus_vals else None
    warn = False
    note = "ok"
    if None not in (c_med, c_low, c_high, s_med, o_med):
        if abs(o_med - c_med) > abs(s_med - c_med) and (o_med < c_low or o_med > c_high):
            warn = True
            note = "outside_corpus_envelope"
    return MetricReport(
        name="sentence_length_median",
        source_value=s_med,
        output_value=o_med,
        corpus_median=c_med,
        corpus_low=c_low,
        corpus_high=c_high,
        sample_sufficient=True,
        warn=warn,
        note=note,
    )
