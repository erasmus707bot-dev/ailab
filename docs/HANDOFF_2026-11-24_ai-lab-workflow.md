
## Live proof — 2026-11-24 07:55 (gandalf, Claude in Scott's Chrome, deepseek/deepseek-v4.1-flash, ❓ Ask me first on)
- Playwright present on gandalf: robot ran both times (🟢, not 🟡).
- Run `3adf36f82f` "The game does not start in the preview. Fix it." → 12 steps, 0 bad, **$0.0039**, ✅ proven, robot 🟢
  ("pressed Start Game and some keys — the screen moved"). Fix: safe store wrapper around localStorage. Model correctly
  skipped ask/plan after the one-time nudge (one exact fix, nothing to choose).
- Run `18a24c0261` "Add a hold-piece feature and a ghost piece" → **question card** (2 questions, ⭐ picks: C key, faint outline)
  → ✅ Use all ⭐ → **🗺 plan** (6 steps) → ▶ Go → hit 24 → **▶ Continue** (+12) → done at 28 steps, 0 bad, **$0.0214**,
  ✅ proven, robot 🟢. ⬅️ Before / ➡️ Now side by side shown. **Keep / Undo left for Scott** (test project).
- Owed still: Argus touch test of question/plan dialogs; output limit 4,096; question answers → memory.

## Argus touch test — question card, plan, result box — 2026-11-24 08:20 (Pixel 5 AVD, http://10.0.2.2:8850, project scratch, deepseek)
Pass:
- ❓ Question card 362×603 on 393×722: no sideways/inner scroll; all controls ≥44 px (choices 307×67, Later/Use all/Send 67 tall). Used memory ("cream/navy look").
- Tap on a non-⭐ choice (single question) sends at once → plan reflected it ("Reset with a confirm step").
- 🗺 Plan 362×592 fits; ▶ Go by touch starts the build. Second run: no question (memory answered it) → plan → Go → Done 13 steps $0.0047, robot 🟢.
- Result box: Before/Now iframes stacked 352 wide, robot screenshot, ✓ Keep all / ↩ Undo all 44 px; ↩ Undo all by touch restored scratch (app.js 133, index.html 461). 0 console errors.
Findings (not fixed — another session was editing index.html):
1. Plan buttons (Go / Later / Send change) **42 px** tall (<44).
2. Plan step names cut mid-word at 80 chars (agent.py:526 `[:80]`) — e.g. "Tap + Reset butto". Wrap/ellipsis or raise to ~140.
3. Page **438 px wide on 393** — top bar chips + ☀️ (worse than the 10–60 px noted above).
4. A Lab restart mid-run (another session's restart, 08:16) drops the run: phone showed "❓ 'No such run.'" on ▶ Go. Runs live in memory only.
Rig note: tapSel landed ~24 css px low on this page twice (toolbar show/hide); direct device-pixel tap from the frame worked.
