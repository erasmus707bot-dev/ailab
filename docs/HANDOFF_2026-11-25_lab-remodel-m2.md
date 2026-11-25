# HANDOFF 2026-11-25 — AI Lab remodel M2 (Keep loop) + M2b (choose-censorship card)

Scott picked **1: M2 + M2b together**. Builds on `docs/HANDOFF_2026-11-24_lab-remodel-m1.md`.

## Built — NOT committed (same reason as M1: index.html carries other sessions' overlapping uncommitted hunks)
Files: `ailab/shelf.py` (new), `ailab/server.py`, `ailab/web/index.html`, `tests/test_remodel_m2.py` (new), this doc.
My diffs: `~/hermes-data/_tmp/remodel/page_m2.patch`, `server_m2.patch` (M1: `page.patch`, `server.patch`).

- **Finish bar under every result:** ✅ Keep & start new ⭐ · 🗑 Throw away · 🆕 Just clear (decide later). All three end on a
  clean slate in the same project; the status line says what happened ("✅ Kept as #3 in <project>").
- **Keep** → `POST /api/shelf/keep` → next number in `<project>/.shelf/shelf.json`. Same run twice = same number.
- **Throw away** → `POST /api/shelf/toss` → files the run CREATED move to `<project>/.shelf/trash/<run>/` (hidden, not
  deleted); edits to files that already existed go back through the run's own undo. A kept run that is thrown away loses its number.
- **↩ Bring back** → `POST /api/shelf/restore` for 30 days; never overwrites (a taken name returns as "name (restored)").
  After 30 days the hidden copy is removed (checked whenever the shelf is read).
- **📚 Library:** `#N` badge on kept things, ✅ Kept filter chip, 🗑 Thrown away list with days left and ↩ Bring back.
- **M2b:** ▶ Start on a build (any non-art chip, or build-looking words) with a 🔓 model selected and 🔓-only on → card:
  🔓 Stay uncensored ⭐ · 🔒 Filtered coder, this run only: <model> · ✖ Cancel · ☐ don't ask again in this project (always
  stay 🔓). The filtered pick is sent for that one run; his saved model is not changed. Art prompts get no card.

## Verified
- Browser (cloud container, Chrome/Playwright, shelf + run + model list faked): Keep → "Kept as #1", badge + ✅ Kept chip,
  starters back; Throw away → list shows it, ↩ clears it; build prompt → card, nothing starts until a pick; coder pick sends
  `qwen-coder` while the saved model stays 🔓; art prompt → no card. No page errors.
- Device VM tests: 476 pass / 7 fail, 0 new (all 7 were failing before M1). 7 new tests: numbering, hide-only-created,
  bring back, no overwrite, 30-day purge, path safety, page wiring.

## NOT verified
- Anything on gandalf with a real run. Argus touch test owed (M1 + M2).
- Keep / Throw away need the run in the Lab's memory: after a Lab restart an old finished run may answer "can't find that
  run" (not checked which runs come back).
- Thrown-away pictures/videos the Lab also saved to the Hermes Gallery / Media Studio stay there — only the project copy is hidden.
- Bring back does not re-apply undone edits to old files (only created files return).
- Whether a filtered coder + the 🎭 art split keeps his words intact on a real build.

## Scott on gandalf
1. Restart the Lab (desktop icon) — shelf routes are server-side.
2. Make a picture → ✅ Keep → see #1 in 📚 Library. Make another → 🗑 Throw away → 🗑 list → ↩ Bring back.
3. Pick 🌐 Website, type a build, ▶ Start → the 🔓/🔒 card.

## Next
- **M3 Shelf:** ✏️ Change this from any Library item; compare two; kept/thrown prompts feed the 🪄 improver.
- **M4 Wrap:** 🏁 Project done, Argus touch test, commit when the other sessions' index.html work lands.

Continue: `continue AI Lab remodel M3 from the 2026-11-25 handoff`
