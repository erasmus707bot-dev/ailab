#!/usr/bin/env bash
# Standalone install test (M8): a fresh clone of the COMMITTED repo, no ~/.config/ailab, no Hermes —
# must pass its tests, start, and scan clean. Touches nothing outside a temp folder.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d /tmp/ailab-install-XXXXXX)"
export AILAB_HOME="$T/home" AILAB_CACHE="$T/cache"
git clone -q "$SRC" "$T/ailab"
cd "$T/ailab"
python3 -m unittest discover -s tests -t . </dev/null 2>&1 | tail -1 | grep -q "^OK" || { echo "❌ tests failed in the fresh clone ($T)"; exit 1; }
python3 -m ailab status </dev/null | python3 -c 'import json,sys; s=json.load(sys.stdin); assert s.get("mode")=="standalone", s' \
  || { echo "❌ status failed in the fresh clone ($T)"; exit 1; }
python3 -m ailab secretscan </dev/null | tail -1
echo "✅ standalone install OK (fresh clone in $T)"
