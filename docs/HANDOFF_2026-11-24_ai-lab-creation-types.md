# HANDOFF 2026-11-24 — AI Lab 🧩 creation type chips

**Commits (~/ailab):** `ff47ae9` backend + tests · chip UI went into `c3c5d75` (a parallel session's 📦 app-name commit swept up index.html). **Not pushed.** 269 tests green (+18 `tests/test_creation.py`).

## Built (M1–M5)
- **M1 Types file** — `ailab/creation.py`: 🌐 Website · 📱 Android · 🪟 Windows · 🐧 Linux · 🎮 Game · 📝 Text · 🔧 Edit existing · 🖼 Image · 🎬 Video. Each = icon, model kind, robot test, ship target, guess words, agent lines, starter questions. Add/replace/hide types in `<lab home>/creation_types.json` — no code change. Route `GET /api/creation_types`.
- **M2 Chip row** — above the task box (agent page + workbench). Any number on. Until Scott taps, the Lab's ⭐ guess follows the words; after a tap it's his pick + **↺ Guess for me**. 44 px chips. Remembered per project. Sent as `ctypes` on ▶ Start.
- **M3 Model pick** — 💡 suggestion uses the first chip's model kind; 🖼/🎬 try 🎨 fewer-limits models first.
- **M4 Agent** — system prompt gets "Scott picked: …" + per-type build rules; with ❓ Ask me first, up to 3 type questions (⭐ usual pick), skipping what his saved picks answer.
- **M5 Test + ship** — robot per type: game = play (screen must move) · website/apps/edit = page (a still screen is fine, errors still red) · text/image/video = none (✅ without "built, not run"). Done run: 📦 **Make it an app: 📱 Android ⭐** with only the chip platforms ticked; 🖼/🎬 → **Take the brief to Image Studio (/models) / Media Studio (/media) ⭐** (`image_brief.md` / `video_brief.md`).
- No chips = old behaviour exactly (play test, "built, not run" for non-page files).

## Proven live 10:05 (gandalf, after Scott's restart)
- 9 chips load; ⭐ guess live: "tetris … android phone" → 📱 + 🎮 · "thank-you note … letter.md" → 📝 · Hermes repo task → 🔧. 💡 model tip follows the chips.
- 📝 run `ab05cfd3fc` (deepseek v4.1 flash): ✅ done, no robot, $0.0012 (before chips this ended "built, not run").
- 📱 run `8ebb402641`: ✅ done, robot 🟢 page mode + phone fit, $0.003; result shows **📦 Make it an app: 📱 Android**, ship box opens with only Android ticked. ↩ Undo all → Scratch restored.
- Bug found + fixed live: stray "null" after the 🎬 chip (`edeb2bd`).
- Chips 44 px, wrap to 3 rows in the agent pane, no sideways scroll (desktop). Chrome window would not resize to phone width.

## Argus touch test 10:20 (Pixel 5 AVD, real Chrome, http://10.0.2.2:8850)
Pass:
- 393 = 393 (no sideways scroll), every chip 44 px, 0 console errors.
- Real taps: 🎮 → on + ↺ appears · 📱 → both on · ↺ → back to guessing. Typing "a snake game for my phone" → 📱 ⭐ + 🎮 ⭐.
Finding → fixed (`0626afd`):
- 9 chips wrapped to 4 rows (194 px) and pushed ▶ Start to 865 on a 722 screen. Phones (≤640 px) now show only the picked
  chips + **▾ More** (or **▾ Pick what you're making** when none) in one 44 px line; label hidden; tap ▾ More → all 9 + ▴ Fewer (real tap OK).
Picker squeeze 10:35 (`6d38ecd`), Argus:
- Phones (≤640 px): ▶ Start moved right under the task box (model picker after it); picker 202 → 133 px
  (provider + model on one row, tag help + 🎨 on one row). ▶ Start 865 → **503** on a 722 screen, page 393 wide,
  tag help opens/closes by real tap. Desktop layout unchanged.

Image hand-off 10:30 (`df52566`):
- 🖼 run `fe2a2c2338` (deepseek v4.1 flash): ✅ done $0.0057, image_brief.md (title + 3 prompts, 9:16 1440×3120, avoid list), no robot.
- Bug: hermes_url is empty in Lab config → only a note showed. Fixed: button uses ⌂ Home's address (hermes_url, else where the Lab was opened from).
- After ✓ Keep all: **🖼 Take the brief to Image Studio ⭐** is the main button → opened Hermes Image Studio (127.0.0.1:8780/models).

## Still open
1. Scratch has `letter.md` + `image_brief.md` from the test runs (test project).
2. 🎬 Video hand-off: same code path as 🖼, unit-tested only.

## Known gaps
- Lab still can't make pictures/video itself — needs a Hermes MCP tool (later module).
- Parallel session active on ~/ailab today — check `git log` before editing.

Continue phrase: `continue AI Lab creation types from the 2026-11-24 handoff — next type`
