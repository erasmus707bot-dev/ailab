# HANDOFF 2026-11-25 — R4b: R3 committed + 👁 onlooker check (build prompt #2)

## Commits (ailab, local master, ahead of origin by 7 — not pushed)
- `c7e7133` 🧍 Study tab +9 parts (anatomy session's uncommitted work, its own piece)
- `86cf824` 🎭 cast: picture.run "done" never ends the cast run
- `044976b` 🎬 R3 backend — rebuild.py, agent dispatch, server `/api/rebuild` + `/src` (+ craft route move, breakdown `fresh`),
  tests, `tools/r4_rung1.py`; includes R5's level-3 motion path
- `6615d23` 🎬 R3 UI — start card + ⚖️ Review
- `1e0943d` 👁 **onlooker check** — `eyes.onlooker_point()`: "apart from the main N people, does anyone else have the same hair
  and clothes as a main person (…)?" want **no**, kind `onlooker`. Rebuild: last identity point → an identity miss → the $0
  remake adds "anyone else … wears plain dark clothes and has different hair from the main people". Story: `onlooker_pt()` rides
  in the same $0 look as the writing check (one call, two points); cast looks read from the brief.
- `ac6f4d5` docs (R3, R5/L3, P4 handoffs) · left untracked: `docs/_r4_compare.jpg`, `docs/_rebuild_test_contact.jpg`

## Tests
ailab full suite **719 pass** (3 new). Another session committed `30bf0b5` story wardrobe mid-run — no overlap, story tests green.

## Live — NOT run (this shell can't reach the Lab; it needs a restart to load the new check)
```bash
systemctl --user restart ailab
```
Then (after `5ef1ac7`) AI Lab → 🎬 Rebuild → ⚖️ Review (video-testing, `bd-f30682caee785320`) → shot 7 → **🔁 Retry this shot**. $0.
Pass: 👁 ≥ 70 %, no ⚠️ identity, the standing onlooker no longer grey-haired in red.

## Shot 7 retry — 14:21–14:27, run `bc16a725b9`, $0.0002 (writer)
- Ran via ⚖️ retry (resumed once after another session restarted the Lab). 👁 **100 %, no identity miss** — but **by eye it still
  fails**: the standing onlooker has Dina's grey hair + Mara's plum top. The first check asked "same hair AND clothes" → a mixed
  copy passes. (The 13:29 still was the same mix, not a pure Dina copy.)
- Fix `5ef1ac7`: `eyes.onlooker_points()` — one point per cast member, "anyone else with {hair} hair **or** {outfit} clothes?",
  fix line "anyone else wears plain dark clothes (not {outfit}) and has hair that is not {hair}". Rebuild + Story. Tests green.
- **Not live yet:** the Lab (started 14:21) runs the old check; this shell can't restart it.
- ⚠️ Not mine: `tests/test_eyes.py::test_switch_and_standalone_turn_it_off` red since `e5db841` (eyes.settings now has `retry`).

## Owed
Shot-7 retry (above) · push ailab · Argus touch test of 🎬 Rebuild + ⚖️ Review · rung 2 (next clip).

Continue: `continue video rebuild + cast + styles + R&D from the 2026-11-25 R4b handoff`
