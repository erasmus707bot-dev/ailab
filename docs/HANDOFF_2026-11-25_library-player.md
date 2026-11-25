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


## Argus touch test, 2026-11-25 10:15 (Pixel 5 AVD, real Chrome, http://10.0.2.2:8850, 447×822 CSS px)
- **Pass:** real tap on ◀ and on ▶ each moved one item; a left swipe on the picture moved to the next item without scrolling the page (0 px); a real tap on ▶ Slideshow turned it to "⏸ Slideshow on" and it moved every 3 s; a video came up with sound on (muted=false, because the tap is a real user gesture).
- **Pass:** all 7 player controls are ≥44 px tall (◀ 46×44 · ▶ 46×44 · Slideshow 115 · 🎬 146 · 📝 158 · ⏱ 70 · ⛶ 44×44); the picture is 373×545 on an 822 px screen.
- **Rig finding:** tap y was off by 73–94 CSS px (the Chrome toolbar moved). I worked around it with a probe tap on the 📍 line before each tap. Two stray taps toggled 📝 and opened ⤢ — the rig, not the page.
- **Not finished:** a 30 s mp4 never loaded on the emulator (readyState 0), then the emulator hung ("Pixel Launcher isn't responding"; DevTools dropped). Video play-through was verified on desktop Chrome only.
- **Fix from this:** e690787 — when a video hasn't started within 15 s, the slideshow skips it, so it never gets stuck. Desktop re-check: a playing video was not cut off at 15 s (it was at 18 s, same video).
- **Not tested:** the native ⏱ picker by finger, and full screen on the phone.

## Real phone, 2026-11-25 10:51
Scott tested on his S24+: slideshow works, including videos. Feature done.
