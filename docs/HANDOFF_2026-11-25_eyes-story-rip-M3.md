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
