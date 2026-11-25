# HANDOFF 2026-11-25 — eyes + story + rip follow-up 2: 👁 $0 redo after a low score

## Shipped — ailab `e5db841`
- Before: the only automatic redo was 🔢 a **wrong count** (`count_fix`, same prompt, new seed).
- Now: any 🖼 picture on a **local** model that scores under his low line (`eyes.low`, default 70%) gets a redo — new seed,
  the misses added after the prompt in code (`picture.redo_prompt`: "… Make sure: clearly show a bathtub."; comma tags for
  Pony/Illustrious). **No writer call → $0.** His words stay first, byte for byte. A count miss alone keeps the prompt.
- The better of the two by 👁 score becomes the main picture; both are saved. Step line says "$0 on gandalf, no writer".
- Count he sets: `~/.config/ailab/config.json` → `"eyes": {"retry": n}` (0–3, 0 = off). Not set → old `count_fix.retry` → 1.
- Paid routes (Venice etc.) never redo on their own — 🔁 Fix and try again stays a tap. Batches unchanged (they sort, ⭐ best).

## Tests
- `test_count_fix.py` +4 class tests + 1 function test (redo spells the miss after his words, count-only keeps prompt,
  count he sets 0/2, good score + paid route never redo, tag form). `test_refs` fallback test now checks "never Venice"
  (the 2nd juggernaut call is the redo). Full ailab suite green (61 modules, 4 chunks).

## Live — NOT run
`systemctl --user restart ailab` → 🖼 on a local model, ask for something it tends to miss (e.g. "a red fox wearing a blue scarf
on a snowy bridge") → if 👁 < 70%, 📜 Steps shows "👁 only n% match — one more try … ($0 on gandalf, no writer)" and two pictures.

## Owed
Live check · Argus: nothing new on screen (no UI change) · `.git/stale-*` lock files from several sessions (delete when allowed).
Night tail: none.

Continue: `continue AI Lab eyes + story + rip follow-ups — option 2` (🎞 Break it down on Harvest videos).
