# HANDOFF 2026-11-24 — Local pictures M3 tags (anime models get tag prompts)

M3 proof PASSED 20:45 (3/3, $0, checked by eye): Photo → Juggernaut XL, Anime → Illustrious XL, Watercolor → SDXL base.
Anime missed the prompt (closed umbrella, no rain, park bench). Scott 20:46 "1" (tag prompts), 20:48 "1. go" (writer + rules fallback).

## Built (ailab)
- `ailab/tag_prompt.py` — for `local/illustrious-xl-v0.1` and `local/pony-v6-xl` only: prompt = model quality tags + tags + Scott's words exactly (at the end). Tags by the prompt writer (one extra short call, same writer order); refusal/junk/error → simple rules. Model negatives added in front of the usual one.
- `ailab/picture.py` — per-model switch inside the try-each-model loop; every other model (and the Venice / default fallbacks) gets the sentence prompt back. New run step `tags` ("🏷 tag prompt …") shows tags, who made them, the full prompt.
- `tools/m3_tag_proof.sh` — same idea, seed 20261124, sentence · rules tags · hand-written writer-style tags × Illustrious + Pony → 6 pictures, real timings (5 s steps).

## Tests
`tests/test_tag_prompt.py` +11. Full suite 448: all pass (2 fail in the Cowork VM only — its /sessions disk is full; both pass with `HOME=/tmp/h`).

## Not verified
- **Whether tags fix the miss** — needs the proof run on gandalf.
- **Live writer tags** — the proof uses a fixed tag line; the real writer shows on the 🏷 line of an Anime picture in the Lab.
- Quality/negative tags (`masterpiece…`, `score_9…`) are from memory, not checked against the model cards.
- Writer call cost not measured (shows in the run's cost line).
- Still owed from M3: Argus touch check of ⚙️ "🖼 Pictures: which side first". Keep-model-loaded parked. Nothing pushed.

## Proof result (21:07, 6/6 made, $0, checked by eye — one seed only)
- **Illustrious:** sentence → open umbrella + sign but NO rain, stray second handle · rules tags → rain + sign, odd red shape behind her · writer-style tags → rain, puddles, two signs, city, full body. **Tags clearly best.**
- **Pony:** sentence already had rain + open umbrella + sign; rules about the same; writer-style tags → full wet-street scene. **Small gain.**
- Sentence did better here than in the M3 proof (closed umbrella) → part of that miss was seed luck.
- "full body, city" tags made the girl small in frame — the tags steer framing, so the live writer's tag choice matters.
- Real card time: 34–39 s per picture (5 s steps).
- Still not verified: the live writer's own tags (🏷 line in the Lab).

## Live Lab check (21:13 + 21:18, Claude ran it in Scott's Chrome, project "image testing")
- Run 1: route → Illustrious, 🏷 tags by venice-uncensored-1-2, 42 s, $0.0002 (writer calls). Girl, open red umbrella, rain, bus stop sign — but the sign read **"CALM"** (writer tag "calm" painted as text) + a stray second handle.
- Fix `4acd5e9`: writer told "only things that can be seen", mood/feeling words filtered from writer tags; the Look's own mood word stays.
- Run 2 after restart: no mood tags, **no sign text**. Girl, open red umbrella, rain, a red bus behind her (no bus stop sign this time). 44 s.
- Fix (this commit): Look words were doubled in the tag list ("anime style, cel shading" twice) — now once each. Needs a Lab restart to load.
- One picture each side — the "calm" → sign reading is likely, not proven.

## Quality tags checked + doubling fixed (2026-11-25, Scott 1)
- Found: Hermes already prepends a quality prefix + model negative on the card (`forge/studios/comfy/models.py` → `workflows.py`), so the Lab's own prefix made Pony's score chain appear twice and Illustrious "masterpiece, best quality" twice; Hermes's Pony negative `score_4, score_5, score_6` fought the score chain.
- Checked (community guides — Civitai Pony + Illustrious pages, stable-diffusion-art.com, tensor.art; no single official card): Pony = full chain `score_9 … score_4_up` + `source_anime`, other `source_` tags in the negative. Illustrious = `masterpiece, best quality, good quality` / `worst quality, bad quality`. "amazing quality" was a fine-tune's trigger. Clip skip 2 already set by Hermes for both.
- hermes `31860e36`: checked tags in `models.py` (the one place). ailab `4327e39`: Lab sends only scene tags + Scott's words; `negative()` passes the Lab's leave-out words through.
- Tests: ailab picture/route/tags 61/61 · hermes `test_mcp_images_local` 12/12, `test_mcp_images_refs` + `test_mcp_images` 16/16.
- Not yet live: needs `systemctl --user restart hermes-mcp` (image_make runs there, port 8790) + `systemctl --user restart ailab`.

## Still open
- Writer doesn't say the umbrella's state ("open umbrella") though asked.
- Argus touch check of ⚙️ "🖼 Pictures: which side first". Keep-model-loaded parked. Nothing pushed.

## Gandalf
```
systemctl --user restart hermes-mcp
systemctl --user restart ailab
```
Then Claude re-runs the Anime picture in the Lab and checks the 🏷 step shows no quality tags (Hermes adds them on the card).

Continue: `continue local image service — live check after hermes-mcp + ailab restart, from the 2026-11-24 M3 tags handoff`
