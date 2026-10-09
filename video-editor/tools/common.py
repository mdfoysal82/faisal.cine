"""Shared helpers for the pipeline tools: job paths, JSON I/O, ffprobe, ffmpeg."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
OUTPUTS = ROOT / "outputs"
PRESETS = ROOT / "presets"
ASSETS = ROOT / "assets"
MUSIC = ROOT / "music"

# Homebrew's plain `ffmpeg` formula has no libass (captions) or freetype (drawtext);
# `ffmpeg-full` has both but is keg-only, so put it first on PATH when it is installed.
for _prefix in ("/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin"):
    if os.path.isfile(os.path.join(_prefix, "ffmpeg")):
        os.environ["PATH"] = _prefix + os.pathsep + os.environ.get("PATH", "")
        break


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def hf_cli_version() -> str:
    return read_json(ROOT / "skills-lock.json")["hyperframes"]["cli"]


def hyperframes_cmd() -> list[str]:
    return ["npx", "-y", f"hyperframes@{hf_cli_version()}"]


# Render telemetry is off unless the user opts in (set HYPERFRAMES_NO_TELEMETRY=0).
os.environ.setdefault("HYPERFRAMES_NO_TELEMETRY", "1")


class Job:
    """A job lives in projects/<name>/ with raw/, work/ and job.json."""

    def __init__(self, name: str):
        self.name = name
        self.dir = PROJECTS / name
        self.raw = self.dir / "raw"
        self.work = self.dir / "work"
        self.meta_path = self.dir / "job.json"
        if not self.meta_path.exists():
            die(f"job '{name}' not found - run intake first ({self.meta_path})")
        self.meta = read_json(self.meta_path)

    def save(self) -> None:
        write_json(self.meta_path, self.meta)

    @property
    def format(self) -> dict:
        return load_format(self.meta["format"])

    @property
    def source(self) -> Path:
        return self.dir / self.meta["source"]

    def w(self, name: str) -> Path:
        return self.work / name

    def mark(self, step: str, **info) -> None:
        self.meta.setdefault("steps", {})[step] = info
        self.save()

    def stage_input(self, stage: str) -> Path:
        """The video a stage should start from: the output of the nearest
        earlier stage that has run. Order: roughcut -> graphics -> captioned -> music."""
        order = ["roughcut.mp4", "graphics.mp4", "captioned.mp4", "music.mp4"]
        stage_out = {"graphics": "graphics.mp4", "captions": "captioned.mp4",
                     "music": "music.mp4", "finalize": None}[stage]
        stop = order.index(stage_out) if stage_out else len(order)
        for name in reversed(order[:stop]):
            p = self.w(name)
            if p.exists() and self.stage_enabled(name):
                return p
        die("no rough cut yet - run the rough-cut step first")

    def stage_enabled(self, out_name: str) -> bool:
        step = {"roughcut.mp4": "rough-cut", "graphics.mp4": "graphics",
                "captioned.mp4": "captions", "music.mp4": "music"}[out_name]
        return not self.meta.get("steps", {}).get(step, {}).get("disabled", False)


def load_format(fmt: str) -> dict:
    formats = read_json(PRESETS / "formats.json")
    if fmt not in formats:
        die(f"unknown format '{fmt}'. choose one of: {', '.join(formats)}")
    return formats[fmt] | {"id": fmt}


def load_preset(name: str) -> dict:
    return read_json(PRESETS / f"{name}.json")


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,sample_rate:stream_side_data=rotation:format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    info = {"duration": float(data["format"]["duration"]), "has_audio": False}
    for s in data["streams"]:
        if s["codec_type"] == "video" and "width" not in info:
            num, den = s["r_frame_rate"].split("/")
            w, h = s["width"], s["height"]
            rot = next((abs(int(sd.get("rotation", 0))) for sd in s.get("side_data_list", [])), 0)
            if rot in (90, 270):
                w, h = h, w
            info.update(width=w, height=h, fps=round(float(num) / float(den), 3))
        elif s["codec_type"] == "audio":
            info["has_audio"] = True
    return info


def run(cmd: list[str], quiet: bool = True, cwd: Path | None = None) -> None:
    if not quiet:
        print("+", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=quiet, text=True, cwd=cwd)
    if r.returncode != 0:
        if quiet:
            sys.stderr.write((r.stderr or "")[-4000:])
        die(f"command failed: {cmd[0]} (exit {r.returncode})")


def ffmpeg(*args: str, cwd: Path | None = None) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], cwd=cwd)


def require(tool: str) -> None:
    if not shutil.which(tool):
        die(f"'{tool}' is not installed - run ./setup.sh")


def fmt_time(t: float) -> str:
    m, s = divmod(max(t, 0.0), 60)
    return f"{int(m):02d}:{s:05.2f}"


# Video encode settings shared by every stage so intermediate files stay consistent.
VENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
AENC = ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
ENCODE = VENC + AENC
