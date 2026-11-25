"""🎨 Picture Looks (2026-11-24, Scott: "checkboxes for style/theme/mood/etc., broad and organized, must not take the
whole screen").

A Look is a short list of chip names from looks.json (Medium · Style · Theme · Mood · Light · Colour · Camera · Era ·
Finish). It travels in the task text as one line — `Look: Oil painting · Moody · Golden hour` — so 🔁 Make another and
✏️ Change it carry it the same way they carry Style:/Shape:.

Prompt order (research: subject first, then medium/style, then mood/light/colour/composition):
  Scott's exact words → medium + style + theme → the writer's added detail → mood, light, colour, camera, era, finish.
The writer detail is the only part ever shortened to fit the picture model's prompt limit; Scott's words never are.

Limits: Medium 1, every other tab its `max` (3), 8 in all. Clashes (Photo + Watercolor …) are a soft note, never a block.
Saved Looks (named) and the last Look used live in <lab home>/saved_looks.json.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from . import config

DEFAULT = Path(__file__).with_name("looks.json")
HEAD_TABS = ("medium", "style", "theme")                  # before the writer's detail
TAIL_TABS = ("mood", "light", "colour", "camera", "era", "finish")
PROMPT_MAX = 1500        # Venice lustify prompt limit (Venice model list, 2026-11-24 — UNVERIFIED live)
SEP = " · "
LINE_RX = re.compile(r"^Look:\s*(.*)$", re.M)
_lock = threading.Lock()


def catalog() -> dict:
    """looks.json, with <lab home>/looks.json on top (a tab with the same id replaces it; max_total/clash replace)."""
    cat = json.loads(DEFAULT.read_text(encoding="utf-8"))
    over = config.home() / "looks.json"
    try:
        extra = json.loads(over.read_text(encoding="utf-8")) if over.is_file() else {}
    except (OSError, ValueError):
        extra = {}
    if extra:
        tabs = {t["id"]: t for t in cat["tabs"]}
        for t in extra.get("tabs") or []:
            if isinstance(t, dict) and t.get("id"):
                if t.get("off"):
                    tabs.pop(t["id"], None)
                else:
                    tabs[t["id"]] = t
        cat["tabs"] = list(tabs.values())
        for k in ("max_total", "clash"):
            if k in extra:
                cat[k] = extra[k]
    return cat


def _index(cat: dict) -> dict[str, tuple[str, dict]]:
    return {it["n"].lower(): (t["id"], it) for t in cat["tabs"] for it in t.get("items", [])}


def split(text: str) -> list[str]:
    """`Oil painting · Moody, Golden hour` → names (· , ; | all separate). Duplicates dropped, order kept."""
    out = []
    for n in re.split(r"\s*[·;|,]\s*", text or ""):
        n = n.strip(" .")
        if n and n.lower() not in [o.lower() for o in out]:
            out.append(n)
    return out


def from_task(words: str) -> list[str]:
    """The Look named in a task's `Look:` line(s); [] when there is none."""
    names: list[str] = []
    for m in LINE_RX.findall(words or ""):
        names += [n for n in split(m) if n.lower() not in [x.lower() for x in names]]
    return names


def strip_line(words: str) -> str:
    return re.sub(r"^Look:.*(?:\n|$)", "", words or "", flags=re.M).strip()


def line(names: list[str]) -> str:
    return f"Look: {SEP.join(names)}" if names else ""


def normalize(names: list[str], cat: dict | None = None) -> tuple[list[str], list[str]]:
    """Apply the limits. Returns (kept names in catalog spelling, notes about anything dropped).
    Names not in the catalog (typed by hand) are kept as plain words and count toward the total."""
    cat = cat or catalog()
    idx, per = _index(cat), {t["id"]: int(t.get("max") or 3) for t in cat["tabs"]}
    total = int(cat.get("max_total") or 8)
    kept, notes, count = [], [], {}
    for n in names:
        tab, it = idx.get(n.lower(), (None, None))
        name = it["n"] if it else n
        if len(kept) >= total:
            notes.append(f"{name} left out — {total} picks at most")
            continue
        if tab:
            if count.get(tab, 0) >= per.get(tab, 3):
                label = next((t["label"] for t in cat["tabs"] if t["id"] == tab), tab)
                notes.append(f"{name} left out — {per[tab]} {label} pick{'s' if per[tab] > 1 else ''} at most")
                continue
            count[tab] = count.get(tab, 0) + 1
        kept.append(name)
    return kept, notes


def clashes(names: list[str], cat: dict | None = None) -> list[str]:
    """Soft notes like 'Photo + Watercolor may fight each other'. Never blocks a picture."""
    cat = cat or catalog()
    low = {n.lower(): n for n in names}
    out = []
    for a, bs in cat.get("clash") or []:
        if a.lower() in low:
            for b in bs.split("|"):
                if b.lower() in low:
                    out.append(f"{low[a.lower()]} + {low[b.lower()]}")
    return out


def parts(names: list[str], cat: dict | None = None) -> tuple[list[str], list[str]]:
    """(head words, tail words) for the prompt, in tab order. Unknown names go in the head (Scott typed them)."""
    cat = cat or catalog()
    idx = _index(cat)
    head, tail, extra = {t: [] for t in HEAD_TABS}, {t: [] for t in TAIL_TABS}, []
    for n in names:
        tab, it = idx.get(n.lower(), (None, None))
        words = ((it.get("p") or it["n"]) if it else n).strip()
        if tab in head:
            head[tab].append(words)
        elif tab in tail:
            tail[tab].append(words)
        else:
            extra.append(words)
    return [w for t in HEAD_TABS for w in head[t]] + extra, [w for t in TAIL_TABS for w in tail[t]]


def assemble(mine: str, names: list[str], add: str = "", limit: int = PROMPT_MAX, cat: dict | None = None) -> str:
    """Scott's words → medium/style/theme → writer detail → mood, light, colour, camera, era, finish.
    Only the writer detail is cut to fit `limit` (whole words); then tail words; Scott's words and the head never."""
    head, tail = parts(names, cat)
    mine = (mine or "").strip().rstrip(".")
    add = (add or "").strip().strip(".")
    lower = add.lower()                                    # don't say a Look word twice if the writer already did
    head = [w for w in head if w.lower() not in lower]
    tail = [w for w in tail if w.lower() not in lower]

    def build(a: str, t: list[str]) -> str:
        bits = [mine] + ([", ".join(head)] if head else []) + ([a] if a else []) + ([", ".join(t)] if t else [])
        return ". ".join(b for b in bits if b) + "."

    out = build(add, tail)
    while len(out) > limit and add:
        cut = add[: max(0, len(add) - (len(out) - limit) - 1)]
        add = cut.rsplit(" ", 1)[0].rstrip(" ,;:") if " " in cut else ""
        out = build(add, tail)
    while len(out) > limit and tail:
        tail = tail[:-1]
        out = build(add, tail)
    return out


def photo(names: list[str]) -> bool:
    return any(n.lower() in ("photo", "35mm film", "polaroid") for n in names)


def has_look_style(names: list[str], cat: dict | None = None) -> bool:
    """True when the Look already says the medium or style — the ❓ Style question is then skipped."""
    idx = _index(cat or catalog())
    return any(idx.get(n.lower(), ("",))[0] in ("medium", "style") for n in names)


# ---------- saved Looks + last Look ----------
def _file() -> Path:
    return config.home() / "saved_looks.json"


def _read() -> dict:
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(d: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def saved() -> dict:
    d = _read()
    return {"saved": [s for s in d.get("saved") or [] if isinstance(s, dict) and s.get("name")], "last": d.get("last") or []}


def save(name: str, names: list[str]) -> dict:
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:40]
    kept, _ = normalize([str(n) for n in names or []])
    if not name:
        return {"ok": False, "icon": "✏️", "message": "Give the Look a name first."}
    if not kept:
        return {"ok": False, "icon": "🎨", "message": "Pick at least one chip to save."}
    with _lock:
        d = _read()
        rest = [s for s in d.get("saved") or [] if isinstance(s, dict) and str(s.get("name", "")).lower() != name.lower()]
        d["saved"] = [{"name": name, "look": kept}] + rest[:39]
        _write(d)
    return {"ok": True, **saved()}


def delete(name: str) -> dict:
    with _lock:
        d = _read()
        d["saved"] = [s for s in d.get("saved") or [] if str(s.get("name", "")).lower() != str(name or "").lower()]
        _write(d)
    return {"ok": True, **saved()}


def remember_last(names: list[str]) -> None:
    if not names:
        return
    with _lock:
        d = _read()
        d["last"] = list(names)
        _write(d)


def public() -> dict:
    """What the 🎨 Look dialog needs: the catalog plus saved Looks and the last one used."""
    cat = catalog()
    return {"ok": True, "tabs": cat["tabs"], "max_total": int(cat.get("max_total") or 8), "clash": cat.get("clash") or [],
            **saved()}
