# HANDOFF 2026-11-25 — Asset library M1: ⭐ Make a character + 📇 Characters shelf

Scott picked **1** (build M1 after the M0 probe: local FLUX.2 Klein 4B held identity 95/100, $0, armed).
Commit ~/ailab `00bf09f` (not pushed). Other sessions' uncommitted edits in server.py / index.html / cast.py left alone (staged hunk-exact from HEAD).

## Already there before this module (another session's 🎭 cast build, 2026-11-25)
Hermes store `~/hermes-data/assets/c-*/` (card.json, pictures/, sheet/, uses.json) + MCP cast_list/get/make/pin, adults-only, no real people; Lab 🎲 Design a cast, 🎭 Character sheet, project cast strip (faces sent as reference pictures). So M1's store + MCP part was done; this module adds the missing Lab parts.

## Built
- **⭐ Make a character** on every picture (made card, 🎛 batch tile, 📚 library viewer): name · age (18+, required — Lab and Hermes both check) · a few words · ☑ Use in this project now → card in the global cast (anchor = that picture), and into this project's cast (max 4, says so when full).
- **📇 Characters** fold in 📚 Library: card per character (face, name, age, 📌 here, projects), search, tap → details (description, sheet views, used in …), 📌 Use in this project / ✕ Take off.
- `ailab/charcard.py` · POST `/api/cast/character|use|leave` · GET `/api/cast/one`.

## Tests
test_charcard 6 pass · working tree 707 pass. Committed tree: HEAD's 3 `test_made` rephrase failures are pre-existing (other session's uncommitted work), not from this commit.

## Live 2026-11-25 ~12:50 (Lab already restarted by another session)
- 📇 shelf rendered from the real store: Dina 43, Mara 24, Ben 42 (📌 here), Aria 38 (📌 here); Dina's details: description, 5 sheet views, "Used in: video-testing".
- Refusals live: age 17 → 🔞 refused before Hermes; `../../etc/passwd` → refused.
- **Not done live:** saving a real new card (would add a test person to your global cast — no delete tool yet). Try it: a person picture → ⭐ Make a character.
- Screenshots timed out in Chrome (renderer busy) — Argus touch test owed.

## Left in the outline
- **M2:** sheet already exists (🎭 Character sheet). Left: ✅ same / 🔁 redo per view, and the **raw 3D model** from front/side/back via Meshy (spends credits, $25/month cap).
- **M3:** project cast strip already sends faces. Left: per-run character chips + `@Name` typing, and a "From assets" picker in Hermes Image Studio / 3D studio.
- M4 closet · M5 objects · M6 places · M7 scenes · M8 real people (⛔ permissions review).

Continue: `continue asset library build from the M1 handoff`
