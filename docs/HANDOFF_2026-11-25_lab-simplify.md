# HANDOFF 2026-11-25 — AI Lab simplify (Scott picks 1A 2A 3A)

**Status:** built + live-checked in Chrome at 127.0.0.1:8850 (no restart needed — index.html is read per request). 541 + 3 tests green. **NOT committed** — another session was editing `ailab/server.py` / `index.html` at the same time (eyes-story-rip M2); index.html mixes both sessions' hunks.

## What changed (ailab/web/index.html, tests/test_simplify.py)
- 🚪 **Clean start every open** (`welcomeView`, `freshStart`): ▶ Continue last · 📂 Pick a project · ➕ New · 📚 See everything. Each lands on an empty box (clicks 🆕 via `freshgo`), folds closed, files/past runs kept.
- 📚 **All-projects Library** (`libraryAllView`, top-bar `#libtop`): all projects by default, tick projects to narrow, 🎚 Filters (kind, ✅ kept, 🕑 time). Tap → ✏️ Change this / ↗ Go to project (opens the file in that project's Library via `libgo`). Client-side: per project `/api/preview/files` + `/api/shelf` — no server change.
- **Less on screen:** 🪄 Improve = icon beside ▶ Start; 🎛 batch moved into ⚙️ Options; 📜 Steps fold; starters = 2 buttons + 🎯 More ways to start fold; per-project 📚 Library folded by default; ship bar hidden on an empty Stage; mode chip hidden (tap 💲 chip shows mode + spend); 🔓 censorship card = one line, the why folds.

## Not done
- Argus phone touch test (TOUCH_TEST_STANDARD) — not run.
- Commit — run once the other session has finished:
  `cd ~/ailab && git add tests/test_simplify.py && git add -p ailab/web/index.html` (take hunks marked 2026-11-25 simplify / welcome / libraryAll / freshgo / cenline), commit "🧹 Lab simplify: clean start, all-projects Library, less on screen".
