---
name: edit-video
description: Edit a raw video end to end with the 7-step pipeline (intake, rough cut, graphics, second pass, captions, background music, export). Use when the user wants to edit a video, gives a clip to edit, or says "ভিডিও এডিট", "edit this video", "make a short/reel/TikTok/YouTube video from this clip".
---

# Edit video - the whole pipeline

Same 7 steps for every job, from raw clip to `outputs/<job>.final.mp4`. Each step has its own
skill; this one runs them in order and keeps the user in the loop.

**Talk to the user in Bangla.** Ask every question with AskUserQuestion (dropdown, 2-4 options,
recommended first). Never ask more than you need; use the defaults below when obvious.

## 0. Kick-off (one AskUserQuestion call)

Ask what you do not already know:
1. Format: `short-explainer` (Short: explainer) / `short-tiktok` (TikTok / raw) / `youtube` (Long-form).
2. Job name (offer a slug made from the file or folder name).
   The user may give one clip, several clips or a folder of clips - all are fine (see `intake`).
3. Background music: none / pick from `music/` (run `python3 tools/music.py <job> --list` after intake).
4. Thumbnail: follow the format default (youtube always, shorts skip) unless they say otherwise.

## Steps

1. **Intake** -> skill `intake`.
2. **Rough cut** -> skill `rough-cut`. Stop for approval of the cut list. Then render and show
   `work/script.md` + a few frames.
3. **Graphics** -> skill `graphics-plan`. Plan the beats from `work/transcript.json`, show the
   plan as a short Bangla table, get a yes, then build.
4. **Second pass** -> skill `second-pass`. Ask the user to watch the current video and give
   notes; apply them with incremental re-composites until they are happy.
5. **Captions** -> skill `captions` (shorts only; youtube gets an `.srt` at export).
6. **Background music** -> skill `background-music` (optional).
7. **Export** -> skill `finalize`. Report the SHIP block. Offer `prune` once they confirm the
   output is good.

Off-ramps, offer when relevant:
- `to-premiere` if they want to finish in Premiere Pro (can happen right after step 2 or 3).
- `thumbnail-generator` for youtube jobs (and shorts if asked).

## Status line

After each step, tell the user in one Bangla line what was done and what is next, e.g.
`✅ ধাপ ২: Rough cut শেষ (2:41 -> 1:58)। এবার graphics plan করব।`

If a step fails, read the error, fix what you can (missing tool -> `./setup.sh`), and only then
ask the user.
