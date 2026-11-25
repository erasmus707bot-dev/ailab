# HANDOFF 2026-11-24 — AI Lab self-edit + 🛡 walled-off Guard (rollback)

**Scott's ask:** the AI Lab can edit its own code and create/edit its own systems; it must be walled off from the
rollback tool; rollback systems in case it breaks.

## Scott's locked choices (2026-11-24)
- **1-1 Wall:** separate privileged guard (system service, root-owned program + root-only copies). Lab = gandalf → can't touch it.
- **2-1 Go-live:** Scott taps ✅ for every self-change (same pattern as today's held `apply`).
- **3-2 Scope:** the Lab may edit **the Lab and Hermes**, both behind the guard.
- **4-1 Keep:** last 30 copies + newest per day for 30 days (+ newest healthy copy always).

## M0 audit (done)
- Code size: ~/hermes tracked ≈ 33 MB (5,751 files) · ~/ailab ≈ 1.4 MB. hermes-forge (80 GB) is data — not guarded.
- Hermes = system service `hermes-daemon` (User=gandalf), dashboard 127.0.0.1:8780 `/health`. gandalf can't restart it without sudo → guard owns restarts.
- Lab = user service `ailab.service`, 127.0.0.1:8850, **no health route yet** (guard checks `/` until M4 adds `/api/health`).
- Lab today: srt sandbox; linked folders (~/hermes) are propose-only (held changes → typed `apply`); ~/ailab not linked; ↔ Before copies are previews, not rollback.
- **UNVERIFIED:** whether gandalf has passwordless sudo. If yes the wall is not real — `ailab-guard check` reports it.

## M1–M3 built + INSTALLED 2026-11-24 20:30 — `ailab-guard check` all ✅ (gandalf needs a sudo password)
Source `~/hermes-forge/ailab-guard/` — `guard.py` (stdlib only), `test_guard.py` (10 pass), `ailab-guard.service`, `install.sh`.
- Copies: git-tracked + would-be-tracked files only (ignored .env/data never touched); unchanged files hard-linked; links saved as links; never reads/writes through a folder that leads outside; refuses `..`/absolute/.git paths.
- Restore: saves a "before going back" copy first (undoable); files the change added are **set aside** in the store, not deleted; chowns back to gandalf; restarts; health check.
- Watchdog: `POST /api/watch` after go-live; 3 misses in a row (15 s apart) → restore pre-change copy + restart + one ntfy ping (`hermes-night`). No watch → never auto-rolls back. Watches survive a guard restart.
- 🛟 page 127.0.0.1:8860 (dark default, light toggle, 48 px buttons, "Tap again" confirm, works while Lab is dead). Install runs `tailscale serve --https=8860`.
- API (127.0.0.1 only): `GET /api/state` · `POST /api/snap` · `/api/watch` · `/api/restart` · `/api/restore` (needs `confirm:"restore"`). **No delete call.**
- Terminal: `ailab-guard list ailab` · `ailab-guard restore ailab last-good` · `ailab-guard check`.
- Running copy = /opt/ailab-guard (root). Editing the source folder changes nothing until Scott re-runs the installer with sudo.

## Install step (done)
```bash
sudo bash ~/hermes-forge/ailab-guard/install.sh
```
Then paste the `check` lines back. Every line must be ✅ before M4 lets the Lab edit itself.

## M4 + M5 built 2026-11-24 (UNCOMMITTED — another session has open hunks in config.py, server.py, index.html; commit named hunks only, never git add -A)
- `ailab/guardlink.py` (new): program_of (guarded = ~/ailab, ~/hermes), Guard client, trial copy + checks in srt (py_compile, node --check, JSON; Lab = full tests + import; Hermes = matching tests/test_<stem>*.py), "already failed before" comparison on a clean copy.
- `review.apply` → guarded targets go to `apply_group`: prove → Guard snap → watch → write (half-write → Guard restore) → restart via Guard after reply. Guard down or proof fail → nothing written. Guard source (`ailab-guard` path part) never writable.
- config: `live_ports` 8860/8861 → **8862/8863** (Guard owns 8860; if Scott's ~/.config/ailab/config.json sets live_ports, change it there too); `guard_url`, `guard_public_url`, `guard_watch_minutes`, `guarded`; the Lab auto-links itself as repo `ailab`.
- server: `GET /api/health`, `GET /api/guard`, `POST /api/review/apply_group`.
- UI (workbench ✋ list + 📋 Review): 🛡 badge, "testing first…" note, `🛡 Apply all N together`, 👀 watching line, 🛟 Rollback page link, Guard-down warning.
- Patches kept: tools/patch_m4_guard.py, tools/patch_m5_guard_ui.py (idempotent). Tests: tests/test_guardlink.py 11 ✅; full suite 423 ✅ (unittest, TMPDIR=/tmp); page script node --check ✅.

## M6 — drill PASSED 2026-11-24 20:46 (Guard restored server.py + Lab answering in ~40 s; Scott ran the pre-edit drill copy, so step 1 restart was skipped — the Guard's restart loaded M4/M5)
- `bash ~/ailab/tools/guard_drill.sh` — restarts the Lab (loads M4/M5), Guard copy + 3-min watch, adds a crash line to server.py, expects the Guard to restore + restart within 2 min. FAIL path restores by hand.
- Owed after: a real Lab-made change applied through 🛡 (Lab + Hermes), Hermes break drill, Argus touch test of 🛟 page + 🛡 rows, commits.

## (original plan) M4 — Self-edit lane (Lab) · model: Sonnet
- `/api/health` route in `ailab/server.py` (ok + git short sha); switch guard config `ailab.health` to it.
- New lane "🔧 Improve the Lab / Hermes": the agent works on a **trial copy** (tracked files rsynced to `~/hermes-data/ailab/_trial/<run>/`), never the real folder.
- Hard deny in `repos.py` + srt `denyWrite`: `~/hermes-forge/ailab-guard`, `/opt/ailab-guard`, `/etc/ailab-guard`, `/var/lib/ailab-guard`, `tools/ailab.service`. Test that the agent can't propose a change there.
- Proof before ✅ unlocks: ailab → full pytest + trial Lab on :8851 (temp AILAB_HOME) answers `/api/health` + robotcheck; hermes → pytest on touched modules + `py_compile` + `node --check` on touched JS.
- Before/after view (existing ↔) + plain done/doing/left list; no code shown by default.

## M5 — Go-live (Lab + guard) · model: Opus
- ✅ tap → `POST guard /api/snap` (why = run title) → **refuse if the guard doesn't answer** → copy only changed files into the real folder → `POST /api/restart` → `POST /api/watch` 5 min.
- Lab shows 👀 Watching / ✅ Kept / 🛟 Rolled back (reads `/api/state`). Lab restart mid-watch: comes back paused, reads guard state.
- 🛟 links: Lab top bar, Hermes Remote card, Iris ☰ More (Hermes nav standard; dark/light).

## M6 — Proof · model: Opus
- Promote a deliberately broken Lab change (syntax error in server.py) → guard rolls back alone within ~60 s, ping arrives.
- Same with a broken Hermes route change.
- Undo a rollback from the 🛟 page. Touch test the 🛟 page on Argus. Commit named paths only.

## Follow-up session 2026-11-24 21:00 — owed items
**Found + fixed (source only — needs Scott's sudo re-install):** the Guard checked Hermes health on the dashboard
(:8780, gandalf's USER unit `hermes-dashboard`) but restarted only `hermes-daemon` (system unit). So a Lab change to
dashboard code would never load, the watch would pass on the old process, and a Hermes break would never roll back.
- `guard.py`: `restart` may be several commands (`run_restart`, all must work); Hermes default = daemon + dashboard.
- `install.sh`: brings an old `/etc/ailab-guard/config.json` up to date. `test_guard.py` 10 ✅ (3 new asserts).
- **UNVERIFIED:** that `hermes-dashboard` really is a user unit on gandalf today (ledger row is UNVERIFIED since 2026-10-11) — the Hermes drill proves it either way (it prints ⚠️ HALF if the dashboard never goes down).

**Real Lab-made changes — both made by the Lab (deepseek-v4.1-flash, project Scratch), both WAITING in ✋ for Scott's 🛡 tap:**
- Lab — run `f3d49a4533`: `ailab/server.py` `/api/health` also returns `pid` + `started` (+2 lines, 1 changed).
- Hermes — run `369b888978`: `web/remote.html` gets a 🛟 Rollback tile after the AI Lab tile (+9 lines). Static page, safe to apply before the re-install.

**Hermes break drill:** `bash ~/ailab/tools/guard_drill_hermes.sh` (new). Refuses until the re-install is done; dashboard down ~1 min; refuses during a ⚡ compare fast copy; lists other Hermes files put back.

**🛟 page, desktop Chrome check (not the Argus test):** viewport meta ✅, 18 px text, buttons 48 px high, no sideways scroll.

**Still owed:** Scott's 2 🛡 taps · sudo re-install · Hermes drill · Argus touch test (🛟 page + 🛡 rows) · commits (other session's hunks still open in config.py, server.py, index.html — checked 21:00).

**Scott's order:** 1) tap 🛡 on both ✋ rows in the Lab → 2) `sudo bash ~/hermes-forge/ailab-guard/install.sh` → 3) `bash ~/ailab/tools/guard_drill_hermes.sh` → 4) Argus: open the 🛟 page + Lab ✋ list.

## Argus touch test 2026-11-24 21:15 (emulator Pixel 5, Chrome 113, 393×722 CSS px; reached via `location.href='http://10.0.2.2:8860/'` after `openweb /remote`)
Seen first: both ✋ rows were already applied (Lab `/api/health` answers pid + started; Remote page shows the 🛟 tile), Guard settings re-installed 21:05, Hermes went back to a 21:05 copy at 21:06 (looks like the drill — result not seen by this session).
- **🛟 page:** loads ✅ · no sideways scroll ✅ · swipe scrolls ✅ · 🌗 tap flips theme ✅ · ↩ Go back first tap arms "Tap again to go back" (48 px) ✅, second tap NOT sent · no console errors ✅.
- **Findings (fixed in `guard.py` source — needs one more sudo re-install, then a re-check):** (1) "All copies" closed by itself within 10 s (auto-refresh rebuilt the list) → open lists are remembered; (2) "All copies" row 42 px → 48 px; (3) an armed "Tap again" stayed armed forever → disarms after 8 s.
- **Findings, not changed (Scott's call):** text is 18 px / 16 px, under the 17pt floor; page defaults to dark (his standard: light). Lab's "🛟 Rollback page" link is 30 px high, ✏️ Edit / 👁 Preview 39 px (index.html has another session's open hunks).
- **Lab ✋ list on the phone:** loads, "🛡 Guard on" line shows, no sideways scroll. **🛡 rows + "Apply all" NOT touch-tested** — nothing was waiting.
- **Hermes /remote:** 🛟 Rollback tile 336×56 px ✅.
- Not done: screenshot, load-twice no_late_shift check. Left behind: `~/hermes-forge/ailab-guard/__pycache__/` (from a compile check).

## Session 3 — 2026-11-24 21:30 (Scott: "do the still owed work and raise the text to the 17pt floor")
**Proven from the Guard's own copy list (🛟 page `api/state`):**
- Lab real change ✅ — copy "before a Lab change: ailab/server.py" 20:59 → "healthy after the change (watch passed)" 21:04. `/api/health` answers pid + started.
- Hermes real change ✅ applied 21:05 (remote.html tile live). Its 5-min watch was replaced by the drill's watch 33 s later, so there is no "watch passed" copy for it.
- Hermes drill: copy 21:05:33 → Guard went back by itself 21:06:22 (49 s), Hermes healthy since. The Guard only goes back after 3 missed health checks, so the dashboard did go down and the restart fix reaches it. **The drill script's own PASS line was not seen by this session.**
- Re-install ran again 21:13 → the 3 page fixes are live and **re-tested on Argus ✅**: "All copies" still open after 11 s; row 50 px; "Tap again" disarms by 9 s; no console errors.

**17pt floor + light default (source only — one more sudo re-install):** `guard.py` page: text 23 px everywhere (≈17pt), headings 25/26 px, default light, copy rows wrap. Checked on Argus by injecting the same CSS into the live page: smallest text 23 px, nothing under 44 px, no sideways scroll. Guard tests 10 ✅.

**🛡 row touch test (Argus) ✅ with one row waiting:** Lab run `7ab35e1f13` proposed `ailab/web/index.html` — "🛟 Rollback page" link 48 px tall (1 line). On the phone: row shows 🛡 + "the Lab itself — tested first…", no sideways scroll, "what changed" toggles by touch, swipe scrolls, no console errors. ✅ Apply NOT tapped (Scott's tap) — **this row is still waiting in ✋.**
- Findings in the Lab row (not changed): "type apply" box 42 px high; smallest text 13.9 px; ✅ Apply / ✗ Reject 44 px.
- "🛡 Apply all N together" (2+ rows) not touch-tested — only one row was waiting.

**Commits: still waiting.** Other sessions' open edits grew (21:20): livepage.py, preview.py, ship.py, video.py, gate.py, test_local_video.py besides config.py / server.py / index.html. `~/hermes-forge` is not a git repo here, so the Guard source has no commit to make.

**Owed now:** Scott: type apply + ✅ on the waiting row · `sudo bash ~/hermes-forge/ailab-guard/install.sh` (17pt page) · commits once the other sessions land.

## Session 4 — 2026-11-25 04:30 — committed (Scott: "done. continue")
Scott applied the waiting row (Rollback link 48 px is in index.html) and re-ran the installer (17pt page — re-checked on Argus 04:35 as installed ✅: light default, smallest text 23 px, nothing under 44 px, no sideways scroll).
Other sessions were still editing the same files (index.html 04:08, tag_prompt.py 04:12), so the guard work was committed **without their hunks**: HEAD copy + `patch_m4_guard.py` + `patch_m5_guard_ui.py` + the two Lab-made lines, staged with `git update-index --cacheinfo` (working tree untouched).
- ailab `0e405b4` — 🛡 code + tests (config.py, review.py, server.py, index.html, guardlink.py, test_guardlink.py). test_guardlink 11 ✅; full suite on that tree: same failures as HEAD (+2 "No space left on device" in the test VM, not code).
- ailab `50b61fc` — tools (guard_drill.sh, guard_drill_hermes.sh, patch_m4_guard.py, patch_m5_guard_ui.py).
- hermes `90233f49` — remote.html 🛟 Rollback tile (the Lab-made Hermes change).
- Not pushed (ailab → GitHub origin; hermes is 153 ahead of its Dropbox mirror — Scott's call, NUC terminal).
- Guard source `~/hermes-forge/ailab-guard/` is not in any git repo — only copy is that folder + /opt/ailab-guard.

**Left:** "🛡 Apply all N together" touch test (needs 2+ rows) · Iris ☰ More 🛟 link (M5 plan, never built) · Lab row findings (type-apply box 42 px, 13.9 px text) · put the Guard source under git.

No night tail: M4 needs the guard installed + `check` all ✅ first.

**Continue phrase:** `continue AI Lab self-edit guard from the 2026-11-24 handoff`
