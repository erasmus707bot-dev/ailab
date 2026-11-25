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
