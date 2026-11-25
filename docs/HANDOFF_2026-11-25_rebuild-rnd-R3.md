# HANDOFF 2026-11-25 — R3 🎬 Video Rebuild (build prompt #2)

Depends on: #1 M4 breakdown (Hermes `a925b500`, fix `569a6e28`) · R1 cast · #1 M2 refs · #1 M3 story helpers (`story.segment / join /
_clip_ai`, other session, uncommitted) · Hermes `narrate` / `narrate_status` (other session).

## Shipped (ailab, uncommitted — same uncommitted base)
- `ailab/rebuild.py` (new) — breakdown → **beats** (busy scenes split evenly, 2–4 s, said-words shared out) with clean recipes
  (source looks scrubbed) → per beat: still with the beat's cast anchors as `refs_abs` + official-style Look → 👁 recipe points **+
  identity points** (exact count · each person's hair + outfit · no hair/outfit swap · no merged limbs) → one $0 remake on a low score
  or identity miss → clip: 🆓 pan-and-zoom ⭐ · 🏠 local AI · Venice (one price card first) → AI clips re-checked on 3 frames → sound →
  joined film. Record `.shelf/rebuild/<bd>.json` (beats, scores, identity misses, sync table, 🔒 personal).
- Switches (Gate A1 ⭐ defaults): 🔁 whole ⭐ / 🎯 pick scenes · level 2 ⭐ / 3 → **"not available yet"** note (no motion-transfer
  host wired; 🔒 private source says it never leaves gandalf); never spends · audio ✍️ rewrite+narrate ⭐ (writer re-tells the
  transcript per beat) / 🔊 keep original (source audio cut per beat) / 🔇 silent · voice 🎙 narrator ⭐ / 🗣 per character (Kokoro
  voices from `narrate_status`) / 👄 lip sync → not available yet, falls back to per-character.
- 🔁 Retry: `{"retry": k}` re-makes beat k only, keeps every other still/clip, rejoins.
- `batch.py` kind `rebuild` · `agent.py` dispatch · `server.py` `GET /api/rebuild` (list / record) · `GET /api/rebuild/src` (only the
  record's source, inside ~/hermes-data, ≤ 400 MB).
- `index.html` — start card **🎬 Rebuild a video with my cast** (beside 📖 Story): cast picker, video pick, mode + scene strip, level,
  sound, voice, clip path, ▶ Rebuild it. **⚖️ Review**: original + rebuild side by side, original follows the rebuild through the beat
  table (play / pause / seek), per-shot row (👁 score, ⚠️ identity misses, ▶ Jump, 🔁 Retry this shot), ✅ Keep whole rebuild.
  Stacked on a phone.

## Tests
- ailab full suite **599 pass** (14 new `test_rebuild.py`: norm, beat splitter, no source looks, identity points + parser, cast
  letters, sync offsets, private level 3, whole run $0 with narration, identity swap → one $0 remake each, retry one beat only,
  lip-sync/private notes, no cast explains, Venice shows a price card before any spend, UI wiring).
- Hermes breakdown tests 7 pass after the looks-regex fix.

## Live — NOT run (shell can't reach the Lab / Hermes / ComfyUI)
```bash
systemctl --user restart hermes-mcp && systemctl --user restart ailab
```
R4 rung 1 is the live proof: your ~30 s hand-slap / arm-wrestling clip into a Lab project → 🎞 Break it down → 🎭 cast (♻️ or 🆕) →
🎬 Rebuild a video with my cast → ▶ → ⚖️ Review. Pass bar: every shot ≥ 70 % with no identity miss, total spend shown.

## Owed
- Live check / R4 rung 1 · Argus touch test (start card, scene strip, review pair, retry) · ailab commit after M1 → M2 → R2 → R1 → M4
  → M3 (other session) → R3.
- Level 3 host + lip-sync host: R0 Gate B1 (Venice Kling motion-control, quote-probe first) still unbuilt — the switch says so.
- Night tail: none (ailab base uncommitted).

Continue: `continue video rebuild + cast + styles + R&D from the 2026-11-25 build prompt #2` (next = R4 proof ladder — needs your clip).
