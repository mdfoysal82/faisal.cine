# Claude Video Editor

Claude Code দিয়ে ভিডিও এডিট করার একটা pipeline। Raw ক্লিপ থেকে শুরু করে
`outputs/<job>.final.mp4` পর্যন্ত, প্রতিবার একই ৭টা ধাপে।

```
1 Intake → 2 Rough cut → 3 Graphics → 4 Second pass → 5 Captions → 6 Music → 7 Export
                 └─ off-ramp: Premiere Pro XML                       thumbnail: Canva
```

| ধাপ | কী হয় |
|---|---|
| 1. Intake | raw ক্লিপ `projects/<job>/raw/`-এ কপি হয় |
| 2. Rough cut | Whisper দিয়ে word-level transcript তৈরি হয়। ফিলার (um, উম...), তোতলানো, retake আর লম্বা বিরতি কাটা হয়। আপনি cut list অনুমোদন করলে render হয়। অডিও পরিষ্কার করা হয় আর script তৈরি হয়। |
| 3. Graphics | Transcript পড়ে কোথায় কোন card বসবে তার plan করা হয়। তারপর HyperFrames দিয়ে card বানানো হয় আর zoom যোগ হয়। |
| 4. Second pass | আপনার মতামত নিয়ে শুধু বদলানো অংশটুকু আবার render হয় |
| 5. Captions | শুধু short ভিডিওতে: যে শব্দ বলা হচ্ছে সেটা highlight হয় (বাংলা font সহ)। YouTube-এর জন্য `.srt` ফাইল দেওয়া হয়। |
| 6. Music | `music/` ফোল্ডার থেকে গান নেওয়া হয়। কথা বলার সময় গানের আওয়াজ নিজে থেকে কমে যায় (sidechain duck)। |
| 7. Export | -14 LUFS loudness ঠিক করে `outputs/<job>.final.mp4` তৈরি হয় |

তিনটা format আছে: `short-explainer` (9:16), `short-tiktok` (9:16), `youtube` (16:9)।
Format বদলালে শুধু ধাপ ৩ (graphics) আর ধাপ ৫ (captions) বদলায়।

## Setup (Mac, একবারই করতে হবে)

```bash
git clone https://github.com/mdfoysal82/faisal.cine.git && cd faisal.cine/video-editor
./setup.sh                 # ffmpeg, Node 22+, Python 3 আর HyperFrames ঠিক আছে কিনা দেখে
./setup.sh --whisperx      # (ঐচ্ছিক) WhisperX ইঞ্জিন
```

Homebrew আগে থেকে ইনস্টল থাকতে হবে (https://brew.sh)। Caption-এর জন্য libass লাগে,
তাই setup নিজে থেকে `ffmpeg-full` install করে নেয়, কারণ Homebrew-এর সাধারণ `ffmpeg`-এ এটা নেই।
Claude Code install করা না থাকলে: `curl -fsSL https://claude.ai/install.sh | bash`, তারপর
নতুন Terminal window খুলুন। প্রথমবার transcription চালালে
Whisper large-v3 model (~3 GB) ডাউনলোড হবে।

## ব্যবহার

`video-editor` ফোল্ডারের ভেতর থেকে Claude Code চালু করুন (`cd faisal.cine/video-editor && claude`), তাহলে skill-গুলো লোড হবে। তারপর লিখুন:

```
ভিডিও এডিট করো ~/Movies/raw/my-clip.mov
```

অথবা `/edit-video` লিখুন। Claude সব প্রশ্ন বাংলায় dropdown আকারে করবে, আর প্রতিটা ধাপ
শেষ হলে আপনাকে দেখিয়ে নেবে।

## ফোল্ডার

```
.claude/skills/   pipeline skills (edit-video, intake, rough-cut, graphics-plan, second-pass,
                  captions, background-music, finalize, to-premiere, thumbnail-generator)
                  + vendored HyperFrames skills (হাতে বদলাবেন না)
tools/            Python/ffmpeg scripts
presets/          locked styles: signature, captions, tiktok-raw, liquid-glass,
                  caption-corrections.json (ব্র্যান্ড নাম/বানান ঠিক করার তালিকা), cut-rules.json
assets/fonts/     Hind Siliguri, Anek Bangla, Noto Sans Bengali (SIL OFL)
music/            আপনার background গান (git-এ যায় না)
projects/<job>/   প্রতিটা কাজের raw/ আর work/ ফাইল (git-এ যায় না)
outputs/          final ভিডিও, .srt, Premiere XML, thumbnail
```

## HyperFrames আপডেট

HyperFrames engine `skills-lock.json`-এ একটা নির্দিষ্ট commit আর CLI version-এ বাঁধা আছে।
আপডেট করতে:

```bash
tools/update_vendor.sh <new-commit-or-tag>   # তারপর skills-lock.json-এ "cli" version বদলান
```

## Test

```bash
tests/run_pipeline.sh short-explainer   # কৃত্রিম ক্লিপে পুরো pipeline চালায় (espeak-ng লাগবে)
```

## Credits

- [HyperFrames](https://github.com/heygen-com/hyperframes) (Apache-2.0). Vendored skills আছে `.claude/skills/`-এ, license: `.claude/skills/HYPERFRAMES-LICENSE`
- GSAP (`assets/vendor/gsap.min.js`). GreenSock standard license অনুযায়ী বিনামূল্যে ব্যবহার করা যায়।
- Hind Siliguri, Anek Bangla, Noto Sans Bengali: SIL Open Font License (`assets/fonts/OFL-*.txt`)
