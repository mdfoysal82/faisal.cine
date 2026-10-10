#!/usr/bin/env python3
"""Step 1 - Intake: copy raw footage into projects/<job>/raw/ and create job.json.

  python3 tools/intake.py /path/to/clip.mov --job my-video --format short-explainer
  python3 tools/intake.py clip1.mov clip2.mov clip3.mov --job my-video --format youtube
  python3 tools/intake.py /path/to/folder-of-clips --job my-video --format short-tiktok

Several clips (or a folder) are joined in order into raw/combined.mov - natural file-name
order by default (IMG_2 before IMG_10), or recording time with --order time. Clips with a
different size/fps are scaled and padded to the first clip; clips without sound get silence.
"""
import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from common import PROJECTS, die, ffmpeg, load_format, probe, require, write_json

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mts", ".m2ts", ".webm", ".3gp"}


def natural_key(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def collect(sources: list[Path], order: str) -> list[Path]:
    files = []
    for s in sources:
        if s.is_dir():
            files += [p for p in s.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXT
                      and not p.name.startswith(".")]
        elif s.is_file():
            files.append(s)
        else:
            die(f"not found: {s}")
    if not files:
        die("no video files found")
    if order == "time":
        return sorted(files, key=lambda p: p.stat().st_mtime)
    if order == "name":
        return sorted(files, key=natural_key)
    return files  # as given


def join(clips: list[Path], infos: list[dict], out: Path) -> dict:
    """Normalize every clip to the first clip's frame size/fps, then concatenate."""
    w, h = infos[0]["width"], infos[0]["height"]
    fps = min(round(infos[0]["fps"]), 60) or 30
    parts = out.parent / ".parts"
    parts.mkdir()
    listing = []
    for i, (clip, info) in enumerate(zip(clips, infos), 1):
        part = parts / f"{i:03d}.mov"
        frames = max(1, round(info["duration"] * fps))
        dur = frames / fps
        args = ["-i", str(clip)]
        if not info["has_audio"]:
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        vf = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,"
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v]")
        af = f"[{0 if info['has_audio'] else 1}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{dur:.6f}[a]"
        ffmpeg(*args, "-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]",
               "-frames:v", str(frames), "-t", f"{dur:.6f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p",
               "-g", str(fps * 2), "-c:a", "pcm_s16le", str(part))
        listing.append(f"file '{part.name}'\n")
        print(f"\r  joining clip {i}/{len(clips)}", end="", flush=True)
    print()
    (parts / "list.txt").write_text("".join(listing))
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(parts / "list.txt"), "-c", "copy", str(out))
    shutil.rmtree(parts)
    return probe(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", type=Path, nargs="+", help="video file(s) or a folder of clips")
    ap.add_argument("--job", required=True, help="job name (letters, digits, dashes)")
    ap.add_argument("--format", required=True, help="short-explainer | short-tiktok | youtube")
    ap.add_argument("--language", default="bn", help="spoken language for transcription (default bn)")
    ap.add_argument("--order", default="name", choices=["name", "time", "given"],
                    help="clip order when joining several clips (default: natural file-name order)")
    ap.add_argument("--force", action="store_true", help="replace an existing job of the same name")
    a = ap.parse_args()

    require("ffprobe")
    fmt = load_format(a.format)
    if not a.job.replace("-", "").replace("_", "").isalnum():
        die("job name may only contain letters, digits, '-' and '_'")
    clips = collect(a.sources, a.order)

    job_dir = PROJECTS / a.job
    if job_dir.exists():
        if not a.force:
            die(f"job '{a.job}' already exists (use --force to replace it)")
        shutil.rmtree(job_dir)
    raw = job_dir / "raw"
    raw.mkdir(parents=True)
    (job_dir / "work").mkdir()

    copies, infos = [], []
    for clip in clips:
        dest = raw / clip.name
        if dest.exists():
            die(f"two clips share the name {clip.name} - rename one")
        shutil.copy2(clip, dest)
        info = probe(dest)
        if not info.get("width"):
            die(f"no video stream in {clip.name}")
        copies.append(dest)
        infos.append(info)

    clip_list = None
    if len(copies) == 1:
        source, info = copies[0], infos[0]
    else:
        require("ffmpeg")
        source = raw / "combined.mov"
        info = join(copies, infos, source)
        t, clip_list = 0.0, []
        for c, ci in zip(copies, infos):
            fps = min(round(infos[0]["fps"]), 60) or 30
            d = max(1, round(ci["duration"] * fps)) / fps
            clip_list.append({"file": c.name, "start": round(t, 3), "end": round(t + d, 3)})
            t += d

    meta = {
        "job": a.job,
        "format": a.format,
        "language": a.language,
        "source": str(source.relative_to(job_dir)),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_info": info,
        "target": {"width": fmt["width"], "height": fmt["height"],
                   "fps": min(round(info["fps"]), 60) or 30},
        "reframe": {"x": 0.5, "y": 0.5},
        "steps": {"intake": {"done": True}},
    }
    if clip_list:
        meta["clips"] = clip_list
    write_json(job_dir / "job.json", meta)
    print(f"intake ok: {source}" + (f"  ({len(copies)} clips joined)" if clip_list else ""))
    if clip_list:
        for n, c in enumerate(clip_list, 1):
            print(f"  {n:>2}. {c['file']}  {c['start']:.1f}s - {c['end']:.1f}s")
    print(f"  {info['width']}x{info['height']} @ {info['fps']}fps, {info['duration']:.1f}s, audio={info['has_audio']}")
    print(f"  format {a.format} -> {fmt['width']}x{fmt['height']}")


if __name__ == "__main__":
    main()
