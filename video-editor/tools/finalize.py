#!/usr/bin/env python3
"""Step 7 - Export: promote the latest stage to outputs/<job>.final.mp4

Two-pass loudness normalization to the format target (YouTube/TikTok/Reels: -14 LUFS,
-1 dBTP), video stream copied untouched, then a spec check. YouTube jobs also get
outputs/<job>.srt (cut-timeline transcript) for closed captions.

  ./finalize.sh <job>
"""
import argparse
import json
import re
import shutil
import subprocess

from common import AENC, OUTPUTS, Job, die, ffmpeg, probe, require


def measure(path, target) -> dict:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-map", "0:a", "-af",
                        f"loudnorm=I={target}:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        die("could not measure loudness")
    return json.loads(m.group(0))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    a = ap.parse_args()

    require("ffmpeg")
    job = Job(a.job)
    src = job.stage_input("finalize")
    chain = [job.w(n) for n in ("roughcut.mp4", "graphics.mp4", "captioned.mp4", "music.mp4")
             if job.w(n).exists() and job.stage_enabled(n)]
    for prev, nxt in zip(chain, chain[1:]):
        if nxt.stat().st_mtime < prev.stat().st_mtime:
            die(f"work/{nxt.name} is older than work/{prev.name} - run: "
                f"python3 tools/rebuild.py {job.name} --from <first changed step>")
    target = job.format.get("loudness_lufs", -14)
    OUTPUTS.mkdir(exist_ok=True)
    out = OUTPUTS / f"{job.name}.final.mp4"

    m = measure(src, target)
    ln = (f"loudnorm=I={target}:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
          "linear=true,aresample=48000")
    ffmpeg("-i", str(src), "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af", ln, *AENC, str(out))

    if job.meta["format"] == "youtube" and job.w("transcript.srt").exists():
        shutil.copy(job.w("transcript.srt"), OUTPUTS / f"{job.name}.srt")

    info = probe(out)
    after = measure(out, target)
    t = job.meta["target"]
    ok_size = (info["width"], info["height"]) == (t["width"], t["height"])
    job.mark("finalize", output=str(out.relative_to(OUTPUTS.parent)), source=src.name,
             lufs=float(after["input_i"]), true_peak=float(after["input_tp"]))
    print(f"SHIP: {out}")
    print(f"  from      work/{src.name}")
    print(f"  size      {info['width']}x{info['height']} {'ok' if ok_size else 'MISMATCH'} @ {info['fps']}fps")
    print(f"  duration  {info['duration']:.2f}s")
    print(f"  loudness  {float(after['input_i']):.1f} LUFS (target {target}), peak {float(after['input_tp']):.1f} dBTP")
    if job.meta["format"] == "youtube":
        print(f"  captions  outputs/{job.name}.srt (upload as YouTube CC)")


if __name__ == "__main__":
    main()
