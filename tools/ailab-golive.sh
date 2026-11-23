#!/usr/bin/env bash
# AI Lab five fixes — go live on gandalf (2026-11-23). Safe to run twice.
set -u
ok(){ echo "✓ $*"; }; bad(){ echo "✗ $*"; }
# 1) robot check needs Playwright (drives the installed Chrome — no browser download)
python3 -c "import playwright" 2>/dev/null && ok "playwright already installed" \
  || { pip install --user --break-system-packages -q playwright && ok "playwright installed" || bad "pip install playwright failed"; }
C=$(command -v google-chrome || command -v google-chrome-stable || command -v chromium || command -v chromium-browser)
[ -n "$C" ] && ok "browser for the robot: $C" || bad "no Chrome/Chromium on PATH — robot will stay yellow (fix: python3 -m playwright install chromium)"
# 2) Show & change switch on
python3 - <<'P'
import json, pathlib
p = pathlib.Path.home() / ".config/ailab/config.json"
c = json.loads(p.read_text() or "{}") if p.exists() else {}
c.setdefault("flags", {})["live"] = True
p.write_text(json.dumps(c, indent=1)); print("✓ flag live = on")
P
# 3) connected mode + reboot-proof MCP server (installs hermes-mcp unit on 8851) + restarts the Lab
bash "$HOME/ailab/tools/ailab-connect.sh" || bad "ailab-connect.sh stopped — read the line above"
# 4) Hermes re-reads model_preferences (OpenRouter on for the Lab)
systemctl --user restart hermes-mcp 2>/dev/null && ok "hermes-mcp restarted" || bad "hermes-mcp restart failed"
systemctl --user restart hermes-dashboard 2>/dev/null && ok "hermes-dashboard restarted" || bad "hermes-dashboard restart failed"
sleep 3
systemctl --user is-active hermes-mcp hermes-dashboard | paste -sd' ' | sed 's/^/  services: /'
systemctl --user is-enabled hermes-mcp 2>/dev/null | sed 's/^/  hermes-mcp at boot: /'
curl -s -o /dev/null -w "  Lab page: HTTP %{http_code}\n" http://127.0.0.1:8850/
curl -s http://127.0.0.1:8850/api/state | python3 -c "import json,sys;d=json.load(sys.stdin);print('  Lab mode:',d.get('mode'),'· live:',d['flags'].get('live'),'· agent:',d['flags'].get('agent'))" 2>/dev/null || bad "Lab /api/state not answering"
echo "Next: OpenRouter key in Hermes → Settings → API keys (if not there yet). Then tell Claude 'done'."
