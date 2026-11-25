# HANDOFF 2026-11-25 — M4 🎞 Video breakdown (prompt #1, built for prompt #2 R3 + R5)

## Shipped
**Hermes** — commit `a925b500`
- `forge/projects/mcp_breakdown.py` + MCP tools `video_breakdown` (do) · `breakdown_get` · `breakdown_list` · `breakdown_search` (look).
- Any video in Hermes's folders (Harvest library, `~/hermes-data` incl. Lab project files, picture library): scene cuts
  (`viewer_tools._scene_times`, short scenes folded, ≤ 60) → start/middle/end frame → local `qwen3.5:4b` captions the middle
  frame + writes a **shot recipe** from start+end (subject · setting · motion · framing · camera · light; people = person A/B,
  looks words scrubbed) → transcript words per scene (Harvest transcript first, else faster-whisper if installed) →
  `nomic-embed-text` vector → `~/hermes-data/breakdowns/bd-<id>/breakdown.json` + `frames/` + standalone `breakdown.md`.
- $0, one card slot for the whole video, nothing leaves gandalf. `private` kept (own flag or 🔒 Harvest item/collection) for R3
  level-3. Restart-safe: finished scenes kept, the next call carries on. Search = meaning, falls back to plain words.

**AI Lab** — uncommitted (same uncommitted base as M1/M2/R2/R1)
- `ailab/rip.py` (new) — 🎬 Make one like this (recipe → words, person A/B → the project's chosen cast names, page starts a
  picture run = his tap) · 📌 Use frame as reference (copied into `pictures/`, pinned) · recipe shelf `.shelf/recipes.json`.
- `server.py` — `/api/breakdowns|breakdown|breakdown/search|breakdown/status|breakdown/pic` · `POST /api/breakdown/start|make|frame`.
  `_taste()` + improver now also get the last 5 recipe-shelf lines.
- `index.html` — video viewer `🎞 Break it down` · 📚 Library → 🎞 Video breakdowns (ask-across-videos box, list, scene sheet
  with frame · Shown · Said · Recipe · two buttons; stacked on a phone).

## Not built
- 📦 Add frames to dataset (Gate C1 = no trainer) · 🏃 Use this motion (needs R3's level-3 switch) · PDF export (the .md is there;
  Paperless one-click unchanged).
- **M3 📖 Story: NOT built by this session** — another session is building it right now (`ailab/story.py`, 09:15 local,
  uncommitted). Left alone to avoid two copies.

## Tests
- Hermes `forge/projects/tests` **117 pass** (7 new: spans, recipe shape + looks scrub, cast swap, whole fixture clip
  cut→frame→caption→merge, search meaning/words, restart keeps scenes, path guard).
- ailab full suite **571 pass** (6 new `test_rip.py`).

## Live — NOT run (shell can't reach Hermes / Ollama)
```bash
systemctl --user restart hermes-mcp && systemctl --user restart ailab
```
Lab → a project with a video → open it → 🎞 Break it down → sheet opens (≈ 15–20 s per scene warm) → 🎬 Make one like this on
one scene. Harvest videos have no button yet — R3/R5 call `video_breakdown` on them directly.

## Owed
Live check · Argus touch test (Break it down, sheet, both buttons, search box) · ailab commit in order M1 → M2 → R2 → R1 → M4.
Night tail: none (ailab base uncommitted).

Continue: `continue video rebuild + cast + styles + R&D from the 2026-11-25 build prompt #2` (next = R3 🎬 Rebuild once M3 lands).
