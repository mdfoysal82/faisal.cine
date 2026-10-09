"""Transcript helpers: remap to the cut timeline, brand/spelling corrections, sentences, SRT."""
from __future__ import annotations

import re

from common import PRESETS, read_json

PUNCT = re.compile(r"[\s\.,!?;:।॥\"'“”‘’()\[\]{}…\-–—]+")
SENTENCE_END = re.compile(r"[\.!?।॥]$")


def norm(t: str) -> str:
    return PUNCT.sub("", t.lower())


def remap(words: list[dict], keeps: list[list[float]], durations: list[float]) -> list[dict]:
    """Move words from raw time onto the cut timeline. `durations` are the frame-quantized
    lengths actually rendered for each keep range. Words mostly inside a cut are dropped."""
    out, offset = [], 0.0
    for (s, e), d in zip(keeps, durations):
        for w in words:
            mid = (w["start"] + w["end"]) / 2
            if s <= mid < e:
                ns = offset + max(w["start"], s) - s
                ne = offset + min(w["end"], e) - s
                out.append({"text": w["text"], "start": round(ns, 3), "end": round(min(ne, offset + d), 3)})
        offset += d
    return out


def apply_corrections(words: list[dict]) -> list[dict]:
    """Replace (multi-word) phrases from presets/caption-corrections.json, keeping timings."""
    table = read_json(PRESETS / "caption-corrections.json").get("replace", {})
    rules = sorted(((tuple(norm(x) for x in k.split()), v) for k, v in table.items()),
                   key=lambda r: len(r[0]), reverse=True)
    out, i = [], 0
    toks = [norm(w["text"]) for w in words]
    while i < len(words):
        for key, val in rules:
            if key and tuple(toks[i:i + len(key)]) == key:
                last = words[i + len(key) - 1]
                trail = re.search(r"[\.,!?;:।]+$", last["text"])
                out.append({"text": val + (trail.group(0) if trail else ""),
                            "start": words[i]["start"], "end": last["end"]})
                i += len(key)
                break
        else:
            out.append(dict(words[i]))
            i += 1
    return out


def sentences(words: list[dict], max_gap: float = 0.7, max_words: int = 40) -> list[list[dict]]:
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and (w["start"] - cur[-1]["end"] > max_gap or len(cur) >= max_words):
            out.append(cur)
            cur = []
        cur.append(w)
        if SENTENCE_END.search(w["text"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(words: list[dict], max_chars: int = 42) -> str:
    """Readable sidecar subtitles (YouTube CC) - lines of up to max_chars."""
    cues, cur = [], []
    for sent in sentences(words):
        for w in sent:
            if cur and len(" ".join(x["text"] for x in cur + [w])) > max_chars:
                cues.append(cur)
                cur = []
            cur.append(w)
        if cur:
            cues.append(cur)
            cur = []
    lines = []
    for n, c in enumerate(cues, 1):
        lines += [str(n), f"{srt_time(c[0]['start'])} --> {srt_time(c[-1]['end'])}",
                  " ".join(w["text"] for w in c), ""]
    return "\n".join(lines)
