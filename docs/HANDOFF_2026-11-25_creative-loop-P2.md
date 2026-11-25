# HANDOFF 2026-11-25 — Creative Loop Phase 2 (shared spine) DONE

**Prompt:** `~/ailab/docs/CREATIVE_LOOP_BUILD_2026-11-25.md` · **Design:** `~/hermes/docs/CREATIVE_LOOP_DESIGN.md`
**§9 answers (Scott, 2026-11-25):** all 7 recommendations — Mode A std + Mode B per job · $0.50/job threshold ·
✅ Keep / 🔁 Redo / ❌ Wrong + reason chips · explore on (1 in 10) · Three.js lazy + 2D fallback · 16 primitives · mount ~/SonoVault.

## Commits (hermes)
- `eb962d0d` forge/creative spine + 24 tests
- `f1cd002c` wiring: `Library.log_event` (non-lifecycle only) · `recipes_search` adds side/runs/q/avg_usd/avg_s ·
  licence choke 1 = `review.publish` refuses non-portfolio assets · choke 2 = Site Studio `check()` reads `.creative/assets.json`
- `0e193786` design doc (status line updated after, uncommitted 1-line)

## Built (`~/hermes/forge/creative/`)
jobspec (DAG, cycle check) · license (`may_use`, fail-closed, derive=strictest, recreate) · estimate (unknown → $2 high) ·
recipelog (Library events `run`/`rating`, q prior 0.5×2, rating 2×) · ratings · route (filters → rule order → score → explore,
hold *proposals* only) · planner (3-good-runs reuse at $0, env-named model, sensitive → local or wait) + `run_piece`
(estimate → threshold/trust → spend_check → run → spend_record → log) · trust (all off; erasmus.arm/delete have no toggle) ·
inbox (creative review queue jsonl) · connectors/base (contract + licence choke 3) + projects.json.

## Tests
- `python3 -m pytest -q forge/creative/tests` → 24 passed
- Regression: ailab review + mcp_server 41 ✓ · studios library users 58 ✓ · sitestudio static/check/publish 79 ✓
- `test_owner_render.py` can't import `fastapi` in the Cowork VM — env, not this change.

## Not done / UNVERIFIED
- `HERMES_CREATIVE_PLANNER_MODEL` not set on gandalf → hosted planning refuses with a plain message until set.
- No `settings.json` yet → code defaults (the §9 answers) apply.
- ProReady render-side licence check = Phase 5/6. ~/SonoVault still not mounted.
- Creative inbox not shown in Needs You yet (Phase 3 UI).

## Next
Phase 3 — AI Lab side + MCP Batch 1 (`creative_job_plan/run/get`, `creative_rate`, `creative_estimate`, `trust_list`,
`proready_*`), rating buttons, Mode B recreate flow. **Model: Opus.**

## No night tail
Phase 3 sits behind the gate "Proceed to Phase 3? (model: Opus)" — the night must not open a gate Scott hasn't.

**Continue:** `continue Creative Loop Phase 3 from the 2026-11-25 P2 handoff`
