#!/usr/bin/env bash
# 🎨 Looks M4c (2026-11-24): Lustify v8 still draws "watercolor" as a photo (A/B, 4 pictures). Try the local models on
# gandalf's card — $0. Watercolor fox + comic street (same Looks as the A/B), Scott's-words-first order (A),
# anti-photo negative added to every SDXL negative. 8 pictures, ~5 min. Run on gandalf:  bash ~/ailab/tools/looks_proof_local.sh
# Pictures: ~/hermes-data/_scratch/looks_proof/local/<case>/<model>.png  ·  report.txt beside them.
set -u
OUT="$HOME/hermes-data/_scratch/looks_proof/local"; mkdir -p "$OUT"
cd "$HOME/hermes" || exit 1
PYTHONPATH="$HOME/hermes:$HOME/ailab" python3 - "$OUT" "$@" <<'PY' 2>&1 | tee "$OUT/report.txt"
import sys
from pathlib import Path
from forge.studios.comfy import proof as P, workflows as WF
from forge.studios.comfy.models import MODELS
from ailab import looks, picture
out = Path(sys.argv[1]); only = [m for a in sys.argv[2:] for m in a.split(",") if m]
CASES = [("fox-watercolor", "a fox in the snow", ["Watercolor", "Serene", "Golden hour"]),
         ("comic-street", "a city street in the rain", ["Comic book", "Cyberpunk", "Teal & orange", "Low angle"])]
ANTI = "photograph, photo, photorealistic, realistic photo, 3d render"
_build = WF.build
def build(mid, prompt, **kw):                                   # SDXL: add the anti-photo words to the model's negative
    g = _build(mid, prompt, **kw)
    if MODELS[mid]["kind"] != "flux2":
        g["4"]["inputs"]["text"] = (g["4"]["inputs"]["text"] + ", " + ANTI).strip(", ")
    return g
P.WF.build = build
try:
    info = P._get(f"{P.URL}/object_info", 60)
except Exception as e:                                          # noqa: BLE001
    print(f"ComfyUI isn't answering at {P.URL} ({e}). Check: systemctl --user status hermes-comfy"); sys.exit(1)
ids = only or [m for m in ("flux2-klein-4b", "illustrious-xl-v0.1", "sdxl-base-1.0", "pony-v6-xl") if m in P.installed()]
print("models:", ", ".join(ids), "| ollama unloaded:", P.free_ollama())
rows = []
for slug, words, look in CASES:
    prompt = looks.assemble(words, look); d = out / slug; d.mkdir(exist_ok=True)
    print(f"\n[{slug}] {prompt}")
    for mid in ids:
        r = P.run_one(P.URL, mid, prompt, info, d); rows.append((slug, r))
        print(f"  {MODELS[mid]['label']:<25} {'ok' if r['ok'] else 'FAIL':<5} {r.get('seconds','-')!s:>6} s  "
              f"peak {r.get('peak_vram_mb','-')} MB" + ("" if r["ok"] else f"  {r['error']}"), flush=True)
print(f"\n{sum(r['ok'] for _, r in rows)}/{len(rows)} ok · $0 · pictures under {out}")
PY
