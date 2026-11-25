# HANDOFF 2026-11-25 — eyes + story + rip follow-ups: live checks (15:00–15:20, Chrome on gandalf)

Both services were already running the new code (Lab bible has `props`; dashboard answers `bd_*`).

## ✅ 🎞 Harvest Break it down (hermes `687a6840`)
- "Managing AI — CompTIA A+ 4.10" (10 min) → 3 scenes in ~3 min, $0. Sheet opened from ⋯ More → 🎞 Break it down:
  frames load, 👁 Shown + 💬 Said right. Saved `~/hermes-data/breakdowns/bd-93b07b7a7aa525a3/`.
- Seen, not fixed: talking-head video cuts coarsely (one 438 s scene → its 💬 Said is the whole transcript, a long block);
  scene 3's recipe (podium + audience) doesn't match its Shown (man at a mic) — recipe reads start/end frames, caption the middle;
  title-card scene has an empty recipe → no 📋 button (correct). Sheet text inherits the page's serif font.
- Library is mostly adult videos — the test used a CompTIA lesson on purpose.

## ✅ Bible editor keeps When (ailab `e349b74`)
- Project `test`: saved the bible without `when` → "midnight, neon light, rain on the stones" kept, facts unchanged.
- 🕒 When + 🧳 Things fields render in the 📖 Story fold.

## 🐛 → fixed: Story props (ailab `8faf85b`, live after the next Lab restart)
- Run in `fast-pictures-check` ("Two couriers race their red motorbikes through a rainy night market…", stills only, no voice):
  bible props = "two red motorbikes", "a small brown package" ✅. The planner listed them in its own words ("red motorbike")
  → the exact match dropped them; shot 3 "swerving through the crowd" would have had **no bike**; shots with "motorbike" in
  the action got "two red motorbikes" → a whole pack of red bikes in one-rider shots (`_pilot/props_check.jpg`).
- Fix: match by the main word in the planner's list too; the planner's words win when they keep the look words ("red
  motorbike"), else the bible's. Tests: test_story 20 pass.
- That run was left going on the old code ($0, ~3 min a shot, card swaps ComfyUI ↔ 👁). Re-run after restart to see shot 3 keep its bike.

## Not checked live
- 👁 $0 redo (`e5db841`) on plain 🖼 pictures — the Story still path has its own remake; shot 1 was made twice there.
- Argus touch test — all three still owed.

## Restart
`systemctl --user restart ailab`

Continue: `continue AI Lab eyes + story + rip follow-ups — option 2`

## 15:17 — proof on the real run (old code still live, no restart yet)
- Same 6 planned shots through both matchers: **old** → shots 3, 4, 6 get no prop; **new** (`8faf85b`) → every shot gets
  "red motorbike" / "small brown package" / "red motorbikes".
- Shot 3 "swerving through the crowd" made on the old code: Alex **on foot in both tries**, bike gone
  (`~/hermes-data/ailab/_pilot/props_shot3_old.jpg`). Shot 2 (bike named) kept it.
- After `systemctl --user restart ailab`: in `fast pictures check` → 📖 Story, untick 🆕 New story → ▶ Make the story — the
  unfinished chapter carries on from shot 4 on the new code (shots 4 + 6 are the ones the old code left bare).
