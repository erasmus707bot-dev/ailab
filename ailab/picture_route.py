"""🏠 Picture route (local pictures M3, 2026-11-24 — Scott 1).

Which picture model a Lab picture run tries, in order:
  photo (Photo/35mm/Polaroid, Realism, a photo Style) → Juggernaut XL, else FLUX.2 Klein
  anime / manga                                        → Illustrious XL, else Pony V6
  any other drawn medium or style                      → SDXL base
  nothing said                                         → FLUX.2 Klein
Only local models Hermes lists as fitting the card are used (cached 60 s). Venice is the other side.
🏠 local-first (default) or 🌐 Venice-first — <lab home>/picture_route.json {"first": "local"|"venice"}, cfg
picture_first overrides. A local refusal or failed card job drops the rest of the local list (the card is busy or
off) and goes to the other side once. A forced cfg picture_model always wins. cfg local_drawn=false keeps drawn
Looks off the card (2026-11-24 switch, kept).
⚡ fast (default) or 🎨 full for the local SDXL models (2026-11-25, Scott 1) — same file, {"speed": …}; cfg
picture_speed overrides. Sent to Hermes image_make as speed; Hermes falls back to full if the speed LoRA is missing.
"""
from __future__ import annotations

import json
import time

from . import config, looks

ROUTES = {
    "photo": ["local/juggernaut-xl-v9", "local/flux2-klein-4b"],
    "anime": ["local/illustrious-xl-v0.1", "local/pony-v6-xl"],
    "drawn": ["local/sdxl-base-1.0"],
    "plain": ["local/flux2-klein-4b"],
}
STUDY_ROUTES = {"photo": ["local/juggernaut-xl-v9", "local/flux2-klein-4b"], "drawn": ["local/juggernaut-xl-v9", "local/sdxl-base-1.0"]}
# run 2: SDXL base kept drawing whole figures for thighs/legs; Juggernaut draws écorché detail when asked for anatomy.
WORDS = {"photo": "photo", "anime": "anime / manga", "drawn": "drawn style", "plain": "picture"}
ANIME = ("anime", "manga")
FIRSTS = ("local", "venice")
SPEEDS = ("fast", "full")
_ROWS = {"at": 0.0, "rows": None, "src": None}


def kind(look: list[str], style: str) -> str:
    names = [n.lower() for n in look or []]
    s = (style or "").lower()
    if any(n in ANIME for n in names) or any(w in s for w in ANIME):
        return "anime"
    if looks.photo(look) or "realism" in names or (not look and any(w in s for w in ("photo", "realis"))):
        return "photo"
    if (look and looks.negative(look, "")) or (not look and s):
        return "drawn"
    return "plain"


def _file():
    return config.home() / "picture_route.json"


def _saved() -> dict:
    try:
        v = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def _save(key: str, value: str) -> None:
    d = _saved()
    d[key] = value
    p = _file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d) + "\n", encoding="utf-8")


def first(run=None) -> str:
    c = str(((run.cfg if run is not None else {}) or {}).get("picture_first") or "")
    if c in FIRSTS:
        return c
    v = _saved().get("first")
    return v if v in FIRSTS else "local"


def set_first(value: str) -> dict:
    if value not in FIRSTS:
        return {"ok": False, "code": "bad_value", "message": "first is local or venice"}
    _save("first", value)
    return {"ok": True, "first": value, "speed": speed()}


def speed(run=None) -> str:
    c = str(((run.cfg if run is not None else {}) or {}).get("picture_speed") or "")
    if c in SPEEDS:
        return c
    v = _saved().get("speed")
    return v if v in SPEEDS else "fast"


def set_speed(value: str) -> dict:
    if value not in SPEEDS:
        return {"ok": False, "code": "bad_value", "message": "speed is fast or full"}
    _save("speed", value)
    return {"ok": True, "first": first(), "speed": value}


def rows(run) -> list[dict]:
    """Hermes image_models rows (cached 60 s). Any error = no rows (off is a normal state)."""
    src = id(getattr(run.lab, "mcp", None))
    if _ROWS["rows"] is not None and _ROWS["src"] == src and time.time() - _ROWS["at"] < 60:
        return _ROWS["rows"]
    try:
        r = run.lab.mcp.call("image_models", {}).get("models") or []
    except Exception:                                        # noqa: BLE001
        r = []
    _ROWS.update(at=time.time(), rows=list(r), src=src)
    return _ROWS["rows"]


def forget() -> None:
    _ROWS.update(at=0.0, rows=None)


def ready(run) -> set[str]:
    return {r.get("id") for r in rows(run) if str(r.get("id", "")).startswith("local/") and r.get("fits", True)}


def plan(run, look: list[str], style: str, venice_model: str, forced: bool) -> dict:
    k = kind(look, style)
    if forced:
        return {"kind": k, "first": "forced", "models": [venice_model]}
    if looks.study(look):                                    # 🦴 2026-11-25: Study runs stay on the local card, never Venice
        want = STUDY_ROUTES["drawn" if k in ("drawn", "anime") else "photo"]
        return {"kind": k, "first": "study", "models": [m for m in want if m in ready(run)]}
    want = ROUTES[k]
    if k == "drawn" and run.cfg.get("local_drawn") is False:
        want = []
    loc = [m for m in want if m in ready(run)] if want else []
    f = first(run)
    return {"kind": k, "first": f, "models": (loc + [venice_model]) if f == "local" else ([venice_model] + loc)}


def keys_line(run, model: str) -> str:
    """🔑 Keys this needs — never shows a key, only whether Hermes has it."""
    if model.startswith("local/"):
        return "🔑 Keys this needs: none — $0, stays on gandalf"
    if model.startswith("venice/"):
        rs = rows(run)
        if not rs:
            return "🔑 Keys this needs: Venice (in Hermes)"
        on = any(str(r.get("id", "")).startswith("venice/") for r in rs)
        return "🔑 Keys this needs: Venice (in Hermes) — " + ("✅ set" if on else "⛔ not added in Hermes yet")
    return "🔑 Keys this needs: OpenRouter (in Hermes)"
