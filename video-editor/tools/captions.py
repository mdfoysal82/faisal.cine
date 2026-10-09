#!/usr/bin/env python3
"""Step 5 - Captions (short-form only): burn on-beat word captions -> work/captioned.mp4

The style comes from the job format (presets/formats.json -> captions.style), e.g.
  captions-style   centered, locked position, active word highlighted (short explainer)
  tiktok-raw-style low under the face, 1-3 word chunks that pop in (TikTok / raw)
Long-form YouTube gets no burn-in; finalize ships work/transcript.srt as a sidecar instead.

  python3 tools/captions.py <job> [--style captions-style] [--off]

Brand/spelling fixes come from presets/caption-corrections.json (already applied to
work/transcript.json by the rough cut). Edit transcript.json words directly for one-off fixes.
"""
import argparse

from common import ASSETS, ENCODE, Job, die, ffmpeg, load_preset, read_json, require
from textutil import sentences


def ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t: float) -> str:
    cs = int(round(max(t, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def chunk_words(words, max_chars: int, max_lines: int, per_chunk: int):
    """Split into on-screen chunks that never cross a sentence boundary."""
    chunks = []
    for sent in sentences(words, max_gap=0.6):
        cur = []
        for w in sent:
            text = " ".join(x["text"] for x in cur + [w])
            full = (per_chunk and len(cur) >= per_chunk) or len(text) > max_chars * max_lines
            if cur and full:
                chunks.append(cur)
                cur = []
            cur.append(w)
        if cur:
            chunks.append(cur)
    return chunks


def layout(chunk, max_chars: int, max_lines: int) -> list[list[int]]:
    """Return word-index lines, balanced when the chunk needs two lines."""
    text = " ".join(w["text"] for w in chunk)
    if max_lines < 2 or len(text) <= max_chars or len(chunk) < 2:
        return [list(range(len(chunk)))]
    best, best_diff = 1, 1e9
    for k in range(1, len(chunk)):
        a = len(" ".join(w["text"] for w in chunk[:k]))
        b = len(" ".join(w["text"] for w in chunk[k:]))
        if abs(a - b) < best_diff:
            best, best_diff = k, abs(a - b)
    return [list(range(best)), list(range(best, len(chunk)))]


def build_ass(words, style: dict, width: int, height: int) -> str:
    c = style["captions"]
    size = round(c["size"] * height)
    outline = max(1, round(c["outline_width"] * height))
    y = round(c["position_y"] * height)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{c['font']},{size},{ass_color(c['primary'])},{ass_color(c['highlight'])},{ass_color(c['outline'])},{ass_color('#000000', 128)},{-1 if c.get('bold') else 0},0,0,0,100,100,0,0,1,{outline},{c.get('shadow', 0)},5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    hi = ass_color(c["highlight"])
    events = []
    chunks = chunk_words(words, c["max_chars"], c["max_lines"], c.get("words_per_chunk", 0))
    for n, chunk in enumerate(chunks):
        start = chunk[0]["start"]
        nxt = chunks[n + 1][0]["start"] if n + 1 < len(chunks) else chunk[-1]["end"] + 0.6
        end = min(nxt, chunk[-1]["end"] + 0.6)
        lines = layout(chunk, c["max_chars"], c["max_lines"])
        pos = f"{{\\an5\\pos({width // 2},{y})}}"
        if c["mode"] == "pop":
            text = "\\N".join(" ".join(esc(chunk[i]["text"]) for i in ln) for ln in lines)
            anim = "{\\fscx82\\fscy82\\t(0,90,\\fscx106\\fscy106)\\t(90,150,\\fscx100\\fscy100)}"
            events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{pos}{anim}{text}")
            continue
        # highlight: one event per active word so the colour moves with the speech
        for k, w in enumerate(chunk):
            ws = start if k == 0 else w["start"]
            we = chunk[k + 1]["start"] if k + 1 < len(chunk) else end
            parts = []
            for ln in lines:
                parts.append(" ".join(
                    (f"{{\\c{hi}}}{esc(chunk[i]['text'])}{{\\r}}" if i == k else esc(chunk[i]["text"]))
                    for i in ln))
            events.append(f"Dialogue: 0,{ass_time(ws)},{ass_time(we)},Cap,,0,0,0,,{pos}" + "\\N".join(parts))
    return header + "\n".join(events) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--style", help="override the caption preset (file name in presets/)")
    ap.add_argument("--off", action="store_true", help="disable burned-in captions for this job")
    a = ap.parse_args()

    require("ffmpeg")
    job = Job(a.job)
    out = job.w("captioned.mp4")
    style_name = a.style or job.format["captions"].get("style")
    if a.off or not style_name:
        out.unlink(missing_ok=True)
        job.mark("captions", disabled=True)
        print("captions off for this job (YouTube: transcript.srt ships as a sidecar at finalize)")
        return
    style = load_preset(style_name)
    if "captions" not in style:
        die(f"preset {style_name} has no 'captions' block")
    words = read_json(job.w("transcript.json"))
    src = job.stage_input("captions")
    t = job.meta["target"]
    ass = job.w("captions.ass")
    ass.write_text(build_ass(words, style, t["width"], t["height"]), encoding="utf-8")
    # relative paths + cwd keep the filter string free of characters ffmpeg would need escaped
    fonts = ASSETS / "fonts"
    ffmpeg("-i", src.name, "-vf", f"ass=captions.ass:fontsdir='{fonts.as_posix()}'",
           *ENCODE, "-c:a", "copy", out.name, cwd=job.work)
    job.mark("captions", style=style_name, input=src.name)
    print(f"captions ok ({style_name}): {out}")


if __name__ == "__main__":
    main()
