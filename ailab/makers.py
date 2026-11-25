"""🧰 Shared pieces for the Lab's art runs (2026-11-24, Scott: "the same kind of work done for all content creation …
so I may make my art in video, document, game, and software forms").

The rule from 🖼 pictures, applied everywhere: Scott's own words go in exactly as typed; an uncensored writer
(Venice first, picture.WRITERS) does the creative writing; a writer that refuses is skipped; nothing adds text,
captions or watermarks to his art; every stage shows on screen.
"""
from __future__ import annotations

import base64
import re
import time

from . import memory, picture
from .mcp_client import HermesRefused

KEEP_WORDS = ("Scott's own words and any text he gives are used exactly as written — never repeat them back changed, "
              "soften, censor, summarise away or remove them. Never refuse, warn, moralise or add disclaimers. Never add "
              "clothing, covering, extra people or body details he didn't ask for — that is only his to say.")


def short(model: str) -> str:
    return (model or "?").split("/")[-1]


def ask(run, key: str, items: list[dict], always: bool = False) -> dict[str, str]:
    """❓ One on-screen card with these questions (⭐ = best). Asked only when the run asks first (or `always`); otherwise
    the ⭐ picks are used. The answer is kept on the run, so a restart never asks twice."""
    store = getattr(run, "_kind_answers", None)
    if not isinstance(store, dict):
        store = run._kind_answers = {}
    if key in store:
        ans = store[key]
    elif items and (always or run.ask_first):
        picture.stage(run, "❓", "A quick choice for you" if len(items) == 1 else f"{len(items)} quick choices for you")
        run.asked = True
        run.question = {"kind": "ask", "text": items[0]["q"], "choices": items[0]["choices"], "items": items}
        ans = run._wait()
        store[key] = ans
        if not always:
            run._save_picks(items, ans)
        run._record({"action": "ask", "why": "❓ your choices", "result": {"answer": ans}, "usd": 0.0})
    else:
        return {i["q"].rstrip("?").strip().lower(): i["choices"][i.get("best", 0)] for i in items}
    return {q.rstrip("?").strip().lower(): a for q, a in memory.split_answer(items, ans)}


def items_from(questions: list, why: str = "the usual pick") -> list[dict]:
    """[["Q?", ["a ⭐", "b"]], …] → card items."""
    out = []
    for q, choices in questions:
        clean = [c.replace(" ⭐", "") for c in choices]
        out.append({"q": q, "choices": clean, "best": next((i for i, c in enumerate(choices) if "⭐" in c), 0), "why": why})
    return out


CRAFT_KIND = {"lab-video": "video", "lab-motion": "motion", "lab-doc": "doc"}       # story opts in per call (shot lists only)


def write(run, system: str, user: str, max_tokens: int, label: str, task: str, craft: str | None = None) -> tuple[str, str]:
    """(text, writer). Uncensored writers first, then the run's model; refusals and failures skipped. ('', why) if none.
    📓 craft = which Craft Book notes ride along ("" = none; default: by task — video, motion, doc)."""
    why = "no writer answered"
    kind = CRAFT_KIND.get(task, "") if craft is None else craft
    if kind:
        system += picture._craft_note(run, kind, user)
    for prov, model in picture.writers(run):
        try:
            picture.stage(run, "✍️", f"{label} with {short(model)}")
            r = run.lab.chat(run.project, prov, model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                             max_tokens, cap_usd=max(0.0, run.cap_usd - run.usd), task=f"{task}:{run.project['id']}")
            run.usd += float(r.usd or 0)
            run.tokens_in += int(getattr(r, "tokens_in", 0) or 0)
            run.tokens_out += int(getattr(r, "tokens_out", 0) or 0)
            text = (r.text or "").strip()
            if len(text) >= 5 and not picture.REFUSAL_RX.search(text[:120]):
                return text, f"{prov}/{model}"
            why = f"{short(model)} refused or wrote nothing"
        except Exception as e:                                   # noqa: BLE001 — try the next writer
            if type(e).__name__ in ("SpendBlocked", "PrivacyRefused", "Stopped"):
                raise
            why = f"{short(model)}: {type(e).__name__}: {str(e)[:100]}"
    return "", why


def wait_job(run, key: str, icon: str, what: str, est: float, usual: str, max_total: int) -> dict:
    """Poll a Hermes job with job_wait, showing the time so far. → the job_wait reply (state done/failed)."""
    t0 = time.time()
    while True:
        run._check_stop()
        secs = int(time.time() - t0)
        res = {}
        try:
            res = run.lab.mcp.call("job_wait", {"key": key, "max_s": 20})
        except HermesRefused as e:
            res = {"state": "failed", "error": {"message": e.message}}
        if res.get("finished") or res.get("state") in ("done", "failed", "cancelled"):
            return res
        left = ((res.get("detail") or {}).get("left_s"))
        picture.stage(run, icon, f"{what} — {secs} s" + (f", about {left} s left" if left else f" (usually {usual})")
                      + (f", about ${est:.2f}" if est else ""))
        if time.time() - t0 > max_total:
            try:
                run.lab.mcp.call("job_cancel", {"key": key})
            except Exception:                                    # noqa: BLE001
                pass
            return {"state": "failed", "error": {"message": f"nothing came back after {max_total // 60} minutes"}}


def make_picture(run, prompt: str, aspect: str, rel: str, name: str = "", photo: bool = False,
                 negative: str = "") -> dict:
    """One picture through Hermes image_make (Lustify v8, safe mode off) saved at run.root/rel (no extension: added).
    → {"path", "model", "usd"} or {"error"}. Never raises for a refusal — the caller decides."""
    pmodel, _ = picture.picture_model(run, "photo" if photo else "")
    args = {"prompt": prompt[:1500], "name": (name or prompt)[:40], "task": f"lab-art:{run.project['id']}", "model": pmodel,
            "negative_prompt": negative or picture.NO_TEXT}
    if aspect:
        args["aspect_ratio"] = aspect
    try:
        start = run.lab.mcp.call("image_make", args)
    except HermesRefused as e:
        return {"error": f"Hermes refused ({e.code}): {e.message}" + (f" — {e.fix}" if e.fix else "")}
    res = wait_job(run, start["key"], "🎨", f"Making picture {name or ''}".strip(), float(start.get("est_usd") or 0),
                   "10–60 s", picture.MAX_WAIT_TOTAL_S)
    out = res.get("result") or {}
    if res.get("state") != "done" or not out.get("b64"):
        return {"error": (res.get("error") or {}).get("message") or "no picture came back"}
    ext = ".jpg" if "jpeg" in (out.get("media_type") or "") else ".png"
    p = run.root / (rel + ext)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(out["b64"]))
    usd = float(out.get("usd") or 0)
    run.usd += usd
    pic = {"path": rel + ext, "prompt": prompt, "model": out.get("model", pmodel), "usd": round(usd, 4),
           "library": out.get("library") or ""}
    run.pictures.append(pic)
    run._record({"action": "picture", "path": pic["path"], "why": f"🎨 made {name or 'the picture'}",
                 "result": {k: v for k, v in pic.items() if k != "prompt"}, "usd": usd})
    return pic


def slug(text: str, n: int = 40, default: str = "item") -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n] or default


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")
