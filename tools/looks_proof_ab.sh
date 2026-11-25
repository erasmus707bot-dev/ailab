#!/usr/bin/env bash
# 🎨 Looks M4b (2026-11-24): the M4 proof drew "watercolor" as a photo and "comic book" as a cinematic still on Lustify v8.
# A/B, 4 pictures (~$0.04), both with the new anti-photo negative:  A = Scott's words first (current order)
#                                                                    B = medium/style first, then Scott's words
# Writes to ~/hermes-data/_scratch/looks_proof/ab/. Run on gandalf:  bash ~/ailab/tools/looks_proof_ab.sh
set -u
OUT="$HOME/hermes-data/_scratch/looks_proof/ab"; mkdir -p "$OUT"
cd "$HOME/hermes" || exit 1
PYTHONPATH="$HOME/hermes:$HOME/ailab" python3 - "$OUT" <<'PY' 2>&1 | tee "$OUT/report.txt"
import base64, sys, time
from forge.projects import mcp_server as M
from ailab import looks, picture
out = sys.argv[1]
ctx = M.ctx_for("builder", "ailab", category="ailab")
def call(n, a):
    r = M.call_tool(n, a, ctx); sc = r.get("structuredContent") or {}
    if r.get("isError"): raise RuntimeError(f"REFUSED {n} {sc.get('code')} - {sc.get('message')}")
    return sc
CASES = [("fox-watercolor", "a fox in the snow", ["Watercolor", "Serene", "Golden hour"]),
         ("comic-street", "a city street in the rain", ["Comic book", "Cyberpunk", "Teal & orange", "Low angle"])]
for slug, words, look in CASES:
    head, tail = looks.parts(look)
    neg = looks.negative(look, picture.NO_TEXT)
    for v, prompt in (("A", looks.assemble(words, look)),
                      ("B", f"{', '.join(head)}. {words}. {', '.join(tail)}.")):
        print(f"\n[{slug}-{v}] {prompt}\n  negative ends: …{neg[-60:]}")
        try:
            st = call("image_make", {"prompt": prompt, "model": "venice/lustify-v8", "aspect_ratio": "1:1", "name": f"looks-{slug}-{v}",
                                     "negative_prompt": neg, "category": "ailab", "task": "looks-proof"})
            end = time.time() + 150
            while time.time() < end:
                j = call("job_get", {"key": st["key"]})
                if j["state"] != "running": break
                time.sleep(2)
            if j["state"] != "done": print("  FAILED:", str(j.get("error"))[:300]); continue
            r = j["result"]; f = f"{out}/{slug}-{v}.png"; open(f, "wb").write(base64.b64decode(r["b64"]))
            print(f"  OK ${r['usd']} {r['ms']} ms → {f}")
        except Exception as e:                                     # noqa: BLE001
            print("  ERROR:", e)
print(f"\n== ailab spent today: ${M._ledger().spent_today_category('ailab'):.4f}")
PY
