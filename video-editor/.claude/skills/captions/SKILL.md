---
name: captions
description: Step 5 of the video pipeline - burn on-beat word captions into short-form videos using the locked caption presets (centered highlight for explainers, low pop captions for TikTok). Long-form YouTube gets an SRT sidecar instead. Use after graphics/second pass, or when the user asks for subtitles on a short.
---

# Captions (short-form only)

```bash
python3 tools/captions.py <job>                         # style from the format
python3 tools/captions.py <job> --style tiktok-raw-style   # override
python3 tools/captions.py <job> --off                   # none
```

| format | preset | look |
|---|---|---|
| short-explainer | `captions-style` | centered at 62% height (below the top-half cards), max 2 lines, active word in yellow, on the beat |
| short-tiktok | `tiktok-raw-style` | low under the face (70%), 1-3 word chunks that pop in |
| youtube | none | no burn-in; `finalize` ships `outputs/<job>.srt` for YouTube CC |

The presets are LOCKED - do not tweak sizes/colors per video. If the user wants a different
look, change the preset file once (ask first) so every future video matches.

Before burning, scan `work/transcript.json` for ASR mistakes (brand names, English words
written in Bangla script, numbers). Fix one-offs in place (keep `start`/`end`); recurring ones
go into `presets/caption-corrections.json` (then `tools/rebuild.py <job> --from rough-cut`).

Check 2-3 frames (`ffmpeg -ss T -i work/captioned.mp4 -frames:v 1 ...`) - captions must not
cover a graphic card or the speaker's mouth. Bangla text is shaped by libass (HarfBuzz) with
the bundled Hind Siliguri font.

For cinematic/embedded VFX captions (text behind the subject), the vendored
`embedded-captions` skill can do it, but it is a separate, heavier workflow - only on request.
