---
name: second-pass
description: Step 4 of the video pipeline - manual review round. Ask the user for notes on the current cut, apply them (cut changes, card text/timing, zooms, captions fixes) and re-composite incrementally. Use after graphics, or whenever the user gives feedback on a rendered video.
---

# Second pass (manual review)

1. Tell the user which file to watch (the newest of `work/music.mp4`, `captioned.mp4`,
   `graphics.mp4`, `roughcut.mp4`) and ask with AskUserQuestion (Bangla):
   - `সব ঠিক আছে, পরের ধাপে যান (Recommended)`
   - `কাটায় পরিবর্তন` (cut changes)
   - `গ্রাফিক্সে পরিবর্তন` (graphics changes)
   - `লেখা/বানান ঠিক করুন` (text fixes)
   Then collect the specific notes (they can type in "Other"). Notes usually reference times in
   the video they watched = the CUT timeline.

2. Apply each note at its source:

| note | edit | rebuild from |
|---|---|---|
| cut more / restore a part | `tools/cutlist.py cut/keep/toggle` (RAW times: map cut-time -> raw with `work/timeline.json`: walk `keeps` adding `durations`) | `rough-cut` |
| card text / timing / new card / zoom | `work/graphics-plan.json` | `graphics` |
| a misspelled word | `work/transcript.json` (one-off) or `presets/caption-corrections.json` (recurring, then rebuild from `rough-cut`) | `captions` |
| music too loud / different track | `tools/music.py ... --bed -33` | `music` |

   A cut change shifts everything after it - after a rough-cut rebuild, re-time the graphics
   plan and check it against the new `work/transcript.json`.

3. Rebuild only what changed - cached segments and cards are reused:

```bash
python3 tools/rebuild.py <job> --from <rough-cut|graphics|captions|music>
```

4. Show frames of the changed spots, then repeat from 1 until the user picks "সব ঠিক আছে".
Keep a short log of what changed in `projects/<job>/review.md`.
