# HANDOFF 2026-11-25 — AI Lab Library player

**Commit:** 7d555f4 (ailab/web/index.html, tests/test_libplay.py). Only player hunks were committed; another session's uncommitted R3 rebuild work in index.html is still in the working tree, not committed.

**What:** `libPlayer()` is shared by 📚 Everything you've made and each project's 📚 Library big viewer.
- ◀ ▶ buttons, swipe, ← → keys: step through whatever the current filters show
- ▶ Slideshow: moves on by itself and loops
- 🎬 Play videos: a video plays to the end, then moves on (off = the slideshow skips videos)
- 📝 Writing & pages: off by default; when on, they stay up for the same seconds as a picture
- ⏱ 3/5/8/12 s per picture, default 5
- ⛶ full screen
- Settings are saved in localStorage `ailab.libplay.*`
- Closing the viewer stops the timer

**Verified live (Chrome, 127.0.0.1:8850):** both Libraries; next/prev/arrow keys; video ended → advanced; picture advanced after 3 s; no console errors. 4/4 static tests pass.

**Open:** Argus phone touch test (swipe, 44 px buttons) not done yet.
