# Handoff — 🧪 model sweep + 🏠 local video path (2026-11-24)

All **uncommitted** (other sessions have uncommitted work in both repos). Nothing restarted; nothing ran on the card.

## 1. Sweep (`ailab/tools/model_sweep.sh`) — first live run 20:41, words = the oasis idea
- Writers ✅ (7): hermes-4-405b, venice/uncensored, venice-uncensored-1-2, glm-5-3-flash-uncensored,
  e2ee-gemma-4-26b…, venice-uncensored-role-play, abliteration…large-flash. Defaults (`picture.WRITERS`) both pass → unchanged.
- Writers empty, NOT refusals (3): deepseek-v4-1-flash-uncensored, qwen-3-6-plus, glm-4.7-flash-heretic — likely
  thinking models out of tokens at 300. Sweep now retries at 1500 and says "⚠️ slow thinker" / "⚠️ empty".
- Ollama dolphin3:8b / hermes3:8b: not installed (404) → now "⏭ not installed".
- Video: wan-2-7-enhanced-image-to-video ✅ $0.64/145 s. wan-2-2-enhanced i2v: SSL drop (not a refusal; now retried
  once). wan-2-7-enhanced t2v: daily video cap hit ($4.49 of $5). MiniMax H3 Chili ×2 + H3 Enhanced: quote 400
  "resolution" (they aren't 720p) → sweep now uses each model's own sizes. **Chili still UNTESTED** — no 🔓 label added.
- Re-run tomorrow (cap resets): `VIDEO_ONLY=1 ONLY="wan-2-2-enhanced-image-to-video wan-2-7-enhanced-text-to-video minimax-h3-chili-image-to-video minimax-h3-chili-text-to-video minimax-h3-enhanced-text-to-video" bash ~/ailab/tools/model_sweep.sh`

## 2. Local video path (Scott pick 4: 5B first, 14B second switch, "off by default, takes an unlock button")
- hermes `forge/studios/comfy/video.py` (new): `wan22-5b` (official Comfy-Org files, ~17 GB) and 🔒
  `wan22-14b-rapid-q4` (Phr00t Rapid AIO Mega NSFW v12.2, Novice25 Q4 GGUF 11.6 GB + ComfyUI-GGUF add-on); graphs, render.
- hermes `forge/projects/mcp_video.py`: `local/<id>` in video_models / video_quote ($0) / video_make — no Venice, no
  cap, CardSlot + Ollama hand-off, 60 min limit, max 5 s clip. `weights_licence.py`: 2 rows.
- hermes `forge/studios/comfy/install_video.sh`, `video_proof.sh` (new).
- ailab `video.py`: kind `local`; paths `local_5b` (on) and `local_14b` (🔒 off). Lock: can't switch on / ⭐ until
  `{"id","unlock":true}`; "Lock again" switches it off; the json file can't remove the lock. $0 clip skips the price
  card; local failure → Venice price card (nothing spent without a tap). `web/index.html`: 🔓 Unlock / 🔒 Lock again.
- Tests: hermes test_mcp_video 14 pass (4 new); ailab 459 pass, 4 new files' worth in `tests/test_local_video.py` (8).
  2 ailab failures are this test box only (test_compare secret scan, test_workflow before-page 503) — untouched code.
- **UNVERIFIED (needs gandalf's card):** ComfyUI node names/inputs (missing ones are reported by name), speed and
  memory on the 2060, 16 GB RAM with the 10 GB 5B file, the whole 14B graph (first frame via WanVaceToVideo control
  video — written from the model card, never run), touch test of the Unlock button on the Argus phone.

## Next (on gandalf)
1. `bash ~/hermes/forge/studios/comfy/install_video.sh` → downloads 5B, restarts ComfyUI, makes a 3 s fox proof clip.
2. Restart Hermes + the Lab. ⚙️ Settings → 🎬 Video paths shows the two 🏠 rows.
3. Proof with the real first frame: `bash ~/hermes/forge/studios/comfy/video_proof.sh wan22-5b <picture.png> "<words>" 3`
4. Only if 5B works and isn't enough: `ONLY=wan22-14b-rapid-q4 bash …/install_video.sh`, then 🔓 Unlock.

**Continue phrase:** `continue model-sweep from the 2026-11-24 handoff`

## 2026-11-25 05:15 addendum
- **Install check:** NOT loaded — no Wan files, no `.part` files, no ComfyUI-GGUF, no proof report in
  `~/hermes-forge/comfy/ComfyUI/models`. `install_video.sh` hasn't run to the download step.
- **Fixed:** `NameError: name 'looks' is not defined` — `ailab/video.py` used `looks` (video-look work) without importing it.
- **New `ailab/guide.py`:** unknown errors now say what broke, whose fault, and 👉 the next step (Lab bug → the line to
  paste into 🛠 Change ailab; connection; missing file; permissions; disk full; out of memory). Trace → `~/.config/ailab/errors.log`.
- **New `tests/test_guide.py`:** every Lab file is scanned for names used but never imported/defined (catches this class).
- ailab suite: see session report. Uncommitted. Lab restart needed.
