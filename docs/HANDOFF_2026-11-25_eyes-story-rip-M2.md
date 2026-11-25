# HANDOFF 2026-11-25 — AI Lab 🎭 M2 Characters + references (prompt #1, built for prompt #2 R1)

## Shipped (ailab, uncommitted)
- `ailab/refs.py` (new) — 📌 cast strip: 1–4 reference pictures per project (`<project>/.shelf/refs.json`), only project
  pictures, deleted files drop off. `for_run()` → absolute paths (a sheet's own source wins). `queue()` puts reference-capable
  models first: `local/flux2-klein-4b` only if the plan already has a ready local model, `venice/qwen-edit-uncensored` only if the
  plan already allows Venice. 🎭 `sheet_task()` 5 views (front · side · three-quarter · back · face expressions). `side_by_side()`
  via ffmpeg (Lab stays zero-dependency). `same_face()` → 👁 "same face + hair?", "same clothes?".
- `picture.py` — sends `reference_images` to Hermes `image_make` on those models only; Hermes refusal (route off until the
  identity probe passes, bad path…) → one 🎭 "references not used — …" step and the same model again with words only. No
  reference-capable model → says so, words only. A forced model is never reordered.
- `batch.py` — `{"sheet": "<path>"}` batch = 5 views, dial 0, source as the reference; after: `same_faces()` scores each view
  and names drift (`🎭 same-face check: n of 5 views match — drifted: …`).
- `eyes.py` — `ask(run, raw, points, label)` split out of `check()` (behaviour unchanged).
- `server.py` — `GET /api/refs` · `POST /api/refs/pin|unpin`.
- `index.html` — 📚 Library: 🎭 Cast strip (thumbs + ✕), picture viewer `📌 Use as reference` / `📌 Reference ✓` and
  `🎭 Character sheet` (starts a 5-view sheet run through 🤖 Make).

## Not built
- Video switches `last_frame` / `motion_from_video` (off-by-default path kinds) — next to R3's level switch.
- Training / dataset builder — Gate 0 C1 = no trainer.

## Tests
- `tests/test_refs.py` 9 pass · full ailab suite **540 pass** (R2's "541" was a double count across split runs).

## Live — NOT run (shell can't reach ComfyUI / the Lab)
On gandalf:
1. `cd ~/hermes && python3 -m forge.projects.probe_identity` — proves `build_ref` nodes (`missing_nodes()`) and same-face on
   the local route. Pass → `~/hermes-data/settings/image_ref_flags.json` `{"local": true}` (Venice: `"venice": true` after its probe).
2. `systemctl --user restart hermes-mcp && systemctl --user restart ailab`.
3. Lab → a picture of a person → 📌 Use as reference → "her in a café", "her on a beach", "her at night", "her in the rain"
   (4 scenes) → faces hold. Then 🎭 Character sheet → 5 views + same-face line.

## Owed
- Probe + live check · Argus touch test (cast strip, viewer buttons) · commit.
- **Uncommitted** — same stack as M1/R2: `picture.py batch.py eyes.py server.py index.html` (and untracked `shelf.py`) carry the
  uncommitted model-sweep, self-edit-guard, remodel M0–M4 and video-look hunks. Clean new files: `ailab/refs.py tests/test_refs.py`.
- Night tail: none (uncommitted base).

Continue: `continue video rebuild + cast + styles + R&D from the 2026-11-25 build prompt #2` (next = R1 global cast).

## Live update 2026-11-25 07:28 (eyes session)
- ✅ Probe ran **$0, all local**: `probe_identity --go --only local --anchor local --vision-model local --skip-meshy`. FLUX.2 Klein anchor + 4 shots (front · side · back · smile), ~30 s each, peak card 5.7 GB. Judge `qwen3.5:4b`: **95 / 95 / 95 / 95**.
- ✅ Checked by eye (grid `~/hermes-data/assets/_probe/2026-11-25/local-flux2-klein-4b-grid.png`): same face, freckles, auburn hair, grey tee in all four. The identity holds.
- ✅ **Armed by Scott:** `~/hermes-data/settings/image_ref_flags.json` = `{"local": true}`.
- ⚠️ The 4b judge tops out at 95 and gave the same number four times — it confirms a match but **may not catch small drift**. Before trusting the 🎭 same-face line, test it once on a planted mismatch (two different people) and see it score low.
- Next: `systemctl --user restart hermes-mcp && systemctl --user restart ailab`, then live step 3 above (pin a picture → 4 scenes → 🎭 Character sheet).

## Live reference test 2026-11-25 09:15–09:19 (Claude, Lab via the built-in browser)
- Why the 07:43 try failed: `journalctl` shows a **local Wan 2.2 video job** (another session) took the card at 07:38:48, hit card-memory allocation failures at 07:43:03, and `hermes-comfy` stopped at 07:43:08 (14.3 GB RAM peak, no restart line). Scott restarted ComfyUI + the Lab.
- Pinned `a-girl-with-a-red-umbrella` (anime, kept) → "the same girl reading a book in a cozy cafe, sunny afternoon". The Lab was restarted mid-run by someone else → came back paused → ▶ Resume → **local/flux2-klein-4b with the reference, 104 s, $0**. 👁 100% match on the words.
- **By eye: partial hold.** Kept: anime look, dark hair with bangs, white collared shirt, dark skirt. Drifted: hair longer and lighter brown, face rounder/more polished. Good enough for "same character, new scene"; not a strict likeness.
- Note: the per-picture 👁 check compares words only. Same-face is checked only in 🎭 Character sheet runs. Pin removed again.
- 🎭 Character sheet live test still owed (5 pictures, ~8–10 min of card time).

## 🎭 Character sheet live test 2026-11-25 09:27–09:30 (Claude)
- Sheet of `a-girl-with-a-red-umbrella` (anime): 5 views, local FLUX.2 Klein + reference, ~30 s each, **$0**.
- 👁 same-face line: **"2 of 5 views match — drifted: three-quarter view, back view, close-up of the face"**. Checked by eye (`~/hermes-data/ailab/_pilot/sheet_check.jpg`): **correct**. Front + side kept her (anime, bob, white shirt, black skirt). Three-quarter and back became a photo-real woman; the "four expressions" view became six different real adults. The same-face check works and names drift honestly.
- Cause: the sheet prompt said only "Character sheet of the person in this picture … plain light-grey background" — no who, no art style, so the model read it as a photo shoot.
- 🐛 → fixed (uncommitted): `refs.describe()` names who is in the source first — his own words + Look line when the picture is on the shelf, else the local eyes' caption cut to the person + clothes ($0). `SHEET_WORDS` adds "the same art style"; the expressions view is one face, gentle smile. `batch.py` records "🎭 the sheet keeps: …". Tests: `test_refs.py` 11 pass; ailab suite **599 pass**.
- **Live after a Lab restart.** Re-run the sheet to confirm 4–5 of 5.

## 🎭 Sheet re-run with the fix 2026-11-25 09:40–09:47 (Claude)
- New step works: **"🎭 the sheet keeps: a girl with a red umbrella at a rainy bus stop · Look: Anime · Serene"** (his kept words, no vision call).
- 1st try (09:40): hermes-mcp went down during picture 2 and stayed down for 3–5 (someone restarted it). Retried.
- 2nd try: views 1–4 on local FLUX.2 Klein + reference, $0. **By eye (`_pilot/sheet_check2.jpg`): all 4 are her** — same anime style, long black hair, white blouse, dark pleated skirt; front · side · three-quarter · back all correct. Before the fix: 2 of 5.
- Side effect: her own words carry the red umbrella + rain into every view (not a plain background). Fine for a cast sheet; could strip scene words later.
- View 5 (face close-up): **ComfyUI "connection reset by peer" at 09:46 → fell back to venice/lustify-v8 without the reference, $0.01 → a photo-real stranger.** Same silent-fallback problem as before; in a sheet run a picture without the reference is useless.
- 👁 same-face check scored views 1–2 (same, 100) then stopped with no summary line and no error step. Cause not found from here (services were being restarted under the run). Owed: re-check `same_faces()` ends with a line even when interrupted.
- Owed: ① in sheet runs (and when a 📌 reference is pinned), never fall back to a model that can't take the reference — say "the card is busy, try again" instead · ② `same_faces()` always writes its line.

## Fixes for the two owed items 2026-11-25 10:15–10:40 (Claude, uncommitted, live after a Lab restart)
- ① **No silent fallback with a reference in play** (`picture.py`): when a 📌 reference or a sheet source is in play, only reference-capable models are tried (`local/flux2-klein-4b`, `venice/qwen-edit-uncensored`). If none makes it → the run fails with "🎭 Nothing made: the picture model that keeps the face didn't answer (…). The graphics card may be busy with a video. 👉 Try again in a minute — nothing was made without your reference, and no picture was paid for." Hermes refusing the reference route → stops with its message + fix instead of words-only. No reference pinned → the normal fallback is unchanged. In a sheet, a failed view counts as failed and the next view still tries.
- ② **same-face line always written** (`batch.py same_faces()`): try/finally; the line now reads "n of m checked views match … · k not checked (why)". Re-checking skips views already judged.
- Tests: `test_refs.py` +3 (card-down never falls to a model without the reference · no pin keeps the normal fallback · line written when the check breaks); 1 changed (refused route now stops). ailab suite **667 pass**.
