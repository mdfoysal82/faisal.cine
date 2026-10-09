---
name: intake
description: Step 1 of the video pipeline - copy a raw clip into projects/<job>/raw/ and create the job (format, language, target size). Use when starting a new video job.
---

# Intake

```bash
python3 tools/intake.py "/path/to/raw clip.mov" --job <job> --format <short-explainer|short-tiktok|youtube> [--language bn]
```

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
