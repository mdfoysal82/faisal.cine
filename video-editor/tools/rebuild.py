#!/usr/bin/env python3
"""Second pass: re-run every stage downstream of a change, with the settings each stage
last used. Unchanged rough-cut segments and graphic cards come from cache.

  python3 tools/rebuild.py <job> --from rough-cut   # after editing the cut list
  python3 tools/rebuild.py <job> --from graphics    # after editing graphics-plan.json
  python3 tools/rebuild.py <job> --from captions    # after fixing transcript.json words
  python3 tools/rebuild.py <job> --from music
"""
import argparse
import subprocess
import sys

from common import ROOT, Job

ORDER = ["rough-cut", "graphics", "captions", "music"]


def step(*args: str) -> None:
    print("->", " ".join(args))
    if subprocess.run([sys.executable, str(ROOT / "tools" / args[0]), *args[1:]]).returncode:
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--from", dest="start", required=True, choices=ORDER)
    a = ap.parse_args()

    job = Job(a.job)
    steps = job.meta.get("steps", {})
    for name in ORDER[ORDER.index(a.start):]:
        info = steps.get(name)
        if name == "rough-cut":
            step("apply_cut.py", a.job, *(["--no-polish"] if info and not info.get("polish", True) else []))
        elif not info or info.get("disabled"):
            continue
        elif name == "graphics":
            step("graphics.py", a.job)
        elif name == "captions":
            step("captions.py", a.job, "--style", info["style"])
        elif name == "music":
            step("music.py", a.job, "--track", info["track"], "--bed", str(info["bed"]), "--duck", str(info["duck"]))
    print("rebuild ok - review, then ./finalize.sh", a.job)


if __name__ == "__main__":
    main()
