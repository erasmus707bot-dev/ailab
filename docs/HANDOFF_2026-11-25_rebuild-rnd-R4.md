# HANDOFF 2026-11-25 — R4 🏁 proof ladder, rung 1 (arm-wrestle clip → 2 women) — build prompt #2

## Result — ✅ works, one real identity flaw (13:05–13:30, story session, via the Lab API)
- Breakdown `bd-f30682caee785320` (11 shots, 0–29.5 s) · cast Mara + Dina (2 women, designed by `tools/r4_rung1.py`) · level 2 ·
  🆓 pan-and-zoom · ✍️ rewrite + 🎙 narrator. The 12:06 script run made nothing; a 12:40 run was killed by the 12:42 Lab restart
  after 2 shots; resumed twice (one hermes-mcp restart mid-run) — **finished stills were kept each time** (restart-safe holds).
- **11 / 11 shots, 👁 avg 97 %, $0.000.** Film `video-testing/videos/rebuild-rebuild-test-r7ouawxxp60-20261125-132518.mp4`.
- By eye (original frame vs rebuild, shots 1/4/7/10): the two men became the two women; **both hold** across shots (red braid +
  glasses + plum top · grey hair + red top); room, crowd, table, grip and framing follow the original; **the source's burned-in
  captions are gone**.
- ❌ Pass bar not fully met: shot 7 "identity trouble" survived 🔁 Retry. Looked at it: 👁 says "merged limbs", but the real fault is
  **a third person — the standing onlooker — is a copy of Dina** (same grey hair, same red outfit). The source scene has a standing
  spectator and the cast look leaked onto them; "exact count" passes because onlookers are allowed.

## Fix idea (not built — `ailab/rebuild.py` is still another session's uncommitted R3 work)
- Add an identity point: "Apart from the two people arm wrestling, does anyone else in the picture have the same hair and outfit as
  either of them?" (want: no) → counts as an identity miss → the $0 remake adds "onlookers in plain dark clothes, different hair".
- Same leak is possible in 📖 Story crowd shots.

## Owed
- That identity point + re-run shot 7 · commit R3 (`rebuild.py`, `test_rebuild.py`, `tools/r4_rung1.py` + hunks in agent/server/
  index.html) — its own session's job, uncommitted since 12:22 · Argus touch test of 🎬 Rebuild + ⚖️ Review · rung 2 (next clip).
