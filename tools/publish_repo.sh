#!/usr/bin/env bash
# Make the AI Lab repo public (M8). Pushes ONLY after: clean secret scan, tests OK, fresh-clone install OK,
# and Scott typing "publish". Needs a GitHub remote named "origin" (nothing is created for you).
set -euo pipefail
cd "$(dirname "$0")/.."
git remote get-url origin >/dev/null 2>&1 || { echo "❌ no 'origin' remote — create the empty GitHub repo, then: git remote add origin <url>"; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "❌ uncommitted changes — commit first"; exit 1; }
python3 -m ailab secretscan || { echo "❌ secret scan not clean — nothing pushed"; exit 1; }
bash tools/install_test.sh
echo "About to push $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD) to $(git remote get-url origin)"
read -r -p 'Type publish to push: ' A
[ "$A" = "publish" ] || { echo "stopped — nothing pushed"; exit 1; }
git push -u origin "$(git rev-parse --abbrev-ref HEAD)"
