# HANDOFF 2026-11-25 — 📓 Craft Book (the Lab learns the work, not only Scott)

Commits: ailab `afde7a6` · hermes `f1b55deb` (session init § Craft tail). Not pushed.

Scott 2026-11-25: "teach my system as you build with it so that it gets better … anything done these past few days or in
the future must be built into the ai lab system." Gate: he picked **1** — measured notes go live by themselves (with undo);
notes written by hand get one batch review. Lab tests **648 OK** on the working tree (626 before; +22 craft, 1 flag list updated).

## What it is
- `ailab/craft.py` — notes `{kind, when, do, why}` in `~/.config/ailab/craft/notes.json`, change log + ↶ undo, sensitive gate.
- **Use:** `picture.write_prompt` (pictures + first frames) and `makers.write` (video, motion, doc; story shot lists opt in)
  add the fitting live notes to the writer's system prompt. Step line: "📓 used 2 craft notes: …". His words are never touched.
- **Build lessons** (`kind: build`) ride in `memory.for_context` → the Lab agent, Ask models and the 📝 Prompt builder see them.
- **Learn:** every 👁 check (picture, video, story shot) → used / helped per note, score with vs without notes per kind.
  A miss type seen 3× in the last 10 checks wakes its note **live** (count · look · writing · thing not shown).
  A 🔁 fix that raised the score keeps its wording on the note. ✅ Keep / 🗑 Throw away count on the notes that run used.
  Used 6×, helped 0 → flagged "Retire it?" (never removed by itself).
- **Seed:** `ailab/craft_seed.json` — 19 lessons from the Nov 22–25 handoffs + commits, each with its evidence
  ("not measured here" where it is general practice). They load as *proposed*.
- **Future:** fenced `craft` block in any `HANDOFF_*.md` (ailab/docs, hermes/docs) → 📥 Read new handoffs → proposed.
  Rule written into `ailab/CLAUDE.md` and `hermes/prompts/HERMES_SESSION_INIT.md` § Craft tail (v1.5.0).
- **Page:** `/craft` (📓 in the Lab top bar) — Waiting for you (✅ Make all live · ⬇ review .md · ⬆ answers), live notes with
  their counts, ➕ add your own, ↶ undo. 23 px text, 48 px targets, light/dark.
- Flag `craft` (off until the go-live line). `config.json "craft": {"on", "max": 6, "holdout": 5}` — holdout 5 = every 5th
  run goes without notes so the page can show with vs without. Set 0 to stop that.

## NOT covered (honest gaps)
- Notes reach **writer models only**. Makers that build the prompt in code get none: cast sheets (`cast.py`),
  `story.shot_prompt`, `rebuild.words_for`, batch variations. Their lessons from this week are already in code.
- Batch pictures are checked by `batch.look_at` — not yet sent to `craft.observe`.
- 🔁 Loop ratings (`creative_rate`, Hermes side) do not feed the Craft Book yet.
- "helped" for notes without a miss type = score ≥ the kind's average before the note went live (min 70). Rough on purpose.
- The 19 seeds: 5 are marked not measured (general practice or untested wording); the rest cite a live result.

## UNVERIFIED — live, not run (shell can't reach the Lab or restart it)
- Go-live, page in a real browser, Argus touch test of `/craft`.
- Real writer + real picture with a note riding along; with/without scores after ~20 pictures.

## Owed on gandalf (one line)
`bash ~/ailab/tools/ailab-craft-golive.sh`

## Then
1. Lab → 📓 → read the 19 → ✅ Make all of these live (or one by one).
2. Make 5 pictures (one with a number of things, one watercolor). Each run should show a "📓 used …" step.
3. Tell Claude "craft is live" → live proof + Argus touch test + the three gaps above.

Continue phrase: `continue AI Lab Craft Book from the 2026-11-25 handoff — live proof + gaps`

## Session 2 (2026-11-25 pm) — ailab `37bae60`, 652 tests OK
- Checked live (Chrome → /api/craft): go-live ran · flag on · holdout 5 · **19 proposed, 0 live**. Live proof waits on Scott's ✅.
- Gap closed: batch pictures → `craft.observe(..., compare=False)` — misses wake notes and fix wording is kept; the
  with/without score skips them (batch words are built in code, would bias "without"). Needs a Lab restart to load.
- Gap re-scoped: 🔁 Loop pieces are run by Hermes executors (`forge/creative/executors.py`), not Lab runs — they never
  carry craft notes, so a rating has nothing to credit. Needs a choice (see chat), not wiring.
- Still open: code-built prompts (cast, story.shot_prompt, rebuild.words_for) get no notes — by design for now.
