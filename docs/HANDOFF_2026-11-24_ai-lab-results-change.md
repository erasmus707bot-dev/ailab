# HANDOFF 2026-11-24 — AI Lab: real pictures, live status, What was made + Change it

**Commits (not pushed):**
- Hermes `cc029cfb` — MCP `image_models` + `image_make` (`forge/projects/mcp_images.py`): OpenRouter Image API with Hermes's key, cap-checked, `img:` job → `job_wait`, cost recorded, copy in picture library `ai-lab/`, `data_collection: deny` never dropped. Tests `forge/projects/tests/test_mcp_images.py` (8); forge/projects 37 green.
- ailab `a0bd9d8` — 🖼 picture runs (`ailab/picture.py`: ❓ style/shape → ✍️ prompt via chat model → 🎨 image_make → `pictures/…` + Gallery); 📣 stage line on every run; plain plan step names; agent saves picture bytes to a file, never the model.
- ailab `6018850` — screens: big stage card in both panes, picture gallery (🔁 Make another · ✏️ Change it · ⬇ Download), Before/Now only for pages and apps.
- ailab `8c75fdb` — 📦 **What was made** tiles + ✏️ **Change it** (own words / 🪄 Help me say it → edit → ▶ Make this change) right under the status card; build-prompt runs stop honestly at a module check-in (⏸ + **▶ Go on to Module N**); prompt builder Send keeps the 🧩 chips + robot test. Committed own hunks only — the parallel "AI Lab online" session's changes in server.py / index.html stay uncommitted in the working tree.
- 299 ailab tests green.

## Why Scott's runs gave no picture
1. Hermes had no text-to-picture service (Image Studio /models edits; workshop imagestudio container off; 6 GB card too small).
2. The 13:14 phone run came from 📝 Idea → build prompt → Send to Lab: chips were dropped and the prompt said "Module 0 then stop" → a read-only audit marked ✅ Done.

## Proven live
- 10:57: picture run asked style/shape, stage line moved ❓ → ✍️, prompt written ($0.0003), then failed plainly: **hermes-mcp still had the old code** (`unknown_tool image_make`, audit.jsonl 18:57 UTC).

## Not proven yet (needs restarts)
1. `systemctl --user restart hermes-mcp` — check `ss -ltnp | grep 8851` shows the new process. Audit must stop saying unknown_tool.
2. Lab restart (desktop icon, or `systemctl --user restart ailab` if the online handoff's unit is installed) — `/api/agent/rephrase` 404s until then.
3. Then: live picture run (oasis, Photo-real, Wide), Change it on it, 🪄 Help me say it, a gated build prompt → ▶ Go on to Module 1, Argus touch test of the tiles + Change it box.

Continue phrase: `continue AI Lab results + change from the 2026-11-24 handoff — live check`
