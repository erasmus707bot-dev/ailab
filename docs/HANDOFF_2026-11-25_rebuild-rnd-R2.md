# HANDOFF 2026-11-25 — R2 🎨 Official styles + lesson promotion (build prompt #2)

Gate (R0, "proceed" = all ⭐): A1 rewrite+narrate / narrator · B1 Venice Kling motion-control (quote-probe first, off) ·
C1 SearXNG · D1 ERASMUS intake folder · E1 R2 → #1 M2 → R1 → #1 M3+M4 → R3 → R4 → R5 → R6.
Audit: `~/hermes/docs/AUDIT_2026-11-25_rebuild-cast-styles-rnd.md`.

## Shipped (ailab)
- `ailab/styles.py` (new) — global store `<AILAB_HOME>/styles.json`: `{name, look[], model, prompt_lessons[], example_pictures[], locked:true}`.
  `promote()` copies the project's kept/thrown lines (+👁 seen) into the style; a taken name is refused (locked never overwritten).
  `choose()` per project → `<project>/.shelf/style.json`, sets the Look chips' last Look. `proposal()` ≥4 kept share Look+model,
  none covers → once; Not now snoozes until 4 more; Never final. `answer()` Yes needs a name.
- `shelf.keep(..., facts)` stores `look` + `model` on each kept entry (`styles.facts(run)` from the run's look step + last picture/video).
- `picture.py` / `video.py`: no Look line in his words → the chosen style's Look. `write_prompt` system prompt + style lessons (`_style_note`).
- `server.py`: `_taste()` adds `style{name,lessons}`; improver prompt gets "Lessons from his official style …".
  `GET /api/styles` · `POST /api/styles/make|choose|answer`.
- `index.html`: 📚 Library → `🎨 Official styles` fold — proposal card (🔒 Yes / Not now / Never for this look), style picker,
  `🔒 Make this an official style` on the last 6 kept results that have a Look/model.

## Not built
- Button on a Library *file* tile (only on kept entries; a file only becomes a style source once kept).
- Hermes-side MCP access to styles (not needed until R1/R3 call it).

## Tests
- `tests/test_styles.py` 9 pass. Full ailab suite: 541 pass (`test_restore` mid-step test flaked once under full-suite load, passes alone 14/14).
- `index.html` scripts parse.

## Live — NOT run (shell can't reach the Lab service)
On gandalf: `systemctl --user restart ailab` → open a project with ≥1 kept picture → 📚 Library → 🎨 Official styles →
name + 🔒 Make this an official style → pick it in a second project → make a picture there with no Look: the run's 🎨 Look step shows the style's chips.

## Owed
- Live check · **Argus touch test** (fold, select, buttons on phone) · commit.
- **Uncommitted.** Reason: `server.py shelf.py picture.py video.py index.html` carry prompt #1 M1's uncommitted hunks that R2 builds on
  (shelf `seen`, `_taste` 👁 lines); committing R2 alone would not run. Commit M1 first, then R2. Clean new files: `ailab/styles.py tests/test_styles.py docs/HANDOFF_2026-11-25_rebuild-rnd-R2.md`.
- **Night tail: none** — base uncommitted (same reason as M1).

Restart: `systemctl --user restart ailab`.
