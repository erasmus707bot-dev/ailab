#!/usr/bin/env bash
# 2026-11-25 🦴 Anatomy study test (Scott). M2: local card only, Figure tab; optional arg = parts, e.g. face,hips,stomach. Makes 2 pictures per Study preset × 2 mediums (Photo, Anatomy atlas)
# on Venice lustify-v8 AND the local card (Juggernaut XL for photo, SDXL base for atlas). Venice ≈ $0.40; stops at $1.
# Run on gandalf:  nohup bash ~/ailab/tools/anatomy_study.sh > ~/hermes-data/_scratch/anatomy_study/run.log 2>&1 &
set -u
OUT="$HOME/hermes-data/_scratch/anatomy_study/$(date +%Y%m%d-%H%M)"; mkdir -p "$OUT"
cd "$HOME/hermes" || exit 1
python3 - "$OUT" "${1:-}" <<'PY'
import base64, json, sys, time
sys.path.insert(0, "."); sys.path.insert(0, "../ailab")
from forge.projects import mcp_server as M
from ailab import looks
from ailab.picture import NO_TEXT
out = sys.argv[1]; ctx = M.ctx_for("builder", "ailab", category="ailab")
L = M._ledger(); start = L.spent_today_category("ailab"); CAP = 1.00
def call(n, a):
    r = M.call_tool(n, a, ctx); sc = r.get("structuredContent") or {}
    return (None, sc) if r.get("isError") else (sc, None)
cat = looks.catalog(); parts = [i["n"] for t in cat["tabs"] if t["id"] == "study" for i in t["items"]]
mediums = {"Photo": ("local/juggernaut-xl-v9",), "Anatomy atlas": ("local/juggernaut-xl-v9",)}
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else []
FIG = {"face": "Male figure", "shoulders": "Male figure"}
rows = []
for part in parts:
    if ONLY and part.split()[0].lower() not in ONLY: continue
    for med, models in mediums.items():
        names = [med, FIG.get(part.split()[0].lower(), "Female figure"), part]
        prompt, neg = looks.assemble("figure study", names, ""), looks.negative(names, NO_TEXT)
        for model in models:
            for v in (1, 2):
                if model.startswith("venice/") and L.spent_today_category("ailab") - start >= CAP:
                    print("CAP reached — skipping Venice"); continue
                tag = f"{part.split()[0].lower()}_{'photo' if med == 'Photo' else 'atlas'}_{model.split('/')[-1]}_{v}"
                st, err = call("image_make", {"prompt": prompt, "negative_prompt": neg, "model": model, "aspect_ratio": "3:4",
                                              "name": tag, "category": "ailab", "task": "anatomy-study"})
                row = {"tag": tag, "part": part, "medium": med, "model": model, "prompt": prompt, "negative": neg}
                if err: row["error"] = f"{err.get('code')}: {err.get('message')}"; print("REFUSED", tag, row["error"]); rows.append(row); continue
                end, j = time.time() + 300, {}
                while time.time() < end:
                    j, e2 = call("job_get", {"key": st["key"]})
                    if e2 or j.get("state") != "running": break
                    time.sleep(2)
                if j and j.get("state") == "done" and j["result"].get("b64"):
                    f = f"{out}/{tag}.png"; open(f, "wb").write(base64.b64decode(j["result"]["b64"]))
                    row.update(file=f, usd=j["result"].get("usd"), ms=j["result"].get("ms"), blurred=j["result"].get("blurred"))
                    print("OK", tag, row["usd"], row["ms"])
                else:
                    row["error"] = json.dumps((j or {}).get("error"))[:300]; print("FAILED", tag, row["error"])
                rows.append(row)
                json.dump(rows, open(f"{out}/manifest.json", "w"), indent=1)
print(f"DONE {len([r for r in rows if r.get('file')])}/{len(rows)} pictures · Venice spent ${L.spent_today_category('ailab') - start:.2f} · {out}")
PY
