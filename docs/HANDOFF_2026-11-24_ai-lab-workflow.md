
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

## Touch-test fixes 1–3 — 2026-11-24 08:40 (ailab `31d224e`, 226 tests OK)
- Plan Go / Later / Send change + change box → 44 px (`#askdlg .btn`).
- Plan step names: `_short(x, 160)` trims at a word break with … (was `[:80]` mid-word). Test `PlanNames`.
- Phone top bar: ≤640 px the spend chip shows today only (`.cap` hidden), picker min 4rem, tighter chips. Headless Chrome 393×722 with ✋ chip + "$0.07 / $2.00": **446 → 393 px**, all header buttons 44 px.
- index.html/agent.py change → **Lab restart needed** (agent.py is server code). Argus re-check owed.
Still open: **4. runs survive a Lab restart** (runs live in memory only).

## Finding 4 fixed — runs survive a Lab restart — 2026-11-24 09:10 (ailab `93bdb22`, 239 tests OK)
- Saved to `projects/<p>/agent/<run>.state.json` (atomic) after each step, on each ❓/🗺 card, at the end. Lanes not kept.
- Lab start loads runs from the last 24 h. Waiting card → still waiting; ▶ Go / a choice carries on. Mid-step → **⏸ Paused — Lab restarted** + **▶ Resume ⭐** (`POST /api/agent/resume`); never restarts by itself (Scott's pick 1).
- A half-done write/run/tool step is not replayed; the model is told it may or may not have happened.
- Proven: 8 unit tests incl. the exact case over HTTP (plan up → server replaced on same home → Go → done); headless phone 393 px: Resume 44 px, tap posts.
- Not proven: on gandalf with a real model. Needs a Lab restart (desktop icon) first. Check: start a run with ❓ Ask me first, restart while the card is up, tap the answer.

## Live restart proof — 2026-11-24 09:15 (gandalf, Scott's Chrome, openrouter deepseek/deepseek-v4.1-flash)
- Scott restarted the Lab (new code: `/api/agent/resume` answers 400 not 404).
- Run `2fb6372ac6` (scratch, "dark-mode toggle", ❓ Ask me first) → question card (2 questions, ⭐ picks) → **Scott restarted the Lab with the card up**
  → run back: state running, `restored`, card intact, not stuck → page showed the card → ✅ Use all ⭐ → 🗺 plan (5 steps, none cut) → ▶ Go
  → **✅ done, 21 steps (2 bad), $0.0055, robot 🟢**. Scratch now has the toggle (test project — keep or undo, no matter).
- Argus (Pixel 5, real Chrome, http://10.0.2.2:8850): top bar **393 = 393**, header controls all 44 px; plan dialog 362×515, 0 controls under 44 px,
  long steps wrap whole; a real tap on ▶ Go hit the button (sample run → "No such run", as expected). 0 console errors.
- Not covered: a mid-step restart (▶ Resume) on gandalf — unit + headless only.
Still open: question answers → Lab memory.

## Answers → memory + Claude import top-up — 2026-11-24 09:45 (ailab `483463d`, `0a011dc`; 251 tests OK)
- ❓ card answers → subject **lab-picks**, tagged [scott], "Q? → pick (project x)"; same question again → newest wins. Run shows them under 🧠 saved.
  (The agent.py call `_save_picks` landed in `a6f6d51` with another session's commit.) Memory flag off → nothing saved. Plan answers are not saved.
- Agent context: lab-picks right after profile/preferences, only picks that fit the task ("don't ask these again"); plus up to 12 single lines
  from any other subject that fit the task (so imported rules files reach the agent, not only subjects whose name matches).
- Claude export topped up (`~/hermes-data/claude-memory-export/`): new **standing-rules.md** (16 rules: nav, libraries, releases, testing, sounds,
  sharing, local models, offline-first), 4 lines added to ai-lab.md. Imported live via `/api/memory/import`: claude-standing-rules 16, claude-ai-lab 14; 1 line skipped (health).
- Not proven live: needs a Lab restart (memory.py is server code). Check: run with ❓ → answer → Memory page shows lab-picks → a second run with
  the same kind of task doesn't ask that question.
