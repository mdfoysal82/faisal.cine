#!/usr/bin/env python3
"""Step 6 - Background music (optional): bed a track under the voice with sidechain
ducking, then re-normalize -> work/music.mp4

  python3 tools/music.py <job> --list                 # tracks available in music/
  python3 tools/music.py <job> --track music/calm.mp3 [--bed -30] [--duck 8]
  python3 tools/music.py <job> --off

The track loops to the video length, fades in/out, is ducked whenever the voice speaks
(sidechain compression), and the mix is loudness-normalized to the format target.
"""
import argparse
from pathlib import Path

from common import AENC, MUSIC, Job, die, ffmpeg, require

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".aiff", ".aif"}


def tracks() -> list[Path]:
    return sorted(p for p in MUSIC.rglob("*") if p.suffix.lower() in AUDIO_EXT)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--track", type=Path)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--bed", type=float, default=-30.0, help="music loudness before ducking, LUFS (default -30)")
    ap.add_argument("--duck", type=float, default=8.0, help="how hard the voice ducks the music (ratio, default 8)")
    ap.add_argument("--off", action="store_true")
    a = ap.parse_args()

    require("ffmpeg")
    job = Job(a.job)
    if a.list:
        found = tracks()
        print("\n".join(str(p.relative_to(MUSIC.parent)) for p in found) or "music/ is empty - add tracks first")
        return
    if a.off:
        job.w("music.mp4").unlink(missing_ok=True)
        job.mark("music", disabled=True)
        print("music off for this job")
        return
    if not a.track:
        die("pick a track with --track (see --list)")
    track = a.track if a.track.is_absolute() else (MUSIC.parent / a.track)
    if not track.exists():
        die(f"track not found: {a.track}")

    src = job.stage_input("music")
    dur = float(job.meta["steps"]["rough-cut"]["duration"])
    target = job.format.get("loudness_lufs", -14)
    graph = (
        "[0:a]asplit=2[voice][sc];"
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
        f"loudnorm=I={a.bed}:TP=-3:LRA=11,afade=t=in:d=1.0,afade=t=out:st={max(0, dur - 2.5):.3f}:d=2.5[bed];"
        f"[bed][sc]sidechaincompress=threshold=0.015:ratio={a.duck}:attack=25:release=450:makeup=1[duck];"
        "[voice][duck]amix=inputs=2:normalize=0:duration=first,"
        f"loudnorm=I={target}:TP=-1.5:LRA=11,aresample=48000[a]"
    )
    out = job.w("music.mp4")
    ffmpeg("-i", str(src), "-stream_loop", "-1", "-i", str(track), "-filter_complex", graph,
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AENC, "-t", f"{dur:.3f}", str(out))
    job.mark("music", track=str(track.relative_to(MUSIC.parent)) if MUSIC.parent in track.parents else str(track),
             bed=a.bed, duck=a.duck, input=src.name)
    print(f"music ok: {out}")


if __name__ == "__main__":
    main()
