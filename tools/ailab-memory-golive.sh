#!/usr/bin/env bash
# AI Lab 🧠 Memory + 📝 Prompt builder — switch on and restart (2026-11-24). Safe to run twice.
# Running this IS Scott flipping the two flags (there is deliberately no API for it).
set -u
python3 - <<'P'
import json, pathlib
p = pathlib.Path.home() / ".config/ailab/config.json"
c = json.loads(p.read_text() or "{}") if p.exists() else {}
f = c.setdefault("flags", {})
f["memory"] = True; f["prompt"] = True
p.write_text(json.dumps(c, indent=1)); print("✓ flags memory + prompt = on")
P
[ -d "$HOME/hermes-data/claude-memory-export" ] && echo "✓ Claude memory export found ($(ls "$HOME/hermes-data/claude-memory-export" | wc -l) files)" \
  || echo "✗ no ~/hermes-data/claude-memory-export — ask Claude to re-export"
grep -q '"channel": *"ntfy"' "$HOME/hermes-forge/alerts.json" 2>/dev/null && echo "✓ phone pings: Hermes ntfy found" || echo "✗ phone pings off (no ntfy in alerts.json)"
AILAB_NO_OPEN=1 bash "$HOME/ailab/tools/ailab-open.sh" >/dev/null 2>&1
sleep 2
curl -s http://127.0.0.1:8850/api/state | python3 -c "import json,sys;d=json.load(sys.stdin);f=d['flags'];print('  Lab:',d.get('mode'),'· memory:',f.get('memory'),'· prompt:',f.get('prompt'))" 2>/dev/null || echo "✗ Lab not answering — see ~/.config/ailab/serve.log"
echo "Next: tell Claude 'done' — it runs the live proof in your Chrome."
