---
name: finalize
description: Step 7 of the video pipeline - export. Promote the latest stage to outputs/<job>.final.mp4 with two-pass loudness normalization and a spec check; prune intermediates afterwards. Use when the user is happy with the video, or asks to export/ship/prune.
---

# Export: finalize / prune

```bash
./finalize.sh <job>
```

- Picks the newest enabled stage (music > captioned > graphics > roughcut), refuses if a later
  stage is older than an earlier one (then run `python3 tools/rebuild.py <job> --from <step>`).
- Two-pass loudnorm to -14 LUFS / -1 dBTP, video stream copied (no quality loss).
- youtube jobs also get `outputs/<job>.srt` for closed captions.
- Prints a SHIP block: size, fps, duration, loudness. Relay it to the user in Bangla with the
  output path.

## Prune (after the user confirms the final is good)

Ask first (AskUserQuestion, Bangla): `intermediate ফাইল মুছুন (Recommended)` / `raw ফুটেজও মুছুন` / `কিছু মুছবেন না`.

```bash
./prune.sh <job>              # segments, card renders, stage videos, extracted audio
./prune.sh <job> --raw --yes  # also the raw/ copy - only if the user explicitly chose it
```

Plans, cut list, transcripts and script stay, so the job can be rebuilt later.
