"""🖼 Picture runs (2026-11-24, Scott: "it produced no image … I need to know what is going on").

A run whose only chip is 🖼 Image skips the step-by-step agent: ❓ style + shape card → ✍️ the chat model writes the
picture prompt → 🎨 Hermes image_make (OpenRouter Image API, Hermes's key) → the picture lands in this project's
pictures/ folder and in Scott's picture library (ai-lab/). Every stage is shown on screen with the time so far.
Needs 🔌 connected mode (Hermes holds the key); standalone says so plainly.

🎨 Art freedom (2026-11-24, Scott's option 1): pictures go to Venice (venice/lustify-v8 for photo-real, venice/chroma
for every other style; Hermes sends safe_mode false). The prompt writer is Venice's uncensored model first and only
ADDS detail — Scott's own words go into the picture prompt exactly as he typed them. Same $2/day cap + cost record.
If Venice isn't set up in Hermes yet, the run says so on screen and uses Hermes's default (filtered) model.
"""
from __future__ import annotations

import base64
import re
import time
from pathlib import Path

from . import creation, eyes, looks, memory, picture_route, tag_prompt
from .mcp_client import HermesRefused

SHAPES = {"square": "1:1", "wide": "16:9", "tall": "9:16"}
PROMPT_SYS = ("You help write prompts for a text-to-picture model. Scott's own words go into the prompt exactly as he "
              "wrote them — you never repeat, reword, soften, censor or remove them. Reply ONLY with extra detail to put "
              "after his words: style, colours, light, setting, framing, camera or medium — 20–60 words, plain "
              "description, no lists, no quotes, no warnings, no extra talk. Match his choices (style, shape, look). "
              "Never contradict or tone down anything he asked for. Never add clothing, covering, extra people or "
              "body details he didn't ask for — what people wear, or don't, is only his to say. Never ask for text, captions, "
              "labels, signs or watermarks in the picture unless he did.")
WRITERS = [("venice", "venice-uncensored-1-2"), ("openrouter", "venice/uncensored")]   # then the run's own model
VENICE_PHOTO, VENICE_ART = "venice/lustify-v8", "venice/lustify-v8"
# 2026-11-24 live (Scott 1 — test both, fix): Chroma painted fake artist signatures in 2 of 3 paintings even with
# "signature" in the negative prompt and "unsigned" in the prompt (10-step model, ignores negatives). Lustify v8 with the
# style in the prompt: painted look, 4 of 4 clean. Chroma stays choosable via cfg picture_model.
REFUSAL_RX = re.compile(r"\b(i can'?t|i cannot|i won'?t|i'?m not able|sorry|as an ai)\b", re.I)
WAIT_S = 20
MAX_WAIT_TOTAL_S = 240


def claim(root, rel: str) -> str:
    """2026-11-24 parallel runs: reserve a file name no other run has (atomic create). Same second + same words in
    two runs → name.png, name-2.png … — never an overwrite."""
    import os
    base, ext = os.path.splitext(rel)
    for i in range(1, 1000):
        cand = rel if i == 1 else f"{base}-{i}{ext}"
        path = os.path.join(str(root), cand)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))
            return cand
        except FileExistsError:
            continue
    raise OSError(f"no free name for {rel}")


def stage(run, icon: str, text: str) -> None:
    run.stage = {"icon": icon, "text": text, "at": time.time()}
    run.last_progress = time.time()
    run.save()


def _questions(run) -> list[dict]:
    """The 🖼 type's questions, with Scott's last pick (lab-picks) as ⭐ when it matches a choice."""
    ty = next((t for t in creation.pick(["image"])), None) or {}
    last = {}
    try:
        for ln in memory.read(memory.PICKS).get("lines", []):
            m = re.match(r"(.+?)\? → (.+?)(?: \(project .*\))?$", ln.get("text", ""))
            if m:
                last[m.group(1).strip().lower()] = m.group(2).strip()
    except Exception:                                          # noqa: BLE001 — memory is a help
        pass
    items = []
    for q, choices in ty.get("questions", []):
        clean = [c.replace(" ⭐", "") for c in choices]
        star = next((i for i, c in enumerate(choices) if "⭐" in c), 0)
        prev = last.get(q.rstrip("?").strip().lower())
        if prev in clean:
            star = clean.index(prev)
        items.append({"q": q, "choices": clean, "best": star, "why": "your last pick" if prev in clean else "the usual pick"})
    return items


def _items(run, look: list[str]) -> list[dict]:
    """The ❓ questions; with a 🎨 Look that already names the medium or style, the Style question is skipped."""
    items = _questions(run)
    if look and looks.has_look_style(look):
        items = [i for i in items if not i["q"].lower().startswith("style")]
    return items


def _parse(items: list[dict], ans: str) -> dict[str, str]:
    return {q.rstrip("?").strip().lower(): a for q, a in memory.split_answer(items, ans)}


def aspect_from(choice: str) -> str:
    c = (choice or "").lower()
    return next((v for k, v in SHAPES.items() if k in c), "")


NO_TEXT = ("text, words, letters, writing, caption, subtitles, labels, table, chart, document, watermark, signature, "
           "logo, username, frame, border")                      # 2026-11-24: Scott — "my work needs to not have these"


def picture_words(task: str) -> str:
    """2026-11-24 live: a 🖼 run started from a build prompt sent all 2,617 characters (rules, module table) to the
    picture model, which drew them as text. From a build prompt keep only Scott's idea line (or the title), plus any
    Style:/Shape: lines; a plain task is unchanged."""
    t = task or ""
    if not (t.startswith("Follow this build prompt") or "Idea (Scott's words)" in t or re.search(r"^#\s.*Build Prompt", t, re.M)):
        return t
    m = re.search(r"Idea \(Scott'?s words\)\W*\s*(.+)", t)
    idea = m.group(1).strip() if m else ""
    if not idea:
        h = re.search(r"^#\s+(.+?)(?:\s+[—-]\s+Build Prompt.*)?$", t, re.M)
        idea = h.group(1).strip() if h else ""
    keep = "\n".join(re.findall(r"^(?:Style|Shape|Change|Look):.*$", t, re.M))
    return (idea + ("\n" + keep if keep else "")).strip() or t


def own_words(words: str) -> str:
    """Scott's words without the Style:/Shape:/Look: lines the Lab adds (those go to the writer as choices) or markdown marks."""
    w = re.sub(r"^(Style|Shape|Look):.*$\n?", "", words, flags=re.M)
    w = re.sub(r"[*`#]+", "", w)
    return re.sub(r"[ \t]+", " ", w).strip() or words.strip()


def writers(run) -> list[tuple[str, str]]:
    cfg = [tuple(w) for w in (run.cfg.get("picture_writers") or []) if isinstance(w, (list, tuple)) and len(w) == 2]
    out = cfg or list(WRITERS)
    if (run.provider, run.model) not in out:
        out.append((run.provider, run.model))
    return [w for w in out if w[0] in getattr(run.lab, "providers", {w[0]: 1})]


def _craft_note(run, kind: str, words: str) -> str:
    """📓 Craft Book: the fitting notes for the writer ('' when off or nothing fits). Never a blocker."""
    try:
        from . import craft
        return craft.for_run(run, kind, words)
    except Exception:                                            # noqa: BLE001
        return ""


def _craft_seen(run, kind: str, e: dict, words: str, compare: bool = True) -> None:
    """📓 what 👁 saw goes back to the Craft Book (counts on the notes used; a measured need wakes its note)."""
    try:
        from . import craft
        craft.observe(run, kind, e, words, compare)
    except Exception:                                            # noqa: BLE001
        pass


def _style_note(run) -> str:
    """🎨 R2: lessons of the project's official style (empty when none is chosen)."""
    try:
        from . import styles
        return styles.writer_note(run.root)
    except Exception:                                            # noqa: BLE001 — a style is a bonus, never a blocker
        return ""


_REF_MODELS = ("local/flux2-klein-4b", "venice/qwen-edit-uncensored")


def _refs(run) -> list[str]:
    """🎭 M2: absolute reference-picture paths for this run (empty = words only, the old path)."""
    try:
        from . import refs
        return refs.for_run(run)
    except Exception:                                            # noqa: BLE001 — references are a bonus, never a blocker
        return []


def write_prompt(run, words: str) -> str:
    """Scott's words stay exactly as typed; a writer model (uncensored first) only adds detail after them.
    Any writer that refuses or fails is skipped; with none left, his words alone make the picture."""
    mine, why = own_words(words), "no writer answered"
    sys = PROMPT_SYS + _style_note(run) + _craft_note(run, "picture", words)
    for prov, model in writers(run):
        try:
            stage(run, "✍️", f"Adding detail to your words with {model.split('/')[-1]}")
            r = run.lab.chat(run.project, prov, model,
                             [{"role": "system", "content": sys}, {"role": "user", "content": words}], 300,
                             cap_usd=max(0.0, run.cap_usd - run.usd), task=f"lab-picture:{run.project['id']}")
            run.usd += float(r.usd or 0)
            run.tokens_in += int(getattr(r, "tokens_in", 0) or 0)
            run.tokens_out += int(getattr(r, "tokens_out", 0) or 0)
            add = re.sub(r"^\s*(prompt|details?)\s*:\s*", "", (r.text or "").strip(), flags=re.I).strip().strip('"').strip()
            if add.lower().startswith(mine.lower()):              # repeated his words — keep only the addition
                add = add[len(mine):].lstrip(" ,.;:-").strip()
            if 5 <= len(add) <= 2500 and not REFUSAL_RX.search(add[:80]):
                text = f"{mine.rstrip('.')}. {add}"
                run._record({"action": "prompt", "why": f"✍️ your words kept exactly + detail from {model.split('/')[-1]}",
                             "result": {"text": text, "yours": mine, "added": add, "writer": f"{prov}/{model}"},
                             "usd": float(r.usd or 0)})
                return text
            why = f"{model} didn't give usable detail"
        except Exception as e:                                   # noqa: BLE001 — try the next writer
            why = f"{model}: {type(e).__name__}: {str(e)[:100]}"
    run._record({"action": "prompt", "why": "✍️ used your own words (the writer model didn't help)",
                 "result": {"text": mine, "note": why}, "usd": 0.0})
    return mine


def picture_model(run, style: str) -> tuple[str, bool]:
    """(model, chosen by Scott in config). Every style → Lustify v8 (Chroma signed paintings, 2026-11-24)."""
    forced = str(run.cfg.get("picture_model") or "")
    if forced:
        return forced, True
    return (VENICE_PHOTO if "photo" in (style or "").lower() else VENICE_ART), False


def _wait(run, start: dict, pmodel: str):
    """Poll one image_make job → (result, model, est_usd, start time)."""
    key, model, est = start.get("key"), start.get("model", pmodel or "?"), float(start.get("est_usd") or 0)
    hint = "usually 25–40 s on gandalf's card" if str(model).startswith("local/") else "usually 10–60 s"
    t0 = time.time()
    while True:
        run._check_stop()
        stage(run, "🎨", f"Making the picture with {model.split('/')[-1]} — {int(time.time() - t0)} s ({hint}, about ${est:.3f})")
        try:
            res = run.lab.mcp.call("job_wait", {"key": key, "max_s": WAIT_S})
        except HermesRefused as e:
            res = {"state": "failed", "error": {"message": e.message}}
        if res.get("finished") or res.get("state") in ("done", "failed", "cancelled"):
            return res, model, est, t0
        if time.time() - t0 > MAX_WAIT_TOTAL_S:
            return {"state": "failed", "error": {"message": f"no picture after {MAX_WAIT_TOTAL_S} s"}}, model, est, t0


def run(run) -> None:
    """The whole picture run. Raises Stopped / SpendBlocked like the agent loop (handled by Run.loop)."""
    if not run.connected:
        run.state = "failed"
        run.why = "🔌 Pictures are made by Hermes (it holds the OpenRouter key) — switch the Lab to connected mode."
        return
    words = picture_words(run.task)
    look, look_notes = looks.normalize(looks.from_task(words))          # 🎨 Look line (2026-11-24)
    if not look:                                             # 🎨 R2: the project's official style supplies the Look
        from . import styles
        look = styles.project_look(run.root)
    choices = {}
    if getattr(run, "_picture_answer", None) is None and run.ask_first:
        items = _items(run, look)
        if items:
            stage(run, "❓", "Two quick choices for you" if len(items) > 1 else "A quick choice for you")
            run.asked = True
            run.question = {"kind": "ask", "text": items[0]["q"], "choices": items[0]["choices"], "items": items}
            ans = run._wait()
            run._save_picks(items, ans)
            run._picture_answer = ans
            choices = _parse(items, ans)
            run._record({"action": "ask", "why": "❓ your choices", "result": {"answer": ans}, "usd": 0.0})
    elif getattr(run, "_picture_answer", None):
        choices = _parse(_items(run, look), run._picture_answer)
    style, shape = choices.get("style", ""), choices.get("shape", "")
    inline = {k.lower(): v.strip() for k, v in re.findall(r"^(Style|Shape):\s*(.+)$", words, re.M)}   # 🔁 Make another / ✏️ Change it
    style, shape = style or inline.get("style", ""), shape or inline.get("shape", "")
    extra = (f"\nStyle: {style}" if style and "style" not in inline else "") + (f"\nShape: {shape}" if shape and "shape" not in inline else "")
    run._check_stop()
    prompt = write_prompt(run, words + extra)
    run._check_stop()
    t_mine = own_words(words)                                # 🏷 kept for the anime models' tag prompt (M3 tags)
    t_add = prompt[len(t_mine):].lstrip(" .") if prompt.startswith(t_mine) else ""
    if look:                                                 # 🎨 words → medium/style → detail → mood/light/colour/camera
        mine = own_words(words)
        add = prompt[len(mine):].lstrip(" .") if prompt.startswith(mine) else ""
        names = look + ([style] if style and not looks.has_look_style(look) else [])
        prompt = looks.assemble(mine, names, add)
        looks.remember_last(look)
        clash = looks.clashes(look)
        run._record({"action": "look", "why": f"🎨 Look: {looks.SEP.join(look)}",
                     "result": {"look": look, "notes": look_notes, "clash": clash, "prompt_chars": len(prompt)}, "usd": 0.0})
    elif style and style.lower() not in prompt.lower():     # 2026-11-24 live: the Style line was stripped and only reached
        m = own_words(words)                                # the model if the writer happened to say it (Lustify drew photos)
        prompt = (f"{m.rstrip('.')}. {style}. {prompt[len(m):].lstrip(' .')}" if prompt.startswith(m)
                  else f"{prompt.rstrip('.')}. {style}.").strip()
    vmodel, forced = picture_model(run, "photo" if looks.photo(look) else ("" if look and looks.has_look_style(look) else style))
    plan = picture_route.plan(run, look, style, vmodel, forced)
    if not plan["models"]:                                   # 🦴 Study with the local card off — never falls to Venice
        run._record({"action": "route", "why": "🦴 Study pictures are made on gandalf only — the local picture card is off",
                     "result": {"plan": plan}, "usd": 0.0})
        run.state, run.why = "failed", "🦴 Study pictures are made on gandalf only, and the local picture service is off. Start it and try again."
        return
    speed = picture_route.speed(run)                         # ⚡ fast / 🎨 full for local SDXL (2026-11-25)
    if plan["models"][0].startswith("local/"):
        run._record({"action": "route", "why": f"🏠 {picture_route.WORDS[plan['kind']]} → {plan['models'][0].split('/')[-1]} on gandalf ($0)"
                     + (" · ⚡ fast" if speed == "fast" else " · 🎨 full"),
                     "result": {"models": plan["models"], "first": plan["first"], "speed": speed}, "usd": 0.0})
    args = {"prompt": prompt, "name": own_words(words)[:40], "task": f"lab-picture:{run.project['id']}",
            "negative_prompt": looks.negative(look, NO_TEXT)}
    asp = aspect_from(shape)
    if asp:
        args["aspect_ratio"] = asp
    queue, res, out, model, est, t0, pmodel, venice_off, refused = list(plan["models"]), {}, {}, "?", 0.0, time.time(), "", None, None
    base_prompt, base_neg, tagged = args["prompt"], args["negative_prompt"], None
    ref_paths, ref_added = ([] if forced else _refs(run)), False   # 🎭 M2: the cast strip / a character sheet's source
    strict = False                                           # True = a reference is in play: never make it without one
    if ref_paths:
        from . import refs as R
        local_ok = any(m.startswith("local/") for m in queue) and R.REF_MODELS[0] in picture_route.ready(run)
        q2 = R.queue(queue, local_ok, any(m.startswith("venice/") for m in queue))
        ref_added = R.REF_MODELS[1] in q2 and R.REF_MODELS[1] not in queue
        queue = q2
        if any(m in R.REF_MODELS for m in queue):
            # 🎭 live 2026-11-25: when the card dropped, a sheet view / pinned run fell to venice/lustify WITHOUT the reference
            # and drew a stranger. With a reference in play only reference-capable models are tried — no silent fallback.
            queue = [m for m in queue if m in R.REF_MODELS]
            strict = True
            run._record({"action": "refs", "why": f"🎭 {len(ref_paths)} reference picture{'s' if len(ref_paths) > 1 else ''} sent so the face holds",
                         "result": {"refs": [Path(x).name for x in ref_paths], "models": list(queue)}, "usd": 0.0})
        else:
            run._record({"action": "refs", "why": "🎭 no picture model here can use reference pictures (start the local picture "
                         "service or turn Venice on) — made from your words only", "result": {"refs": []}, "usd": 0.0})
            ref_paths = []
    while queue:
        pmodel = args["model"] = queue.pop(0)
        if ref_paths and pmodel in _REF_MODELS:
            args["reference_images"] = ref_paths
        else:
            args.pop("reference_images", None)
        if pmodel.startswith("local/"):
            args["speed"] = speed
        else:
            args.pop("speed", None)
        pose = (getattr(run, "batch", None) or {}).get("pose_abs") or ""     # 🏃 Motion Presets: a key moment's skeleton
        if pose and pmodel.startswith("local/") and "flux" not in pmodel and not args.get("reference_images"):
            args["pose_image"] = pose
        else:
            args.pop("pose_image", None)
        if tag_prompt.wants(pmodel):                         # 🏷 Illustrious / Pony read comma tags, not sentences
            if tagged is None:
                t_names = look + ([style] if style and not (look and looks.has_look_style(look)) else [])
                t_look = [w for part in looks.parts(t_names) for w in part]
                tagged = tag_prompt.write(run, writers(run), t_mine, t_look, t_add, stage)
                run._record({"action": "tags", "why": "🏷 tag prompt for the anime model — your words kept at the end"
                             + (" (simple rules — no writer helped)" if tagged[1] == "rules" else f" (tags by {tagged[1].split('/')[-1]})"),
                             "result": {"tags": tagged[0], "by": tagged[1], "prompt": tag_prompt.build(pmodel, tagged[0], t_mine)}, "usd": 0.0})
                run._check_stop()
            args["prompt"], args["negative_prompt"] = tag_prompt.build(pmodel, tagged[0], t_mine), tag_prompt.negative(pmodel, base_neg)
        else:
            args["prompt"], args["negative_prompt"] = base_prompt, base_neg
        stage(run, "🎨", "Asking Hermes to make the picture")
        try:
            start = run.lab.mcp.call("image_make", args)
        except HermesRefused as e:
            if args.get("pose_image") and e.code in ("not_installed", "bad_path", "bad_args"):
                run._record({"action": "pose", "why": f"🦴 pose not used — {e.message} Made from the words only.",
                             "result": {"fix": getattr(e, "fix", "") or ""}, "usd": 0.0})
                run.batch.pop("pose_abs", None)
                args.pop("pose_image", None)
                queue.insert(0, pmodel)
                continue
            if strict and args.get("reference_images") and e.code in ("not_enabled", "bad_path", "bad_args", "too_big"):
                if queue:                                    # another reference-capable model may still take it
                    run._record({"action": "refs", "why": f"🎭 {pmodel.split('/')[-1]} can't take the reference — {e.message} Trying {queue[0].split('/')[-1]}.",
                                 "result": {"note": e.message}, "usd": 0.0})
                    continue
                run._record({"action": "refs", "why": f"🎭 references not used — {e.message}",
                             "result": {"note": e.message, "fix": getattr(e, "fix", "") or ""}, "usd": 0.0})
                run.state, run.why = "failed", (f"🎭 Nothing made: the reference picture can't be used right now — {e.message}"
                                               + (f" 👉 {e.fix}" if getattr(e, "fix", "") else " 👉 Take the 📌 reference off to make it from your words only."))
                return
            if args.get("reference_images") and e.code in ("not_enabled", "bad_path", "bad_args", "too_big"):
                run._record({"action": "refs", "why": f"🎭 references not used — {e.message}",   # Hermes: route off until its probe passes
                             "result": {"note": e.message, "fix": getattr(e, "fix", "") or ""}, "usd": 0.0})
                ref_paths = []
                args.pop("reference_images", None)
                if ref_added:
                    queue = [m for m in queue if m != _REF_MODELS[1]]
                if pmodel != _REF_MODELS[1]:
                    queue.insert(0, pmodel)                  # same model, words only
                continue
            if pmodel.startswith("venice/") and e.code in ("not_enabled", "no_key") and not forced:
                venice_off = e
            refused, res = e, {}
            if forced:
                break
            if pmodel.startswith("local/"):
                picture_route.forget()
                queue = [m for m in queue if not m.startswith("local/")]
            if queue:
                run._record({"action": "picture", "why": f"↪️ {pmodel.split('/')[-1]} not available — trying {queue[0].split('/')[-1]}",
                             "result": {"note": e.message}, "usd": 0.0})
            continue
        refused = None
        res, model, est, t0 = _wait(run, start, pmodel)
        out = res.get("result") or {}
        if (res.get("state") == "done" and out.get("b64")) or forced:
            break
        err = (res.get("error") or {}).get("message") or "no picture"
        if pmodel.startswith("local/"):
            picture_route.forget()
            queue = [m for m in queue if not m.startswith("local/")]
        if queue:
            run._record({"action": "picture", "why": f"↪️ {pmodel.split('/')[-1]} failed — trying {queue[0].split('/')[-1]}",
                         "result": {"error": err}, "usd": 0.0})
    if strict and not (res.get("state") == "done" and out.get("b64")):
        msg = (res.get("error") or {}).get("message") or (refused.message if refused is not None else "no picture came back")
        run._record({"action": "picture", "why": "🎭 the face-keeping model didn't make it — nothing made without your reference",
                     "result": {"error": msg}, "usd": 0.0})
        run.state, run.why = "failed", ("🎭 Nothing made: the picture model that keeps the face didn't answer "
                                       f"({msg[:120]}). The graphics card may be busy with a video. 👉 Try again in a minute — "
                                       "nothing was made without your reference, and no picture was paid for.")
        return
    if venice_off is not None and not (res.get("state") == "done" and out.get("b64")):   # Venice not set up, nothing else made it
        run._record({"action": "picture", "why": "🔑 Venice isn't set up in Hermes yet — using Hermes's default "
                     "picture model (it has content filters)", "result": {"note": venice_off.message, "fix": venice_off.fix}, "usd": 0.0})
        stage(run, "🔑", "Venice key not added yet — using the default picture model (filtered)")
        args.pop("model", None)
        args.pop("speed", None)
        args.pop("reference_images", None)
        args["prompt"], args["negative_prompt"] = base_prompt, base_neg
        pmodel = ""
        try:
            start = run.lab.mcp.call("image_make", args)
        except HermesRefused as e:
            refused, res = e, {}
        else:
            res, model, est, t0 = _wait(run, start, pmodel)
            out = res.get("result") or {}
    if not res and refused is not None:
        e = refused
        run._record({"action": "picture", "why": "🎨 make the picture", "result": {"error": f"Hermes refused ({e.code}): {e.message}"}, "usd": 0.0})
        run.state, run.why = "failed", f"🎨 Hermes couldn't make the picture: {e.message}" + (f" — {e.fix}" if e.fix else "")
        return
    if res.get("state") != "done" or not out.get("b64"):
        msg = (res.get("error") or {}).get("message") or "no picture came back"
        run._record({"action": "picture", "why": "🎨 make the picture", "result": {"error": msg}, "usd": 0.0})
        run.state, run.why = "failed", f"🎨 {msg}"
        return
    stage(run, "💾", "Saving the picture")
    ext = ".jpg" if "jpeg" in (out.get("media_type") or "") else ".png"
    slug = re.sub(r"[^a-z0-9]+", "-", words.lower()).strip("-")[:40] or "picture"
    rel = claim(run.root, f"pictures/{time.strftime('%Y%m%d-%H%M%S')}-{slug}{ext}")
    p = run.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(out["b64"]))
    usd = float(out.get("usd") or 0)
    run.usd += usd
    pic = {"path": rel, "prompt": prompt, "model": out.get("model", model), "usd": round(usd, 4),
           "seconds": int(time.time() - t0), "library": out.get("library") or "", "style": style, "shape": shape,
           "look": look, "keys": picture_route.keys_line(run, pmodel or "")}
    if out.get("timing"):                                    # ⏱ where a local picture's seconds went (2026-11-25 probe)
        pic["timing"] = out["timing"]
    run.pictures.append(pic)
    run._record({"action": "picture", "path": rel, "why": "🎨 made the picture", "result": {k: v for k, v in pic.items() if k != "prompt"},
                 "usd": usd})
    if eyes.on(run) and not getattr(run, "batch", None):     # 👁 M1: does it match his words? ($0, never fails the run)
        pic["eyes"] = eyes.check(run, p.read_bytes(), words, look, label="the picture")
        eyes.record(run, "picture", pic["eyes"])
        _craft_seen(run, "picture", pic["eyes"], words)
    run.state = "done"
    run.why = (f"🖼 Picture made with {pic['model'].split('/')[-1]} in {pic['seconds']} s for ${usd:.3f}. "
               f"Saved in {rel}" + (" and in your Gallery (ai-lab)." if pic["library"] else ".") + f" {pic['keys']}")
    if (pic.get("eyes") or {}).get("score") is not None:
        e = pic["eyes"]
        run.why += f" 👁 {e['score']}% match" + (f" — missing: {', '.join(e['missing'])}." if e["missing"] else ".")
    stage(run, "✅", "Done")
