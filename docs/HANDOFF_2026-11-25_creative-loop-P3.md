# HANDOFF 2026-11-25 — Creative Loop Phase 3 (Lab side + MCP Batch 1)

**Prompt:** `~/ailab/docs/CREATIVE_LOOP_BUILD_2026-11-25.md` · **Design:** `~/hermes/docs/CREATIVE_LOOP_DESIGN.md` · **P2:** `HANDOFF_2026-11-25_creative-loop-P2.md`

## Commits
- hermes `936a9240` — `forge/projects/mcp_creative.py` (creative_job_plan/run/get, creative_jobs, creative_rate,
  creative_estimate, creative_spend_ok [owner PIN], trust_list) · `forge/creative/executors.py` (lab.image, lab.recreate,
  lab.video, proready.primitive, lab.code_effect) · planner `persist=` + no double spend record · 3 lines in mcp_server.py
- ailab `9ca34c6` — `ailab/loop.py` · `ailab/web/loop.html` (🔁 page: plan, ✍️ write primitive/effect, ▶ run, 💲 PIN tap,
  ✅/🔁/❌ + reason chips, A/B fold) · 21 lines server.py · 1 line index.html (🔁 header link)
- Shared files committed with **own lines only** (HEAD-copy blob + private index). Other sessions' edits in
  mcp_server.py / server.py / index.html left uncommitted for them.

## ⚠ Overlap to tell the motion-presets session
P2 commit `f1cd002c` (hermes) swept in their uncommitted `mcp_server.py` hunks (`_mot`, motion_pull/motion_get,
pose_image on image_make). HEAD imports `forge.projects.mcp_motion` lazily, and that file is still untracked → they
should commit `mcp_motion.py` (+ its tests) soon. No history rewritten.

## Tests
- hermes: `python3 -m pytest -q forge/creative/tests forge/projects/tests/test_mcp_server.py` → 62 passed
- ailab: full suite 653 passed (incl. 7 new in tests/test_loop.py)

## Not done / UNVERIFIED
- **Hermes review-space UI** for the creative queue (A/B picks, ratings, hold proposals) + **Settings → Trusted tasks**
  toggles: lives in `dist/hermes-local/hermes_local/dashboard.py` (live runtime) → needs restart + Argus touch test. Own module.
- **Restarts needed** before the page works: Hermes MCP HTTP server (new tools) and the Lab.
- **Argus touch test** of `/loop` not done (cloud session can't).
- Near-copy threshold `NEAR_COPY_BITS=10` (dHash) untuned; Pillow missing → recreate stays reference-only (fail closed).
- Hermes pull/edit methods = Phase 4; router skips them until built. ProReady `proready_*` tools = Phase 5.
- **Real low-cost image job** by Scott — command below.

## Scott's terminal test (one real picture, ~cents)
```bash
cd ~/hermes && python3 - <<'PY'
from forge.creative import jobspec as JS, planner as P, route as RT, library, executors as EX
from forge.projects import mcp_creative as CR
s = JS.new_job("Flat labelled diagram of the 7 OSI layers", project="proready", field="aplus", asset_type="image", tags=["osi"])
p = JS.new_piece(1, "draw the 7 OSI layers as stacked labelled bars")
pr = CR.prices(s); print("price table:", pr)
RT.apply(p, {"side": "lab", "method": "lab.image", "why": "terminal test", "est_usd": pr.get("lab.image", 2.0)})
s["pieces"] = [p]; P.save(s)
s = P.run_piece(s, 1, library(), EX.execute, prices=pr)
print(s["id"], s["pieces"][0]["state"], s["pieces"][0].get("asset") or s["pieces"][0].get("blocked") or s["pieces"][0].get("fail"))
PY
```
Expect `done` + `ai-lab/…png`. Empty price table → $2 fallback → waits for a tap (that's the guard working).

## Next
Phase 4 — Hermes scavenger + editor (Openverse/Wikimedia/NASA pulls with licence capture, edit pipeline, Haiku tags).
**Model: Sonnet.** Optional before it: P3b Hermes review-space UI + Trusted tasks toggles (Opus).

## No night tail
Phase 4 sits behind the gate "Proceed to Phase 4? (model: Sonnet)".

**Continue:** `continue Creative Loop Phase 4 from the 2026-11-25 P3 handoff`
