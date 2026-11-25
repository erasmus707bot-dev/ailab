# HANDOFF 2026-11-25 — 🏃 Motion Presets (M0–M5 built · M6 live proof owed)

Gate (Scott 09:28 "proceed" = all ⭐): A1 DWPose on CPU · B1 SDXL OpenPose ControlNet (its own download prompt) ·
C1 vision reads 3 frames for the camera · D1 build on the 🎞 breakdown (M4 had landed) · E1 $0 stick-figure previews ·
F1 order M1→M6. Audit: `docs/AUDIT_2026-11-25_motion-presets.md`.

## Shipped
**Hermes `fa338532`** (registration in `mcp_server.py` went in with another session's `aaccefc5`)
- `forge/projects/mcp_motion.py` — MCP `motion_pull` (do, $0, local) clip+range (≤30 s) or one picture → 2–6 key frames,
  DWPose skeletons via `pose_worker.py` in its own venv (OpenPose 18 pts, people left→right = A, B…), camera word +
  "what they do" as person A/B (looks scrubbed) by local vision, looping 320 px preview. `motion_get`. Restart-safe cache.
- `image_make` `pose_image` → `forge/studios/comfy/pose.py` wraps local **SDXL** graphs with ControlNetApplyAdvanced.
  Anything else refused plainly (FLUX/Venice = words only). Licence row `sdxl-openpose-xinsir`.
- `forge/studios/comfy/install_pose.sh` (`--control` adds the ControlNet, asks with the real size first).
- Tests: `test_mcp_motion_pull.py` 8 (my first `test_mcp_motion.py` was overwritten by aaccefc5's Kling test — renamed).
  Committed tree: `forge/projects/tests` 123 pass.

**AI Lab `21c5a7f`**
- `motions.py` library (`<lab home>/motions/<id>/motion.json` v1; roles + `{A}` slots, ⭐ moment, feel range, camera,
  shelves, aliases, source; trash not wipe; $0 SVG stick-figure / role-dot preview).
- `timeline.py` scene per project (`.shelf/motion_scene.json`): rows per person, then/at N s/sequence, camera row, idle
  presets, words ⇄ blocks, ~3-action warning + ✂️ split, stills per block, clips ≤ model length.
- `motion_fill.py` run kind `motionfill`: ⭐ pull · write · save-from-result → draft → 💾 Save card.
- `motion_make.py` run kind `motion`: 🖼 one still per block (cast anchors as refs, pose → local SDXL, refusal → words) ·
  🎬 clips: first from a picture, next from the previous clip's last frame, fresh still every 3 links, Venice one price
  card, ffmpeg join.
- `video.py` ⛓ `last_frame` path (off by default). `picture.py` pose hook. Server `/api/motions`, `/api/motion/scene|file|save|delete`.
- UI: 🏃 Motion line under the idea box → library sheet (search, shelves, previews) → 👥 Who does this? → ⏱ Timeline
  (drag/stretch, ⛓/📌, feel, camera row, idle, words box) → 🖼/🎬 make. 📚 viewer `🏃 Save its motion`; breakdown scene `🏃 Use this motion`.
- Tests: `test_motions.py` 16 · `test_motion_run.py` 11. Committed tree 624 pass (+1 test_compare needs a git repo — same on HEAD).
- Left untouched: another session's uncommitted R3 rebuild hunks in agent.py / batch.py / server.py / index.html.

## Live — NOT run (this shell can't reach gandalf's services)
```bash
bash ~/hermes/forge/studios/comfy/install_pose.sh            # detector (~200 MB models on first use)
bash ~/hermes/forge/studios/comfy/install_pose.sh --control  # ControlNet ~2.5 GB — size shown, asks y/N
systemctl --user restart hermes-comfy && systemctl --user restart hermes-mcp && systemctl --user restart ailab
```
M6 proofs (by eye: right people moving, no text, same faces across clips):
1. 📚 a video → 🏃 Save its motion → 4 s range → name + 💾 · ✍️ Write a motion · ⭐ a made picture → 🏃 Save its motion.
2. Project with a 5-person cast → 🏃 Add a motion (2-person) → Who does this? → 🖼 Make pictures: 3 others "in the background".
3. Add a second motion at the same time → both in one still. 4. Three blocks chained → 🎬 Make the video (🏠 local).

## UNVERIFIED
ControlNet file size + fit on the 6 GB 2060 · rtmlib API on gandalf · ~3-actions limit · local Wan 5B clip (no proof
clip yet) · Venice pose input (none). Kling motion control (aaccefc5) could become a 4th clip mode "drive from the source clip".

## Owed
Live proofs above · Argus touch test (Motion line, sheet, Who does this?, timeline drag on a phone, draft card).
Night tail: none — what's left is live on gandalf.

Continue: `continue motion presets from the 2026-11-25 handoff — Module 6 live proof`
