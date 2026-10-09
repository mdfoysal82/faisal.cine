#!/usr/bin/env python3
"""Off-ramp: export the rough cut as a Premiere Pro timeline (FCP7 XML / xmeml).

  python3 tools/to_premiere.py <job>    -> outputs/<job>.premiere.xml

Premiere: File > Import > the .xml. The sequence has
  V1/A1  the kept ranges of the RAW clip (full quality, re-editable handles)
  V2     the rendered graphic cards (transparent ProRes 4444), if any
  A2     the background music track, if one was chosen
Captions are not included (bring outputs/<job>.srt in as a caption track if needed).
"""
import argparse
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from common import MUSIC, OUTPUTS, Job, die, probe, read_json


def file_el(fid: str, path: Path, fps: int, info: dict | None, audio: bool) -> str:
    dur = round((info or probe(path))["duration"] * fps)
    media = ""
    if info and info.get("width"):
        media += (f"<video><samplecharacteristics><width>{info['width']}</width>"
                  f"<height>{info['height']}</height></samplecharacteristics></video>")
    if audio:
        media += "<audio><channelcount>2</channelcount></audio>"
    return (f"<file id=\"{fid}\"><name>{escape(path.name)}</name>"
            f"<pathurl>file://{quote(str(path.resolve()))}</pathurl>"
            f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate><duration>{dur}</duration>"
            f"<media>{media}</media></file>")


def clip(cid: str, kind: str, name: str, fid: str, file_xml: str, start: int, end: int,
         in_: int, out: int, fps: int, extra: str = "") -> str:
    return (f"<clipitem id=\"{cid}\"><name>{escape(name)}</name><enabled>TRUE</enabled>"
            f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"
            f"<start>{start}</start><end>{end}</end><in>{in_}</in><out>{out}</out>"
            f"{file_xml}{extra}</clipitem>")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    a = ap.parse_args()

    job = Job(a.job)
    if not job.w("timeline.json").exists():
        die("render the rough cut first (tools/apply_cut.py)")
    tl = read_json(job.w("timeline.json"))
    t = job.meta["target"]
    fps = int(round(t["fps"]))
    src_info = job.meta["source_info"]
    scale = max(t["width"] / src_info["width"], t["height"] / src_info["height"]) * 100
    motion = ("<filter><effect><name>Basic Motion</name><effectid>basic</effectid><effecttype>motion</effecttype>"
              "<mediatype>video</mediatype><parameter><parameterid>scale</parameterid><name>Scale</name>"
              f"<value>{scale:.2f}</value></parameter></effect></filter>")

    v1, a1, pos = [], [], 0
    for i, ((s, _), d) in enumerate(zip(tl["keeps"], tl["durations"]), 1):
        n = round(d * fps)
        fx = file_el("raw", job.source, fps, src_info, src_info["has_audio"]) if i == 1 else '<file id="raw"/>'
        in_ = round(s * fps)
        v1.append(clip(f"v1-{i}", "video", job.source.name, "raw", fx, pos, pos + n, in_, in_ + n, fps, motion))
        if src_info["has_audio"]:
            a1.append(clip(f"a1-{i}", "audio", job.source.name, "raw", '<file id="raw"/>', pos, pos + n,
                           in_, in_ + n, fps, "<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>"))
        pos += n
    total = pos

    v2 = []
    rendered = job.w("graphics") / "rendered.json"
    plan = job.w("graphics-plan.json")
    if rendered.exists() and plan.exists() and not job.meta["steps"].get("graphics", {}).get("disabled"):
        names = read_json(rendered)
        for c in read_json(plan)["cards"]:
            if c["id"] not in names:
                continue
            mov = job.w("graphics") / "cache" / names[c["id"]]
            if not mov.exists():
                continue
            info = probe(mov)
            n = round(info["duration"] * fps)
            st = round(c["start"] * fps)
            v2.append(clip(f"v2-{c['id']}", "video", c["id"], c["id"],
                           file_el(f"card-{c['id']}", mov, fps, info, False), st, st + n, 0, n, fps))

    a2 = []
    music = job.meta["steps"].get("music", {})
    if music.get("track") and not music.get("disabled"):
        track = MUSIC.parent / music["track"]
        if track.exists():
            info = probe(track)
            n = min(round(info["duration"] * fps), total)
            a2.append(clip("a2-music", "audio", track.name, "music", file_el("music", track, fps, info, True),
                           0, n, 0, n, fps))

    def track(items):
        return f"<track>{''.join(items)}</track>"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4"><sequence id="seq"><name>{escape(job.name)} rough cut</name><duration>{total}</duration>
<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>
<media><video><format><samplecharacteristics><rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>
<width>{t['width']}</width><height>{t['height']}</height><pixelaspectratio>square</pixelaspectratio>
</samplecharacteristics></format>{track(v1)}{track(v2) if v2 else ''}</video>
<audio>{track(a1)}{track(a2) if a2 else ''}</audio></media></sequence></xmeml>
"""
    OUTPUTS.mkdir(exist_ok=True)
    out = OUTPUTS / f"{job.name}.premiere.xml"
    out.write_text(xml, encoding="utf-8")
    job.mark("to-premiere", output=str(out.relative_to(OUTPUTS.parent)))
    print(f"premiere xml ok: {out}  ({len(v1)} cuts, {len(v2)} cards, music={'yes' if a2 else 'no'})")


if __name__ == "__main__":
    main()
