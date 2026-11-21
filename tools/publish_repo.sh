#!/usr/bin/env bash
# Make the AI Lab repo public (M8). Pushes ONLY after: clean secret scan, tests OK, fresh-clone install OK,
# and typing "publish". Needs a GitHub remote named "origin".
set -euo pipefail
cd "$(dirname "$0")/.."
git remote get-url origin >/dev/null 2>&1 || { echo "❌ no 'origin' remote — create the empty GitHub repo, then: git remote add origin <url>"; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "❌ uncommitted changes — commit first"; exit 1; }
python3 -m ailab secretscan || { echo "❌ secret scan not clean — nothing pushed"; exit 1; }
bash tools/install_test.sh
echo "About to push $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD) to $(git remote get-url origin)"
read -r -p 'Type publish to push: ' A
[ "$A" = "publish" ] || { echo "stopped — nothing pushed"; exit 1; }
# Credentials: if $AILAB_GIT_ASKPASS points at a helper (Scott's lives outside this repo), git asks it for the
# token — never printed, never stored. Otherwise git uses your normal credential setup.
if [ -n "${AILAB_GIT_ASKPASS:-}" ]; then
  GIT_ASKPASS="$AILAB_GIT_ASKPASS" GIT_TERMINAL_PROMPT=0 git -c credential.helper= push -u origin "$(git rev-parse --abbrev-ref HEAD)" \
    || { echo "❌ push refused — check the token your helper returns (Contents: read/write on this repo)"; exit 1; }
else
  git push -u origin "$(git rev-parse --abbrev-ref HEAD)" || { echo "❌ push refused"; exit 1; }
fi
echo "✅ published: $(git remote get-url origin)"
