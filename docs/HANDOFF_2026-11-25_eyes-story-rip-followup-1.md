# HANDOFF 2026-11-25 — eyes + story + rip follow-up 1: 📖 Story props + who-in-shot

## Shipped — ailab `e349b74`
- **Who is in a two-person shot:** already fixed before this session — `17b16b7` (a name in the action joins the shot) +
  `1e0943d` (👁 onlooker point: nobody but the cast wears a cast look). Nothing added.
- **🧳 Props:** bible gets `props` (key objects/vehicles with their look, e.g. "two red motorbikes"); planner lists the props
  per shot; `story.props_in()` also adds any bible prop whose main word is in the action/place ("rides off on his motorbike").
  They ride into the picture words **and** the 👁 words ("…, with two red motorbikes, …") → a bicycle now costs points.
- **🐛 Bible editor wiped When** on 💾 Save (the form never sent it). `save_bible` now merges over the stored bible; editor
  gained 🕒 When + 🧳 Things that come back fields.

## Tests
- `test_story.py` 23 pass (3 new: props by word / listed / none, props reach only the lamp shot end-to-end, editor save keeps
  unsent fields). Full ailab suite **676 pass** (run in 4 chunks). `index.html` scripts parse (node --check).

## Live — NOT run
`systemctl --user restart ailab` → 📖 Story → 🆕 New story, idea with a vehicle ("Aria and Ben race motorbikes through the
night market") → ⚡ Short · 🆓 → check 📚 bible shows 🧳 Things, every shot keeps motorbikes. Then 💾 Save the bible → When stays.

## Owed
Live check · Argus touch test (two new bible fields) · git left `.git/stale-HEAD-lock-e349b74` (moved, harmless; delete when allowed).
Night tail: none.

Continue: `continue AI Lab eyes + story + rip follow-ups — option 2` (👁 $0 auto-retry without the paid writer).
