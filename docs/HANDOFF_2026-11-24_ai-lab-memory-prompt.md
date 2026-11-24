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
