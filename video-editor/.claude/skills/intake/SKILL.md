---
name: intake
description: Step 1 of the video pipeline - copy a raw clip, several clips, or a folder of clips into projects/<job>/raw/ (joined in order) and create the job (format, language, target size). Use when starting a new video job.
---

# Intake

```bash
python3 tools/intake.py "/path/to/raw clip.mov" --job <job> --format <short-explainer|short-tiktok|youtube> [--language bn]
python3 tools/intake.py clip1.mov clip2.mov clip3.mov --job <job> --format <fmt>   # several clips
python3 tools/intake.py "/path/to/folder" --job <job> --format <fmt>               # every video in a folder
```

## Several clips

Raw footage often comes as many short clips. Give them all (or the folder) in one call; they
are joined into `raw/combined.mov` in natural file-name order (IMG_2 before IMG_10).
- Before joining, list the clips in the order they will be joined and confirm with the user
  (Bangla dropdown: `এই ক্রমেই ঠিক আছে (Recommended)` / `রেকর্ড করার সময় অনুযায়ী সাজাও` /
  `আমি ক্রম বলে দেব`). `--order time` sorts by file time, `--order given` keeps the order you pass.
- Clips are scaled/padded to the FIRST clip's frame size and fps; silent clips get silence.
- `job.json` -> `clips` records where each clip starts/ends on the raw timeline, so you can
  tell the user "clip 3 (IMG_0457)" when discussing cuts. Repeated takes across clips are
  normal - the rough-cut retake pass keeps the best one.

- Copies (never moves) the clip into `projects/<job>/raw/`, probes it, writes `projects/<job>/job.json`.
- `--language` is the spoken language for transcription: `bn` (default, also right for mixed
  Bangla + English), `en`, or `auto`.
- Existing job with the same name: ask the user (Bangla dropdown: নতুন নাম / পুরনোটা মুছে ফেলুন)
  before passing `--force`.

## Reframe

`job.json` -> `"reframe": {"x": 0.5, "y": 0.5}` is the focus point used when the raw aspect
differs from the format (e.g. 16:9 footage into a 9:16 short: crop around x). If the speaker
is not centered, grab a frame, look at it, and set `x` (0 = left edge, 1 = right edge) before
the rough cut renders:

```bash
ffmpeg -v error -ss 3 -i projects/<job>/raw/<file> -frames:v 1 -vf scale=960:-2 /tmp/frame.jpg
```

Taller-than-target footage (9:16 into 16:9) gets a blurred fill background automatically.
