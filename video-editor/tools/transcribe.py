#!/usr/bin/env python3
"""Rough-cut part 1: word-level transcript of the RAW clip -> work/transcript.raw.json

Engines:
  hyperframes (default) - local whisper.cpp via the HyperFrames CLI; uses Metal on Apple Silicon.
  whisperx              - WhisperX + wav2vec2 forced alignment (pip install whisperx).
  import                - import an existing transcript (.json word list / whisperx json / .srt).

  python3 tools/transcribe.py <job> [--engine hyperframes] [--model large-v3] [--language bn]
  python3 tools/transcribe.py <job> --engine import --file transcript.srt

Output is a flat list: [{"text": "...", "start": s, "end": e}, ...]
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from common import Job, die, ffmpeg, hyperframes_cmd, read_json, require, write_json

# wav2vec2 alignment models for languages WhisperX has no default for.
ALIGN_MODELS = {"bn": "arijitx/wav2vec2-xls-r-300m-bengali"}


def extract_audio(job: Job) -> Path:
    out = job.w("audio.wav")
    if not job.meta["source_info"]["has_audio"]:
        die("the raw clip has no audio track - nothing to transcribe")
    ffmpeg("-i", str(job.source), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out))
    return out


def run_hyperframes(audio: Path, model: str, language: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [*hyperframes_cmd(), "transcribe", str(audio), "-d", tmp, "--json",
               "--engine", "whisper", "--model", model]
        if language and language != "auto":
            cmd += ["--language", language]
        print("transcribing with whisper.cpp (", model, language, ") - first run downloads the model ...")
        r = subprocess.run(cmd, text=True, capture_output=True)
        if r.returncode != 0:
            sys.stderr.write(r.stdout[-2000:] + r.stderr[-3000:])
            die("hyperframes transcribe failed")
        path = Path(tmp) / "transcript.json"
        if not path.exists():
            die("hyperframes transcribe produced no transcript.json")
        return normalize(read_json(path))


def run_whisperx(audio: Path, model: str, language: str, align_model: str | None) -> list[dict]:
    try:
        import whisperx  # type: ignore
    except ImportError:
        die("whisperx is not installed - run: pip install whisperx  (or use --engine hyperframes)")
    device = "cpu"  # ctranslate2 has no Metal backend; int8 on CPU is the fast path on a Mac
    lang = None if language == "auto" else language
    asr = whisperx.load_model(model, device, compute_type="int8", language=lang)
    data = whisperx.load_audio(str(audio))
    result = asr.transcribe(data, batch_size=8, language=lang)
    lang = result.get("language", lang)
    name = align_model or ALIGN_MODELS.get(lang)
    try:
        amodel, ameta = whisperx.load_align_model(language_code=lang, device=device, model_name=name)
        result = whisperx.align(result["segments"], amodel, ameta, data, device)
    except Exception as e:  # alignment is best-effort; segment-level timings still work
        print(f"warning: alignment failed ({e}); falling back to evenly spaced word timings", file=sys.stderr)
    return normalize(result)


def normalize(data) -> list[dict]:
    """Accept a flat word list, a whisperx/whisper result, or {'words': [...]}."""
    if isinstance(data, dict):
        if "segments" in data:
            words = []
            for seg in data["segments"]:
                if seg.get("words"):
                    words += seg["words"]
                else:
                    words += spread(seg["text"], seg["start"], seg["end"])
            data = words
        elif "words" in data:
            data = data["words"]
    out = []
    for w in data:
        text = (w.get("text") or w.get("word") or "").strip()
        if not text or "start" not in w or "end" not in w:
            continue
        out.append({"text": text, "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3)})
    # Repair overlaps/zero-length words that ASR engines sometimes emit.
    for i, w in enumerate(out):
        if i and w["start"] < out[i - 1]["end"]:
            w["start"] = out[i - 1]["end"]
        w["end"] = max(w["end"], w["start"] + 0.04)
    return out


def spread(text: str, start: float, end: float) -> list[dict]:
    toks = text.split()
    if not toks:
        return []
    total = sum(len(t) for t in toks)
    words, t = [], start
    for tok in toks:
        d = (end - start) * len(tok) / total
        words.append({"text": tok, "start": t, "end": t + d})
        t += d
    return words


def parse_srt(text: str) -> list[dict]:
    def ts(s: str) -> float:
        h, m, rest = s.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest)

    words = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        tl = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if tl is None:
            continue
        a, b = [x.strip().split()[0] for x in lines[tl].split("-->")]
        words += spread(" ".join(lines[tl + 1:]), ts(a), ts(b))
    return words


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--engine", default="hyperframes", choices=["hyperframes", "whisperx", "import"])
    ap.add_argument("--model", default="large-v3", help="whisper model (large-v3 is best for Bangla)")
    ap.add_argument("--language", help="language code, or 'auto' (default: the job's language)")
    ap.add_argument("--align-model", help="whisperx only: override the wav2vec2 alignment model")
    ap.add_argument("--file", type=Path, help="import only: transcript file")
    a = ap.parse_args()

    job = Job(a.job)
    require("ffmpeg")
    language = a.language or job.meta.get("language", "bn")

    if a.engine == "import":
        if not a.file or not a.file.exists():
            die("--engine import needs --file <transcript>")
        raw = a.file.read_text(encoding="utf-8")
        words = parse_srt(raw) if a.file.suffix.lower() == ".srt" else normalize(json.loads(raw))
    else:
        audio = extract_audio(job)
        if a.engine == "hyperframes":
            words = run_hyperframes(audio, a.model, language)
        else:
            words = run_whisperx(audio, a.model, language, a.align_model)

    if not words:
        die("transcript is empty")
    write_json(job.w("transcript.raw.json"), words)
    job.mark("transcribe", engine=a.engine, model=a.model, language=language, words=len(words))
    print(f"transcript ok: {len(words)} words -> {job.w('transcript.raw.json')}")
    print("  " + " ".join(w["text"] for w in words[:40]) + (" ..." if len(words) > 40 else ""))


if __name__ == "__main__":
    main()
