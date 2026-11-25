# HANDOFF 2026-11-25 — R1 🎭 Global cast library + Lab-designed cast (build prompt #2)

Order (Gate E1): R2 ✅ → #1 M2 ✅ → **R1 ✅ (this)** → #1 M3 📖 Story + M4 🎞 breakdown → R3 → R4 → R5 → R6.

## Shipped
**Hermes** — commit `c4f5a051`
- `forge/projects/mcp_cast.py` — the asset-library characters store (no second copy): `~/hermes-data/assets/c-<slug>-<hex>/`
  `card.json` · `pictures/anchor.*` · `sheet/view-n.*` · `uses.json`. Pictures sit inside hermes-data → valid `reference_images`.
- MCP tools: `cast_list` (look; `query`, `cast` filter, named casts) · `cast_get` (look) · `cast_make` (do; new needs name + age ≥ 18 +
  anchor; `id` = add sheet/brief/casts; `real:true` refused — M8 blocked) · `cast_pin` (do; records the project in uses.json).
  Verifier sees look tools only. Nothing spends.

**AI Lab** — uncommitted (sits on the uncommitted M1/M2/R2 base)
- `ailab/cast.py` (new) — 🎲 `design(n)` picks every trait without repeats across the cast (hair colour + length, skin, build, height,
  outfit colour, signature item; ages 22–45); `validate()` = hair colour + outfit colour never shared, ≥ 5 of 7 traits differ, adults,
  unique names; `redesign()` swaps all of one person's traits for unused ones. Run: writer names them → anchor each (**words only**,
  never the project's 📌 refs) → 👁 "can you tell them apart?" per pair side by side, closest pair first, redesign + remake the 2nd
  person ≤ 2 rounds (last look decides; a pair that never passes is named in the result) → M2 character sheet (5 views, anchor as
  reference, 👁 same-face per view) → `cast_make` each with the cast name → project remembers it (`.shelf/cast.json`).
  `pull()` ♻️ reuse = `cast_pin` each + remember · `import_refs()` ⬆ 📌 references → global cast by copy (age set 18, "please check").
- `batch.py` — `{"cast": {"n": 2..4}}` batch kind `cast`; price = 8 pictures per person; view carries briefs / apart / saved.
- `agent.py` — cast batch → `cast.run`. `server.py` — `GET /api/cast` · `GET /api/cast/pic` (only `assets/c-*/` files) ·
  `POST /api/cast/choose|import`.
- `index.html` — `castPicker(p, hooks, opts)` = the start screen: ♻️ Reuse a cast (pick list) · 🆕 Make a new one (2/3/4 people) ·
  all characters strip · ⬆ copy references. Shown now in 📚 Library → 🎭 Global cast. `hooks.castDesign(n, forWhat)`.

## Not built (waits on its module)
- 📖 Story / 🎬 Rebuild start screens don't exist yet (prompt #1 M3, R3). They call `castPicker(p, hooks, {forWhat, onPick})`.
- Story/Rebuild runs sending the chosen cast's sheets as references — R3 (multi-character refs per beat).

## Tests
- Hermes `forge/projects/tests` **107 pass** (6 new `test_mcp_cast.py`: restart-safe store, two projects one character, adult-only, no
  real people, path tricks, verifier).
- ailab full suite **565 pass** (21 in `test_cast.py`: validator over 120 seeded casts, redesign, norm/price, reuse pins, ref import
  copies, thumbnail path guard, whole run with a redesign, never-passing pair reported, no 📌 refs leak into anchors, UI wiring).

## Live — NOT run (this shell can't reach the Lab, Hermes MCP or ComfyUI)
On gandalf:
```bash
systemctl --user restart hermes-mcp && systemctl --user restart ailab
```
Lab → new project "game duo" → 📚 Library → 🎭 Global cast → 2 people → 🆕 Make a new one → watch 🤖 Make.
**Pass:** 2 anchors + 10 sheet views on screen, result line "Tell-apart: 1/1 pairs pass", both show in a **second** project's
🎭 Global cast → ♻️ Reuse a cast. Cost $0 on local FLUX.2 Klein (≈ 12–15 pictures × ~30 s + 👁 checks ≈ 10–15 min).
⚠️ Known from the M2 probe: the 4b judge tops out at 95 and may not catch small drift — plant a mismatch once before trusting it.

## Owed
- Live check · **Argus touch test** (🎭 Global cast fold, both buttons, pick list) · ailab commit after M1 → M2 → R2 → R1 in order.
- Night tail: none (ailab base uncommitted).

Continue: `continue video rebuild + cast + styles + R&D from the 2026-11-25 build prompt #2` (next = prompt #1 M3 📖 Story + M4 🎞 breakdown, then R3).
