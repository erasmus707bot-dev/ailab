#!/usr/bin/env bash
# 🛟 Hermes break drill (2026-11-24): break the Hermes dashboard on purpose and prove the 🛡 Guard puts it back by itself.
# Run on gandalf as Scott:  bash ~/ailab/tools/guard_drill_hermes.sh
# The dashboard (:8780, Iris too) is down for about a minute. Don't run it while another session is saving Hermes files:
# the Guard puts back EVERY Hermes file changed after its copy (they stay in the "before going back" copy on the 🛟 page).
# If anything goes wrong:  ailab-guard restore hermes last-good
set -uo pipefail
G=http://127.0.0.1:8860
DASH=http://127.0.0.1:8780/health
SRV="$HOME/hermes/dist/hermes-local/hermes_local/dashboard.py"
MARK=$(mktemp /tmp/guard-drill.XXXXXX)
j() { curl -sf -H 'Content-Type: application/json' "$@"; }
up() { [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "$DASH")" != 000 ]; }
others() { find "$HOME/hermes" -type f -newer "$MARK" -not -path '*/.git/*' -not -path '*/__pycache__/*' \
           -not -path '*/node_modules/*' -not -path '*/graphify-out/*' -not -path "$SRV" 2>/dev/null | head -20; }

echo "1/6 🧰 Guard knows the dashboard is part of Hermes?"
grep -q 'hermes-dashboard.service' /etc/ailab-guard/config.json 2>/dev/null \
  || { echo "❌ Not yet — run once:  sudo bash ~/hermes-forge/ailab-guard/install.sh   then run this again."; exit 1; }
echo "2/6 🩺 Hermes dashboard answering now?"; up || { echo "❌ :8780 isn't answering before the drill — fix that first."; exit 1; }
HROOT="${HARVEST_DATA_ROOT:-$HOME/hermes-data/harvest}"
if [ -n "$(find "$HROOT/compare" "$HROOT"/people/*/compare -maxdepth 1 -name '*.part.mp4' -mmin -1 2>/dev/null)" ]; then
  echo "❌ A ⚡ compare fast copy is being made — a restart would throw it away. Run the drill after it finishes."; exit 1; fi
echo "3/6 🛡 Guard saves a copy + starts watching (3 min)"
SNAP=$(j -X POST $G/api/snap -d '{"target":"hermes","why":"Hermes drill — before breaking it on purpose","by":"drill"}' \
       | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])') || { echo "❌ Guard not answering"; exit 1; }
j -X POST $G/api/watch -d "{\"target\":\"hermes\",\"snap\":\"$SNAP\",\"minutes\":3,\"why\":\"drill\"}" >/dev/null
BEFORE=$(sha256sum "$SRV" | cut -c1-12)
echo "4/6 💥 Breaking the dashboard (adds a crash line to dashboard.py) and restarting Hermes through the Guard"
echo 'raise SystemExit("guard drill — this line should be removed by the Guard")' >> "$SRV"
j -X POST $G/api/restart -d '{"target":"hermes"}' >/dev/null || echo "   ⚠️ the Guard's restart reported a problem (carrying on — the watch is running)"
sleep 8; DOWN=no; up || DOWN=yes
echo "   dashboard down after the break: $DOWN"
echo "5/6 ⏳ Waiting for the Guard (up to 3 min)…"
SEEN=""
for i in $(seq 1 36); do
  sleep 5; up || DOWN=yes; O=$(others); [ -n "$O" ] && SEEN="$O"
  if [ "$(sha256sum "$SRV" | cut -c1-12)" = "$BEFORE" ] && up; then
    if [ "$DOWN" = yes ]; then
      echo "6/6 ✅ PASS — the dashboard went down, the Guard put dashboard.py back and Hermes is answering again (~$((8+i*5)) s)."
      echo "     Your phone should have a '🛟 Hermes rolled back' ping."
    else
      echo "6/6 ⚠️ HALF — dashboard.py was put back, but the dashboard never went down, so the break never loaded."
      echo "     The Guard's restart isn't reaching the dashboard. Check:  systemctl --user status hermes-dashboard"
    fi
    [ -n "$SEEN" ] && { echo "     ⚠️ Other Hermes files changed during the drill and were put back too — find them in the"; \
                        echo "        'before going back' copy on the 🛟 page:"; echo "$SEEN" | sed "s|$HOME/hermes/|        |"; }
    rm -f "$MARK"; [ "$DOWN" = yes ]; exit $?
  fi
done
echo "6/6 ❌ FAIL — the Guard didn't fix it in 3 min. Fixing by hand now:"
rm -f "$MARK"
ailab-guard restore hermes "$SNAP"
exit 1
