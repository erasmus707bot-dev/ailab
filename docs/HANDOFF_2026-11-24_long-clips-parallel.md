# HANDOFF 2026-11-24 — AI Lab: long clips stream + art runs side by side

Scott picked **1, 1** (asset-library brainstorm). Build prompt: Project `claude/BUILD_PROMPT_2026-11-24_ai-lab-long-clips-parallel-runs.md`.

**Commits (not pushed):** ~/ailab `6dff45b` · ~/hermes `cb4a1862`. Other sessions' uncommitted ~/ailab work (self-edit guard, picture_route) left alone; server.py / index.html / picture.py committed hunk-exact from HEAD.

## Built
- **L1 long clips:** `/preview/<pid>/<file>` streams video/audio from the srt sandbox in 4 MB slices with HTTP Range (206, Content-Range, 416; 8 MB per open-ended answer). Any length opens and seeks. Pages/pictures unchanged; anything over the old 25 MB cap streams too. `pipe_server` ops `stat` + `range` (same path guards).
- **L2 parallel runs:** 🖼 🎬 📝 🎛 art runs share a project with anything; build/code runs stay one per project (start/more/resume). `/api/agent/live` + 🏃 strip under ▶ Start (tap a run to watch it, ⏹ each). ▶ Start stays on.
- **Cap race:** Lab `LocalLedger.hold()` = check + hold in one locked step. Hermes `video_make`: clips still rendering count against the cap ("$x already rendering").
- **Names:** `picture.claim()` reserves file names atomically (pictures, batch docs, videos, docs) → `-2`, never an overwrite.

## Tests
~/ailab 402 pass (working tree); committed tree 390 pass + 1 pre-existing HEAD failure (`test_looks` Page — that page line is in another session's uncommitted index.html). ~/hermes `test_mcp_video.py` 10 pass.

## Not verified live (shell can't restart services)
- A long clip playing + scrubbing in the real Lab viewer.
- Picture batch + video in one project at once on the real Lab.
- 🏃 strip on the Argus phone (touch test owed).

## On the NUC
1. `systemctl --user restart hermes-mcp && systemctl --user restart ailab`
2. Lab → a project → 🎬 make a 10 s clip → while it renders, 🖼 4-picture batch in the same project → 🏃 strip shows both → both finish.
3. Open the clip, drag the scrub bar to the end — it jumps without loading the whole file.
4. `cd ~/ailab && git push` · `cd ~/hermes && git push origin master && git push offsite master`

Continue: `continue asset library build from the M0 handoff`

No night tail: this build prompt is finished; asset M1 waits on the M0 live probe (it spends money).

## PROVEN live 2026-11-25 11:45 (Lab already restarted by other sessions)
- `/api/agent/live` answers 200 → new code is running.
- **Long clip:** 30 s / 67.8 MB clip (`test/videos/longclip-check-30s.mp4`, 3× the 10 s waves clip, stream copy, $0) — 206 ranges, metadata loaded, seek to 28 s in 1.4 s, played; only 0–0.5 s and 20–30 s buffered (no whole-file load).
- **Parallel:** two 🖼 runs started back-to-back in project `test` — both `running` together, both listed in `/api/agent/live`, both finished (local flux2-klein-4b, $0.000, 26 s / 46 s).
- Still owed: 🏃 strip seen on screen + Argus touch test.
