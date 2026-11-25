# HANDOFF 2026-11-25 — AI Lab simplify (Scott picks 1A 2A 3A)

**Status:** built, live-checked, **committed** 158f1d6…28e1f43 (whole uncommitted ailab stack, 5 category commits, 565 tests green, secret scan clean).

## What changed (ailab/web/index.html, tests/test_simplify.py)
- 🚪 **Clean start every open** (`welcomeView`, `freshStart`): ▶ Continue last · 📂 Pick a project · ➕ New · 📚 See everything. Each lands on an empty box (clicks 🆕 via `freshgo`), folds closed, files/past runs kept.
- 📚 **All-projects Library** (`libraryAllView`, top-bar `#libtop`): all projects by default, tick projects to narrow, 🎚 Filters (kind, ✅ kept, 🕑 time). Tap → ✏️ Change this / ↗ Go to project (opens the file in that project's Library via `libgo`). Client-side: per project `/api/preview/files` + `/api/shelf` — no server change.
- **Less on screen:** 🪄 Improve = icon beside ▶ Start; 🎛 batch moved into ⚙️ Options; 📜 Steps fold; starters = 2 buttons + 🎯 More ways to start fold; per-project 📚 Library folded by default; ship bar hidden on an empty Stage; mode chip hidden (tap 💲 chip shows mode + spend); 🔓 censorship card = one line, the why folds.

## Not done
- Argus phone touch test (TOUCH_TEST_STANDARD) — not run.

## Argus touch test 2026-11-25 (Pixel 5, 402×738 CSS)
- 🚪 Start screen: Continue tap → clean slate (empty box, "🧼 Clean slate"), Make tab; ▶ Start at y=344, ⚙️ Options y=534 — all above the fold. No sideways scroll (scrollWidth 402).
- 📚 Library: 94 things, all projects; project chip tap narrows (60 of 94), multi-pick works (67 of 94 · 2 projects); tile → viewer; ✏️ Change this → switches project, Stage tab, file open in its Library.
- Fixed: project chips pushed the first picture to y=450 → folded "📁 Projects — all" on phones (now y≈308); viewer buttons were 42 px / ⬇ 38 px → 44 px.
- 0 console errors. Small targets left: 2 checkboxes (16 px) inside 44 px labels — OK.
