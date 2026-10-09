#!/usr/bin/env python3
"""Step 1 - Intake: copy a raw clip into projects/<job>/raw/ and create job.json.

  python3 tools/intake.py /path/to/clip.mov --job my-video --format short-explainer
"""
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

from common import PROJECTS, die, load_format, probe, require, write_json


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="raw video file")
    ap.add_argument("--job", required=True, help="job name (letters, digits, dashes)")
    ap.add_argument("--format", required=True, help="short-explainer | short-tiktok | youtube")
    ap.add_argument("--language", default="bn", help="spoken language for transcription (default bn)")
    ap.add_argument("--force", action="store_true", help="replace an existing job of the same name")
    a = ap.parse_args()

    require("ffprobe")
    fmt = load_format(a.format)
    if not a.source.is_file():
        die(f"file not found: {a.source}")
    if not a.job.replace("-", "").replace("_", "").isalnum():
        die("job name may only contain letters, digits, '-' and '_'")

    job_dir = PROJECTS / a.job
    if job_dir.exists():
        if not a.force:
            die(f"job '{a.job}' already exists (use --force to replace it)")
        shutil.rmtree(job_dir)
    raw = job_dir / "raw"
    raw.mkdir(parents=True)
    (job_dir / "work").mkdir()

    dest = raw / a.source.name
    shutil.copy2(a.source, dest)
    info = probe(dest)
    if not info.get("width"):
        die("no video stream in that file")

    meta = {
        "job": a.job,
        "format": a.format,
        "language": a.language,
        "source": str(dest.relative_to(job_dir)),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_info": info,
        "target": {"width": fmt["width"], "height": fmt["height"],
                   "fps": min(round(info["fps"]), 60) or 30},
        "reframe": {"x": 0.5, "y": 0.5},
        "steps": {"intake": {"done": True}},
    }
    write_json(job_dir / "job.json", meta)
    print(f"intake ok: {dest}")
    print(f"  {info['width']}x{info['height']} @ {info['fps']}fps, {info['duration']:.1f}s, audio={info['has_audio']}")
    print(f"  format {a.format} -> {fmt['width']}x{fmt['height']}")


if __name__ == "__main__":
    main()
