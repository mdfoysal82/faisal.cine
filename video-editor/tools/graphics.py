#!/usr/bin/env python3
"""Step 3 - Graphics: build the cards in work/graphics-plan.json with HyperFrames and
composite them (plus punch-in zooms) over the rough cut -> work/graphics.mp4

  python3 tools/graphics.py <job>                # render changed cards + composite
  python3 tools/graphics.py <job> --only c03     # re-render one card (second pass)
  python3 tools/graphics.py <job> --preview c03  # PNG still of a card mid-way, no video
  python3 tools/graphics.py <job> --off          # no graphics for this job

graphics-plan.json (times are on the CUT timeline, i.e. work/transcript.json):
{
  "style": "signature-style",             # optional, defaults to the format's style
  "cards": [
    {"id": "c01", "start": 0.3, "end": 3.2, "kind": "title",
     "kicker": "পর্ব ১", "title": "Claude দিয়ে ভিডিও এডিট", "accent": 0},
    {"id": "c02", "start": 4.0, "end": 7.5, "kind": "list", "title": "৩টি ধাপ",
     "items": ["কাটা", "গ্রাফিক্স", "ক্যাপশন"]},
    {"id": "c03", "start": 9.0, "end": 11.0, "kind": "stat", "stat": "90%", "body": "দ্রুত"},
    {"id": "c04", "start": 12.0, "end": 15.0, "kind": "custom",
     "html": "<div class='panel'>...</div>", "css": "...", "js": "tl.from(...)"}
  ],
  "zooms": [{"start": 5.0, "end": 8.0, "scale": 1.15, "x": 0.5, "y": 0.4}]
}
kinds: title, point, stat, list, quote, hook, lower-third, custom.  Optional per card:
"zone" (top | center | lower-third | side) to override the style's default placement.

Each card is rendered alone to a transparent ProRes 4444 MOV and cached by content hash, so
changing one card only re-renders that card. Glass styles blur the footage under the card.
"""
import argparse
import hashlib
import html
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from common import (ASSETS, ENCODE, Job, die, ffmpeg, hyperframes_cmd, load_preset, read_json,
                    require, write_json)

TEMPLATE_VERSION = 3
FONT_FILES = {
    "Hind Siliguri": [("HindSiliguri-Regular.ttf", 400), ("HindSiliguri-SemiBold.ttf", 600),
                      ("HindSiliguri-Bold.ttf", 700)],
    "Anek Bangla": [("AnekBangla.ttf", "100 800")],
    "Noto Sans Bengali": [("NotoSansBengali-Regular.ttf", 400), ("NotoSansBengali-Bold.ttf", 700)],
}
DEFAULT_ZONE = {"signature": "top", "tiktok-raw": "top", "liquid-glass": "lower-third"}


def e(t) -> str:
    return html.escape(str(t or ""))


def card_inner(card: dict) -> str:
    k = card.get("kind", "point")
    kicker = f"<div class='kicker stag'>{e(card.get('kicker'))}</div>" if card.get("kicker") else ""
    title = f"<div class='title stag'>{e(card.get('title'))}</div>" if card.get("title") else ""
    body = f"<div class='body stag'>{e(card.get('body'))}</div>" if card.get("body") else ""
    if k == "custom":
        return card.get("html", "")
    if k == "stat":
        return (f"<div class='panel'>{kicker}<div class='stat stag'>{e(card.get('stat'))}</div>"
                f"{title}{body}</div>")
    if k == "list":
        items = "".join(f"<li class='stag'><span class='dot'></span><span>{e(i)}</span></li>"
                        for i in card.get("items", []))
        return f"<div class='panel'>{kicker}{title}<ul>{items}</ul></div>"
    if k == "quote":
        return (f"<div class='panel'><div class='qmark stag'>“</div>"
                f"<div class='title quote stag'>{e(card.get('title'))}</div>{body}</div>")
    if k == "hook":  # TikTok native: one white box per line of text
        return f"<div class='hook'><span class='hookline'>{e(card.get('title'))}</span></div>"
    if k == "lower-third":
        return f"<div class='panel lt'><div class='bar'></div><div>{title}{body}</div></div>"
    return f"<div class='panel'>{kicker}{title}{body}</div>"


def zone_css(zone: str, style: dict, w: int, h: int) -> str:
    z = style.get("zone", {})
    side = round(z.get("side", 0.06) * w)
    if zone == "top":
        top = round(z.get("top", 0.07) * h)
        maxh = round(z.get("height", 0.40) * h)
        return f"left:{side}px;right:{side}px;top:{top}px;max-height:{maxh}px;"
    if zone == "center":
        return f"left:{side}px;right:{side}px;top:{round(h * 0.34)}px;"
    if zone == "side":
        return f"right:{side}px;width:{round(w * 0.36)}px;top:{round(h * 0.18)}px;"
    y = round(z.get("lower_third_y", 0.70) * h)
    return f"left:{side}px;max-width:{round(w * 0.62)}px;top:{y}px;"


def build_html(card: dict, style: dict, w: int, h: int, dur: float) -> str:
    c = style["colors"]
    unit = min(w, h)
    ts = style["type_scale"]
    accent = c["accents"][int(card.get("accent", 0)) % len(c["accents"])]
    title_len = len(card.get("title") or "")
    fit = 1.0 if title_len <= 40 else 0.8 if title_len <= 70 else 0.65
    zone = card.get("zone") or DEFAULT_ZONE.get(style["name"], "top")
    m = style["motion"]
    faces = []
    for fam in {style["fonts"]["display"], style["fonts"]["body"]}:
        for f, wt in FONT_FILES[fam]:
            faces.append(f"@font-face{{font-family:'{fam}';src:url('{f}');font-weight:{wt}}}")
    glass = style.get("glass")
    panel_bg = c["panel"]
    border = f"border:2px solid {c['border']};" if c.get("border") else ""
    shadow = "box-shadow:0 20px 60px rgba(0,0,0,.25);" if not glass else ""
    css = f"""
{''.join(faces)}
html,body{{margin:0;background:transparent}}
#root{{position:relative;width:100%;height:100%;overflow:hidden}}
#card{{position:absolute;inset:0}}
.wrap{{position:absolute;{zone_css(zone, style, w, h)}}}
.panel{{background:{panel_bg};{border}{shadow}border-radius:{style['radius']}px;padding:{round(unit * .045)}px {round(unit * .05)}px;color:{c['text']};font-family:'{style['fonts']['body']}';}}
.kicker{{font-family:'{style['fonts']['body']}';font-weight:600;font-size:{round(ts['kicker'] * unit)}px;letter-spacing:.06em;color:{accent};text-transform:uppercase;margin-bottom:{round(unit * .012)}px}}
.title{{font-family:'{style['fonts']['display']}';font-weight:700;font-size:{round(ts['title'] * unit * fit)}px;line-height:1.18}}
.body{{font-size:{round(ts['body'] * unit)}px;line-height:1.35;color:{c['muted']};margin-top:{round(unit * .012)}px}}
.stat{{font-family:'{style['fonts']['display']}';font-weight:800;font-size:{round(ts['stat'] * unit)}px;line-height:1;color:{accent}}}
ul{{list-style:none;margin:{round(unit * .02)}px 0 0;padding:0}}
li{{display:flex;align-items:center;gap:{round(unit * .02)}px;font-size:{round(ts['body'] * unit * 1.1)}px;line-height:1.3;margin:{round(unit * .012)}px 0}}
.dot{{flex:none;width:{round(unit * .018)}px;height:{round(unit * .018)}px;border-radius:50%;background:{accent}}}
.qmark{{font-family:'{style['fonts']['display']}';font-size:{round(ts['stat'] * unit)}px;line-height:.6;color:{accent};height:{round(ts['stat'] * unit * .45)}px}}
.lt{{display:flex;gap:{round(unit * .025)}px;align-items:stretch}}
.bar{{flex:none;width:{round(unit * .008)}px;border-radius:4px;background:{accent}}}
.hook{{text-align:center;font-family:'{style['fonts']['display']}';font-weight:700;font-size:{round(ts['title'] * unit * fit)}px;line-height:1.5}}
.hookline{{background:{c['panel']};color:{c['text']};padding:.08em .35em;border-radius:{style['radius']}px;-webkit-box-decoration-break:clone;box-decoration-break:clone}}
{card.get('css', '')}
"""
    out_at = max(dur - m["out"], m["in"])
    js = f"""
const tl = gsap.timeline({{ paused: true }});
const wrap = document.querySelector('.wrap');
tl.fromTo(wrap, {{ y: {round(unit * .04)}, opacity: 0, scale: 0.98 }},
          {{ y: 0, opacity: 1, scale: 1, duration: {m['in']}, ease: 'power3.out' }}, 0);
const stag = document.querySelectorAll('.stag');
if (stag.length) tl.fromTo(stag, {{ y: {round(unit * .02)}, opacity: 0 }},
          {{ y: 0, opacity: 1, duration: {m['in']}, stagger: {m['stagger']}, ease: 'power2.out' }}, {m['in'] * 0.4:.3f});
{card.get('js', '')}
tl.to(wrap, {{ opacity: 0, y: {-round(unit * .02)}, duration: {m['out']}, ease: 'power2.in' }}, {out_at:.3f});
window.__timelines['main'] = tl;
"""
    return f"""<!doctype html>
<html lang="bn"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width={w}, height={h}"/>
<script src="gsap.min.js"></script>
<style>{css}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-width="{w}" data-height="{h}" data-duration="{dur:.3f}">
<section id="card" class="clip" data-start="0" data-duration="{dur:.3f}"><div class="wrap">{card_inner(card)}</div></section>
</div>
<script>{js}</script>
</body></html>
"""


def stage_card(job: Job, card: dict, style: dict) -> tuple[str, object]:
    t = job.meta["target"]
    dur = round(card["end"] - card["start"], 3)
    if dur <= 0.2:
        die(f"card {card['id']} is too short")
    page = build_html(card, style, t["width"], t["height"], dur)
    key = hashlib.sha1(json.dumps([page, t, TEMPLATE_VERSION]).encode()).hexdigest()[:12]
    bdir = job.w("graphics") / "build" / card["id"]
    if bdir.exists():
        shutil.rmtree(bdir)
    bdir.mkdir(parents=True)
    (bdir / "index.html").write_text(page, encoding="utf-8")
    shutil.copy(ASSETS / "vendor" / "gsap.min.js", bdir)
    for fam in {style["fonts"]["display"], style["fonts"]["body"]}:
        for f, _ in FONT_FILES[fam]:
            shutil.copy(ASSETS / "fonts" / f, bdir)
    return key, bdir


def render_card(job: Job, card: dict, key: str, bdir, force: bool) -> str:
    out = job.w("graphics") / "cache" / f"{card['id']}-{key}.mov"
    if out.exists() and not force:
        return out.name
    out.parent.mkdir(exist_ok=True)
    cmd = [*hyperframes_cmd(), "render", "--format", "mov", "--fps", str(job.meta["target"]["fps"]),
           "-o", str(out), "--quiet", "--skill", "talking-head-recut"]
    r = subprocess.run(cmd, cwd=bdir, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        die(f"HyperFrames render failed for card {card['id']} (page: {bdir / 'index.html'})")
    print(f"  rendered {card['id']}")
    return out.name


def zoom_expr(zooms: list[dict], ease: float) -> tuple[str, str, str]:
    """Piecewise zoom factor + focus point as ffmpeg expressions of t (smoothstep ramps)."""
    if not zooms:
        return "1", "0.5", "0.5"

    def env(z):
        s, e_ = z["start"], z["end"]
        r = min(ease, (e_ - s) / 2)
        up = f"clip((t-{s})/{r},0,1)"
        down = f"clip(({e_}-t)/{r},0,1)"
        lin = f"min({up},{down})"
        return f"({lin}*{lin}*(3-2*{lin}))"

    zexpr = "+".join(f"{z.get('scale', 1.12) - 1}*{env(z)}" for z in zooms)
    fx = "+".join(f"if(between(t,{z['start'] - ease},{z['end'] + ease}),{z.get('x', 0.5)},0)" for z in zooms)
    fy = "+".join(f"if(between(t,{z['start'] - ease},{z['end'] + ease}),{z.get('y', 0.5)},0)" for z in zooms)
    inside = "+".join(f"between(t,{z['start'] - ease},{z['end'] + ease})" for z in zooms)
    return f"(1+{zexpr})", f"if({inside},{fx},0.5)", f"if({inside},{fy},0.5)"


def composite(job: Job, plan: dict, style: dict, movs: list[tuple[dict, str]]) -> None:
    t = job.meta["target"]
    w, h, fps = t["width"], t["height"], t["fps"]
    src = job.stage_input("graphics")
    dur = float(job.meta["steps"]["rough-cut"]["duration"])
    ease = style.get("zoom", {}).get("ease_seconds", 0.35)
    z, fx, fy = zoom_expr(plan.get("zooms", []), ease)
    inputs = ["-i", src.name]
    for _, name in movs:
        inputs += ["-i", f"graphics/cache/{name}"]
    g = []
    if plan.get("zooms"):
        # upscale by z, then crop the target frame around the focus point
        g.append(f"[0:v]scale=w='trunc({w}*{z}/2)*2':h='trunc({h}*{z}/2)*2':eval=frame:flags=bicubic,"
                 f"crop={w}:{h}:x='(in_w-{w})*({fx})':y='(in_h-{h})*({fy})',setsar=1[base]")
    else:
        g.append("[0:v]null[base]")
    if movs:
        g.append(f"color=c=black@0.0:s={w}x{h}:r={fps}:d={dur:.3f},format=yuva444p[l0]")
        for i, (card, _) in enumerate(movs, 1):
            g.append(f"[{i}:v]setpts=PTS-STARTPTS+{card['start']}/TB[c{i}]")
            g.append(f"[l{i - 1}][c{i}]overlay=eof_action=pass:format=auto[l{i}]")
        layer = f"[l{len(movs)}]"
        if style.get("glass"):
            blur = style.get("glass_blur", 28)
            g.append(f"{layer}split[ga][gb]")
            g.append("[gb]alphaextract,lut=y='min(255,val*7)',boxblur=2:1[mask]")
            g.append("[base]split[b1][b2]")
            g.append(f"[b2]boxblur={blur}:2,eq=brightness=0.04:saturation=1.15[blur]")
            g.append("[b1][blur][mask]maskedmerge[frost]")
            g.append("[frost][ga]overlay=format=auto,format=yuv420p[v]")
        else:
            g.append(f"[base]{layer}overlay=format=auto,format=yuv420p[v]")
    else:
        g.append("[base]format=yuv420p[v]")
    ffmpeg(*inputs, "-filter_complex", ";".join(g), "-map", "[v]", "-map", "0:a?",
           *ENCODE, "-c:a", "copy", "-t", f"{dur:.3f}", "graphics.mp4", cwd=job.work)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--only", nargs="+", help="force re-render of these card ids")
    ap.add_argument("--preview", help="render a PNG still of one card (no video)")
    ap.add_argument("--off", action="store_true", help="disable graphics for this job")
    ap.add_argument("--jobs", type=int, default=2, help="cards rendered in parallel")
    a = ap.parse_args()

    require("ffmpeg")
    job = Job(a.job)
    if a.off:
        job.w("graphics.mp4").unlink(missing_ok=True)
        job.mark("graphics", disabled=True)
        print("graphics off for this job")
        return
    plan_path = job.w("graphics-plan.json")
    if not plan_path.exists():
        die("no work/graphics-plan.json yet - write the plan first (see the graphics-plan skill)")
    plan = read_json(plan_path)
    style_name = plan.get("style") or job.format["graphics"]["style"]
    style = load_preset(style_name)
    cards = plan.get("cards", [])
    ids = [c["id"] for c in cards]
    if len(ids) != len(set(ids)):
        die("card ids must be unique")
    end = float(job.meta["steps"]["rough-cut"]["duration"])
    for c in cards:
        c["end"] = min(c["end"], end)

    if a.preview:
        card = next((c for c in cards if c["id"] == a.preview), None) or die(f"no card {a.preview}")
        _, bdir = stage_card(job, card, style)
        mid = round((card["end"] - card["start"]) * 0.5, 2)
        png = job.w("graphics") / f"preview-{card['id']}.png"
        snaps = bdir / "snapshots"
        r = subprocess.run([*hyperframes_cmd(), "snapshot", "--at", str(mid), "--no-end", "-o", str(snaps)],
                           cwd=bdir, capture_output=True, text=True)
        shots = sorted(snaps.glob("*.png"))
        if r.returncode != 0 or not shots:
            sys.stderr.write(r.stdout[-2000:] + r.stderr[-2000:])
            die("snapshot failed")
        shutil.copy(shots[-1], png)
        print(f"preview: {png}")
        return

    staged = [(c, *stage_card(job, c, style)) for c in cards]
    force = set(a.only or [])
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        names = list(pool.map(lambda s: render_card(job, s[0], s[1], s[2], s[0]["id"] in force), staged))
    movs = list(zip(cards, names))
    keep = set(names)
    for old in (job.w("graphics") / "cache").glob("*.mov"):
        if old.name not in keep:
            old.unlink()
    composite(job, plan, style, movs)
    write_json(job.w("graphics") / "rendered.json", {c["id"]: n for c, n in movs})
    job.mark("graphics", style=style_name, cards=len(cards), zooms=len(plan.get("zooms", [])))
    print(f"graphics ok ({style_name}, {len(cards)} cards): {job.w('graphics.mp4')}")


if __name__ == "__main__":
    main()
