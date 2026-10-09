---
name: thumbnail-generator
description: Make a YouTube thumbnail for a job - pick a strong frame from the video, then design it in Canva (title text, brand colors) and save it to outputs/. Falls back to a HyperFrames HTML thumbnail when Canva is not connected. Always for youtube jobs; for shorts only on request.
---

# Thumbnail generator

## 1. Candidate frames

```bash
python3 tools/thumbnail.py frames <job> [--count 8]
```

Look at `work/thumbs/sheet.jpg` (numbered contact sheet). Pick the 2-3 best frames: clear face,
strong expression, eyes open, not mid-blink/mid-word. Ask the user with AskUserQuestion
(Bangla), options = your picks, e.g. `ফ্রেম ৩ - হাসিমুখ (Recommended)`.

## 2. Title

Propose 2-3 thumbnail titles (2-5 words, Bangla or mixed, curiosity/benefit, NOT the video
title repeated). Ask the user to pick.

## 3. Design in Canva (preferred)

Use the Canva connector tools (load them with ToolSearch, query "canva"):
1. Upload the chosen frame `work/thumbs/cand-XX.jpg`: if `create-upload-url` is available,
   request an upload URL and PUT the file to it with curl; otherwise `upload-asset-from-url`
   needs a public URL - ask the user to drag the frame into Canva instead.
2. Create the design with `generate-design` (or `create-design`, type YouTube thumbnail,
   1280x720) using the frame as background, the title in large bold text (Anek Bangla or
   Hind Siliguri if available in their Canva fonts), left-aligned with a dark gradient for
   contrast, accent color from `presets/signature-style.json`. If they have a brand kit
   (`list-brand-kits`), use it.
3. Show the user the design link, iterate on their notes, then `export-design` as PNG and save
   it to `outputs/<job>.thumbnail.png`.

## Fallback (no Canva)

```bash
python3 tools/thumbnail.py html <job> --frame 3 --title "শিরোনাম" [--accent 0]
```

Renders a 1280x720 design with HyperFrames -> `outputs/<job>.thumbnail.png`. Look at it before
showing the user.
