---
name: graphics-plan
description: Step 3 of the video pipeline - plan the graphic beats from the transcript, then build them with HyperFrames (cards, hook, lower thirds, stats, lists, glass panels, punch-in zooms) and composite over the rough cut. Use after the rough cut or when the user asks for on-screen graphics.
---

# Graphics: plan the beats, then build

Style and layout come from the format (`presets/formats.json`):

| format | style preset | what to plan |
|---|---|---|
| short-explainer | `signature-style` | cards in the TOP half (captions sit below at 62%). title / point / list / stat / quote |
| short-tiktok | `tiktok-raw-style` | ONE `hook` card over the first 2-4 s (the scroll-stopper). Maybe one stat/payoff card. Keep it raw. |
| youtube | `liquid-glass-style` | `lower-third` for names/topics, `side` cards for lists/stats, `zooms` for emphasis |

## 1. Plan

Read `work/transcript.json` and `work/script.md` (cut-timeline seconds). Pick beats where a
visual helps: the hook/promise, each key point, numbers, lists, the payoff. Pacing guide:
shorts ~1 card per 6-10 s, youtube ~1 per 15-30 s plus a zoom every 20-40 s on emphasis.
Card text is SHORT (title <= 6-7 words) in the language spoken (Bangla, English terms as
spoken). Start a card ~0.2 s before the words, hold it >= 1.5 s.

Write `work/graphics-plan.json`:

```json
{
  "cards": [
    {"id": "c01", "start": 0.2, "end": 3.0, "kind": "title", "kicker": "পর্ব ১", "title": "...", "accent": 0},
    {"id": "c02", "start": 4.0, "end": 9.0, "kind": "list", "title": "...", "items": ["...", "..."]},
    {"id": "c03", "start": 12.0, "end": 14.5, "kind": "stat", "stat": "90%", "title": "..."},
    {"id": "c04", "start": 20.0, "end": 24.0, "kind": "lower-third", "title": "Faisal Cine", "body": "..."}
  ],
  "zooms": [{"start": 30.0, "end": 34.0, "scale": 1.15, "x": 0.5, "y": 0.4}]
}
```

- kinds: `title`, `point` (title + body), `list`, `stat`, `quote`, `hook`, `lower-third`, `custom`
- optional `"zone"`: `top` | `center` | `lower-third` | `side`; `"accent"`: 0-4 (style palette)
- zoom `x`/`y`: focus point 0-1 (look at a frame to aim at the face); `scale` 1.08-1.25
- cards must not overlap in time unless they use different zones

Show the plan to the user as a short Bangla table (সময় | কার্ড | লেখা) and ask with
AskUserQuestion: `ঠিক আছে, বানান (Recommended)` / `কিছু বদলাতে চাই` / `graphics লাগবে না`.

## 2. Build

```bash
python3 tools/graphics.py <job> --preview c02     # PNG still of one card - look at it first
python3 tools/graphics.py <job>                   # render all cards + composite -> work/graphics.mp4
```

Each card renders alone with HyperFrames to a transparent MOV, cached by content hash; the
composite overlays them (glass styles also blur the footage under each card) and applies the
zooms. Look at 2-3 frames of `work/graphics.mp4` before showing the user.

`python3 tools/graphics.py <job> --off` = no graphics for this job.

## Custom cards (anything the templates can't do)

`"kind": "custom"` takes your own `"html"` (inner markup, put it in a `.panel` or your own
classes), optional `"css"` and `"js"` (extra GSAP tweens added to `tl`; e.g.
`tl.from('.x', {scale: 0, duration: .4}, .3)`). The page follows the HyperFrames composition
contract - read the vendored `hyperframes-core` and `hyperframes-animation` skills before
writing one (no `Math.random`, no clocks, animate children not the `.clip`, fonts available:
Hind Siliguri, Anek Bangla). For full designed overlay packages the vendored
`talking-head-recut` skill has a deep card-design guide; reuse its ideas here, but keep the
output in `graphics-plan.json` so second-pass incremental renders keep working.
