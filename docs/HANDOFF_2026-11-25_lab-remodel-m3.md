# HANDOFF 2026-11-25 — AI Lab remodel M3 (Library: change · compare · improver learns)

Scott picked **1: M3**. Builds on `docs/HANDOFF_2026-11-25_lab-remodel-m2.md`.

## Built — NOT committed (same reason: index.html carries other sessions' overlapping uncommitted hunks)
Files: `ailab/web/index.html`, `ailab/server.py`, `tests/test_remodel_m3.py` (new), `tests/test_remodel_m1.py` (1 string), this doc.
My diffs: `~/hermes-data/_tmp/remodel/page_m3.patch`, `server_m3.patch`.

- **✏️ Change this** on every opened 📚 Library item. Picture/video: `GET /api/shelf/source` finds the words it was made
  from (newest run that made it, else its ✅ kept entry) → starts `<those words>\nChange: <his words>` with the 🖼/🎬 chip.
  No words on record → it says so and starts nothing (no made-up prompt). Page/writing: starts an 🔧 Edit run on that file.
- **⚖️ Compare** chip in the Library: tap two → side by side (stacked on a phone), each with ⬇ and 👀 Open this one.
- **🪄 improver learns:** `App._taste` reads the project's shelf — last 5 kept and last 5 thrown-away prompts (first line,
  de-duplicated) go to the writer as "worked for him" / "do not steer toward". The card shows "🧠 learned from N kept · M thrown away".

## Verified
- Browser (cloud container, faked source/start): picture change sent `a red fox by a lake\nLook: Oil painting\nChange: make it sunset`
  with `["image"]` (old Change line dropped, Look kept); no source → nothing started + the note; doc change sent an `["edit"]`
  run on `docs/story.md`; compare showed 2 figures; no page errors.
- Device VM tests: 0 new failures against the M0 baseline; 3 new tests pass.

## NOT verified
- Anything on gandalf with real runs. Argus touch test owed (M1–M3).
- A picture "change" re-makes the picture from its words plus the change — it does not edit the pixels of that file.
- Words are only on record for runs the Lab still holds or that were ✅ kept; older Library items answer "no longer has the words".
- Whether the kept/thrown lines actually improve the writer's output (needs his eye over a few rounds).

## Scott on gandalf
1. Restart the Lab (desktop icon). 2. 📚 Library → tap a picture → ✏️ Change this. 3. ⚖️ Compare → tap two.
4. ✅ Keep two results, 🗑 throw one away, then 🪄 Improve my prompt → look for the 🧠 line.

## Next
- **M4 Wrap:** 🏁 Project done (hand-off to Media Studio / Make it an app from the Shelf), Argus touch test, commit once the
  other sessions' index.html work lands, ledger line.

Continue: `continue AI Lab remodel M4 from the 2026-11-25 handoff`
