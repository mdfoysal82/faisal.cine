---
name: rough-cut
description: Step 2 of the video pipeline - transcribe (word timings), remove fillers, stutters, retakes and long pauses, polish the audio and produce the script. The cut list must be approved by the user before rendering. Use after intake, or when the user asks to cut/tighten a clip.
---

# Rough cut

Three commands: transcribe -> plan cut list -> (user approves) -> render.

## 1. Transcribe

```bash
python3 tools/transcribe.py <job>                       # whisper.cpp large-v3 via HyperFrames, Metal on Mac
python3 tools/transcribe.py <job> --engine whisperx     # WhisperX + wav2vec2 alignment (if installed)
python3 tools/transcribe.py <job> --engine import --file subs.srt   # existing transcript
```

First run downloads the model (large-v3 ~3 GB). For a quick draft use `--model small`.
Writes `work/transcript.raw.json` (raw timeline). Read it.

## 2. Plan the cut list

```bash
python3 tools/cutlist.py plan <job>
```

Auto rules (`presets/cut-rules.json`): filler words (um/uh, উম/আ/এ ...), stutters (repeated word),
pauses longer than `max_pause` shrink to `keep_pause`, lead-in and tail silence.
`maybe-filler` rows (like, মানে, আসলে ...) are listed but OFF.

Then do the editor's job the rules cannot: read the transcript and find
- **retakes / false starts** - the speaker says a sentence, stops, says it again. Keep the
  LAST good take; cut the earlier one(s): `python3 tools/cutlist.py cut <job> START END --reason retake`
- off-topic chatter, "ওয়েট, আবার করি", "cut this part" instructions to the editor
- words wrongly flagged: `python3 tools/cutlist.py toggle <job> <id> ...`
- a range that must stay: `python3 tools/cutlist.py keep <job> START END`

Times are raw-timeline seconds from `transcript.raw.json`. Whisper often drops fillers from
the text; they then show up as pauses and are still cut.

## 3. Approval (required)

Show the user `work/cutlist.md` (it is in Bangla: original -> new length, every cut with
context). Summarize the retakes you added. Ask with AskUserQuestion:
- `হ্যাঁ, render করুন (Recommended)` / `কিছু পরিবর্তন করতে চাই` / `maybe-filler গুলোও কাটুন`

Apply their changes, re-show, and only when they say yes:

```bash
python3 tools/cutlist.py approve <job>
python3 tools/apply_cut.py <job>          # --no-polish to skip audio cleanup
```

## Output

- `work/roughcut.mp4` - cut, reframed to the format size, audio polished (high-pass, light
  denoise, de-ess, compression, -16 LUFS)
- `work/transcript.json` - words on the CUT timeline with `caption-corrections.json` applied
- `work/script.md` - the script, sentence per line with timestamps; show it to the user
- `work/transcript.srt`, `work/timeline.json`

Check a couple of joins by looking at frames and tell the user the path to play the video.
If brand names came out wrong (e.g. "ক্লড"), add them to `presets/caption-corrections.json`
and re-run `apply_cut.py` (segments are cached, it is fast).
