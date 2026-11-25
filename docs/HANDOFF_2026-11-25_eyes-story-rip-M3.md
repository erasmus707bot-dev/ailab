# HANDOFF 2026-11-25 — M3 📖 Story (prompt #1, built for prompt #2 R3)

Order (Gate E1): R2 ✅ → M2 ✅ → R1 ✅ → **M3 ✅ (this)** + M4 ✅ (other session, same morning) → R3 → R4 → R5 → R6.

## Shipped
**Hermes** — `0feec1f5` (registry lines rode in `a925b500`)
- `forge/projects/mcp_voice.py` — MCP `narrate` (look, $0: one line → WAV from Lector's Kokoro worker 127.0.0.1:8807, cached)
  · `narrate_status`. Not installed → `not_enabled` + the install command.

**AI Lab** — `a682424` (M4's Lab half committed after it as `4971af8`, full suite green)
- `ailab/story.py` (new) — one run = one chapter. 📚 bible (`.shelf/story/bible.json`: title, tone, people, places, rules, facts)
  → 🗒 outline + shot list (who · where · action · camera · seconds · spoken line; Short clamps to 15–30 s, hook first, loop end)
  → 🖼 still per shot: the chosen 🎭 cast's anchors as `reference_images` (`refs.for_run` honours `batch.refs_abs`), Look from the
  official style, 👁 checked against its shot line; a low score on a **$0** still is remade once with the misses
  (`config "story": {"retries": n}`) → 🎞 clips: 🆓 pan-and-zoom ⭐ · 🏠 local path · 🔓 Venice (one price card for all shots,
  needs a tap) → 🎙 `narrate` per line → ffmpeg join into one film (`videos/story-<title>-ch<n>-….mp4`), no captions.
- 🔗 Continuity: before a chapter, checker vs bible facts → flags → card: ✏️ Fix the chapter ⭐ / 📚 Fix the bible / ↔️ Keep both.
  After a chapter, the writer adds what changed to the facts.
- Restart: chapter file holds shots/stills/clips; an unfinished chapter of the same form is carried on, finished shots skipped.
- ✍️ Words only → bible + outline + prose `docs/story-<title>-ch<n>.md`.
- `batch.py` kind `story` (price ≈ 1.5 picture per shot) · `agent.py` dispatch · `server.py` `GET /api/story` · `POST /api/story/bible`.
- `index.html` — Start screen → `📖 Story — short video, long chapters, or words` fold: 🎭 castPicker · idea · length · motion ·
  🎙 Narrator · 🆕 New story · ▶ Make the story / ▶ Next chapter (n) · 📚 Story bible editor · chapter list (🎞 Film / 📝 Read).

## Not built
- Hermes Quick Cut join — the Lab joins with ffmpeg (same result, no Hermes round trip). Open-in-Quick-Cut button: later if wanted.
- Multi-character per-beat reference weighting = R3.

## Tests
- `tests/test_story.py` 10 pass (bible restart, shot ↔ still ↔ anchors mapping, $0 remake, planted contradiction flag, restart
  skips shots, film joined with voice, narration-off reason, words-only). Hermes `test_mcp_voice.py` 3 pass.
- ailab full suite **581 pass** · Hermes `forge/projects/tests` **117 pass** · `index.html` scripts parse (node --check).

## Live — NOT run (shell can't reach the Lab / Hermes / ComfyUI)
On gandalf:
```bash
bash ~/hermes/forge/lector/deploy/install_tts_on_gandalf.sh      # Kokoro ≈350 MB, once — skip to test without a voice
systemctl --user restart hermes-mcp && systemctl --user restart ailab
```
Lab → project "game duo" (has the R1 cast) → 🚪 start → 📖 Story → ♻️ Reuse the cast → idea → ⚡ Short · 🆓 → ▶ Make the story.
**Pass:** 6 stills on the Stage with 👁 scores, both faces hold where both are named, one film plays (~20 s, voice if Kokoro is in),
result line ends "Spend: $0.000 — all on this computer". Then ▶ Next chapter (2) with 📚 Long to see the 🔗 check run.

## Owed
- Live check · **Argus touch test** (📖 fold, selects, two checkboxes, bible editor, chapter buttons).
- Night tail: none — R3 needs the M3/M4 live results first, and build prompt #2 is only in the Project (not under `prompts/`).

Continue: `continue video rebuild + cast + styles + R&D from the 2026-11-25 build prompt #2` (next = R3 🎬 Rebuild).

## Live 2026-11-25 09:36–09:40 (Kokoro installed, services restarted)
- ✅ Project `test`, ⚡ Short · 🆓 · 🎙, **no cast** (global cast is empty — R1's live run never happened). “Race to the Light”:
  bible → 6 shots → 6 stills on local FLUX.2 Klein (~30 s each) → 👁 avg 90% → pan-and-zoom → narration → **16 s film,
  720×1280, voice audible (mean −24.6 dB)**. **Spend $0.000.** ~4 min end to end. 6 facts went into the bible.
- Seen: without a cast both keepers came out alike (same coat and cap) — the cast references are what fix that.
- Fixed after the run: 👁 graded the bracketed looks ("Ethan (ambitious new keeper)") → now grades only what a picture can show,
  and each shot's 👁 line shows in 📜 Steps. Commit below.
- Still owed: R1 cast live run, then a Story with that cast (faces held per shot) · ▶ Next chapter with 📚 Long (🔗 check) · Argus.

## Live 2026-11-25 11:30–12:00 — cast + Story with the cast
- 🎭 R1 cast live: **“Aria & Ben” saved** to the global cast and chosen for `test` (3rd try — 2 Lab restarts by other sessions,
  1 cast_make "broken pipe"). Anchors went to Venice ($0.01 each, $0.02 total); sheets local $0. Tell-apart 1/1.
- 📖 Story “Night Market Showdown” (⚡ Short · 🆓 · 🎙, resumed twice after restarts / a Hermes outage — finished shots were
  skipped as designed): 6/6 shots, 👁 avg 88%, film `videos/story-night-market-showdown-ch1-20261125-120011.mp4`, **$0.000**.
- ✅ **Faces/outfits hold in every shot**, both people present in all 4 two-person shots (2 anchors as references).
- Found + fixed (committed, Lab restart needed for the last two):
  - `9095117` cast/story stay "running" between pictures → a restart shows interrupted, not a false done.
  - `a7683ba` cast_make got 6 full PNGs (~24 MB) > Hermes's 10 MB → pictures shrunk to 1280 px JPEG.
  - `697486b` Ben's anchor put the teal on his **shirt**, not his hair → all 5 sheet views failed same-face (0/5, correctly).
    Each anchor is now 👁-checked against its own brief (hair colour, outfit colour, one person) and remade ≤ 2×.
  - `64552d1` 👁 marked "Aria" missing (a picture can't show a name) → people are checked as they look (hair + outfit).
- Seen, not fixed:
  - Shot 6 has painted letters on the ground and signs with writing — the no-text rule leaks in busy street scenes
    (negative prompt is sent; FLUX.2 Klein ignores it partly). 👁's "no writing" point didn't catch it.
  - Night market drifts to daylight in shots 4–6 — time of day isn't in the shot line. Fix idea: bible `time` field carried into every shot.
  - Same false-"done" pattern exists in plain 🎛 picture batches (`batch.pictures`) — not touched (another session's hunks in batch.py).

## Live with a cast + chapters 2–3 — 2026-11-25 11:45–12:17 (eyes session, project image-testing, cast Aria & Ben)
- Ch 1 ⚡ Short "Midnight Delivery": hermes-mcp was restarted at 11:50 (a bare restart line) → run failed at shot 4. Re-run
  **carried on at shot 4, shots 1–3 kept** (restart-safe works). Result: 6 shots, 👁 avg 86%, **18 s film with narration, $0**.
- By eye (`~/hermes-data/ailab/_pilot/story_check.jpg`): **Aria holds** (purple top + skirt, braids, red bandana) in all her
  shots. **Ben holds** (teal shirt, orange trousers, orange cap). Misses: shot 5 adds a third person in Ben's colours holding the
  package (meant to be Aria) — 👁 said 86% and missed it; shot 6 shows them running, bikes gone; rainy city reads as dusk/day.
- Ch 2 📚 Long: 🔗 "no contradictions" (correct) → 8 shots, 👁 avg 80%, **35 s film with narration, $0**; bible facts 1 → 2.
- Ch 3 planted contradiction ("Ben never went near any tunnel — he took the bridge") → **🔗 flagged, card with ✏️ / 📚 / ↔️,
  nothing made before a tap.** But the stated reason was off-target ("the plan implies both characters are in the tunnel")
  instead of "Ben says he never used the tunnel". Run stopped, nothing made.
- 🐛 fixed (`49c6cb9`): 👁 graded camera moves ("missing: slow push-in, tracking shot") — a still can't show a move; moves are
  now dropped from the points, framing (close-up, wide) still graded.
- Owed: 👁 doesn't check *who* is in a two-person shot (shot 5) · checker reason wording · time of day in the shot line.
