#!/usr/bin/env bash
# Re-vendor the HyperFrames skills listed in skills-lock.json at the pinned ref.
# This is the ONLY supported way to change files under the vendored skill folders.
#
#   tools/update_vendor.sh            # install exactly what the lock says
#   tools/update_vendor.sh <new-ref>  # bump the lock to <new-ref> (commit sha/tag) and install
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$ROOT/skills-lock.json"

if [[ $# -ge 1 ]]; then
  python3 - "$LOCK" "$1" <<'PY'
import json, sys
p, ref = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["hyperframes"]["ref"] = ref
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False)
open(p, "a").write("\n")
PY
fi

read -r SRC REF DEST SKILLS < <(python3 -c '
import json, sys
h = json.load(open(sys.argv[1]))["hyperframes"]
print(h["source"], h["ref"], h["dest"], ",".join(h["skills"]))
' "$LOCK")

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q
git -C "$TMP" remote add origin "$SRC"
git -C "$TMP" fetch -q --depth 1 origin "$REF"
git -C "$TMP" checkout -q FETCH_HEAD

IFS=',' read -ra LIST <<<"$SKILLS"
for s in "${LIST[@]}"; do
  rm -rf "$ROOT/$DEST/$s"
  cp -R "$TMP/skills/$s" "$ROOT/$DEST/$s"
  echo "vendored $s"
done
cp "$TMP/LICENSE" "$ROOT/$DEST/HYPERFRAMES-LICENSE"
echo "HyperFrames skills pinned at $REF"
