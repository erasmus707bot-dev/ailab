#!/usr/bin/env bash
# 🛟 M6 drill (2026-11-24): break the AI Lab on purpose and prove the 🛡 Guard puts it back by itself.
# Run on gandalf as Scott:  bash ~/ailab/tools/guard_drill.sh
# Safe: the Guard saves a copy first. If anything goes wrong:  ailab-guard restore ailab last-good
set -uo pipefail
G=http://127.0.0.1:8860
LAB=http://127.0.0.1:8850/api/health
SRV="$HOME/ailab/ailab/server.py"
j() { curl -sf -H 'Content-Type: application/json' "$@"; }

echo "1/5 🩺 Lab healthy now?"; curl -sf "$LAB" >/dev/null || curl -sf http://127.0.0.1:8850/ >/dev/null \
  || { echo "❌ The Lab isn't answering before the drill — start it first."; exit 1; }
echo "2/5 🛡 Guard saves a copy + starts watching (3 min)"
SNAP=$(j -X POST $G/api/snap -d '{"target":"ailab","why":"M6 drill — before breaking it on purpose","by":"drill"}' \
       | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])') || { echo "❌ Guard not answering"; exit 1; }
j -X POST $G/api/watch -d "{\"target\":\"ailab\",\"snap\":\"$SNAP\",\"minutes\":3,\"why\":\"drill\"}" >/dev/null
BEFORE=$(sha256sum "$SRV" | cut -c1-12)
echo "3/5 💥 Breaking the Lab (adds a crash line to server.py) and restarting it"
echo 'raise SystemExit("guard drill — this line should be removed by the Guard")' >> "$SRV"
systemctl --user restart ailab.service
echo "4/5 ⏳ Waiting for the Guard (up to 2 min)…"
for i in $(seq 1 24); do
  sleep 5
  if [ "$(sha256sum "$SRV" | cut -c1-12)" = "$BEFORE" ] && curl -sf http://127.0.0.1:8850/ >/dev/null; then
    echo "5/5 ✅ PASS — the Guard put server.py back and the Lab is answering again (after ~$((i*5)) s)."
    echo "     Your phone should have a '🛟 AI Lab rolled back' ping. The 🛟 page shows the drill copies."
    exit 0
  fi
done
echo "5/5 ❌ FAIL — the Guard didn't fix it in 2 min. Fixing by hand now:"
ailab-guard restore ailab "$SNAP"
exit 1
