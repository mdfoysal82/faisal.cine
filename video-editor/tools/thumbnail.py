#!/usr/bin/env python3
"""Thumbnail helpers (the design itself is made in Canva - see the thumbnail-generator skill).

  python3 tools/thumbnail.py frames <job> [--count 8]
      sharp candidate frames -> work/thumbs/cand-XX.jpg + work/thumbs/sheet.jpg (contact sheet)
  python3 tools/thumbnail.py html <job> --frame 3 --title "শিরোনাম" [--accent 0]
      fallback when Canva is not connected: 1280x720 HyperFrames design
      -> outputs/<job>.thumbnail.png
"""
import argparse
import html
import shutil
import subprocess
import sys

from common import ASSETS, OUTPUTS, Job, die, ffmpeg, hyperframes_cmd, load_preset, require


def frames(job: Job, count: int) -> None:
    src = job.w("roughcut.mp4") if job.w("roughcut.mp4").exists() else job.source
    dur = float(job.meta.get("steps", {}).get("rough-cut", {}).get("duration") or job.meta["source_info"]["duration"])
    out = job.w("thumbs")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    for i in range(count):
        t = dur * (0.06 + 0.88 * i / max(1, count - 1))
        # 'thumbnail' picks the most representative (least blurry/odd) frame of the next 45
        ffmpeg("-ss", f"{max(0, t - 0.75):.2f}", "-i", str(src), "-vf", "thumbnail=45,scale=1280:-2",
               "-frames:v", "1", "-q:v", "2", str(out / f"cand-{i + 1:02d}.jpg"))
    cols = 4
    rows = (count + cols - 1) // cols
    ffmpeg("-framerate", "1", "-i", str(out / "cand-%02d.jpg"), "-vf",
           f"scale=480:-2,drawtext=fontfile='{(ASSETS / 'fonts' / 'HindSiliguri-Bold.ttf').as_posix()}':"
           f"text='%{{eif\\:n+1\\:d}}':x=16:y=12:fontsize=48:fontcolor=white:"
           f"box=1:boxcolor=black@0.6:boxborderw=8,tile={cols}x{rows}:padding=6",
           "-frames:v", "1", str(out / "sheet.jpg"))
    print(f"candidates: {out}/cand-01..{count:02d}.jpg\ncontact sheet: {out / 'sheet.jpg'}")


def html_thumb(job: Job, frame: int, title: str, accent: int) -> None:
    cand = job.w("thumbs") / f"cand-{frame:02d}.jpg"
    if not cand.exists():
        die("run 'thumbnail.py frames <job>' first")
    style = load_preset("signature-style")
    color = style["colors"]["accents"][accent % len(style["colors"]["accents"])]
    bdir = job.w("thumbs") / "build"
    shutil.rmtree(bdir, ignore_errors=True)
    bdir.mkdir()
    shutil.copy(cand, bdir / "bg.jpg")
    shutil.copy(ASSETS / "fonts" / "AnekBangla.ttf", bdir)
    shutil.copy(ASSETS / "vendor" / "gsap.min.js", bdir)
    size = 112 if len(title) <= 22 else 92 if len(title) <= 36 else 76
    (bdir / "index.html").write_text(f"""<!doctype html>
<html lang="bn"><head><meta charset="UTF-8"/><script src="gsap.min.js"></script><style>
@font-face{{font-family:'Anek Bangla';src:url('AnekBangla.ttf');font-weight:100 800}}
html,body{{margin:0}}
#root{{position:relative;width:100%;height:100%;overflow:hidden;background:#000}}
.bg{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;filter:saturate(1.25) contrast(1.08)}}
.shade{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.82) 0%,rgba(0,0,0,.35) 55%,rgba(0,0,0,0) 80%)}}
.t{{position:absolute;left:64px;top:90px;width:700px;font-family:'Anek Bangla';font-weight:800;font-size:{size}px;line-height:1.12;color:#fff;text-shadow:0 6px 24px rgba(0,0,0,.6)}}
.t span{{color:{color}}}
.bar{{position:absolute;left:64px;bottom:72px;width:180px;height:16px;border-radius:8px;background:{color}}}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-width="1280" data-height="720" data-duration="1">
<img class="bg" src="bg.jpg"/><div class="shade"></div><div class="t">{html.escape(title)}</div><div class="bar"></div>
</div><script>window.__timelines['main']=gsap.timeline({{paused:true}});</script></body></html>
""", encoding="utf-8")
    snaps = bdir / "snapshots"
    r = subprocess.run([*hyperframes_cmd(), "snapshot", "--at", "0.5", "--no-end", "-o", str(snaps)],
                       cwd=bdir, capture_output=True, text=True)
    shots = sorted(snaps.glob("*.png"))
    if r.returncode or not shots:
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-2000:])
        die("snapshot failed")
    OUTPUTS.mkdir(exist_ok=True)
    out = OUTPUTS / f"{job.name}.thumbnail.png"
    ffmpeg("-i", str(shots[-1]), "-vf", "scale=1280:720", str(out))
    job.mark("thumbnail", via="html", output=str(out.relative_to(OUTPUTS.parent)))
    print(f"thumbnail: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("frames")
    p.add_argument("job")
    p.add_argument("--count", type=int, default=8)
    p = sub.add_parser("html")
    p.add_argument("job")
    p.add_argument("--frame", type=int, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--accent", type=int, default=0)
    a = ap.parse_args()
    require("ffmpeg")
    job = Job(a.job)
    if a.cmd == "frames":
        frames(job, a.count)
    else:
        html_thumb(job, a.frame, a.title, a.accent)


if __name__ == "__main__":
    main()
