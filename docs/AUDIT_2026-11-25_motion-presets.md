# AUDIT 2026-11-25 — 🏃 Motion Presets (Module 0, read-only)

Build prompt: Project `Motion Presets — Build Prompt (2026-11-25)`. Checked from the device shell 2026-11-25 ~09:20.
The shell can't reach the running Lab, ComfyUI or Venice — anything that needs a live call is UNVERIFIED.

## What exists and what presets reuse
| Piece | State | Reuse for presets |
|---|---|---|
| 🎨 Looks `ailab/looks.py` + `looks.json` | ✓ committed (`aba93b7`) | Same shape: catalog JSON + tabs, `Look:` task line, saved file with lock + atomic write, `public()` for the dialog → 🏃 Motion line = `Motion:` task line, same chip/sheet UI |
| 🛤 Video paths `ailab/video.py` | ✓ 6 paths (`picture_first` ⭐, words, newest, free, local_5b, local_14b 🔒) | Every clip goes through these; new kind `last_frame` = one handler + one JSON row (the "new METHOD" slot already documented) |
| 🎭 Global cast (R1) `ailab/cast.py` + Hermes `mcp_cast.py` | ✓ committed | "Who does this?" card lists the project's cast (`.shelf/cast.json`); steady characters = cast sheet pictures as `reference_images` |
| 📌 References (M2) `ailab/refs.py` | ✓ committed; local identity probe passed 95/95/95/95 (`image_ref_flags.json` `{"local": true}`) | Pose frames + cast refs ride the same `reference_images` hand-off |
| 🎨 Official styles (R2) `ailab/styles.py` | ✓ committed | Global-store pattern (`<lab home>/styles.json`) → `<lab home>/motions/<id>/` |
| 🎞 Video breakdown (prompt #1 M4) | ✗ **not built** | Pull-from-video was meant to sit on it. Scene cuts already exist: Hermes `forge/studios/viewer_tools.py` `scenes()` (ffmpeg) |
| `last_frame` / `motion_from_video` path switches (M2 plan) | ✗ not built (listed "Not built" in M2 handoff) | Module 5 builds `last_frame`; motion presets ARE the `motion_from_video` idea |
| Spend | ✓ `ailab-video` $5/day, one clip ≤ $2.50 (`mcp_video.py:27`), free `/video/quote` price | Price card before ▶ |

## Checks
| Check | Result |
|---|---|
| Pose detector on gandalf | **✗ none installed.** Comfy venv has torch 2.14 cu126 only — no mediapipe, onnxruntime, opencv, rtmlib, controlnet_aux. ComfyUI custom_nodes: only `Comfy-WaveSpeed` (no ControlNet preprocessors). → needs an install (see Gate A) |
| Pose guidance (ControlNet) in local ComfyUI | Core nodes ✓ (`ControlNetApplyAdvanced` in `comfy_extras/nodes_controlnet.py`). **Model files ✗** (`models/controlnet/` empty). Local checkpoints: SDXL base, Juggernaut XL, Pony V6, Illustrious, FLUX.2 Klein 4B fp8. Fit of SDXL + OpenPose ControlNet on the **6 GB** 2060 = **UNVERIFIED** (expected tight but workable with fp16 + offload; must be proven) |
| FLUX.2 Klein taking a skeleton picture as a reference | **UNVERIFIED** (Klein multi-reference works for faces — probe passed — not tested for pose) |
| Venice video takes a start picture | **✓** image-to-video sends `image_url` (`mcp_video.py:333`); wan-2-7-enhanced i2v proven live 2026-11-24 ($0.64, 145 s) |
| Venice video takes a pose/skeleton picture | **✗ / UNVERIFIED** — no pose input in our code or model list we have |
| Venice motion transfer (drive a character from a clip) | Venice lists `kling-v3-pro/standard-motion-control` (video-to-video). Params, price/second, content strictness **UNVERIFIED** (R2 Gate B1 = quote-probe first, off by default) |
| Venice picture takes references | ✓ `venice/qwen-edit-uncensored` via `refs.py` (route flag `venice` not yet set → probe owed) |
| Wan clip length — local | ✓ in code: 5B **max 5 s @ 24 fps**, 14B **max 5 s @ 16 fps** (`comfy/video.py` defaults `max_s: 5`; frames = 4n+1). 5B file is now on disk (`wan2.2_ti2v_5B_fp16.safetensors`); **no proof clip found** in ComfyUI `output/` → local video **UNVERIFIED** |
| Wan clip length — Venice | ✓ durations 3/4/5/6/8/10 s, snapped per model (`mcp_video.py:43, 231`) |
| Camera move detection | No optical-flow library installed (no opencv). ffmpeg ✓ (VM + gandalf). → vision model on 3 frames, or install opencv (Gate C) |
| Vision model | ✓ qwen3.5:4b on Ollama judged the identity probe locally (M1 Eyes) — reusable to describe motion in words alongside the uncensored writer |
| Lab tests baseline | 565 pass (last commit `83b7fa8`); not rerun (read-only module) |

## Risks
- **~3 actions per shot** limit — UNVERIFIED, as the prompt says; Module 3 warning ships with the number in settings.
- Last-frame chaining drifts after a few links (faces/clothes). Cast refs on every clip are the guard; a drift warning after N links.
- Card contention: pose detection on **CPU** keeps the 6 GB card free for ComfyUI.

## Gate — answers decide Modules 1–6
A. Pose detector (CPU) — ⭐ 1 DWPose via `rtmlib` + onnxruntime CPU (multi-person, ~200 MB, best for 2–10 people) · 2 MediaPipe (lighter, weaker with crowds) · 3 none: vision model words only
B. Pose-guided pictures — ⭐ 1 SDXL OpenPose ControlNet locally (~2.5 GB download → its own permission gate, then a fit proof on the 6 GB card; Lustify on Venice stays words-only) · 2 words only for now
C. Camera move from a video — ⭐ 1 vision model reads 3 frames (no install) · 2 opencv optical flow (install)
D. Pull-from-video base — ⭐ 1 build one shared "cut + keyframes + poses" step on `viewer_tools.scenes()` now, which prompt #1 M4 then reuses · 2 build prompt #1 M4 first, presets after
E. Previews for written presets — ⭐ 1 free stick-figure loop drawn from the pose frames ($0), cheap render only on tap · 2 always a priced test render
F. Build order — ⭐ 1 M1 library → M2 (video first) → M3 → M4 → M5 → M6 · 2 M1 → M3 → M4 → M5 first, M2 fill-ways last
