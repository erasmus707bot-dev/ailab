
## Live proof — 2026-11-24 07:55 (gandalf, Claude in Scott's Chrome, deepseek/deepseek-v4.1-flash, ❓ Ask me first on)
- Playwright present on gandalf: robot ran both times (🟢, not 🟡).
- Run `3adf36f82f` "The game does not start in the preview. Fix it." → 12 steps, 0 bad, **$0.0039**, ✅ proven, robot 🟢
  ("pressed Start Game and some keys — the screen moved"). Fix: safe store wrapper around localStorage. Model correctly
  skipped ask/plan after the one-time nudge (one exact fix, nothing to choose).
- Run `18a24c0261` "Add a hold-piece feature and a ghost piece" → **question card** (2 questions, ⭐ picks: C key, faint outline)
  → ✅ Use all ⭐ → **🗺 plan** (6 steps) → ▶ Go → hit 24 → **▶ Continue** (+12) → done at 28 steps, 0 bad, **$0.0214**,
  ✅ proven, robot 🟢. ⬅️ Before / ➡️ Now side by side shown. **Keep / Undo left for Scott** (test project).
- Owed still: Argus touch test of question/plan dialogs; output limit 4,096; question answers → memory.
