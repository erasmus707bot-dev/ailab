"""🏃 Motion Presets library (Scott 2026-11-25: "saved presets of motions, movements and interactions between 2–10
participants … tap one and it goes into the prompt for a video, picture or any creative piece").

A preset (motion.json, schema v1) — global like the cast library, in <lab home>/motions/<id>/:
  name · roles [{key A.., label, min, max}] · words with role slots ("{A} spots {B} on the bench") ·
  moments [{name, words, star, t, frame, pose, people}] (exactly one ⭐ — the default still) · camera · feel range
  [lo, hi] + feel (calm 0 ↔ 1 explosive, one slider in place of speed + intensity) · seconds · preview (looping
  mp4 cut from the clip, or a $0 stick-figure SVG drawn from the poses) · source (video+range / written / result) ·
  shelves (sports, dance, everyday, fight, play …) · aliases (other words for it in the timeline words box).
Three ways in (Module 2 — motion_fill.py): ⭐ pull from a video, write it, save from a result.
"""
from __future__ import annotations

import json
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

from . import config

V = 1
SHELVES = ("sports", "lifting", "track", "dance", "everyday", "fight", "play", "romance", "work", "travel", "other")
CAMERAS = ("still", "slow push-in", "pull-out", "pan left", "pan right", "tilt up", "tilt down", "slow orbit",
           "low tracking", "tracking", "handheld")
ROLE_KEYS = "ABCDEFGHIJ"
MAX_PEOPLE = 10
MAX_MOMENTS = 6
FEEL_WORDS = ((0.2, "slow, calm and controlled"), (0.4, "steady and smooth"), (0.6, ""), (0.8, "fast and energetic"),
              (1.01, "explosive, powerful and sudden"))
ASSET_EXT = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".svg"}
SLOT = re.compile(r"\{([A-J])\}")
_lock = threading.Lock()


# ---------------------------------------------------------------- paths
def home() -> Path:
    return config.home() / "motions"


def new_id(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")[:24] or "motion"
    return f"m-{s}-{secrets.token_hex(3)}"


def _dir(mid: str) -> Path:
    if not re.fullmatch(r"m-[a-z0-9-]{1,24}-[0-9a-f]{6}", str(mid or "")):
        raise ValueError("bad motion id")
    return home() / mid


def asset(mid: str, rel: str) -> Path | None:
    """A file inside one preset's folder (previews, frames, poses) — never anything outside it."""
    try:
        d = _dir(mid).resolve()
        p = (d / str(rel or "")).resolve(strict=True)
    except (ValueError, OSError, RuntimeError):
        return None
    return p if d in p.parents and p.suffix.lower() in ASSET_EXT and p.is_file() else None


# ---------------------------------------------------------------- shape
def feel_word(f) -> str:
    try:
        f = max(0.0, min(1.0, float(f)))
    except (TypeError, ValueError):
        f = 0.5
    return next(w for lim, w in FEEL_WORDS if f < lim)


def _num(x, lo, hi, d):
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return d


def clean(raw: dict) -> dict:
    """Any preset-like dict → schema v1 (missing bits filled, junk dropped). validate() says what is still wrong."""
    r = raw if isinstance(raw, dict) else {}
    roles = []
    for i, x in enumerate((r.get("roles") or [])[:MAX_PEOPLE]):
        x = x if isinstance(x, dict) else {"label": str(x)}
        mn = int(_num(x.get("min"), 1, MAX_PEOPLE, 1))
        roles.append({"key": ROLE_KEYS[i], "label": str(x.get("label") or f"person {ROLE_KEYS[i]}")[:30],
                      "min": mn, "max": int(_num(x.get("max"), mn, MAX_PEOPLE, mn))})
    words = re.sub(r"\s+", " ", str(r.get("words") or "")).strip()[:400]
    if not roles:
        keys = sorted(set(SLOT.findall(words))) or ["A"]
        roles = [{"key": k, "label": f"person {k}", "min": 1, "max": 1} for k in ROLE_KEYS[:len(keys)]]
    moments = []
    for x in (r.get("moments") or [])[:MAX_MOMENTS]:
        if isinstance(x, dict) and (x.get("name") or x.get("words")):
            m = {"name": str(x.get("name") or x.get("words"))[:50], "words": re.sub(r"\s+", " ", str(x.get("words") or x.get("name"))).strip()[:300],
                 "star": bool(x.get("star"))}
            for k in ("t", "frame", "pose"):
                if x.get(k) not in (None, ""):
                    m[k] = x[k]
            if isinstance(x.get("people"), list):
                m["people"] = x["people"][:MAX_PEOPLE]
            moments.append(m)
    if moments and sum(m["star"] for m in moments) != 1:
        first = next((i for i, m in enumerate(moments) if m["star"]), 0)
        for i, m in enumerate(moments):
            m["star"] = i == first
    lo, hi = (r.get("feel_range") or [0.0, 1.0])[:2] if isinstance(r.get("feel_range"), list) and len(r.get("feel_range")) >= 2 else (0.0, 1.0)
    lo, hi = _num(lo, 0, 1, 0.0), _num(hi, 0, 1, 1.0)
    lo, hi = min(lo, hi), max(lo, hi)
    cam = str(r.get("camera") or "still").lower()
    out = {"v": V, "id": str(r.get("id") or ""), "name": re.sub(r"\s+", " ", str(r.get("name") or "")).strip()[:40],
           "roles": roles, "words": words, "moments": moments, "camera": cam if cam in CAMERAS else "still",
           "feel_range": [lo, hi], "feel": _num(r.get("feel"), lo, hi, (lo + hi) / 2),
           "seconds": _num(r.get("seconds"), 1, 30, 4.0),
           "shelves": [s for s in (r.get("shelves") or []) if s in SHELVES][:4] or ["other"],
           "aliases": [str(a).strip().lower()[:30] for a in (r.get("aliases") or []) if str(a).strip()][:6],
           "source": r.get("source") if isinstance(r.get("source"), dict) else {"kind": "written"},
           "preview": str(r.get("preview") or ""), "made": float(r.get("made") or time.time()), "uses": int(r.get("uses") or 0)}
    return out


def people_range(p: dict) -> tuple[int, int]:
    return sum(r["min"] for r in p["roles"]), sum(r["max"] for r in p["roles"])


def validate(p: dict) -> list[str]:
    bad = []
    if not p.get("name"):
        bad.append("Give the motion a name.")
    if not p.get("words"):
        bad.append("Say what happens (the motion words).")
    lo, hi = people_range(p)
    if not 1 <= lo <= MAX_PEOPLE or hi > MAX_PEOPLE:
        bad.append(f"A motion is for 1–{MAX_PEOPLE} people.")
    missing = [r["key"] for r in p["roles"] if f"{{{r['key']}}}" not in p["words"]]
    if missing:
        bad.append("The words need a slot for every role: " + ", ".join(f"{{{k}}}" for k in missing) + ".")
    if not p.get("moments"):
        bad.append("Add at least one key moment (one is the ⭐ default picture).")
    return bad


# ---------------------------------------------------------------- store
def _read(mid: str) -> dict | None:
    try:
        return clean(json.loads((_dir(mid) / "motion.json").read_text(encoding="utf-8")))
    except (ValueError, OSError):
        return None


def get(mid: str) -> dict | None:
    return _read(mid)


def save(raw: dict, files: dict[str, Path] | None = None) -> dict:
    """Validate, give it an id, copy its asset files in (rel name → source path). {"ok": False, "problems"} if wrong."""
    p = clean(raw)
    bad = validate(p)
    if bad:
        return {"ok": False, "icon": "🏃", "message": bad[0], "problems": bad}
    with _lock:
        if not p["id"] or _read(p["id"]) is None:
            taken = {x["name"].lower() for x in all_motions()}
            if p["name"].lower() in taken and not raw.get("id"):
                return {"ok": False, "icon": "✏️", "message": f"There is already a motion called {p['name']!r} — pick another name."}
            p["id"] = p["id"] if p["id"] and re.fullmatch(r"m-[a-z0-9-]{1,24}-[0-9a-f]{6}", p["id"]) else new_id(p["name"])
        d = _dir(p["id"])
        d.mkdir(parents=True, exist_ok=True)
        for rel, src in (files or {}).items():
            rel = str(rel).lstrip("/")
            if ".." in Path(rel).parts or Path(rel).suffix.lower() not in ASSET_EXT:
                continue
            dst = d / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copyfile(src, dst)
            except OSError:
                continue
        if not p["preview"] or not (d / p["preview"]).is_file():
            (d / "preview.svg").write_text(preview_svg(p), encoding="utf-8")
            p["preview"] = "preview.svg"
        tmp = d / "motion.tmp"
        tmp.write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(d / "motion.json")
    return {"ok": True, "motion": p}


def delete(mid: str) -> dict:
    """Moved into motions/_trash/ (the Lab keeps a way back; nothing is wiped)."""
    try:
        d = _dir(mid)
    except ValueError:
        return {"ok": False, "message": "No such motion."}
    if not d.is_dir():
        return {"ok": False, "message": "No such motion."}
    t = home() / "_trash" / f"{mid}-{int(time.time())}"
    t.parent.mkdir(parents=True, exist_ok=True)
    d.rename(t)
    return {"ok": True}


def used(mid: str) -> None:
    p = _read(mid)
    if p:
        p["uses"] += 1
        with _lock:
            (_dir(mid) / "motion.json").write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")


def all_motions() -> list[dict]:
    out = []
    if home().is_dir():
        for d in sorted(home().iterdir()):
            if d.is_dir() and d.name.startswith("m-"):
                p = _read(d.name)
                if p:
                    out.append(p)
    return out


def search(query: str = "", shelf: str = "", people: int = 0) -> list[dict]:
    q = [w for w in re.findall(r"[a-z0-9]+", str(query or "").lower()) if len(w) > 1]
    out = []
    for p in all_motions():
        if shelf and shelf not in p["shelves"]:
            continue
        lo, hi = people_range(p)
        if people and not lo <= people:
            continue
        hay = " ".join([p["name"], p["words"], " ".join(p["aliases"]), " ".join(m["name"] for m in p["moments"]),
                        " ".join(p["shelves"])]).lower()
        if q and not all(w in hay for w in q):
            continue
        out.append(p)
    return sorted(out, key=lambda p: (-p["uses"], -p["made"]))


def card(p: dict) -> dict:
    """What a chip / sheet row needs."""
    lo, hi = people_range(p)
    star = next((m for m in p["moments"] if m["star"]), {})
    return {"id": p["id"], "name": p["name"], "words": p["words"], "roles": p["roles"], "people": [lo, hi],
            "camera": p["camera"], "feel": p["feel"], "feel_range": p["feel_range"], "seconds": p["seconds"],
            "shelves": p["shelves"], "source": p["source"].get("kind", "written"), "preview": p["preview"],
            "star": star.get("name", ""), "moments": [{k: m.get(k) for k in ("name", "star", "frame", "pose")} for m in p["moments"]],
            "poses": any(m.get("pose") for m in p["moments"]), "uses": p["uses"]}


def public(query: str = "", shelf: str = "") -> dict:
    return {"ok": True, "motions": [card(p) for p in search(query, shelf)], "shelves": list(SHELVES), "cameras": list(CAMERAS)}


# ---------------------------------------------------------------- into words
def fill(text: str, who: dict[str, str]) -> str:
    """{A} → the person picked for role A ("someone" if nobody was)."""
    return SLOT.sub(lambda m: who.get(m.group(1)) or "someone", str(text or ""))


def sentence(p: dict, who: dict[str, str], feel=None, moment: str = "") -> str:
    """One motion as plain words: the moment (or the whole motion), its feel, nothing about looks."""
    m = next((x for x in p["moments"] if x["name"] == moment), None) if moment else None
    base = fill(m["words"] if m else p["words"], who).rstrip(". ")
    fw = feel_word(p["feel"] if feel is None else feel)
    return f"{base}, {fw}" if fw else base


# ---------------------------------------------------------------- $0 stick-figure preview
LIMBS = ((1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13), (1, 0),
         (0, 14), (14, 16), (0, 15), (15, 17))
COLOURS = ("#7aa2c8", "#c8a24a", "#8fb38a", "#c78f8f", "#a58fc7", "#8fc7c2", "#c7b38f", "#9aa0a6", "#b38fc7", "#8fa8c7")


def _person_paths(kps: list, w: int, h: int) -> str:
    segs = []
    for a, b in LIMBS:
        if a < len(kps) and b < len(kps) and kps[a][2] >= 0.3 and kps[b][2] >= 0.3:
            segs.append(f"M{kps[a][0] * w:.0f} {kps[a][1] * h:.0f}L{kps[b][0] * w:.0f} {kps[b][1] * h:.0f}")
    return " ".join(segs) or "M0 0"


def preview_svg(p: dict, w: int = 160, h: int = 200) -> str:
    """Looping SVG: the poses of each key moment, one after another (SMIL, no script, plays in any browser, $0).
    With no poses: one dot per role that drifts, so a written preset still has something moving before a test render."""
    frames = [m.get("people") or [] for m in p.get("moments") or []]
    dur = max(1.5, min(6.0, float(p.get("seconds") or 4)))
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<rect width="{w}" height="{h}" fill="#1b2430"/>')
    if any(frames):
        n = max(len(f) for f in frames)
        body = []
        for i in range(n):
            ds, last = [], "M0 0"
            for f in frames:
                last = _person_paths(f[i]["kps"], w, h) if i < len(f) and f[i].get("kps") else last
                ds.append(last)
            if len(ds) > 1:
                ds.append(ds[0])
            vals = ";".join(ds)
            anim = (f'<animate attributeName="d" values="{vals}" dur="{dur:.1f}s" repeatCount="indefinite" calcMode="discrete"/>'
                    if len(ds) > 1 else "")
            body.append(f'<path d="{ds[0]}" stroke="{COLOURS[i % len(COLOURS)]}" stroke-width="4" stroke-linecap="round" fill="none">{anim}</path>')
        return head + "".join(body) + "</svg>"
    roles = p.get("roles") or [{"key": "A"}]
    body = []
    for i, r in enumerate(roles[:MAX_PEOPLE]):
        x = w * (i + 1) / (len(roles) + 1)
        body.append(f'<g><circle cx="{x:.0f}" cy="{h * 0.55:.0f}" r="14" fill="{COLOURS[i % len(COLOURS)]}">'
                    f'<animate attributeName="cy" values="{h * 0.55:.0f};{h * 0.4:.0f};{h * 0.55:.0f}" dur="{dur:.1f}s" '
                    f'begin="{i * 0.25:.2f}s" repeatCount="indefinite"/></circle>'
                    f'<text x="{x:.0f}" y="{h * 0.85:.0f}" font-size="20" text-anchor="middle" fill="#e8dfc8">{r["key"]}</text></g>')
    return head + "".join(body) + "</svg>"
