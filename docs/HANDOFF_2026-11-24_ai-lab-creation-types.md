# HANDOFF 2026-11-24 — AI Lab 🧩 creation type chips

**Commits (~/ailab):** `ff47ae9` backend + tests · chip UI went into `c3c5d75` (a parallel session's 📦 app-name commit swept up index.html). **Not pushed.** 269 tests green (+18 `tests/test_creation.py`).

## Built (M1–M5)
- **M1 Types file** — `ailab/creation.py`: 🌐 Website · 📱 Android · 🪟 Windows · 🐧 Linux · 🎮 Game · 📝 Text · 🔧 Edit existing · 🖼 Image · 🎬 Video. Each = icon, model kind, robot test, ship target, guess words, agent lines, starter questions. Add/replace/hide types in `<lab home>/creation_types.json` — no code change. Route `GET /api/creation_types`.
- **M2 Chip row** — above the task box (agent page + workbench). Any number on. Until Scott taps, the Lab's ⭐ guess follows the words; after a tap it's his pick + **↺ Guess for me**. 44 px chips. Remembered per project. Sent as `ctypes` on ▶ Start.
- **M3 Model pick** — 💡 suggestion uses the first chip's model kind; 🖼/🎬 try 🎨 fewer-limits models first.
- **M4 Agent** — system prompt gets "Scott picked: …" + per-type build rules; with ❓ Ask me first, up to 3 type questions (⭐ usual pick), skipping what his saved picks answer.
- **M5 Test + ship** — robot per type: game = play (screen must move) · website/apps/edit = page (a still screen is fine, errors still red) · text/image/video = none (✅ without "built, not run"). Done run: 📦 **Make it an app: 📱 Android ⭐** with only the chip platforms ticked; 🖼/🎬 → **Take the brief to Image Studio (/models) / Media Studio (/media) ⭐** (`image_brief.md` / `video_brief.md`).
- No chips = old behaviour exactly (play test, "built, not run" for non-page files).

## Not proven live (needs a Lab restart — desktop icon)
1. Chips show; typing "tetris for my phone" stars 🎮 + 📱; tap → ↺ appears.
2. Run with 📝 Text → ends ✅ with no robot.
3. Run with 📱 → result shows 📦 Make it an app: 📱 Android ⭐, only Android ticked.
4. 🖼 run → image_brief.md + Image Studio button (needs `hermes_url` set; standalone shows a note).
5. Argus touch test of the chip row (phone width wrap, 44 px).

## Known gaps
- Lab still can't make pictures/video itself — needs a Hermes MCP tool (later module).
- Parallel session active on ~/ailab today — check `git log` before editing.

Continue phrase: `continue AI Lab creation types from the 2026-11-24 handoff — live check`
