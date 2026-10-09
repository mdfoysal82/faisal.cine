#!/usr/bin/env python3
"""Rough-cut part 2: plan and edit the cut list (nothing is rendered here).

  python3 tools/cutlist.py plan <job>                       # auto: fillers, stutters, long pauses
  python3 tools/cutlist.py show <job>                       # rewrite + print work/cutlist.md
  python3 tools/cutlist.py cut  <job> 12.40 15.85 --reason retake
  python3 tools/cutlist.py keep <job> 30.0 31.2             # force-keep a range
  python3 tools/cutlist.py toggle <job> 7 9 12              # enable/disable auto cuts by id
  python3 tools/cutlist.py unmanual <job> 2                 # drop manual edit #2

Times are on the RAW clip timeline (seconds). work/cutlist.json keeps auto cuts and
manual edits separately so re-planning never loses the editor's decisions.
"""
import argparse
import sys

from common import Job, die, fmt_time, load_preset, read_json, write_json
from textutil import norm


def phrase_hits(words, phrases):
    """Yield (i, j, phrase) for every word run i..j-1 matching a phrase."""
    toks = [norm(w["text"]) for w in words]
    plist = sorted({tuple(norm(x) for x in p.split()) for p in phrases}, key=len, reverse=True)
    i = 0
    while i < len(toks):
        for p in plist:
            if p and tuple(toks[i:i + len(p)]) == p:
                yield i, i + len(p), " ".join(p)
                i += len(p) - 1
                break
        i += 1


def plan(job: Job) -> dict:
    rules = load_preset("cut-rules")
    words = read_json(job.w("transcript.raw.json"))
    dur = job.meta["source_info"]["duration"]
    lang_lists = lambda key: [x for lst in rules[key].values() for x in lst]
    cuts = []

    def add(start, end, reason, text="", enabled=True):
        if end - start > 0.02:
            cuts.append({"start": round(max(0, start), 3), "end": round(min(dur, end), 3),
                         "reason": reason, "text": text, "enabled": enabled})

    cut_word = [False] * len(words)
    for i, j, p in phrase_hits(words, lang_lists("fillers")):
        for k in range(i, j):
            cut_word[k] = True
        add(words[i]["start"], words[j - 1]["end"], "filler", p)
    for i, j, p in phrase_hits(words, lang_lists("maybe_fillers")):
        if not any(cut_word[i:j]):
            add(words[i]["start"], words[j - 1]["end"], "maybe-filler", p, enabled=False)

    if rules.get("cut_stutters"):
        for i in range(1, len(words)):
            a, b = norm(words[i - 1]["text"]), norm(words[i]["text"])
            if a and a == b and not cut_word[i - 1]:
                cut_word[i - 1] = True
                add(words[i - 1]["start"], words[i]["start"], "stutter", words[i - 1]["text"])

    # Pauses: anything longer than max_pause between kept words shrinks to keep_pause.
    kept = [w for w, c in zip(words, cut_word) if not c]
    if kept:
        add(0, kept[0]["start"] - rules["lead_in"], "lead-in silence")
        for prev, nxt in zip(kept, kept[1:]):
            gap = nxt["start"] - prev["end"]
            if gap > rules["max_pause"]:
                half = rules["keep_pause"] / 2
                add(prev["end"] + half, nxt["start"] - half, "pause", f"{gap:.1f}s")
        add(kept[-1]["end"] + rules["tail_out"], dur, "tail silence")

    cuts.sort(key=lambda c: c["start"])
    for n, c in enumerate(cuts, 1):
        c["id"] = n
    old = read_json(job.w("cutlist.json")) if job.w("cutlist.json").exists() else {}
    return {"source_duration": dur, "auto": cuts, "manual": old.get("manual", []), "approved": False}


def merge(ranges):
    out = []
    for s, e in sorted(ranges):
        if out and s <= out[-1][1] + 1e-3:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def subtract(ranges, s, e):
    out = []
    for a, b in ranges:
        if b <= s or a >= e:
            out.append([a, b])
            continue
        if a < s:
            out.append([a, s])
        if b > e:
            out.append([e, b])
    return out


def keep_ranges(cl: dict) -> list[list[float]]:
    """Final kept ranges on the raw timeline."""
    rules = load_preset("cut-rules")
    cuts = merge([[c["start"], c["end"]] for c in cl["auto"] if c["enabled"]])
    for m in cl["manual"]:
        if m["action"] == "cut":
            cuts = merge(cuts + [[m["start"], m["end"]]])
        else:
            cuts = subtract(cuts, m["start"], m["end"])
    keeps, t = [], 0.0
    for s, e in cuts:
        if s > t:
            keeps.append([t, s])
        t = max(t, e)
    if t < cl["source_duration"]:
        keeps.append([t, cl["source_duration"]])
    return [[round(s, 3), round(e, 3)] for s, e in keeps if e - s >= rules["min_keep"]]


def context(words, s, e):
    inside = [w["text"] for w in words if w["start"] >= s - 0.01 and w["end"] <= e + 0.01]
    before = [w["text"] for w in words if w["end"] <= s + 0.01][-3:]
    after = [w["text"] for w in words if w["start"] >= e - 0.01][:3]
    mid = " ".join(inside) if inside else "·"
    return f"{' '.join(before)} [{mid}] {' '.join(after)}".strip()


def write_md(job: Job, cl: dict) -> str:
    words = read_json(job.w("transcript.raw.json"))
    keeps = keep_ranges(cl)
    new_dur = sum(e - s for s, e in keeps)
    reason_bn = {"filler": "ফিলার শব্দ", "maybe-filler": "সম্ভাব্য ফিলার", "stutter": "তোতলানো/পুনরাবৃত্তি",
                 "pause": "লম্বা বিরতি", "lead-in silence": "শুরুর নীরবতা", "tail silence": "শেষের নীরবতা"}
    lines = [f"# Rough cut - {job.name}", "",
             f"মূল দৈর্ঘ্য **{fmt_time(cl['source_duration'])}** -> কাটার পরে **{fmt_time(new_dur)}** "
             f"({len(keeps)} টি অংশ রাখা হবে)", "",
             "| # | চালু? | সময় (raw) | দৈর্ঘ্য | কারণ | প্রসঙ্গ |", "|---|---|---|---|---|---|"]
    for c in cl["auto"]:
        lines.append(f"| {c['id']} | {'✅' if c['enabled'] else '⬜'} | {fmt_time(c['start'])}-{fmt_time(c['end'])} "
                     f"| {c['end'] - c['start']:.2f}s | {reason_bn.get(c['reason'], c['reason'])} {c['text']} "
                     f"| {context(words, c['start'], c['end'])} |")
    if cl["manual"]:
        lines += ["", "## হাতে করা পরিবর্তন", "", "| # | কাজ | সময় (raw) | কারণ | প্রসঙ্গ |", "|---|---|---|---|---|"]
        for n, m in enumerate(cl["manual"], 1):
            act = "কাটা" if m["action"] == "cut" else "রাখা"
            lines.append(f"| {n} | {act} | {fmt_time(m['start'])}-{fmt_time(m['end'])} | {m.get('reason', '')} "
                         f"| {context(words, m['start'], m['end'])} |")
    lines += ["", f"অনুমোদিত: {'হ্যাঁ' if cl.get('approved') else 'না - render করার আগে অনুমতি নিন'}", ""]
    md = "\n".join(lines)
    job.w("cutlist.md").write_text(md, encoding="utf-8")
    return md


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "show", "approve"):
        sub.add_parser(name).add_argument("job")
    for name in ("cut", "keep"):
        p = sub.add_parser(name)
        p.add_argument("job")
        p.add_argument("start", type=float)
        p.add_argument("end", type=float)
        p.add_argument("--reason", default="manual")
    p = sub.add_parser("toggle")
    p.add_argument("job")
    p.add_argument("ids", type=int, nargs="+")
    p = sub.add_parser("unmanual")
    p.add_argument("job")
    p.add_argument("index", type=int)
    a = ap.parse_args()

    job = Job(a.job)
    path = job.w("cutlist.json")
    if a.cmd == "plan":
        if not job.w("transcript.raw.json").exists():
            die("no transcript yet - run tools/transcribe.py first")
        cl = plan(job)
    else:
        if not path.exists():
            die("no cut list yet - run: tools/cutlist.py plan <job>")
        cl = read_json(path)
        if a.cmd in ("cut", "keep"):
            if a.end <= a.start:
                die("end must be after start")
            cl["manual"].append({"action": a.cmd, "start": a.start, "end": a.end, "reason": a.reason})
        elif a.cmd == "toggle":
            ids = set(a.ids)
            for c in cl["auto"]:
                if c["id"] in ids:
                    c["enabled"] = not c["enabled"]
        elif a.cmd == "unmanual":
            if not 1 <= a.index <= len(cl["manual"]):
                die("no such manual edit")
            cl["manual"].pop(a.index - 1)
        if a.cmd != "show":
            cl["approved"] = a.cmd == "approve"
    write_json(path, cl)
    sys.stdout.write(write_md(job, cl))


if __name__ == "__main__":
    main()
