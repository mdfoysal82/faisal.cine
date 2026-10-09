#!/usr/bin/env bash
# One-time setup on macOS (Apple Silicon or Intel). Safe to re-run.
#   ./setup.sh             ffmpeg, Node 22+, Python 3, HyperFrames check
#   ./setup.sh --whisperx  also install WhisperX (optional second transcription engine)
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n==> %s\n' "$*"; }

if [[ "$(uname)" == "Darwin" ]] && ! command -v brew >/dev/null; then
  echo "Homebrew is required: https://brew.sh  (then re-run ./setup.sh)"; exit 1
fi

need_brew() {  # need_brew <command> <formula>
  if ! command -v "$1" >/dev/null; then
    if command -v brew >/dev/null; then say "installing $2"; brew install "$2"
    else echo "please install $2 (command '$1' not found)"; exit 1; fi
  fi
}

need_brew ffmpeg ffmpeg
need_brew python3 python@3.12
need_brew node node

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if (( NODE_MAJOR < 22 )); then
  echo "Node $NODE_MAJOR found, HyperFrames needs Node >= 22 (brew upgrade node)"; exit 1
fi

if ! ffmpeg -hide_banner -filters 2>/dev/null | grep -q ' ass '; then
  echo "your ffmpeg has no libass (needed for captions) - brew reinstall ffmpeg"; exit 1
fi

CLI="$(python3 -c 'import json; print(json.load(open("skills-lock.json"))["hyperframes"]["cli"])')"
say "checking HyperFrames $CLI (first run downloads it and a headless Chrome)"
HYPERFRAMES_NO_TELEMETRY=1 npx -y "hyperframes@$CLI" doctor || true

if [[ "${1:-}" == "--whisperx" ]]; then
  say "installing WhisperX into .venv"
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip whisperx
  echo "use it with: .venv/bin/python tools/transcribe.py <job> --engine whisperx"
fi

mkdir -p projects outputs music
chmod +x finalize.sh prune.sh tools/*.py tools/*.sh tests/*.py tests/*.sh 2>/dev/null || true

if [[ "$(uname)" == "Darwin" ]]; then
  # Hardware GPU capture makes HyperFrames renders much faster on a Mac.
  grep -q PRODUCER_BROWSER_GPU_MODE ~/.zprofile 2>/dev/null || \
    echo 'export PRODUCER_BROWSER_GPU_MODE=hardware' >> ~/.zprofile
fi

say "ready. open this folder in Claude Code and say: ভিডিও এডিট করো /path/to/clip.mp4"
