# HANDOFF 2026-11-24 — AI Lab remodel M1 (Make | Stage) + Library + prompt improve cycle + uncensored default

Scott: "the Ai lab needs a layout remodel. there is too much going on with the workspace … a smooth and obvious way to
confirm a build is done, save to project, clear slate … repeat." Then: "i want my prompts to get an improvement cycle and
to steer the models to fully uncensored as default. i will have to choose censorship." Then: "easy access to a library of
content built so far in the individual project folders." Throw away = **hide, recoverable 30 days** (his pick 1).

## Built (M0 + M1) — NOT committed
Files: `ailab/web/index.html`, `ailab/server.py`, `ailab/preview.py`, `tests/test_remodel_m1.py` (new), this doc.
**Why uncommitted:** index.html already carried other sessions' uncommitted hunks (model sweep, self-edit guard) and 4 of my
hunks overlap them — HEAD + mine alone does not apply. server.py / preview.py apply clean but were held back so the tree
stays coherent. My exact diffs: `~/hermes-data/_tmp/remodel/page.patch`, `server.patch` (before-copies beside them).

- **Two zones.** `PANES = ["agent","code"]`: 🤖 Make (≈⅓) | 👀 Stage (≈⅔). Still resizable/swappable (`wblayout2`).
- **Make:** task box · 🪄 Improve my prompt · one chip row (collapsed everywhere, not only phones) · ▶ Start (⏹ Stop shows
  only while running) · status line · ⚙️ Options fold (provider, model, legend, 🔓 toggle, ❓ Ask me first) · step log · 🧰 tools.
  Make column before typing: was ~30 controls, now 6 (box, improve, chip, start, options, tools).
- **Stage:** result once (stage card / Done line, picture/video big, Before|Now, robot test) → `stageExtra` (▶ Go on, batch
  grid, 📦 Files made fold, ✏️ Change it — all moved from the left pane) → sticky **🆕 Start new** bar ("already saved …
  in 📚 Library") → ✨ starters (only while empty: Idea→prompt, Show & change, Change hermes/ailab, goal starters) →
  approvals (`changes`) → 📚 Library → 📦 Make it an app → 🔎 Details fold (file list, editor/preview, run output).
- **📚 Library** (`libraryBox`): every picture / video / writing / page in the project folder, newest first (`mtime` added
  to `preview.list_root`), filter chips, 12 tiles + "+N", tap → opens big in place with ⬇ ⤢ ✖ and 📍 path. Refreshes when a run finishes.
- **🪄 Improve cycle:** `/api/agent/rephrase` `mode:"prompt"` (+ `previous`, `fix`, `ctypes`). `IMPROVE_SYS` keeps every
  word, adds only what the kind (video / image / text / build) is missing. Writers: 🔓 picture writers first, then his model,
  then prompt writer. Card: ✍️ Yours · 🪄 Improved (editable) · ✓ Use it ⭐ · 🔁 Again · ✏️ Fix it · ✗ Keep mine. Cap $0.10/round.
- **🔓 Uncensored default:** `artonly` defaults ON (filtered models hidden until he unticks); first-time model = first 🔓;
  💡 hint ranks 🔓 first for every kind of work; the "use claude-sonnet for linked folders" hint only shows after he unticks.
  Build task on a 🔓 model → calm note: many can't run build tools; untick 🔓 in ⚙️ Options to let a filtered coder do the code.

## Verified (cloud container, Chrome via Playwright — not gandalf)
- Page loads 1600px + 390px, no page errors; 2 panes 521/1043 px; phone tabs 🤖 Make / 👀 Stage.
- Faked run (running → done picture run): stage card once, Done line once, 0 result cards in the left pane, Change-it text
  survives polling, 🪄 card → ✓ Use it fills the box, 🆕 Start new clears and brings starters back.
- Tests in the device VM: 450 pass / 26 fail → the same 26 that failed before I touched anything (srt/robot/env + other
  sessions' work; list in `_tmp/remodel/baseline_fail.txt`) + 0 new. 8 new tests pass.

## NOT verified
- Anything on gandalf: real run through the new Stage, Library thumbnails (preview sandbox was missing in the container, so
  tiles drew but images 503'd), live 🪄 improve call, 🔓 default on each provider.
- **Argus touch test owed** (phone-usable UI change).
- Builds on 🔓 models may stall (known: most can't call tools). Today that is a note, not a fix — see M2b.
- Library reads the first 500 files by path; a huge project could miss its newest.

## Scott on gandalf
1. Restart the Lab (desktop icon) — the server half (improve mode, file dates) needs it. The page half is live on refresh.
2. Open a project → check: two panes, ⚙️ Options, 📚 Library shows your pictures/videos, 🪄 Improve, run one picture → 🆕 Start new.

## Next (each stops at its gate)
- **M2 Keep loop:** ✅ Keep & start new ⭐ · ✏️ Change it · 🗑 Throw away (hidden 30 days, undo); kept/thrown saved per run; "Saved as #N".
- **M2b Choose-censorship card:** build needs tools + 🔓 on → card: 🔓 writer does words/art + 🔒 coder writes code from the brief only / stay 🔓 / cancel. Never silent.
- **M3 Shelf:** numbered kept items, ✏️ Change this from a Library item, compare two; kept/thrown prompts feed the 🪄 improver.
- **M4 Wrap:** 🏁 Project done, Argus touch test, commit once the other sessions' index.html work lands.

Continue: `continue AI Lab remodel M2 from the 2026-11-24 handoff`
