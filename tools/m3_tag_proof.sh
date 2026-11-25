#!/usr/bin/env bash
# 🏷 local pictures M3 tags proof (2026-11-24): does a tag prompt fix the anime miss (closed umbrella, no rain, park bench)?
# Same idea + same seed, 3 prompts × 2 anime models on gandalf's card: sentence (before) · rules tags · writer-style tags.
# The writer-style tags here are a fixed hand-written line (what the Lab's writer is asked to produce) — the live writer
# is checked in the Lab itself (🏷 line on an Anime picture). $0, ~4–5 min.
# Run on gandalf:  bash ~/ailab/tools/m3_tag_proof.sh   → ~/hermes-data/_scratch/local_m3_tags/<model>_<kind>.png + report.txt
set -u
OUT="$HOME/hermes-data/_scratch/local_m3_tags"; mkdir -p "$OUT"
cd "$HOME/hermes" || exit 1
systemctl --user is-active hermes-comfy.service >/dev/null || systemctl --user restart hermes-comfy.service
PYTHONUNBUFFERED=1 PYTHONPATH="$HOME/hermes:$HOME/ailab" python3 - "$OUT" <<'PY' 2>&1 | tee "$OUT/report.txt"
import base64, sys, time
from forge.projects import mcp_server as M
from ailab import looks, tag_prompt as T
out = sys.argv[1]
ctx = M.ctx_for("builder", "ailab", category="ailab")
def call(n, a):
    r = M.call_tool(n, a, ctx); sc = r.get("structuredContent") or {}
    if r.get("isError"): raise RuntimeError(f"{sc.get('code')}: {sc.get('message')}")
    return sc
MINE, LOOK, SEED = "a girl with a red umbrella at a rainy bus stop", ["Anime", "Serene"], 20261124
BASE_NEG = looks.negative(LOOK, "text, words, letters, watermark, signature, logo")
LW = [w for part in looks.parts(LOOK) for w in part]
HAND = T.clean("1girl, solo, standing, holding umbrella, open umbrella, red umbrella, umbrella over head, rain, raining, "
               "wet ground, puddle, bus stop, bus stop sign, street, city, overcast, cloudy sky, full body") + [w.lower() for w in LW]
print("seed", SEED, "· Look words:", LW)
for model in ("local/illustrious-xl-v0.1", "local/pony-v6-xl"):
    short = model.split("/")[-1].split("-")[0]
    for kind, prompt, neg in [("sentence", looks.assemble(MINE, LOOK), BASE_NEG),
                              ("rules", T.build(model, T.rules(MINE, LW), MINE), T.negative(model, BASE_NEG)),
                              ("tags", T.build(model, HAND, MINE), T.negative(model, BASE_NEG))]:
        print(f"\n[{short} · {kind}] {prompt}")
        t0 = time.time()
        try:
            st = call("image_make", {"prompt": prompt, "model": model, "name": "m3-tags", "negative_prompt": neg, "seed": SEED,
                                     "aspect_ratio": "3:4", "category": "ailab", "task": "m3-tags-proof"})
            while True:
                j = call("job_wait", {"key": st["key"], "max_s": 5})
                if j.get("state") != "running" or time.time() - t0 > 600: break
        except RuntimeError as e:
            print("  FAIL", e); continue
        if j.get("state") == "done":
            f = f"{out}/{short}_{kind}.png"; open(f, "wb").write(base64.b64decode(j["result"]["b64"]))
            print(f"  OK ~{round(time.time()-t0)} s (5 s steps) · ${j['result']['usd']} · {f}")
        else:
            print("  FAIL", j.get("state"), (j.get("error") or {}).get("message"))
print("\ndone — tell Claude it finished (it reads report.txt and the 6 pictures itself)")
PY
