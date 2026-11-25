#!/usr/bin/env bash
# 🏠 local pictures M3 proof (2026-11-24): the Lab's picture route picks the model for 3 Looks (Photo · Anime · Watercolor)
# from Hermes's real image_models list, then makes each picture on gandalf's card through image_make. $0, ~2 min.
# Run on gandalf:  bash ~/ailab/tools/m3_route_proof.sh   → ~/hermes-data/_scratch/local_m3/<kind>.png + report.txt
set -u
OUT="$HOME/hermes-data/_scratch/local_m3"; mkdir -p "$OUT"
cd "$HOME/hermes" || exit 1
systemctl --user is-active hermes-comfy.service >/dev/null || systemctl --user restart hermes-comfy.service
PYTHONPATH="$HOME/hermes:$HOME/ailab" python3 - "$OUT" <<'PY' 2>&1 | tee "$OUT/report.txt"
import base64, sys, time
from types import SimpleNamespace as NS
from forge.projects import mcp_server as M
from ailab import looks, picture_route as R
from ailab.mcp_client import HermesRefused
out = sys.argv[1]
ctx = M.ctx_for("builder", "ailab", category="ailab")
class Hermes:
    def call(self, n, a=None):
        r = M.call_tool(n, a or {}, ctx); sc = r.get("structuredContent") or {}
        if r.get("isError"): raise HermesRefused(sc.get("code", "?"), sc.get("message", ""), sc.get("fix", ""))
        return sc
run = NS(cfg={}, lab=NS(mcp=Hermes()))
print("first:", R.first(run), "· ready on the card:", sorted(R.ready(run)))
for look, prompt in [(["Photo", "Golden hour"], "an old fisherman mending a net on a wooden dock"),
                     (["Anime", "Serene"], "a girl with a red umbrella at a rainy bus stop"),
                     (["Watercolor"], "a fox sleeping under a pine tree in snow")]:
    plan = R.plan(run, look, "", "venice/lustify-v8", False)
    model = plan["models"][0]
    print(f"\n[{plan['kind']}] Look {' · '.join(look)} → {plan['models']}")
    if not model.startswith("local/"):
        print("  SKIP — no local model ready for this kind"); continue
    t0 = time.time()
    st = run.lab.mcp.call("image_make", {"prompt": looks.assemble(prompt, look), "model": model, "name": "m3-proof",
                                         "negative_prompt": looks.negative(look, "text, words, letters, watermark, signature, logo"),
                                         "aspect_ratio": "3:4", "category": "ailab", "task": "m3-proof"})
    while time.time() - t0 < 600:
        j = run.lab.mcp.call("job_wait", {"key": st["key"], "max_s": 30})
        if j.get("state") != "running": break
    if j.get("state") == "done":
        f = f"{out}/{plan['kind']}.png"; open(f, "wb").write(base64.b64decode(j["result"]["b64"]))
        print(f"  OK {round(time.time()-t0,1)} s · ${j['result']['usd']} · {f} · {R.keys_line(run, model)}")
    else:
        print("  FAIL", j.get("state"), (j.get("error") or {}).get("message"))
print("\ndone · paste the lines above back to Claude")
PY
