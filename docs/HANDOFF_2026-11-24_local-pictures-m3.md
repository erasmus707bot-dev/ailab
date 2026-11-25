# HANDOFF 2026-11-24 — Local pictures M3 (AI Lab picture route)

Scott 20:24 "1" (build M3 as outlined). M2 smoke passed 20:20: 5/5 rows fit, licences right, FLUX.2 28 s, Pony 38 s, $0, checked by eye.
Commit: ailab `7e6a8f1` (+ this doc and `tools/m3_route_proof.sh`). Not pushed. Hermes: no code change.

## Built (ailab)
- `ailab/picture_route.py` — route table: photo (Photo/35mm/Polaroid/Realism) → Juggernaut XL, else FLUX.2 Klein ·
  anime/manga → Illustrious XL, else Pony V6 · other drawn → SDXL base · nothing said → FLUX.2 Klein. Only rows Hermes
  lists as fitting (cached 60 s, per MCP client).
- 🏠 local-first (default) / 🌐 Venice-first: `<lab home>/picture_route.json`; cfg `picture_first` wins. ⚙️ Settings →
  "🖼 Pictures: which side first" (two buttons, `aria-pressed`). API `GET/POST /api/picture_first`.
- `picture.py` run loop: tries the plan in order. Local refusal or failed card job → drops the remaining local models and
  goes to the other side once. Venice not set up → Hermes default (filtered) as before. Forced `picture_model` wins.
  cfg `local_drawn=false` still keeps drawn Looks off the card.
- "🔑 Keys this needs" on every picture (`pic.keys`, end of the run's why line): none/$0 on gandalf · Venice ✅/⛔ · OpenRouter.

## Tests
ailab 411 → all pass (unittest; pytest missing in the VM, run with `TMPDIR=/tmp/...` — /sessions disk full). New in
`tests/test_local_route.py`: kinds, Juggernaut/FLUX fallback, Illustrious, FLUX plain, Venice-first, failure skips Pony,
setting file, API.

## Not done / not verified
- **3d Image Studio picker — not built.** Image Studio has no text-to-picture generator; no Hermes UI lists
  `image_models`. Needs Scott's call (see menu).
- Juggernaut + Illustrious not yet made through `image_make` → `m3_route_proof.sh`.
- Lab restart needed (server code). Argus touch check of the ⚙️ toggle owed.
- Keep-model-loaded (option 2 from M2) parked — would make Iris wait longer for the card.

## Gandalf
1. `systemctl --user restart ailab` (or the desktop icon)
2. `bash ~/ailab/tools/m3_route_proof.sh` — paste output.

Continue: `continue local image service — M3 proof result, from the 2026-11-24 Module 3 handoff`

```night
{"project": "ailab", "module": "local-pictures-m4-tests-phone", "prompt_file": "docs/HANDOFF_2026-11-24_local-pictures-m3.md", "prompt_anchor": "## Not done / not verified", "acceptance": [{"check": "route tests pass", "cmd": "cd ~/ailab && python3 -m unittest tests.test_local_route", "expect": "OK"}]}
```
