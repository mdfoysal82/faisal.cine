#!/usr/bin/env bash
# End-to-end smoke test on a synthetic clip (needs espeak-ng to build the fixture).
# Runs every step for one format and checks the final output exists.
#   tests/run_pipeline.sh [short-explainer|short-tiktok|youtube]
set -euo pipefail
cd "$(dirname "$0")/.."
FMT="${1:-short-explainer}"
JOB="selftest-$FMT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 tests/make_fixture.py "$TMP"
python3 tools/intake.py "$TMP/fixture.mp4" --job "$JOB" --format "$FMT" --force
python3 tools/transcribe.py "$JOB" --engine import --file "$TMP/fixture.words.json"
python3 tools/cutlist.py plan "$JOB" >/dev/null
python3 tools/cutlist.py approve "$JOB" >/dev/null
python3 tools/apply_cut.py "$JOB"

cat > "projects/$JOB/work/graphics-plan.json" <<'EOF'
{
  "cards": [
    {"id": "c01", "start": 0.2, "end": 2.0, "kind": "hook", "title": "Claude দিয়ে ভিডিও এডিট"},
    {"id": "c02", "start": 2.2, "end": 8.0, "kind": "list", "title": "ধাপগুলো", "items": ["কাটা", "গ্রাফিক্স", "ক্যাপশন"]},
    {"id": "c03", "start": 15.8, "end": 18.0, "kind": "stat", "stat": "90%", "title": "দ্রুত", "zone": "side"}
  ],
  "zooms": [{"start": 8.5, "end": 10.5, "scale": 1.15, "x": 0.5, "y": 0.4}]
}
EOF
python3 tools/graphics.py "$JOB"
python3 tools/captions.py "$JOB"
ffmpeg -v error -y -f lavfi -i "sine=f=220:d=6,volume=0.3" "$TMP/bed.wav"
python3 tools/music.py "$JOB" --track "$TMP/bed.wav"
./finalize.sh "$JOB"
python3 tools/to_premiere.py "$JOB"
python3 -c "import xml.dom.minidom as m; m.parse('outputs/$JOB.premiere.xml')"
test -s "outputs/$JOB.final.mp4"
echo "PASS $FMT"
