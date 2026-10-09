# Claude Video Editor

This folder (`video-editor/` inside the faisal.cine repo) is self-contained: start Claude Code
from here so `.claude/skills/` and this file load. All paths below are relative to this folder.

A 7-step pipeline that turns a raw clip into `outputs/<job>.final.mp4`. Claude runs the steps
with the skills in `.claude/skills/`; the heavy lifting is in `tools/` (Python 3 stdlib + ffmpeg)
and the vendored HyperFrames engine (HTML -> video).

## House rules

- **Talk to the user in Bangla (বাংলা).** Every question goes through the AskUserQuestion tool
  as a dropdown with 2-4 concrete options (recommended option first, marked "(Recommended)").
  Code, file names and commit messages stay in English.
- **Never render the rough cut before the user approves the cut list** (`work/cutlist.md`).
- Show the user what you made before moving on: frame grabs (`ffmpeg -ss T -i X -frames:v 1 ...`)
  you can look at with Read, and the path of the video so they can play it.
- The vendored HyperFrames skills (`hyperframes*`, `talking-head-recut`, `embedded-captions`,
  `media-use`, `motion-graphics`) are read-only. Do not edit them and do not run
  `npx hyperframes skills update` even though those skills suggest it. Update only with
  `tools/update_vendor.sh [<ref>]`, which re-pins `skills-lock.json`.
- The HyperFrames CLI version is pinned in `skills-lock.json` (`cli`); tools call
  `npx -y hyperframes@<that version>`. Render telemetry is off (`HYPERFRAMES_NO_TELEMETRY=1`).

## The pipeline (entry skill: `/edit-video`)

| # | Step | Skill | Tool | Output |
|---|------|-------|------|--------|
| 1 | Intake | `intake` | `tools/intake.py` | `projects/<job>/raw/`, `job.json` |
| 2 | Rough cut | `rough-cut` | `transcribe.py`, `cutlist.py`, `apply_cut.py` | `work/roughcut.mp4`, `script.md` |
| 3 | Graphics | `graphics-plan` | `tools/graphics.py` | `work/graphics.mp4` |
| 4 | Second pass | `second-pass` | `tools/rebuild.py` | updated stage videos |
| 5 | Captions | `captions` | `tools/captions.py` | `work/captioned.mp4` |
| 6 | Music (optional) | `background-music` | `tools/music.py` | `work/music.mp4` |
| 7 | Export | `finalize` | `./finalize.sh`, `./prune.sh` | `outputs/<job>.final.mp4` |

Off-ramp: `to-premiere` (`tools/to_premiere.py`) -> Premiere Pro XML. Thumbnails:
`thumbnail-generator` (Canva, HTML fallback).

## Formats (only steps 3 and 5 change)

| | short-explainer | short-tiktok | youtube |
|---|---|---|---|
| Frame | 9:16 1080x1920 | 9:16 1080x1920 | 16:9 1920x1080 |
| Graphics | top-half cards (`signature-style`) | hook card on raw (`tiktok-raw-style`) | glass + zoom (`liquid-glass-style`) |
| Captions | centered, locked, word highlight (`captions-style`) | low under face, pop (`tiktok-raw-style`) | none burned in; `.srt` sidecar |
| Thumbnail | usually skip | skip | always |

## Layout

```
presets/            formats.json, *-style.json, cut-rules.json, caption-corrections.json
tools/              pipeline scripts (run from the repo root: python3 tools/<x>.py)
assets/fonts        Hind Siliguri, Anek Bangla, Noto Sans Bengali (OFL)
assets/vendor       gsap.min.js for HyperFrames pages
music/              the user's background tracks (git-ignored)
projects/<job>/     raw/, work/, job.json (git-ignored)
outputs/            final deliverables (git-ignored)
tests/              make_fixture.py + run_pipeline.sh (synthetic end-to-end test)
```

Times in `cutlist.json` are on the **raw** timeline; times in `transcript.json`,
`graphics-plan.json` and captions are on the **cut** timeline.

Language: speech is usually mixed Bangla + English. Transcribe with `--language bn` and
`large-v3`; English words may come back in Bangla script - fix recurring ones in
`presets/caption-corrections.json`, one-offs directly in `work/transcript.json`.
