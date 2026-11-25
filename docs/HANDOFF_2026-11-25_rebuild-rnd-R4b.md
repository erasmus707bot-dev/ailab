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

## Push + Argus (14:48–15:00)
- Push: **blocked here** (Cowork allows no git push). Scott: `cd ~/ailab && git push origin master`.
- Argus, partial: Rebuild card at 494 CSS px — no sideways scroll, every control ≥ 44 px, real taps on 👀 Stage + 🎬 summary OK.
  **Found + fixed** (`index.html` base `select` rule): 9 unclassed dropdowns showed cream text on the browser's light-grey box.
  ⚖️ Review opens by JS click (2 videos, rows, no errors); the **real-touch** pass is not done.
- ⚠️ Rig trap: `webeval` ran in a different phone Chrome tab than the one on screen (2 tabs open), so a rect-based tap hit
  **▶ Rebuild it** on the visible tab — it only re-joined the kept stills ($0, film `…-145750.mp4`). Tap from the `frame`
  image when 2+ tabs are open. Then another session took the phone (/models) — stopped there.

## Owed
Shot-7 retry (above) · push ailab · Argus real-touch pass of ⚖️ Review (open, play/seek sync, ▶ Jump — not 🔁 Retry) · rung 2 needs a Twister clip (none on gandalf).

Continue: `continue video rebuild + cast + styles + R&D from the 2026-11-25 R4b handoff`
