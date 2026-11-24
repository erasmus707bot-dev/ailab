# HANDOFF 2026-11-24 — AI Lab 🧠 Memory + 📝 Prompt builder + 🎨 labels

Prompt: `~/hermes/prompts/BUILD_PROMPT_2026-11-24_ai-lab-memory-prompt-builder.md` · audit `docs/AUDIT_2026-11-24_ai-lab-memory-prompt.md`
Gate 0: Scott picked 1 (all defaults + 🎨 as M1b). Lab tests **172 OK** (was 146).

## Commits (~/ailab)
- `0c38373` robot: 403/404 after New's click = fallout of the blocked save (note); load-time 404 still red. Robot live-proven not to click the real page.
- `6bd86ba` M1 🧠 store `~/.config/ailab/memory/*.md`, import (copy-only; sensitive skipped + counted), Memory page, undo. Flags `memory`, `prompt` (default off).
- `01111d7` M1b 🎨 fewer limits / 🔒 strict labels + "🎨 only" filter; roster: hermes-4-405b, venice/uncensored (no tools), dolphin3:8b, hermes3:8b; Keys page warns qwen/kimi direct skip private routing.
- `a1177f6` M2 agent + Ask models get memory ("🧠 used: …"); stated preferences auto-save to `lab-learned` (never sensitive).
- `c84d81f` M3 ⬇ review .md / ⬆ answers .md → before/after with ticks → ✅ → ↶ undo whole review; `/api/memory/questions` for voice.
- `ca228c9` M4 📝 Prompt builder: ✨ model draft (memory + latest handoff) or 📄 free template → 🤖 Lab agent or ✳️ Claude = night **Module 0 AUDIT** order (validated by Hermes `order.py`) + 📋 continue line. Prompts saved in `~/hermes-forge/lab-prompts/` (no repo writes).
- `aea8bed` M5 ✅/🔨/⏳ from the prompt's modules; agent `ask` → pop-up (✕ Later; waiting ≠ stuck); 📱 pings via Hermes ntfy — only finished or stuck, once per run.
- `4697c01` `tools/ailab-memory-golive.sh`.
- Claude memory export written: `~/hermes-data/claude-memory-export/` (7 files, sensitive lines left out). Dry-run import: 11 subjects, 335 lines, 0 skipped.

## UNVERIFIED
- 🎨 tags come from 2026 web guides, not tests; hermes-4-405b / venice ids + prices + ZDR on OpenRouter.
- ntfy topic `hermes-night` reaching the phone/Iris for Lab pings.
- 🎙️ voice review: Lab side only (question list). Iris has no "review my memory" command yet.
- Model drafts of prompts: format tested with fakes only.

## Owed on gandalf (one line)
`bash ~/ailab/tools/ailab-memory-golive.sh`

## Then (Claude, in Scott's Chrome) — M6 live proof
1. 🧠 Memory → 🔄 Copy from my Claude setup → expect ~11 subjects; open claude-preferences.
2. ⬇ Review .md → change 1 line → ⬆ → before/after → ✅ → ↶ undo.
3. 📝 "make the Scan now button green" → 📄 Plain → ✨ Write it (deepseek) → ✳️ Send to Claude → order in night/orders + continue line.
4. 🎨 only toggle on openrouter; Keys page qwen/kimi warning.
5. Argus touch test on Memory + Prompt pages. Then flags stay on only for what passed.

Continue phrase: `continue AI Lab memory + prompt builder from the 2026-11-24 handoff — M6 live proof`

```night
module: M6
prompt_file: /home/gandalf/hermes/prompts/BUILD_PROMPT_2026-11-24_ai-lab-memory-prompt-builder.md
acceptance:
  - check: Lab unit tests pass
    cmd: python3 -m unittest discover -s tests
    expect: exit 0
```

## M6 live proof — 2026-11-24 06:30 (after golive.sh; Claude in Scott's Chrome)
- Flags on: memory, prompt (+ all earlier). 
- 🧠 Import: **14 subjects, 608 lines**, 1 health line skipped (count only) — also picked up `~/.claude/CLAUDE.md` + skills graphify, scott-conventions. Memory page renders, cards open.
- Review round-trip on claude-devices: change + add → before/after (2) → applied as [scott] → ↶ undo back to 3 lines. ✅
- 📝 Plain template ✅ (size: small). ✨ deepseek draft ✅ in format, $0.0018, 🧠 used profile/preferences/rules-claude-code.
- ✳️ Send to Claude: order passed **Hermes order.py** on gandalf → `night/orders/hermes__lab-lab-proof-scan-button-m0.json`, then **parked by Claude** (test only, no night spend).
- 🎨: hermes-4-405b ($0.0007) and venice/uncensored ($0.0002) answered through the ZDR guard → ids + private routing confirmed. "🎨 only (2 here)" on openrouter.
- Keys: qwen/kimi warning shows. **Kimi now reads "⏸ off in Hermes"** (earlier today it listed with a key) — check Hermes → Settings → API keys.
- Fixes after proof (`see next commit`): project rules now load before the long global rules file (rules-hermes was crowded out); order slug no longer "lab-lab-".
- Owed: Argus phone touch test (Memory + Prompt pages); a real 📱 ping (not sent — would buzz Scott's phone for a test); pull dolphin3:8b / hermes3:8b if wanted (`ollama pull dolphin3:8b`).

## Argus touch test — 2026-11-24 06:45 (Pixel 5 AVD, real Chrome, http://10.0.2.2:8850)
Findings fixed (index.html, loads per page view — no restart):
- 🧠 + 📝 had **no button** in the workbench → added to 🧰 More tools + a "📝 Idea → build prompt" button in the 🤖 pane.
- Prompt page was **658 px wide** on a 393 px phone (long model names in the select) → select fills its row, ellipsis.
- Selects/buttons 39–42 px, 🗑 36 px wide → all ≥ 44 px on .keys pages.
Pass after fix: width 393 = 393 · 0 controls under 44 px · ⌂ → 🧰 → 🧠 by touch · card opens · ➕ Add line saved · 🗑 removed it (server 3 lines) ·
📄 Plain template by touch · page swipe scrolls (a swipe that starts in the prompt box scrolls the box — normal) · Send buttons reachable ·
no late shift (Send top 989 px at 1 s and 10 s) · 0 console errors.
Not testable on the rig: ⬆ file picker, the soft keyboard typing path (values set by script), multi-touch.
