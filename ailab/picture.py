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

from . import creation, looks, memory
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


def write_prompt(run, words: str) -> str:
    """Scott's words stay exactly as typed; a writer model (uncensored first) only adds detail after them.
    Any writer that refuses or fails is skipped; with none left, his words alone make the picture."""
    mine, why = own_words(words), "no writer answered"
    for prov, model in writers(run):
        try:
            stage(run, "✍️", f"Adding detail to your words with {model.split('/')[-1]}")
            r = run.lab.chat(run.project, prov, model,
                             [{"role": "system", "content": PROMPT_SYS}, {"role": "user", "content": words}], 300,
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


LOCAL_DRAWN = "local/sdxl-base-1.0"          # 2026-11-24 live: SDXL on gandalf's card paints watercolor/charcoal/storybook; Lustify v8 draws photos
_LOCAL = {"at": 0.0, "ok": False}


def local_ready(run) -> bool:
    """True when Hermes lists local SDXL as installed, running and fitting the card (cached 60 s). Any error = False."""
    if time.time() - _LOCAL["at"] < 60:
        return _LOCAL["ok"]
    ok = False
    try:
        rows = run.lab.mcp.call("image_models", {}).get("models") or []
        ok = any(r.get("id") == LOCAL_DRAWN and r.get("fits", True) for r in rows)
    except Exception:                                        # noqa: BLE001 — off is a normal state
        ok = False
    _LOCAL.update(at=time.time(), ok=ok)
    return ok


def drawn_local(run, look: list[str], style: str, forced: bool) -> bool:
    """A drawn medium/style (not a photo) and local SDXL is up → use it ($0, nothing leaves gandalf). cfg local_drawn=false turns it off."""
    if forced or run.cfg.get("local_drawn") is False or looks.photo(look):
        return False
    drawn = bool(looks.negative(look, "") ) if look else bool(style) and not any(w in style.lower() for w in ("photo", "realis"))
    return drawn and local_ready(run)


def run(run) -> None:
    """The whole picture run. Raises Stopped / SpendBlocked like the agent loop (handled by Run.loop)."""
    if not run.connected:
        run.state = "failed"
        run.why = "🔌 Pictures are made by Hermes (it holds the OpenRouter key) — switch the Lab to connected mode."
        return
    words = picture_words(run.task)
    look, look_notes = looks.normalize(looks.from_task(words))          # 🎨 Look line (2026-11-24)
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
    pmodel, forced = picture_model(run, "photo" if looks.photo(look) else ("" if look and looks.has_look_style(look) else style))
    if drawn_local(run, look, style, forced):
        pmodel = LOCAL_DRAWN
        run._record({"action": "route", "why": "🏠 drawn style → local SDXL on gandalf ($0)", "result": {"model": pmodel}, "usd": 0.0})
    args = {"prompt": prompt, "name": own_words(words)[:40], "task": f"lab-picture:{run.project['id']}", "model": pmodel,
            "negative_prompt": looks.negative(look, NO_TEXT)}
    asp = aspect_from(shape)
    if asp:
        args["aspect_ratio"] = asp
    stage(run, "🎨", "Asking Hermes to make the picture")
    try:
        try:
            start = run.lab.mcp.call("image_make", args)
        except HermesRefused as e:
            if pmodel == LOCAL_DRAWN and not forced:         # local went away between the check and the call → Lustify
                _LOCAL.update(at=time.time(), ok=False)
                run._record({"action": "picture", "why": "🏠 local picture service isn't ready — using Lustify v8",
                             "result": {"note": e.message}, "usd": 0.0})
                pmodel = args["model"] = VENICE_ART
                start = run.lab.mcp.call("image_make", args)
            elif forced or not pmodel.startswith("venice/") or e.code not in ("not_enabled", "no_key"):
                raise
            else:
                run._record({"action": "picture", "why": "🔑 Venice isn't set up in Hermes yet — using Hermes's default "
                             "picture model (it has content filters)", "result": {"note": e.message, "fix": e.fix}, "usd": 0.0})
                stage(run, "🔑", "Venice key not added yet — using the default picture model (filtered)")
                args.pop("model")
                pmodel = ""
                start = run.lab.mcp.call("image_make", args)
    except HermesRefused as e:
        run._record({"action": "picture", "why": "🎨 make the picture", "result": {"error": f"Hermes refused ({e.code}): {e.message}"}, "usd": 0.0})
        run.state, run.why = "failed", f"🎨 Hermes couldn't make the picture: {e.message}" + (f" — {e.fix}" if e.fix else "")
        return
    key, model, est = start.get("key"), start.get("model", pmodel or "?"), float(start.get("est_usd") or 0)
    t0 = time.time()
    res = {}
    while True:
        run._check_stop()
        secs = int(time.time() - t0)
        stage(run, "🎨", f"Making the picture with {model.split('/')[-1]} — {secs} s (usually 10–60 s, about ${est:.3f})")
        try:
            res = run.lab.mcp.call("job_wait", {"key": key, "max_s": WAIT_S})
        except HermesRefused as e:
            res = {"state": "failed", "error": {"message": e.message}}
        if res.get("finished") or res.get("state") in ("done", "failed", "cancelled"):
            break
        if time.time() - t0 > MAX_WAIT_TOTAL_S:
            res = {"state": "failed", "error": {"message": f"no picture after {MAX_WAIT_TOTAL_S} s"}}
            break
    out = res.get("result") or {}
    if (res.get("state") != "done" or not out.get("b64")) and pmodel == LOCAL_DRAWN and not forced:
        _LOCAL.update(at=time.time(), ok=False)              # the card job failed (e.g. out of memory) → once more on Lustify
        run._record({"action": "picture", "why": "🏠 local picture failed — trying Lustify v8",
                     "result": {"error": (res.get("error") or {}).get("message") or "no picture"}, "usd": 0.0})
        pmodel = args["model"] = VENICE_ART
        start = run.lab.mcp.call("image_make", args)
        key, model, est = start.get("key"), start.get("model", pmodel), float(start.get("est_usd") or 0)
        t0 = time.time()
        while True:
            run._check_stop()
            stage(run, "🎨", f"Making the picture with {model.split('/')[-1]} — {int(time.time() - t0)} s (about ${est:.3f})")
            try:
                res = run.lab.mcp.call("job_wait", {"key": key, "max_s": WAIT_S})
            except HermesRefused as e:
                res = {"state": "failed", "error": {"message": e.message}}
            if res.get("finished") or res.get("state") in ("done", "failed", "cancelled") or time.time() - t0 > MAX_WAIT_TOTAL_S:
                break
        out = res.get("result") or {}
    if res.get("state") != "done" or not out.get("b64"):
        msg = (res.get("error") or {}).get("message") or "no picture came back"
        run._record({"action": "picture", "why": "🎨 make the picture", "result": {"error": msg}, "usd": 0.0})
        run.state, run.why = "failed", f"🎨 {msg}"
        return
    stage(run, "💾", "Saving the picture")
    ext = ".jpg" if "jpeg" in (out.get("media_type") or "") else ".png"
    slug = re.sub(r"[^a-z0-9]+", "-", words.lower()).strip("-")[:40] or "picture"
    rel = f"pictures/{time.strftime('%Y%m%d-%H%M%S')}-{slug}{ext}"
    p = run.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(out["b64"]))
    usd = float(out.get("usd") or 0)
    run.usd += usd
    pic = {"path": rel, "prompt": prompt, "model": out.get("model", model), "usd": round(usd, 4),
           "seconds": int(time.time() - t0), "library": out.get("library") or "", "style": style, "shape": shape,
           "look": look}
    run.pictures.append(pic)
    run._record({"action": "picture", "path": rel, "why": "🎨 made the picture", "result": {k: v for k, v in pic.items() if k != "prompt"},
                 "usd": usd})
    run.state = "done"
    run.why = (f"🖼 Picture made with {pic['model'].split('/')[-1]} in {pic['seconds']} s for ${usd:.3f}. "
               f"Saved in {rel}" + (" and in your Gallery (ai-lab)." if pic["library"] else "."))
    stage(run, "✅", "Done")
