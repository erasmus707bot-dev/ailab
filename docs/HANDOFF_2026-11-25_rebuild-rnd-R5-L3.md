# HANDOFF 2026-11-25 — R5 🧪 R&D engine + R3 level 3 🏃 same movement (build prompt #2)

## Shipped
**Hermes — `ef764ab4` R5**
- `forge/rnd/engine.py` — topic → ① intake (🎞 broken-down videos by meaning, 🌐 SearXNG on gandalf, 🧩 Abilities rows,
  🔬 Decompiler findings; archive checked first) → ② extraction (local `qwen3.5:9b`, every claim tied to source + speaker +
  timestamp/URL) → ③ verification (only **independent** evidence: a different site / channel; paid model on the `rnd` cap;
  ✅ / ⚖️ / ❔ + 💰 selling flag) → ④ synthesis (conclusion, confidence, pro, con, what would change it, ERASMUS + Hermes use).
  ⬇ INTAKE_ / CLAIMS_ / VERIFY_ / BRIEF_ / FINAL_ .md, each standalone (glossary on top, no relative links).
- `rnd` cap $1/day in `DEFAULT_CATEGORY_CAPS`, in `SEPARATE_DAILY`. Over the cap → ⏸ "waiting for tomorrow's budget", no ping.
- ⭐ standing topics: `python3 -m forge.rnd.engine standing` re-reads new sources only; Telegram ping (existing Hermes alert
  channel) only when the conclusion changes or confidence moves ≥ 10. Finished / stuck ping once.
- Restart → a running topic shows ⏸ paused; ▶ Resume carries on from its stage. 📌 Pin → 🧠 Notes & Memory board "🔬 R&D".
- Dashboard: 🔬 Study → **🧪 Research & Development** (`/rnd`, owner only): topic box + ⭐, claim search, topic cards with stage
  chips + ⬇ .md per stage, 👀 Open (brief, claims, notes), ▶ Resume / 🔄 Re-check, ☆/⭐.
- Also added finder words for the 🗄 storage card (test_finder was red from another session).

**Hermes — `aaccefc5` level 3**
- `video_make` / `video_quote` take `video_b64` for `kling-*-motion-control`: picture (`image_url`) + driving clip (`video_url`,
  mp4/mov/webm ≤ 50 MB). `probe_motion.py` = free quote only → `~/hermes-data/settings/motion_probe.json`.
- **UNVERIFIED:** Venice's exact field for the driving clip (docs list `video_url` for video-to-video; Kling motion control isn't
  spelled out). First paid clip proves it — only after Scott's tap.

**AI Lab — uncommitted (same base)** `rebuild.py`: level 3 reads the probe file; private source refused; source beats cut to
small mp4 drivers; one price card (per-shot + total) → tap → video_make per beat; identity check on 3 frames; a failed beat
falls back to level 2. Count check now ignores onlookers (live clip has a crowd).

## Tests
Hermes `forge/projects` + `forge/rnd` **129 pass** · dist `test_rnd_web` 3 + `test_finder` 7 pass · ailab **653 pass**.

## Live — NOT run (shell can't reach gandalf services)
```bash
systemctl --user restart hermes-mcp && systemctl --user restart hermes-dashboard && systemctl --user restart ailab
cd ~/hermes && python3 -m forge.projects.probe_motion          # free: prices Kling motion control
docker run -d --name searxng --restart unless-stopped -p 127.0.0.1:8888:8080 searxng/searxng   # R&D web route, then enable json format
```
Then 🔬 Study → 🧪 R&D → one topic end to end. Optional nightly: `crontab -e` → `30 3 * * * cd ~/hermes && python3 -m forge.rnd.engine standing`.
⚠️ Paid model id `google/gemini-2.5-flash` via OpenRouter is UNVERIFIED — set `~/hermes-data/settings/rnd.json` {"provider","model"}
if it refuses (R&D then checks locally and says so).

## Owed
Live R&D topic · probe_motion run · SearXNG install (≈ 300 MB image) · Argus touch test (R&D page) · R6 (proposal → trial →
decision → archive) not started · R4 rung 1 on the arm-wrestle clip (Scott running it).

Continue: `continue video rebuild + cast + styles + R&D from the 2026-11-25 build prompt #2`
