---
name: background-music
description: Step 6 (optional) of the video pipeline - put a background track from music/ under the voice with sidechain ducking and re-normalize loudness. Use when the user wants background music.
---

# Background music (optional)

```bash
python3 tools/music.py <job> --list                       # tracks in music/
python3 tools/music.py <job> --track music/<file> [--bed -30] [--duck 8]
python3 tools/music.py <job> --off
```

- Ask which track with AskUserQuestion (Bangla), listing up to 4 tracks from `--list` that fit
  the video's mood (read `work/script.md`). If `music/` is empty, tell the user to drop
  royalty-free tracks there (`music/` is git-ignored) and skip this step.
- The track loops to the video length, fades in 1 s / out 2.5 s, is loudness-matched to
  `--bed` LUFS, ducked under the voice (sidechain compression, `--duck` ratio) and the mix is
  re-normalized to the format target (-14 LUFS).
- Too loud -> `--bed -33` or `-36`; too quiet -> `--bed -27`. Pumping -> lower `--duck` (5).
- Only use music the user owns or has a license for.
