# HANDOFF 2026-11-23 — Inkling 2 Small pilot (AI Lab)

**Why:** Scott asked about "Inkling 2 mini". No official mini exists (HF `tbmod/Inkling-mini-*` = broken test fixture, gibberish).
Real model: Thinking Machines **Inkling 2 Small** — 594B MoE / 17B active, text+image in, tool calling, 1M context,
weights on HF (Apache 2.0) since 2026-11-12. Too big for gandalf (smallest 1-bit GGUF ≈ 172 GB) → hosted only.

## Done
- `ailab/roster.py`: hosted entry `thinkingmachines/inkling-2-small` (exact match — `:free` and `:nitro` never match; `:free` logs prompts).
- `ailab/config.py`: price $0.30 in / $1.00 out (higher of OpenRouter $0.15/$0.50 vs MindStudio $0.30/$1.00 — UNVERIFIED).
- Lab tests 143 OK.

## UNVERIFIED
- Whether a ZDR provider serves it on OpenRouter (privacy guard refuses the call if not — Lab shows the error).
- Vendor coding scores (DeepSWE 72.1%, SWE-Atlas 61.9%) — self-reported.

## Blocked on Scott
OpenRouter key into Hermes Vault (Keys page shows "⛔ no key in Hermes").

## Pilot (after key, after Lab restart)
⚖️ Compare on a Hermes page: point at "Scan now" → "Scan everything", green. Lanes: inkling-2-small vs deepseek-v4.1-flash, $0.50 cap.
Winner = 🟢 robot at lower $. Throw away after. Record result here; if Inkling wins, make it the Lab default coder in `~/hermes` model_preferences.json (ailab only).

Continue phrase: `continue AI Lab Inkling pilot from the 2026-11-23 handoff`

## Pilot result — 2026-11-24 (done)
Key landed in Vault 05:2x (`/api/providers` openrouter has_key true). Run as two 🪞 Show & change lanes (⚖️ Compare has no robot),
same ask: pointed at "Scan now" → "Rename this button to "Scan everything" and make it green", Hermes home, Scratch project.
| lane | 🚦 robot | $ | steps |
|---|---|---|---|
| thinkingmachines/inkling-2-small | 🟢 (changed, clicked, no new errors) | $0.0055 | 12 — step cap, never said done |
| deepseek/deepseek-v4.1-flash | 🟢 (same) | $0.0034 | 12 — step cap, never said done |
**Winner: deepseek** (both green, ~38% cheaper). Inkling NOT made default; model_preferences.json untouched.
- ZDR: privacy guard let Inkling through → a ZDR provider serves it on OpenRouter (resolves the UNVERIFIED line).
- Both thrown away (live discard, New = Now, 0 held). Lab provider restored to claude.
- Noticed: both hit the 12-step cap on a 1-spot edit — cap may be tight for Show & change. Robot clicks the real "Scan now" on the Now side → triggers a real (read-only) Hermes scan each run.
- Inkling stays in the roster as an option (reads screenshots, 1M context).

## 2026-11-24 — robot fix
`f3094fc`: the robot never clicks the Now (real) page, only New (the test copy). After New's click, the look-only 403 is expected (shown as a note); any other new error → 🔴. 146 tests OK. **Loads at next Lab restart.**
Live re-check owed: 🪞 on "Scan now" → no new Hermes scan starts; 🚦 still 🟢.
Next: `~/hermes/prompts/BUILD_PROMPT_2026-11-24_ai-lab-memory-prompt-builder.md` — continue phrase in that file.

## Step-cap retest — 2026-11-24 05:4x
`7cd6b73`: Show & change runs use `live_step_cap` 60 (agent_start `kind:"live"`); normal agent cap unchanged. Lab restarted by Scott.
Same ask, deepseek-v4.1-flash: 🟢, **$0.0034, 13/60 steps, state done** (said done itself; also renamed the label the scan script resets to). Thrown away; provider back to claude.
Side job: Hermes gemini → gemini-3.8-flash / gemini-4-argon (2.0-flash shut down). model_preferences.json edited in place (backup .bak-2026-11-24-gemini) but NOT committed — that file already held other sessions' uncommitted changes (cloud_default openrouter etc.). providers.py template committed in ~/hermes. Gemini prices UNVERIFIED (conservative 3.5-flash rate). First real Gemini call not yet made.
