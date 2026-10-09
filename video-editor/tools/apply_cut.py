#!/usr/bin/env python3
"""Rough-cut part 3: render the approved cut list -> work/roughcut.mp4

Also reframes to the job format, polishes the audio (high-pass, light denoise, de-ess,
compression, loudness), and writes the cut-timeline transcript, script.md and an SRT.

  python3 tools/apply_cut.py <job> [--no-polish] [--force-unapproved]

Each kept range is rendered once into work/segments/<hash>.mov and reused on later runs,
so a second-pass change only re-encodes the ranges that actually changed.
"""
import argparse
import hashlib
import json

from common import AENC, Job, die, ffmpeg, fmt_time, read_json, require, write_json
from cutlist import keep_ranges
from textutil import apply_corrections, remap, sentences, to_srt

FADE = 0.012  # seconds of audio fade at every join, kills clicks


def reframe_filter(job: Job) -> str:
    src = job.meta["source_info"]
    tw, th = job.meta["target"]["width"], job.meta["target"]["height"]
    fx, fy = job.meta["reframe"]["x"], job.meta["reframe"]["y"]
    sa, ta = src["width"] / src["height"], tw / th
    if abs(sa - ta) < 0.01:
        return f"scale={tw}:{th}:flags=lanczos,setsar=1"
    if sa > ta:  # wider source (16:9 -> 9:16): crop width around reframe.x
        cw = f"ih*{tw}/{th}"
        return (f"crop={cw}:ih:'max(0,min(iw-{cw},iw*{fx}-{cw}/2))':0,"
                f"scale={tw}:{th}:flags=lanczos,setsar=1")
    # taller source (9:16 -> 16:9): blurred fill behind the fitted picture
    return (f"split[a][b];[a]scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},"
            f"boxblur=40:2,eq=brightness=-0.08[bg];[b]scale=-2:{th}:flags=lanczos[fg];"
            f"[bg][fg]overlay=(W-w)/2:0,setsar=1")


def render_segment(job: Job, s: float, e: float, vf: str) -> tuple[str, float]:
    fps = job.meta["target"]["fps"]
    frames = max(1, round((e - s) * fps))
    dur = frames / fps
    has_audio = job.meta["source_info"]["has_audio"]
    key = json.dumps([job.meta["source"], s, dur, vf, fps, has_audio, 2])
    name = hashlib.sha1(key.encode()).hexdigest()[:16] + ".mov"
    out = job.w("segments") / name
    if out.exists():
        return name, dur
    out.parent.mkdir(exist_ok=True)
    af = (f"aresample=48000,apad,atrim=0:{dur:.6f},afade=t=in:d={FADE},"
          f"afade=t=out:st={max(0, dur - FADE):.6f}:d={FADE}")
    args = ["-ss", f"{s:.3f}", "-i", str(job.source)]
    if not has_audio:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    graph = f"[0:v]{vf},fps={fps}[v];[{0 if has_audio else 1}:a]{af}[a]"
    ffmpeg(*args, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
           "-frames:v", str(frames), "-t", f"{dur:.6f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
           "-g", str(fps * 2), "-c:a", "pcm_s16le", "-ac", "2", str(out))
    return name, dur


def write_script(job: Job, words: list[dict]) -> None:
    lines = [f"# Script - {job.name}", ""]
    for sent in sentences(words):
        lines.append(f"**[{fmt_time(sent[0]['start'])}]** " + " ".join(w["text"] for w in sent))
        lines.append("")
    job.w("script.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--no-polish", action="store_true", help="skip the audio polish chain")
    ap.add_argument("--force-unapproved", action="store_true", help="render even if the cut list is not approved")
    a = ap.parse_args()

    require("ffmpeg")
    job = Job(a.job)
    cl_path = job.w("cutlist.json")
    if not cl_path.exists():
        die("no cut list - run: tools/cutlist.py plan <job>")
    cl = read_json(cl_path)
    if not cl.get("approved") and not a.force_unapproved:
        die("cut list not approved yet - show work/cutlist.md to the user, then: tools/cutlist.py approve <job>")

    keeps = keep_ranges(cl)
    if not keeps:
        die("the cut list removes everything")
    vf = reframe_filter(job)
    parts, durs = [], []
    for i, (s, e) in enumerate(keeps, 1):
        name, d = render_segment(job, s, e, vf)
        parts.append(name)
        durs.append(d)
        print(f"\r  segment {i}/{len(keeps)}", end="", flush=True)
    print()

    used = set(parts)
    for old in job.w("segments").glob("*.mov"):
        if old.name not in used:
            old.unlink()
    concat = job.w("segments") / "concat.txt"
    concat.write_text("".join(f"file '{p}'\n" for p in parts))
    joined = job.w("roughcut.joined.mov")
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(joined))

    polish = [] if a.no_polish else [
        "highpass=f=75", "afftdn=nr=10:nf=-40", "deesser=i=0.4",
        "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2",
        "loudnorm=I=-16:TP=-1.5:LRA=11", "aresample=48000",
    ]
    out = job.w("roughcut.mp4")
    ffmpeg("-i", str(joined), "-map", "0:v", "-map", "0:a", "-c:v", "copy",
           *(["-af", ",".join(polish)] if polish else []), *AENC, str(out))
    joined.unlink()

    raw_words = read_json(job.w("transcript.raw.json"))
    words = apply_corrections(remap(raw_words, keeps, durs))
    write_json(job.w("transcript.json"), words)
    write_json(job.w("timeline.json"), {"keeps": keeps, "durations": durs})
    job.w("transcript.srt").write_text(to_srt(words), encoding="utf-8")
    write_script(job, words)

    total = sum(durs)
    job.mark("rough-cut", duration=round(total, 3), segments=len(keeps), polish=not a.no_polish)
    print(f"rough cut ok: {fmt_time(cl['source_duration'])} -> {fmt_time(total)} ({len(keeps)} segments)")
    print(f"  video  {out}\n  script {job.w('script.md')}")


if __name__ == "__main__":
    main()
