#!/usr/bin/env bash
# AI Lab 📓 Craft Book — switch on, load the Nov 22–25 lessons (as proposed), read handoffs, restart. Safe to run twice.
# Running this IS Scott flipping the flag (there is deliberately no API for it).
set -u
cd "$HOME/ailab" || exit 1
python3 - <<'P'
import json, pathlib
p = pathlib.Path.home() / ".config/ailab/config.json"
c = json.loads(p.read_text() or "{}") if p.exists() else {}
c.setdefault("flags", {})["craft"] = True
c.setdefault("craft", {}).setdefault("holdout", 5)      # every 5th run goes without notes, so with/without can be compared; 0 = never
p.write_text(json.dumps(c, indent=1)); print("✓ flag craft = on · holdout =", c["craft"]["holdout"])
from ailab import craft
print("✓ Claude's lessons:", craft.seed())
print("✓ handoffs:", craft.import_handoffs())
v = craft.view(); print("  Craft Book:", v["counts"])
P
AILAB_NO_OPEN=1 bash "$HOME/ailab/tools/ailab-open.sh" >/dev/null 2>&1
sleep 2
curl -s http://127.0.0.1:8850/api/craft | python3 -c "import json,sys;d=json.load(sys.stdin);print('  Lab page: ok' if d.get('ok') else '  Lab page: '+str(d.get('message')), d.get('counts',''))" 2>/dev/null || echo "✗ Lab not answering on 8850"
echo "Next: open the Lab → 📓 (top bar) → ✅ Make all of these live, or tick them one by one."
