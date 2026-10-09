#!/usr/bin/env bash
# Step 7 - promote the latest stage of a job to outputs/<job>.final.mp4
#   ./finalize.sh <job>
set -euo pipefail
cd "$(dirname "$0")"
[[ $# -eq 1 ]] || { echo "usage: ./finalize.sh <job>" >&2; exit 1; }
exec python3 tools/finalize.py "$1"
