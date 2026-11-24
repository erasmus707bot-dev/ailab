"""🖼 Picture runs (2026-11-24, Scott: "it produced no image … I need to know what is going on").

A run whose only chip is 🖼 Image skips the step-by-step agent: ❓ style + shape card → ✍️ the chat model writes the
picture prompt → 🎨 Hermes image_make (OpenRouter Image API, Hermes's key) → the picture lands in this project's
pictures/ folder and in Scott's picture library (ai-lab/). Every stage is shown on screen with the time so far.
Needs 🔌 connected mode (Hermes holds the key); standalone says so plainly.
"""
from __future__ import annotations

import base64
import re
import time

from . import creation, memory
from .mcp_client import HermesRefused

SHAPES = {"square": "1:1", "wide": "16:9", "tall": "9:16"}
PROMPT_SYS = ("You write prompts for a text-to-picture model. From Scott's words and choices, write ONE picture prompt: "
              "subject, setting, style, colours, light, framing — about 40–90 words, plain description, no lists, "
              "no quotes, no extra talk. Keep every detail Scott gave; add only what makes it look good. "
              "Reply with the prompt only.")
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


def _parse(items: list[dict], ans: str) -> dict[str, str]:
    return {q.rstrip("?").strip().lower(): a for q, a in memory.split_answer(items, ans)}


def aspect_from(choice: str) -> str:
    c = (choice or "").lower()
    return next((v for k, v in SHAPES.items() if k in c), "")


def write_prompt(run, words: str) -> str:
    """The chat model turns Scott's words into a picture prompt. Falls back to his own words if it can't."""
    try:
        r = run.lab.chat(run.project, run.provider, run.model,
                         [{"role": "system", "content": PROMPT_SYS}, {"role": "user", "content": words}], 400,
                         cap_usd=max(0.0, run.cap_usd - run.usd), task=f"lab-picture:{run.project['id']}")
        run.usd += float(r.usd or 0)
        run.tokens_in += int(getattr(r, "tokens_in", 0) or 0)
        run.tokens_out += int(getattr(r, "tokens_out", 0) or 0)
        text = re.sub(r"^\s*(prompt\s*:\s*)", "", (r.text or "").strip(), flags=re.I).strip().strip('"').strip()
        if 10 <= len(text) <= 3000 and not re.search(r"\b(i can'?t|i cannot|i won'?t|sorry)\b", text[:80], re.I):
            run._record({"action": "prompt", "why": "✍️ wrote the picture prompt", "result": {"text": text},
                         "usd": float(r.usd or 0)})
            return text
        why = "the model's answer wasn't a usable prompt"
    except Exception as e:                                       # noqa: BLE001 — his words still make a picture
        why = f"{type(e).__name__}: {str(e)[:120]}"
    run._record({"action": "prompt", "why": "✍️ used your own words (the writer model didn't help)",
                 "result": {"text": words, "note": why}, "usd": 0.0})
    return words


def run(run) -> None:
    """The whole picture run. Raises Stopped / SpendBlocked like the agent loop (handled by Run.loop)."""
    if not run.connected:
        run.state = "failed"
        run.why = "🔌 Pictures are made by Hermes (it holds the OpenRouter key) — switch the Lab to connected mode."
        return
    words = run.task
    choices = {}
    if getattr(run, "_picture_answer", None) is None and run.ask_first:
        items = _questions(run)
        if items:
            stage(run, "❓", "Two quick choices for you")
            run.asked = True
            run.question = {"kind": "ask", "text": items[0]["q"], "choices": items[0]["choices"], "items": items}
            ans = run._wait()
            run._save_picks(items, ans)
            run._picture_answer = ans
            choices = _parse(items, ans)
            run._record({"action": "ask", "why": "❓ your choices", "result": {"answer": ans}, "usd": 0.0})
    elif getattr(run, "_picture_answer", None):
        choices = _parse(_questions(run), run._picture_answer)
    style, shape = choices.get("style", ""), choices.get("shape", "")
    inline = {k.lower(): v.strip() for k, v in re.findall(r"^(Style|Shape):\s*(.+)$", words, re.M)}   # 🔁 Make another / ✏️ Change it
    style, shape = style or inline.get("style", ""), shape or inline.get("shape", "")
    extra = (f"\nStyle: {style}" if style and "style" not in inline else "") + (f"\nShape: {shape}" if shape and "shape" not in inline else "")
    run._check_stop()
    stage(run, "✍️", f"Writing the picture prompt with {run.model.split('/')[-1]}")
    prompt = write_prompt(run, words + extra)
    run._check_stop()
    pmodel = str(run.cfg.get("picture_model") or "")
    args = {"prompt": prompt, "name": words[:40], "task": f"lab-picture:{run.project['id']}"}
    if pmodel:
        args["model"] = pmodel
    asp = aspect_from(shape)
    if asp:
        args["aspect_ratio"] = asp
    stage(run, "🎨", "Asking Hermes to make the picture")
    try:
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
           "seconds": int(time.time() - t0), "library": out.get("library") or "", "style": style, "shape": shape}
    run.pictures.append(pic)
    run._record({"action": "picture", "path": rel, "why": "🎨 made the picture", "result": {k: v for k, v in pic.items() if k != "prompt"},
                 "usd": usd})
    run.state = "done"
    run.why = (f"🖼 Picture made with {pic['model'].split('/')[-1]} in {pic['seconds']} s for ${usd:.3f}. "
               f"Saved in {rel}" + (" and in your Gallery (ai-lab)." if pic["library"] else "."))
    stage(run, "✅", "Done")
