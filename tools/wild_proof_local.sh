#!/usr/bin/env bash
# 🎛 Wild on local SDXL (2026-11-24): the 4 real Wild batch prompts (same task as the Lustify batch, dial 90) → SDXL base on
# gandalf's card. $0, ~4 min. Run on gandalf:  bash ~/ailab/tools/wild_proof_local.sh [model-id]
# Pictures: ~/hermes-data/_scratch/looks_proof/wild_local/<model>_<k>.png · report.txt beside them.
set -u
OUT="$HOME/hermes-data/_scratch/looks_proof/wild_local"; mkdir -p "$OUT"
cd "$HOME/hermes" || exit 1
PYTHONPATH="$HOME/hermes:$HOME/ailab" python3 - "$OUT" "${1:-sdxl-base-1.0}" <<'PY' 2>&1 | tee "$OUT/report.txt"
import sys
from pathlib import Path
from forge.studios.comfy import proof as P, workflows as WF
from forge.studios.comfy.models import MODELS
from ailab import batch, looks, picture
out, mid = Path(sys.argv[1]), sys.argv[2]
BASE = "a red fox sitting in fresh snow beside a glowing lantern, pine forest behind"
ANTI = "photograph, photo, photorealistic, realistic photo, 3d render"
_build = WF.build
def build(m, prompt, **kw):
    g = _build(m, prompt, **kw)
    if MODELS[m]["kind"] != "flux2": g["4"]["inputs"]["text"] = (g["4"]["inputs"]["text"] + ", " + ANTI).strip(", ")
    return g
P.WF.build = build
info = P._get(f"{P.URL}/object_info", 60)
print("ollama unloaded:", P.free_ollama())
for k in range(1, 5):
    task, shown, names = batch.picture_task(BASE, 90, k)
    d = out / f"{mid}_{k}"; d.mkdir(exist_ok=True)
    print(f"\n[{k}] {shown}\n{task}")
    r = P.run_one(P.URL, mid, task, info, d)
    print(f"  {'ok' if r['ok'] else 'FAIL'} {r.get('seconds','-')} s" + ("" if r["ok"] else f" {r['error']}"), flush=True)
print(f"\ndone · $0 · {out}")
PY
