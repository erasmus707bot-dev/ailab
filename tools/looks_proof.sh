#!/usr/bin/env bash
# 🎨 Picture Looks M4 live proof (2026-11-24): restart the AI Lab, then make 6 pictures on Venice Lustify v8 from Looks
# only (no writer — tests that the Look words alone reach the picture model). About $0.06 on the ailab cap.
# Writes PNGs + report.txt to ~/hermes-data/_scratch/looks_proof/. Run on gandalf:  bash ~/ailab/tools/looks_proof.sh
set -u
OUT="$HOME/hermes-data/_scratch/looks_proof"; mkdir -p "$OUT"
echo "== restart AI Lab"
if systemctl --user restart ailab.service 2>/dev/null; then sleep 2; systemctl --user is-active ailab.service
else pkill -u "$(id -u)" -f "python3 -m ailab serve" 2>/dev/null; echo "(no ailab.service — reopen the Lab with the desktop icon)"; fi
curl -s -m 5 http://127.0.0.1:8850/api/looks | head -c 120; echo
echo "== 6 Look pictures (lustify-v8)"
cd "$HOME/hermes" || exit 1
PYTHONPATH="$HOME/hermes:$HOME/ailab" python3 - "$OUT" <<'PY' 2>&1 | tee "$OUT/report.txt"
import base64, sys, time
from forge.projects import mcp_server as M
from ailab import looks, picture
out = sys.argv[1]
ctx = M.ctx_for("builder", "ailab", category="ailab")
def call(n, a):
    r = M.call_tool(n, a, ctx); sc = r.get("structuredContent") or {}
    if r.get("isError"): raise RuntimeError(f"REFUSED {n} {sc.get('code')} - {sc.get('message')} | {sc.get('fix')}")
    return sc
CASES = [("fox-watercolor", "a fox in the snow", ["Watercolor", "Serene", "Golden hour"]),
         ("anime-rooftop", "a girl with a sword on a rooftop at night", ["Anime", "Neon light", "Vibrant"]),
         ("pixel-knight", "a knight standing in front of a castle", ["Pixel art", "Medieval", "Warm"]),
         ("oil-lighthouse", "an old lighthouse on a cliff above the sea", ["Oil painting", "Impressionism", "Dramatic", "Moonlight"]),
         ("photo-cafe", "a woman reading a book in a cafe", ["Photo", "Window light", "Cozy", "35mm film", "Shallow depth of field"]),
         ("comic-street", "a city street in the rain", ["Comic book", "Cyberpunk", "Teal & orange", "Low angle"])]
ok = 0
for slug, words, look in CASES:
    names, notes = looks.normalize(look)
    prompt = looks.assemble(words, names)
    print(f"\n[{slug}] {looks.SEP.join(names)}  ({len(prompt)} chars){'  notes: ' + '; '.join(notes) if notes else ''}\n  prompt: {prompt}")
    try:
        st = call("image_make", {"prompt": prompt, "model": "venice/lustify-v8", "aspect_ratio": "1:1", "name": f"looks-{slug}",
                                 "negative_prompt": picture.NO_TEXT, "category": "ailab", "task": "looks-proof"})
        end = time.time() + 150
        while time.time() < end:
            j = call("job_get", {"key": st["key"]})
            if j["state"] != "running": break
            time.sleep(2)
        if j["state"] != "done":
            print("  FAILED:", str(j.get("error"))[:300]); continue
        r = j["result"]; f = f"{out}/{slug}.png"; open(f, "wb").write(base64.b64decode(r["b64"]))
        print(f"  OK {r['model']} ${r['usd']} {r['ms']} ms blurred={r.get('blurred')} → {f}"); ok += 1
    except Exception as e:                                         # noqa: BLE001 — report and carry on
        print("  ERROR:", e)
print(f"\n== {ok}/6 made · ailab spent today: ${M._ledger().spent_today_category('ailab'):.4f}")
PY
echo "== report: $OUT/report.txt"
