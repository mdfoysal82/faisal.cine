---
name: to-premiere
description: Off-ramp from the video pipeline - export the rough cut (plus graphic cards and music) as a Premiere Pro XML timeline so the user can finish the edit in Premiere. Use when the user mentions Premiere, wants to finish manually, or wants an editable timeline.
---

# To Premiere (alternate path)

```bash
python3 tools/to_premiere.py <job>    # -> outputs/<job>.premiere.xml
```

Needs a rendered rough cut (`work/timeline.json`). The XML (FCP7 xmeml, which Premiere imports)
references the RAW clip at full quality:

- V1 / A1 - every kept range, in order, scaled to fill the format frame (Basic Motion scale)
- V2 - rendered graphic cards (transparent ProRes 4444) at their times, if graphics ran
- A2 - the chosen background track, if music ran (un-ducked: duck it in Premiere)

Tell the user (Bangla): Premiere -> File -> Import -> `outputs/<job>.premiere.xml`. Files are
linked by absolute path, so import on the same Mac and do not prune the job first. Captions are
not in the XML: import `work/transcript.srt` as a caption track if needed. Reframing (crop
position) may need a touch in Premiere for 16:9 -> 9:16 jobs.
