# HANDOFF 2026-11-25 — AI Lab 👁 Eyes (eyes + story + rip, M1)

Build prompt: `claude/BUILD_PROMPT_2026-11-25_ai-lab-eyes-story-rip.md` · Audit: `docs/AUDIT_2026-11-25_eyes-story-rip.md`.
Gate 0 taken from "proceed" = the ⭐ picks: **A1** qwen3.5:4b · **B1** local only · **C1** no trainer · **D1** Kokoro · **E1** M1→M2→M3→M4.
A1 **confirmed by the pilot** (06:46). The model is one setting, no code edit to change it.

## Shipped

**Hermes** (`~/hermes`)
- `forge/projects/mcp_vision.py` (new) — MCP tool **`vision_check`**: `image_b64` or `image` (path in Hermes picture folders), up to 12 yes/no `points`, `caption`. Returns job key `vis:…` → `job_wait` → `caption`, `answers[{n,q,yes}]` (`yes` null = model didn't say), `refused`. $0, kind `look`, local only — no hosted path exists.
- Card: takes `CardSlot`, calls ComfyUI `/free` first; the next picture's own hand-off drops the vision model.
- Model: env `HERMES_VISION_MODEL` → `~/hermes-data/studios/vision.json {"model": …}` → `qwen3.5:4b`.
- `forge/projects/mcp_server.py` — 4 small hunks (tool row, `_vis()`, `vis:` status, `vis:` not-found text).
- `forge/projects/tests/test_mcp_vision.py` (new, 8 tests).

**Lab** (`~/ailab`)
- `ailab/eyes.py` (new) — his words → yes/no points (shown things · exact counts · the Look · no writing on the art) → **match score + what is missing** → fix task. His own words are kept byte for byte; misses go in the `Change:` line; Style / Shape / Look kept.
- `picture.py` — every 🖼 result is checked; score on the picture, in the done line, in a step. `video.py` — a middle frame of every 🎬 clip is checked.
- `batch.py` — the batch is checked **after** it is made (one card swap), best match gets ⭐, one failed ask stops the asking.
- `shelf.py` + `server.py` — ✅ Keep / 🗑 Throw away store `seen {score, caption, missing}`; `_taste()` hands the improver `… [👁 83% match — it showed: …]`.
- `web/index.html` — `eyesBox()`: score chip, "missing: …", **🔁 Fix and try again**, "👁 What it saw". On pictures, videos and batch tiles; batch sorted best first. 23 px text, 48 px targets.
- Off switch: `~/.config/ailab/config.json` → `"eyes": {"on": false}`; `"low": 70` sets when the fix button turns primary.
- `tests/test_eyes.py` (new, 11 tests). `tests/test_picture.py`, `tests/test_looks.py`: 3 expected step lists now end with `"eyes"`.

## Not built (say so plainly)

- **Auto-retry of local $0 pictures up to a count.** The retry would call the paid prompt writer, so it is not $0. Needs a no-writer retry path first. The fix is one tap today.
- **Per-model prompt dialect in Hermes.** Tags for Pony/Illustrious still live in the Lab (`tag_prompt.py`); not moved.
- **Same-face check** — that is M2.

## Tests

- ailab: **521 pass** (full suite). hermes: **99 pass** (all of `forge/projects/tests`).
- `index.html` script passes `node --check`; `eyesBox` exercised in node (chip, missing, button → fix task, no button while running).

## Live

1. ✅ **Pilot ran 06:46** — qwen3.5:4b sees, 0 refusals / 12, ~8 s warm. A1 confirmed (details in the audit §3).
2. ✅ **Restarted** `hermes-mcp` + `ailab` (Scott, 06:50).
3. ⏳ **Still owed:** in the Lab, 🖼 "three foxes in the snow". Expect a `👁 NN% match` chip. If the count is wrong: "missing: exactly 3 foxes" → tap 🔁 Fix and try again.

## Added after the pilot

- `forge/projects/probe_identity.py` — `--anchor local --vision-model local`: the asset-library identity probe (M2's first step) can now run **$0, nothing leaves gandalf**: anchor drawn by FLUX.2 Klein, "same person?" judged by the local eyes (both pictures in one look). Test added; hermes `forge/projects/tests` **100 pass**.

## Owed

- Live check above · **Argus touch test** of the chip + fix button (phone) · commit.
- **Uncommitted** in both repos. Reason: `picture.py video.py batch.py server.py shelf.py index.html test_looks.py` already carry other sessions' uncommitted hunks, and git writes from this shell need delete permission. New files are clean to stage: `ailab/eyes.py tests/test_eyes.py tools/vision_pilot.py docs/AUDIT_… docs/HANDOFF_…` and hermes `forge/projects/mcp_vision.py forge/projects/tests/test_mcp_vision.py`.
- Stray `tools/__pycache__/vision_pilot.cpython-310.pyc` (from a compile check; could not delete from this shell).
- **Night tail: none.** M1 is uncommitted and not proven live; a night worktree would build M2 on a base without it.

## Next — M2 🎭 Characters and references

Starts with a `missing_nodes()` proof of `workflows.py:85 build_ref` on gandalf. Nothing touches real people.

Continue phrase: `continue AI Lab eyes + story + rip from the 2026-11-25 build prompt`

## Live check 2026-11-25 07:32–07:43 (Claude, Lab through the built-in browser, project image-testing)
- ✅ "three foxes in the snow" → FLUX.2 Klein, 28 s, $0 → **👁 100% match**, look took 8 s. Checked by eye: 3 foxes, snow, no writing.
- ✅ Miss caught: "seven foxes sitting in a row in the snow" → model drew **5** → **👁 67% match — missing: exactly 7 foxes**, caption "Five red foxes…". Card on screen: chip, missing line, 🔁 Fix and try again (primary, 50 px tall), text 23 px.
- ✅ 🔁 pressed → new run with `Change: there must be exactly 7 foxes — count them`. 1st try: Hermes connection dropped mid-call (nothing charged). Retry: still **5 foxes, 60%** — FLUX.2 Klein can't draw 7 even when told; the eyes reported it honestly.
- 🐛 → fixed: the fix's own Change line became extra points ("missing: exactly 7 foxes, exactly 7 foxes"). `eyes.points()` now drops what `fix_words()` wrote and de-duplicates. Test added (12 eyes tests; Lab suite 541 pass). **Live after a Lab restart.**
- 🎨 fixed: "👁 What it saw" had lost its ▶ marker (summary was inline-flex). Live on page refresh.
- ⚠️ ComfyUI went down between 07:38 and 07:43 (connection refused on 8188; it was up for the 07:38 picture). Cause unknown from this shell — check `journalctl --user -u hermes-comfy --since 07:35`.
- ⚠️ With ComfyUI down, the pinned-reference test fell back to **venice/lustify-v8 without the reference, $0.01**. That fallback is the existing picture route; it means a 📌 reference silently stops working when the card is down. Reference test (M2 live step 3) still owed. Pin removed again; image-testing's cast strip is empty.
