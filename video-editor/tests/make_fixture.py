#!/usr/bin/env python3
"""Build a synthetic test clip with known word timings (needs espeak-ng + ffmpeg).

  python3 tests/make_fixture.py <out-dir>

Writes <out-dir>/fixture.mp4 (1920x1080, mixed Bangla/English speech with fillers,
a stutter and long pauses) and <out-dir>/fixture.words.json (exact word timings), so the
whole pipeline can be exercised without a Whisper model.
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

# (text, voice, pause_after_seconds)
SCRIPT = [
    ("আসসালামু", "bn", 0.05), ("আলাইকুম।", "bn", 0.6),
    ("আজকে", "bn", 0.05), ("আমি", "bn", 0.05), ("আপনাদের", "bn", 0.05), ("দেখাব", "bn", 0.3),
    ("উম", "bn", 0.3),
    ("কিভাবে", "bn", 0.05), ("ক্লড", "bn", 0.05), ("দিয়ে", "bn", 0.05), ("ভিডিও", "bn", 0.05),
    ("এডিট", "bn", 0.05), ("করতে", "bn", 0.05), ("হয়।", "bn", 1.6),
    ("This", "en", 0.04), ("is", "en", 0.04), ("really", "en", 0.04), ("simple.", "en", 0.4),
    ("uh", "en", 0.25),
    ("প্রথমে", "bn", 0.05), ("আমরা", "bn", 0.05), ("আমরা", "bn", 0.05), ("ভিডিওটা", "bn", 0.05),
    ("কাটব।", "bn", 1.2),
    ("তারপর", "bn", 0.05), ("ক্যাপশন", "bn", 0.05), ("যোগ", "bn", 0.05), ("করব।", "bn", 0.5),
    ("Ninety", "en", 0.04), ("percent", "en", 0.04), ("faster!", "en", 0.8),
]
RATE = 22050


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "fixture")
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "words"
    tmp.mkdir(exist_ok=True)
    pcm, words, t = bytearray(), [], 0.6
    pcm += bytes(int(RATE * t) * 2)
    for i, (text, voice, pause) in enumerate(SCRIPT):
        wav = tmp / f"{i:02d}.wav"
        subprocess.run(["espeak-ng", "-v", voice, "-s", "150", "-w", str(wav), text.strip("।.!")], check=True)
        with wave.open(str(wav)) as w:
            assert w.getframerate() == RATE
            data = w.readframes(w.getnframes())
        # espeak pads ~ silence at both ends; trim samples below a small threshold
        samples = memoryview(data).cast("h")
        nz = [k for k in range(len(samples)) if abs(samples[k]) > 300]
        a, b = (nz[0], nz[-1] + 1) if nz else (0, len(samples))
        chunk = data[a * 2:b * 2]
        dur = len(chunk) / 2 / RATE
        words.append({"text": text, "start": round(t, 3), "end": round(t + dur, 3)})
        pcm += chunk + bytes(int(RATE * pause) * 2)
        t += dur + pause
    pcm += bytes(int(RATE * 0.8) * 2)
    total = len(pcm) / 2 / RATE
    audio = out / "fixture.wav"
    with wave.open(str(audio), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(pcm))
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=1920x1080:r=30:d={total:.3f}",
        "-i", str(audio), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
        str(out / "fixture.mp4")], check=True)
    (out / "fixture.words.json").write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"fixture ok: {out / 'fixture.mp4'} ({total:.1f}s, {len(words)} words)")


if __name__ == "__main__":
    main()
