# AUDIT 2026-11-25 — AI Lab 👁 Eyes · 🎭 Characters · 📖 Story · 🎞 Video breakdown (M0)

Build prompt: `claude/BUILD_PROMPT_2026-11-25_ai-lab-eyes-story-rip.md`. M0 = audit + Gate 0. **No feature code written.**
Checked from the Cowork device shell 2026-11-25 ~06:00. Task inboxes (ailab, hermes, hermes-local): 0 PENDING.

## 1. Ground truth — line by line

| Prompt line | Result |
|---|---|
| Lab has no vision / storyboard / last-frame / reference-image code | ✅ confirmed. Only hit: `roster.py:162` — a regex that labels models "🖼 sees images" (reusable for the model picker). |
| `server.py:544 _taste()` + `:555 _improve_msgs()` — prompt text only | ✅ confirmed. `_taste` reads `shelf.view()`, first line of `task`, last 5 kept / 5 tossed. |
| `shelf.py` keep / toss / restore | ✅ confirmed — **but the record field is `files[]`, not `made[]`** (shelf.json rows: `n, run, task, files, at`). M1 adds `caption` + `score` beside them. |
| `picture.py:137 write_prompt`, `:30 WRITERS` | ✅ confirmed. |
| `video.py` paths picture_first ⭐ / words / newest / free / local_5b / local_14b 🔒 | ✅ confirmed. |
| Hermes `workflows.py:85` FLUX.2 1–4 reference graph, not wired to the Lab | ✅ confirmed (`build_ref`). Its own docstring: node names **UNVERIFIED on gandalf**. |
| Speech-to-text, scene cuts, word time markers | ✅ `forge/creator/speech.py`, `forge/lector/transcribe.py` (`word_timestamps=True`), `forge/studios/viewer_tools.py` (`_scene_times`, `_strip`, `scenes`). |
| **Local Wan 2.2 5B is NOT installed** | ❌ **stale.** `wan2.2_ti2v_5B_fp16.safetensors` (10.0 GB), `umt5_xxl_fp8` (6.7 GB) and `wan2.2_vae` are on disk, written 05:25–05:38 today. Whether the proof clip ran is **UNVERIFIED** (shell cannot see the GPU). |
| Remodel M1–M3 + model sweep uncommitted in both repos | ✅ ailab: 17 modified + 20 untracked (`gate.py guide.py shelf.py shots.py` untracked). hermes: 105 changed paths; `comfy/video.py`, `install_video.sh`, `video_proof.sh` untracked. |
| gandalf RTX 2060 6 GB, ~31 GB RAM | ✅ `hardware.json`: 6.0 GB VRAM, 32.6 GB RAM. |

## 2. Reuse list (do not rebuild)

- **Card hand-off:** `comfy/local.py` — `hand_off()` (Ollama drops models), `hand_back()` (ComfyUI `/free`), `hold_start / release_later`, `fits()`, `ollama_busy()`. `vision_check` slots into this; no new lock needed.
- **MCP tool pattern:** `forge/projects/mcp_server.py:836–852` (`image_make` spend, `video_quote` look, `video_make` spend) + `tests/test_mcp_video.py`. `vision_check` local = kind `look` ($0).
- **Lab side:** `guide.explain()` for errors, `picture.stage()`, `shelf`, `roster` vision regex, `looks`.
- **Narration:** Kokoro is already coded — `forge/lector/tts.py` + `forge/lector/deploy/install_tts_on_gandalf.sh` (kokoro-onnx, **~350 MB**, Apache-2.0). `~/hermes-data/lector/tts/` shows no model files → **looks not installed**; speed on gandalf UNVERIFIED.
- **Licence rows:** `forge/studios/weights_licence.py` (path in the prompt said comfy/; it lives one level up).
- **M4:** scene cuts + keyframe strip + transcripts with word times all exist; only caption-merge, recipe shape and sheet UI are new.

## 3. UNVERIFIED items — what the web says (2026-11-25), what still needs gandalf

**Vision model on 6 GB**
- **qwen3.5:4b / 9b (already pulled)** — Qwen3.5 is a unified vision-language family; LM Studio lists both with vision input. Whether **gandalf's Ollama build** accepts pictures for them: UNVERIFIED → the pilot answers it. 0 GB download.
- **qwen3-vl:4b** — 3.3 GB pull, fits. `qwen3-vl:2b` 1.9 GB. `qwen3-vl:8b` 6.1 GB — does not fit beside anything. Plain tags are the Thinking build; `-instruct` tags answer faster. Needs Ollama ≥ 0.12.7.
- **JoyCaption Beta One** — built uncensored for training captions. Full ≈ 17 GB; GGUF Q4_K 4.9 GB (~6–7 GB in use), Q2_K 3.2 GB (~4 GB). Needs a separate mmproj file; not a one-line Ollama pull. On this card it owns the whole card → batch captioning only (M2 dataset), not the per-picture check.
- **Uncensored needed?** UNVERIFIED until the pilot runs on his pictures. The pilot marks refusals 🚫.

**Pilot RAN 2026-11-25 06:46 on gandalf** (`~/hermes-data/ailab/_pilot/vision_pilot_20261125-0646.html`, plus a second overlapping run at 06:48 — two runs fought for the card, so first-picture times are inflated).
- **qwen3.5:4b and qwen3.5:9b both see pictures in gandalf's Ollama. 0 refusals, 0 errors out of 12 each**, on 1 SFW + 5 adult pictures. Captions accurate and explicit (acts, nudity, restraints, fluids named plainly).
- Card: 4b peak ~4.2–5.4 GB, 9b ~4.8–5.1 GB. Warm speed with the card to itself: **4b ~8 s/picture, 9b ~35–50 s**. Cold first load: minutes.
- 9b is a little more specific on explicit detail; 4b is ~5× faster. **Pick: qwen3.5:4b** (default, no setting needed). **No uncensored vision model needed.** qwen3-vl:4b not pulled, not needed.

Original note — script ready, dry-run passed (6 pictures, page renders):
`python3 ~/ailab/tools/vision_pilot.py` → page in `~/hermes-data/ailab/_pilot/`. Runs the two installed models now; adds any pulled later. Never pulls by itself. Only 1 picture is ✅ kept so far, so it uses that one + the 5 newest in `image-testing`.

**Wan Animate / VACE / SVI** — not researched further; SVI targets 14B. Keep as hosted-or-later. `motion_from_video` = hosted first.

**Cloud LoRA trainers**
- **Civitai:** terms ban content based on the likeness of real people in any context; community reading is that the on-site trainer has no exception. Training data kept 30 days by default. → real-person sets cannot go there.
- **fal:** has an NSFW policy and runs automated moderation (OpenAI Omni) on the platform; exact adult-content limits for *training uploads* not read in full → UNVERIFIED. Retention reported by a third party as short logging; not confirmed on fal's own page.
- Nothing uploaded. No account touched.

**Kokoro** — ~350 MB (see reuse list). Speed UNVERIFIED.

## 4. Risks for M1–M4

1. **One card, three tenants** (ComfyUI, Ollama text, Ollama vision). Every vision check after a local picture = model swap (~10–30 s, UNVERIFIED). Batch checks at the end of a batch, not per picture.
2. **`web/index.html` carries other sessions' hunks** and the whole remodel is uncommitted — M1 must stage own lines only, private `GIT_INDEX_FILE`.
3. `build_ref` node names unproven on gandalf → M2 starts with `missing_nodes()` proof.
4. Real-people rule not final → nothing past M0 touches real people.

## 5. Gate 0 menu — his picks

**A. Vision model (the Lab's eyes)**
1. ⭐ `qwen3.5:4b` for checks (already on gandalf, 0 download) — *if the pilot shows it sees and does not refuse*
2. `qwen3-vl:4b` (3.3 GB pull)
3. `qwen3.5:9b` (already there, slower, tighter on the card)
4. Decide after the pilot page

**B. Where it runs**
1. ⭐ Local only; hosted off (his art never leaves gandalf)
2. Local first, hosted fallback under the $2 cap, with a tap
3. Hosted only

**C. LoRA trainer**
1. ⭐ None yet — FLUX.2 references first (M2), revisit after
2. Local training later (needs a card bigger than 6 GB — UNVERIFIED)
3. fal (after reading its training terms in full)
4. Civitai (no real people, 30-day retention)

**D. Narration voice**
1. ⭐ Kokoro local (~350 MB, already coded in Lector)
2. Hosted voice through Hermes
3. No narration yet

**E. Build order**
1. ⭐ M1 Eyes → M2 Characters → M3 Story → M4 Video breakdown (as written)
2. M1 → M4 → M2 → M3 (research use sooner)
3. M1 only, then re-plan

**F. Dataset captioner (only matters if C ≠ 1)**
1. ⭐ Skip until a trainer is picked
2. JoyCaption Q4 GGUF (4.9 GB + mmproj download)

## 6. Handoff

- **Shipped:** this audit · `~/ailab/tools/vision_pilot.py` (new, $0, read-only on his pictures).
- **Uncommitted, on purpose:** both repos carry other sessions' uncommitted work; git writes from this shell need delete permission. Two new files only: `docs/AUDIT_2026-11-25_eyes-story-rip.md`, `tools/vision_pilot.py`.
- **Tests:** none added (no feature code). Pilot dry-run OK.
- **Restart:** none needed. **Argus touch test:** none owed (no UI).
- **Night tail:** none — M1 is gated on picks A + B; the night must not build it.
- **Owed by Scott (NUC terminal):** `python3 ~/ailab/tools/vision_pilot.py` then open the page.

Continue phrase: `continue AI Lab eyes + story + rip from the 2026-11-25 build prompt`
