# HANDOFF 2026-11-25 — AI Lab remodel M4 (live Chrome overview + wrap-up)

Scott: "do an overview on chrome to make sure things are looking right, then move on and keep building."
Builds on `docs/HANDOFF_2026-11-25_lab-remodel-m3.md`.

## Live overview — gandalf, Chrome, http://127.0.0.1:8850, project "image testing", 2264 px wide
- Two panes 738 / 1475 px. Make: box, 🎨 Look, 🪄 Improve, 🖼 chip, batch row, ▶ Start, ⚙️ Options (shows the 🔓 model). 🔓-only is on.
- Stage: Done line once, picture big, ✏️ Change it, finish bar (✅ Keep & start new · 🗑 Throw away · 🆕 Just clear — no overlap).
- 📚 Library (52): 12 thumbnails loaded, 0 broken, filter chips + ⚖️ Compare. Compare showed two side by side; ✏️ Change this shows on an opened item.
- Server half is live: `/api/shelf` answers, file dates present. No long tasks, no request storm (3 light polls in 4 s).
- **Found and fixed in this module:** the Library sat ~1300 px below a tall result → 📚 jump chip in the Stage bar; the "🧠 used: …" line in Make → folded into the step log.
- **Could not do:** screenshots after the first one timed out (capture, not the page — the page stayed responsive); the window would not resize, so no phone-width check on gandalf (390 px was checked in the cloud container at M1).

## Built — NOT committed
Files: `ailab/web/index.html`, `ailab/server.py`, `ailab/shelf.py`, `tests/test_remodel_m4.py` (new), this doc. Diffs: `~/hermes-data/_tmp/remodel/page_m4.patch`, `server_m4.patch`.
- **📚 N jump chip** next to "👀 Stage" → opens and scrolls to the Library.
- **🏁 Project done** chip in the Library → wrap card: "<project> — N kept · M in the Library" · 🏁 Mark it done ⭐ / ↩ Not done yet ·
  📍 Where the files are · 📦 Make it an app · ➕ Start a new project. Done is a mark only (`done_at` in `.shelf/shelf.json`,
  `POST /api/shelf/done`) — nothing is locked, moved or removed; keep building any time.
- Library thumbnails decode off the main thread (`decoding: "async"`).

## Verified
- Live on gandalf (above): jump chip reads "📚 52" and scrolls; wrap card opens with all four actions; 🧠 line 0 in Make / 1 in the log.
- Device VM tests: 463 pass / 26 fail = the M0 baseline 26, 0 new. 2 new tests.

## NOT verified / still owed
- A real run end to end by Scott: ✅ Keep → #N, 🗑 Throw away → ↩ Bring back, 🪄 Improve live, the 🔓/🔒 card on a real build.
- 🏁 Mark it done was not pressed live (it writes to his project).
- **Argus touch test** (M1–M4).
- **Commit:** tried again — 4 of the M1 hunks still do not apply to HEAD without the other sessions' uncommitted index.html
  hunks. All remodel work stays in the working tree; the four module diffs are saved (paths above).
- Thumbnails are the full-size files (no small copies) — fine at 12 tiles, may drag on a project with many large videos.
- SESSION-LEDGER not touched (triage-owned).

## Remodel status
M0–M4 built. Open: Scott's real-run pass, Argus touch test, commit.

Continue: `continue AI Lab remodel — fix list from Scott's live pass (2026-11-25 handoff)`

## 05:05 — 🎨 Look (mood/theme) for 🎬 Video (Scott: "I need access to the mood/theme options")
- The Look picker was shown only while 🖼 Image was picked. Now also with 🎬 Video (`look.show(image || video)`).
- `video.py`: reads the same `Look:` line; `with_look()` puts medium/style after his words and mood/light/colour at the end of
  BOTH the first-frame picture prompt and the clip prompt; a 🎨 Look step shows in Step by step. His words stay first and whole.
- Tests: `tests/test_video_look.py` (4) + the one changed line in `tests/test_looks.py`. Full suite: 0 new failures.
- NOT verified: a real video with a Look on gandalf (needs a Lab restart for video.py; the picker itself is live on refresh).
  A run already going when he restarts comes back paused (his rule) — restart between runs.
- Not done: Look for 📝 Text (asked? no — offered).
- Uncommitted with the rest; diff `~/hermes-data/_tmp/remodel/video_look.patch`.
