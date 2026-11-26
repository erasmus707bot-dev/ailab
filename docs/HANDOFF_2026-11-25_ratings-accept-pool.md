# HANDOFF 2026-11-25 — ⭐ Ratings · 🔁 change verdicts · ✅ Accept · 🗂 Source pool (AI Lab)

Scott picks: Q1-1 (stars + reasons) · Q2 "more sources improve output" → pool + roles + smart pick + ★ credit, roles guessed by 👁 (pick 1) · Q3-1 (keep 🆕 Keep & clear beside ✅ Accept).
Repo ~/ailab. Commits: `19ff2d3` `c4ad7fe` `082b645` (📥 Source button) · `6b3e14a` backend · `0b09f9b` UI.

## How it works
- **⭐ Rate it** (Stage results + Library items): 1–5 stars at 48 px, tap again to clear, keys 0–5. Optional reason chips. Stored in `<project>/.shelf/ratings.json`. Stars **credit the sources** that made the picture (`pic.sources`); re-rating replaces the earlier stars.
- **✅ Accept**: keeps the run (numbered, if the Lab still has it), marks it ✅, and makes a picture the **🖼 Start from**. **Nothing in 🤖 Make is cleared.** Then: 📥 Use as source · 🖼 More like this · 🎬 Video from it (videos: 🔁 More like this). The old button is now **🆕 Keep & clear**.
- **🔁 Did the change work?** A run started from ✏️ Change (Stage or Library) remembers its parent and before-file. When it finishes, the Stage shows Before | After plus 👍 Better · 😐 Same · 👎 Worse, and "Changes that worked here: x/y".
- **🗂 Source pool**: every picture ever used stays in the pool. Jobs: 🖼 Start from (only one) · 👤 Who · 🎨 Style · 🧱 Scene · ❔ Lab decides (👁 guesses once, $0). Each picture run takes ≤4 (Venice ≤3): Start from first, then Who/Style/Scene, best ★ record first. The Steps line names them.
- **🪄 Improve** now also reads 4–5★ / accepted prompts, 1–2★ prompts with reasons, and the changes marked better / worse.

## Verified
- 695 unit tests pass (+4 new: `tests/test_ratings.py`, pool test).
- API smoke on a throwaway Lab (VM, port 8899): upload → rate → accept → role → verdict → get.
- Headless Chromium, desktop 1400 px + phone 393 px: rate, reason, accept → "Your Start from ✓", Source ✓ 2, old source moved to ❔, verdict box. No page errors.

## Not verified
- Real picture runs on gandalf with 2+ sources: whether stacking 👤 Who pictures holds a face better than one does.
- 🎬 Video from it: assumes the video path's first picture uses the Start from. Not proven.
- The 👁 role guess on real pictures.
- Argus touch test still owed.
- Phone: the sticky 👀 Stage tab can sit under the wrapped top bar after scrolling. Playwright's tap hit the header. Possibly pre-existing (7eff070).

## Scott on gandalf
1. Restart the Lab (desktop icon), then Ctrl+Shift+R.
2. Make a picture from the whale → ⭐ rate it → ✅ Accept → 🖼 More like this.
3. ✏️ Change it → answer 🔁 Better/Same/Worse.

Continue: `continue AI Lab ratings from the 2026-11-25 handoff`

```craft
kind: build
when: a Lab page reads a file the user picked (upload, drag-in)
do: read it with FileReader.readAsDataURL, never URL.createObjectURL
why: the Lab's CSP is img-src 'self' data: — blob: pictures never load, so every upload looked like "not a picture" (live 2026-11-25, whale jpg)
```

## Follow-up (same evening) — live whale test + 🖼 edit route
- Commits: `85fa9f4` batch tiles get the rate row · `14fe92f` made_from.json (Library ★ credits sources) · `d8cc6c4` 🖼 Start from = an edit.
- Live finding: "same whale, cosmic nebula style" on FLUX.2 Klein 4B at ⚡ fast with a writer-expanded prompt → generic purple whale, 👁 67% "missing: same whale".
- `d8cc6c4`: when a 🖼 Start from is in use → Venice `qwen-edit-uncensored` first, then local; no writer (his words + Style only); "Edit the given picture: keep… change only:" prefix; local runs at 🎨 full speed when a source is sent. Venice off → a Steps line says so.
- Not verified: the edit route on a real run (needs a Lab restart + Venice on).
- Research (sources in chat 2026-11-25): Klein 4B has a dedicated edit workflow in ComfyUI (style transforms, multi-reference); Qwen-Image-Edit-2511 is the strongest open edit model but Q4 ≈ 11.5 GB, so not practical on the 6 GB RTX 2060; Venice /image/multi-edit now lists newer edit models (firered, qwen-image-2-edit, flux-2-max-edit, seedream) worth a Hermes probe; Flux Redux / SDXL IP-Adapter are the style-only tools for a real 🎨 Style job.
