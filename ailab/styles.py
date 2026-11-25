"""🎨 Official styles (build prompt #2 R2, Scott 2026-11-25): a Look + model + the prompt lessons learned making it, locked.

One global store (<lab home>/styles.json) every project can choose from. Lessons stay inside their project
(.shelf/shelf.json) until he taps 🔒 Make this an official style — promotion COPIES them into the style; nothing else
crosses projects. The Lab may PROPOSE a style (≥ PROPOSE_AT kept results in one project share Look + model and no style
covers them) — once per look, "Not now" snoozes until PROPOSE_AT more are kept, "Never" stays silent. Nothing becomes
official without his tap."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from . import config

PROPOSE_AT = 4
MAX_LESSONS = 20
_lock = threading.Lock()


def _file() -> Path:
    return config.home() / "styles.json"


def _read() -> dict:
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    return {"styles": [s for s in d.get("styles") or [] if isinstance(s, dict) and s.get("name")],
            "answers": d.get("answers") if isinstance(d.get("answers"), dict) else {}}


def _write(d: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def sig(look, model) -> str:
    """Same Look (any order) + same model = same style."""
    return f"{str(model or '').strip()}|" + "+".join(sorted({str(x).strip() for x in look or [] if str(x).strip()}))


# ---------- what a run used ----------
def facts(run) -> dict:
    """The Look and the picture/video model a run used (empty when it made no picture or video)."""
    look = []
    for st in getattr(run, "steps", None) or []:
        res = st.get("result") if isinstance(st.get("result"), dict) else {}
        if st.get("action") == "look" and isinstance(res.get("look"), list):
            look = [str(x) for x in res["look"]]
    made = list(getattr(run, "pictures", None) or []) + list(getattr(run, "videos", None) or [])
    model = str(made[-1].get("model") or "") if made and isinstance(made[-1], dict) else ""
    return {"look": look, "model": model} if (look or model) else {}


# ---------- project lessons (never leave the project unless promoted) ----------
def line(x: dict) -> str:
    t, s = str(x.get("task") or "").split("\n")[0].strip()[:200], x.get("seen") or {}
    if not t or not (s.get("caption") or s.get("score") is not None):
        return t
    bits = ([f"{s['score']}% match"] if s.get("score") is not None else []) + ([f"it showed: {s['caption'][:160]}"] if s.get("caption") else [])
    return f"{t} [👁 {' — '.join(bits)}]"


def project_lessons(root) -> list[str]:
    """This project's ✅ kept / 🗑 thrown prompts (+ 👁 seen), newest last — what promotion copies."""
    from . import shelf
    v = shelf.view(root)
    out = [f"kept: {line(x)}" for x in v["kept"]] + [f"avoid: {line(x)}" for x in v["tossed"]]
    return list(dict.fromkeys(a for a in out if a.split(": ", 1)[1]))[-MAX_LESSONS:]


# ---------- the global store ----------
def all_styles() -> list[dict]:
    return _read()["styles"]


def get(name: str) -> dict | None:
    n = str(name or "").strip().lower()
    return next((s for s in all_styles() if s["name"].lower() == n), None)


def covered(look, model) -> bool:
    k = sig(look, model)
    return any(sig(s.get("look"), s.get("model")) == k for s in all_styles())


def make(name: str, look, model: str, lessons, examples) -> dict:
    """🔒 Lock a new official style. A name already taken is refused (locked styles are never overwritten)."""
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:40]
    look = [str(x) for x in look or [] if str(x).strip()]
    if not name:
        return {"ok": False, "icon": "✏️", "message": "Give the style a name first."}
    if not look and not model:
        return {"ok": False, "icon": "🎨", "message": "That result has no Look or model to lock."}
    with _lock:
        d = _read()
        if any(s["name"].lower() == name.lower() for s in d["styles"]):
            return {"ok": False, "icon": "🔒", "message": f"“{name}” is already an official style — pick another name."}
        st = {"name": name, "look": look, "model": str(model or ""), "prompt_lessons": [str(x) for x in lessons or []][-MAX_LESSONS:],
              "example_pictures": [str(x) for x in examples or []][:8], "locked": True, "at": time.time()}
        d["styles"].append(st)
        _write(d)
    return {"ok": True, "style": st}


def promote(root, name: str, item: dict, project_name: str = "") -> dict:
    """🔒 Make this an official style from one kept result: its Look + model, the project's lessons COPIED in."""
    ex = [f"{project_name}/{f}" if project_name else f for f in item.get("files") or []]
    return make(name, item.get("look"), item.get("model", ""), project_lessons(root), ex)


# ---------- choosing a style in a project ----------
def _choice_file(root) -> Path:
    return Path(root) / ".shelf" / "style.json"


def chosen(root) -> dict | None:
    try:
        n = json.loads(_choice_file(root).read_text()).get("name")
    except (OSError, ValueError, AttributeError):
        return None
    return get(n) if n else None


def choose(root, name: str) -> dict:
    """Use an official style in this project ('' = none). Its Look becomes the chips' last Look."""
    name = str(name or "").strip()
    st = get(name) if name else None
    if name and not st:
        return {"ok": False, "icon": "🎨", "message": "That style isn't on the official list."}
    f = _choice_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"name": st["name"] if st else ""}))
    if st and st.get("look"):
        from . import looks
        looks.remember_last(st["look"])
    return {"ok": True, "chosen": st}


def project_look(root) -> list[str]:
    st = chosen(root)
    return list(st.get("look") or []) if st else []


def writer_note(root) -> str:
    """Appended to a writer's system prompt when the project uses an official style (empty otherwise)."""
    st = chosen(root)
    if not st or not st.get("prompt_lessons"):
        return ""
    return (f" This project uses his official style “{st['name']}”. Lessons learned making it (lean toward 'kept', "
            f"away from 'avoid'): " + " || ".join(st["prompt_lessons"][-10:]))


# ---------- the proposal ----------
def proposal(root, pid: str) -> dict | None:
    """'This looks like a style — make it official?' when ≥4 kept results share Look + model, nothing covers them,
    and he hasn't said Never (or Not now since fewer than 4 more were kept)."""
    from . import shelf
    groups: dict[str, list[dict]] = {}
    for x in shelf.view(root)["kept"]:
        if x.get("look") and x.get("model"):
            groups.setdefault(sig(x["look"], x["model"]), []).append(x)
    ans = _read()["answers"].get(pid) or {}
    for k, xs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        a = ans.get(k) or {}
        if len(xs) < PROPOSE_AT or covered(xs[0]["look"], xs[0]["model"]) or a.get("answer") == "never":
            continue
        if a.get("answer") == "later" and len(xs) < int(a.get("count") or 0) + PROPOSE_AT:
            continue
        return {"sig": k, "look": xs[0]["look"], "model": xs[0]["model"], "count": len(xs), "n": xs[-1].get("n"),
                "examples": [f for x in xs[-4:] for f in (x.get("files") or [])][:4]}
    return None


def answer(root, pid: str, key: str, ans: str, name: str = "", project_name: str = "") -> dict:
    """Yes (needs a name → promote from the newest kept result in that group) · later · never."""
    if ans not in ("yes", "later", "never"):
        return {"ok": False, "icon": "⚠️", "message": "Answer must be yes, later or never."}
    p = proposal(root, pid)
    if not p or p["sig"] != key:
        return {"ok": False, "icon": "🎨", "message": "That suggestion is gone — refresh."}
    if ans == "yes":
        from . import shelf
        item = next(x for x in reversed(shelf.view(root)["kept"]) if sig(x.get("look"), x.get("model")) == key)
        r = promote(root, name, item, project_name)
        if not r["ok"]:
            return r
    with _lock:
        d = _read()
        d["answers"].setdefault(pid, {})[key] = {"answer": ans, "count": p["count"], "at": time.time()}
        _write(d)
    return {"ok": True, "answer": ans}
