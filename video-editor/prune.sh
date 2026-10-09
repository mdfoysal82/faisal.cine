#!/usr/bin/env bash
# Free disk space for a finished job.
#   ./prune.sh <job>              delete re-creatable intermediates (segments, card renders,
#                                 stage videos, extracted audio); keeps raw/, plans, cut list,
#                                 transcripts, script and outputs/
#   ./prune.sh <job> --raw --yes  ALSO delete the raw footage copy (cannot be undone)
set -euo pipefail
cd "$(dirname "$0")"
JOB="${1:-}"
[[ -n "$JOB" && -f "projects/$JOB/job.json" ]] || { echo "usage: ./prune.sh <job> [--raw --yes]" >&2; exit 1; }
shift
RAW=0; YES=0
for arg in "$@"; do
  case "$arg" in
    --raw) RAW=1 ;;
    --yes) YES=1 ;;
    *) echo "unknown option $arg" >&2; exit 1 ;;
  esac
done

W="projects/$JOB/work"
before=$(du -sh "projects/$JOB" | cut -f1)
rm -rf "$W/segments" "$W/graphics/cache" "$W/graphics/build" "$W/thumbs"
rm -f "$W/audio.wav" "$W/roughcut.mp4" "$W/graphics.mp4" "$W/captioned.mp4" "$W/music.mp4"
if [[ $RAW -eq 1 ]]; then
  if [[ $YES -ne 1 ]]; then
    echo "refusing to delete raw footage without --yes" >&2; exit 1
  fi
  [[ -f "outputs/$JOB.final.mp4" ]] || { echo "no outputs/$JOB.final.mp4 - finalize before deleting raw" >&2; exit 1; }
  rm -rf "projects/$JOB/raw"
fi
after=$(du -sh "projects/$JOB" | cut -f1)
echo "pruned $JOB: $before -> $after"
