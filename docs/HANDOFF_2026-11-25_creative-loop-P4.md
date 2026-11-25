# HANDOFF 2026-11-25 — Creative Loop Phase 4 (Hermes scavenger + editor)

**Prompt:** `~/ailab/docs/CREATIVE_LOOP_BUILD_2026-11-25.md` · **P3:** `HANDOFF_2026-11-25_creative-loop-P3.md`

## Commit
- hermes `e563afaf` — `forge/creative/` `scavenge.py` · `edit.py` · `tagging.py` · `hermes_exec.py` (new) · `executors.py` (+2 lines: merges `HERMES_EXECUTORS`) · `tests/test_phase4.py` (new) · `tests/test_phase3.py` (pins Hermes methods off, so its Lab-path tests stay Lab-path)

## Built
- **Pull:** openverse · wikimedia · nasa (search) · web (one https file URL; robots.txt honoured, no logins). Each pull saves source URL + TASL + licence tag. Open licence (cc0/pdm/by/by-sa/nasa) → `open`, `tasl_verified=False` (public surfaces stay blocked until the TASL/Guardian check passes). Everything else, and all `web` → `personal_use`. Mode B: web pull refused; non-open pull → `reference_only`.
- **Edit:** crop · resize · recolor (ProReady palette) · label · compress_image (webp/jpg/png) · svg_optimize (refuses scripts) · trim · compress_video (ffmpeg) · `fit_budget` (offline-size budget, default 300 KB when `offline`). Output licence = strictest parent (`license.derive`).
- **Tags:** Haiku text-only tags + alt-text DRAFT (never for `sensitive` jobs).
- Executors registered for `hermes.pull.*`, `hermes.edit.image/svg/video`, `hermes.convert` → router now picks them (rule order: Hermes before Lab).

## Tests
`python3 -m pytest -q forge/creative/tests forge/projects/tests/test_mcp_server.py` → **74 passed** (VM, py3.10, Pillow + ffmpeg). Includes the round trip: Hermes pulls a diagram → Lab step (mocked) animates → Hermes compresses; licence + TASL carry through, public surface still blocked, 3 recipe-log entries.

## ⚠ UNVERIFIED / owed on gandalf (shell has no network)
1. Live endpoints + field names for Openverse, Wikimedia, NASA are from memory. Run: `cd ~/hermes && python3 -m forge.creative.scavenge openverse "osi model"` (and `wikimedia`, `nasa`) → expect a path, licence, TASL.
2. Set `HERMES_CREATIVE_TAGGER_MODEL` (Haiku tier) in the Hermes env, or tags are skipped (pull still works).
3. Palette in `edit.PALETTE` is a placeholder until Phase 5 reads ProReady's real tokens.
4. `web` pull needs a direct https file URL — there's no web search engine adapter yet.
5. Behaviour change to know: with Hermes pulls available, the planner now tries a pull before generating an image/video (cheapest-first). A bad pull falls back only after Scott rates it or the piece fails; no auto-fallback yet.
6. Restart the Hermes MCP server so the new executors load; no new MCP tools were added.

## Next
Phase 5 — Project connectors (ProReady drafts into admin review, Site Studio, Automation Studio, ERASMUS read-only until 2027-01-01). **Model: Opus.** Optional first: P3b review-space UI + Trusted tasks toggles.

**Gate:** "Proceed to Phase 5? (model: Opus)"
**Continue:** `continue Creative Loop Phase 5 from the 2026-11-25 P4 handoff`

## No night tail
Phase 5 sits behind the gate.
