# HANDOFF 2026-11-23 — AI Lab: the five fixes (from the 2026-11-23 decision doc)

**Source:** Docs artifact "AI Lab decisions 2026-11-23" (voice brainstorm). Order run: 3 → 5 → 1 → 4 → 2.
Lab tests **141 OK** (was 124). Hermes `test_mcp_server` 22 + `test_providers` 11 OK.

## Commits
- ~/ailab `c557794` — 🪞 Show & change committed (fix 3). Flag `live` still off until go-live.
- ~/ailab `6214e50` — fix 5, no false "finished":
  - agent `done` accepted only if a check (run exit 0, or Hermes `mario_level_check` playable / `mario_level_make` ok / `linux_app_build` pass) came **after the last write/edit**. First unproven `done` is refused back to the model; second → state **`unproven`** ("⚠️ Not proven"), never ✅. No-change runs say "ℹ️ No files changed".
  - **Stuck** = running with no new step for `stuck_after_s` (default 600). In run view (`stuck`, `quiet_s`) and `/api/state` `runs[]` (for the Hermes card / later Iris "finished or stuck"). UI shows 🟠 Stuck.
  - Compare: a lane that says done but fails Scott's checks → `unproven`; summary counts only proven lanes.
  - Review apply reads the file back before marking it applied.
- ~/hermes `ae40bbbe` — fix 1: `model_preferences.json` OpenRouter **on, use_for ["ailab"] only** (Hermes task routing + failover unchanged), default `deepseek/deepseek-v4.1-flash`, heavy `moonshotai/kimi-k3.1-pro`. ZDR + data_collection deny already in `llm_call`. Caps unchanged ($2/day, $0.50/run).
- ~/ailab `7a5764d` — fix 4: `ailab/robotcheck.py` + `/api/live/robot`. Headless Chrome (Playwright) opens Now + New, checks the 👆 spot changed (HTML/style/size), clicks it if clickable, compares page errors, saves screenshots under `~/.config/ailab/projects/<id>/live/robot/`. 🚦 **green only after the robot passes**; robot red → red; can't run / sign-in / no spot pointed → yellow.
  - Real-browser proof (cloud Chromium, two test pages): changed → green · unchanged → red · broken script → red · no spot → yellow.
- ~/ailab `db3d37e` — `tools/ailab-golive.sh` (fix 2 go-live).

## UNVERIFIED
- OpenRouter model ids (Lab's live list confirms them). Whether the OpenRouter key is already in Vault.
- Chrome/Chromium on gandalf PATH (script reports it). Hermes pages behind the owner rule may show a sign-in to the headless robot → yellow.
- Everything live (fix 2): Show & change frames, Keys page, panes, reboot-proof hermes-mcp.

## Owed on gandalf (one line)
`bash ~/ailab/tools/ailab-golive.sh`
Expect: ✓ playwright, ✓ browser path, ✓ flag live = on, connect script ✓ lines, services: active active, at boot: enabled, Lab page HTTP 200, mode connected · live True.

## Then (Claude, in Scott's Chrome)
1. Lab → ⚙️ Keys: OpenRouter shows on in Hermes; model list includes deepseek v4.1 flash / kimi k3.1 pro.
2. 🪞 Show & change on a Hermes page: point at a button, "make it bigger", ✨ Make it with deepseek → robot → 🚦; Throw away.
3. Panes drag/swap/reset; phone width stack.
4. Reboot proof: after Scott's next reboot, `systemctl --user is-active hermes-mcp` = active and Lab top bar "Hermes".

## Next
Five fixes code-complete. After the live proof: memory import + prompt builder (decision doc parts 2–3) — needs a build prompt first.
Continue phrase: `continue AI Lab five fixes from the 2026-11-23 handoff — live proof`
