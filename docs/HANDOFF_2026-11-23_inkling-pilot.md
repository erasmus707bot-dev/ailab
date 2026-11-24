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
