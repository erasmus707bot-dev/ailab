"""🏃 Motion timeline (Motion Presets M3+M4, Scott 2026-11-25).

A scene (<project>/.shelf/motion_scene.json, v1):
  people  — the scene's characters (names, from the 🎭 cast or typed)
  blocks  — [{id, preset, who {A: name…}, start (pinned s or None), after (block id or None), dur, feel, moment}]
  camera  — [{id, move, start, dur}]  (the camera row above the people rows)
  idle    — {name: preset id or ""}   people not in a block carry on "in the background" (optional idle preset)
Timing: "after" chains to another block's end ("then"); "start" pins a time ("at N s"); neither = right after that
person's previous block. Words box ⇄ blocks: to_words() writes the words, from_words() reads them back; the page sends
whichever he changed and shows the other.
"""
from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from . import motions as MO

V = 1
MAX_ACTIONS = 3            # ~3 separate actions per shot before video models get shaky — UNVERIFIED (config motion.max_actions)
NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
CALM = re.compile(r"\b(calm|calmly|slow|slowly|gentle|gently|soft|softly)\b", re.I)
WILD = re.compile(r"\b(explosive|explosively|fast|quick|quickly|hard|powerful|powerfully|wild|wildly)\b", re.I)


def _bid() -> str:
    return "b" + secrets.token_hex(3)


def blank(people: list[str] | None = None) -> dict:
    return {"v": V, "people": [str(p)[:30] for p in (people or [])][:MO.MAX_PEOPLE], "blocks": [], "camera": [], "idle": {}}


def _file(root) -> Path:
    return Path(root) / ".shelf" / "motion_scene.json"


def load(root) -> dict:
    try:
        return clean(json.loads(_file(root).read_text()))
    except (OSError, ValueError):
        return blank()


def save(root, scene: dict) -> dict:
    s = clean(scene)
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(s, indent=1, ensure_ascii=False))
    return s


def clean(raw) -> dict:
    r = raw if isinstance(raw, dict) else {}
    s = blank(r.get("people") or [])
    ids = set()
    for b in r.get("blocks") or []:
        if not isinstance(b, dict) or not b.get("preset"):
            continue
        bid = str(b.get("id") or "") if re.fullmatch(r"b[0-9a-f]{6}", str(b.get("id") or "")) else _bid()
        ids.add(bid)
        who = {str(k)[:1]: str(v)[:30] for k, v in (b.get("who") or {}).items() if str(k)[:1] in MO.ROLE_KEYS and v}
        st = b.get("start")
        s["blocks"].append({"id": bid, "preset": str(b["preset"]), "who": who,
                            "start": None if st in (None, "") else max(0.0, round(float(st), 2)),
                            "after": str(b.get("after") or "") or None, "dur": max(0.5, min(30.0, float(b.get("dur") or 4))),
                            "feel": max(0.0, min(1.0, float(b.get("feel") if b.get("feel") is not None else 0.5))),
                            "moment": str(b.get("moment") or "")[:50]})
    for b in s["blocks"]:
        if b["after"] not in ids or b["after"] == b["id"]:
            b["after"] = None
    for c in r.get("camera") or []:
        if isinstance(c, dict) and str(c.get("move") or "") in MO.CAMERAS:
            s["camera"].append({"id": str(c.get("id") or _bid()), "move": c["move"], "start": max(0.0, float(c.get("start") or 0)),
                                "dur": max(0.5, min(60.0, float(c.get("dur") or 4)))})
    s["idle"] = {str(k)[:30]: str(v or "") for k, v in (r.get("idle") or {}).items() if str(k) in s["people"]}
    for b in s["blocks"]:                                       # anyone in a block is a person of the scene
        for n in b["who"].values():
            if n not in s["people"] and len(s["people"]) < MO.MAX_PEOPLE:
                s["people"].append(n)
    return s


# ---------------------------------------------------------------- timing
def resolve(scene: dict) -> list[dict]:
    """Blocks with absolute start/end, in time order. 'after' cycles are broken (the block falls back to sequence)."""
    blocks = {b["id"]: dict(b) for b in scene["blocks"]}
    order = [b["id"] for b in scene["blocks"]]
    done: dict[str, float] = {}
    row_end: dict[str, float] = {}

    def start_of(bid: str, seen: tuple = ()) -> float:
        b = blocks[bid]
        if bid in done:
            return done[bid]
        if b["start"] is not None:
            t = b["start"]
        elif b["after"] and b["after"] in blocks and b["after"] not in seen:
            t = start_of(b["after"], seen + (bid,)) + blocks[b["after"]]["dur"]
        else:
            t = max([row_end.get(n, 0.0) for n in b["who"].values()] or [0.0])
        done[bid] = round(t, 2)
        return done[bid]

    out = []
    for bid in order:
        t = start_of(bid)
        b = blocks[bid]
        for n in b["who"].values():
            row_end[n] = max(row_end.get(n, 0.0), t + b["dur"])
        out.append({**b, "t0": t, "t1": round(t + b["dur"], 2)})
    return sorted(out, key=lambda b: (b["t0"], order.index(b["id"])))


def length(scene: dict) -> float:
    r = resolve(scene)
    return max([b["t1"] for b in r] + [c["start"] + c["dur"] for c in scene["camera"]] + [0.0])


def rows(scene: dict) -> dict[str, list[dict]]:
    """One row per person (the timeline's lanes)."""
    r = resolve(scene)
    return {p: [b for b in r if p in b["who"].values()] for p in scene["people"]}


def busy(scene: dict, t0: float, t1: float) -> list[dict]:
    return [b for b in resolve(scene) if b["t0"] < t1 and b["t1"] > t0]


def max_actions(cfg: dict | None) -> int:
    try:
        return max(1, int(((cfg or {}).get("motion") or {}).get("max_actions") or MAX_ACTIONS))
    except (TypeError, ValueError):
        return MAX_ACTIONS


def too_busy(scene: dict, cfg: dict | None = None) -> list[tuple[float, int]]:
    """Moments where more than ~3 separate actions overlap: [(time, count)]."""
    lim, out = max_actions(cfg), []
    for b in resolve(scene):
        n = len(busy(scene, b["t0"], b["t0"] + 0.01))
        if n > lim:
            out.append((b["t0"], n))
    return out


def shots(scene: dict, cfg: dict | None = None) -> list[tuple[float, float]]:
    """⭐ Split into shots: cut wherever a block starts if keeping it would put > max actions in one shot."""
    lim = max_actions(cfg)
    r = resolve(scene)
    if not r:
        return []
    cuts, cur, live = [r[0]["t0"]], r[0]["t0"], set()
    for b in r:
        live = {x["id"] for x in r if x["t0"] < max(b["t1"], b["t0"] + 0.01) and x["t1"] > cur and x["t0"] <= b["t0"]}
        if len(live) > lim and b["t0"] > cur:
            cuts.append(b["t0"])
            cur = b["t0"]
    end = length(scene)
    return [(a, b) for a, b in zip(cuts, cuts[1:] + [end]) if b > a]


# ---------------------------------------------------------------- words ⇄ blocks
def _who_text(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1] if names else "someone"


def to_words(scene: dict, presets: dict[str, dict]) -> str:
    """Blocks → plain words, one sentence per block, in the order he'd read them."""
    names = {b["id"]: (presets.get(b["preset"]) or {}).get("name", "a motion") for b in scene["blocks"]}
    lines = []
    for i, b in enumerate(resolve(scene)):
        p = presets.get(b["preset"]) or {}
        who = _who_text([b["who"][r["key"]] for r in p.get("roles", []) if b["who"].get(r["key"])] or list(b["who"].values()))
        if b["start"] is not None:
            lead = f"At {b['start']:g} s,"
        elif b["after"]:
            lead = f"After the {names.get(b['after'], 'motion').lower()},"
        else:
            lead = "First," if i == 0 else "Then"
        fw = "calm" if b["feel"] < 0.3 else "explosive" if b["feel"] > 0.7 else ""
        tail = f" ({b['dur']:g} s{', ' + fw if fw else ''})"
        lines.append(f"{lead} {who} {names[b['id']].lower()}{tail}.")
    return " ".join(lines)


def _split(text: str) -> list[str]:
    """Sentences, and "…, then …" pieces (a piece after "then" keeps the word so it chains to the one before)."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    out = []
    for sent in re.split(r"(?<=[.;!?])\s+|\n+", t):
        for j, piece in enumerate(re.split(r",?\s+\bthen\b\s+", sent, flags=re.I)):
            piece = piece.strip(" .;!?,")
            if piece:
                out.append(("then " if j else "") + piece)
    return out


def _find_preset(s: str, presets: dict[str, dict]) -> dict | None:
    low = s.lower()
    best, size = None, 0
    for p in presets.values():
        names = [p["name"].lower()] + list(p.get("aliases") or [])
        names += [re.sub(r"^the\s+", "", n) for n in names if n.startswith("the ")]
        for name in names:
            name = name.strip()
            if name and re.search(rf"\b{re.escape(name)}(?:s|es|ed|ing)?\b", low) and len(name) > size:
                best, size = p, len(name)
    if best:
        return best
    words = set(re.findall(r"[a-z]{4,}", low))          # loose: most of a name's long words appear
    for p in presets.values():
        nw = set(re.findall(r"[a-z]{4,}", p["name"].lower()))
        if nw and len(nw & words) >= max(1, len(nw) - 1) and len(nw & words) > size:
            best, size = p, len(nw & words)
    return best


def from_words(text: str, presets: dict[str, dict], people: list[str], old: dict | None = None) -> tuple[dict, list[str]]:
    """Words → a scene. Returns (scene, notes). A sentence it can't place is named in notes, never guessed."""
    scene = blank(people)
    if old:
        scene["camera"], scene["idle"] = old.get("camera", []), old.get("idle", {})
    notes = []
    prev = None
    for s in _split(text):
        core = re.sub(r"^(?:then\s+|first,?\s+)?(?:after\s+(?:the\s+)?[^,]+,|at\s+\d+(?:\.\d+)?\s*(?:s|sec|secs|seconds)\b,?)\s*",
                      "", s, flags=re.I)
        p = _find_preset(core, presets)
        if not p:
            notes.append(f"🤔 No saved motion matches “{s[:60]}” — save it as a preset, or use a preset's name.")
            continue
        low = s.lower()
        cl = core.lower()
        named = sorted([(cl.find(n.lower()), n) for n in people if re.search(rf"\b{re.escape(n.lower())}\b", cl)])
        names = [n for _, n in named]
        who = {r["key"]: names[i] for i, r in enumerate(p["roles"]) if i < len(names)}
        if len(names) < MO.people_range(p)[0]:
            notes.append(f"👥 “{p['name']}” needs {MO.people_range(p)[0]} people — name who does it.")
        b = {"id": _bid(), "preset": p["id"], "who": who, "start": None, "after": None, "dur": float(p["seconds"]),
             "feel": float(p["feel"]), "moment": ""}
        m = re.search(r"\bat\s+(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)\b", low)
        if m:
            b["start"] = float(m.group(1))
        a = re.search(r"\bafter\s+(?:the\s+)?([a-z' -]+?)(?:,|$)", low)
        if a and not m:
            ref = _find_preset(a.group(1), {k: v for k, v in presets.items()})
            tgt = next((x for x in reversed(scene["blocks"]) if ref and x["preset"] == ref["id"]), None)
            if tgt:
                b["after"] = tgt["id"]
            else:
                notes.append(f"⏱ “after {a.group(1).strip()}” — that motion isn't earlier in the scene, so it follows on.")
        if re.match(r"then\b", low) and not b["after"] and b["start"] is None and prev:
            b["after"] = prev["id"]
        dd = (re.search(r"\((\d+(?:\.\d+)?)\s*s\b", low)
              or re.search(r"\bfor\s+(\d+(?:\.\d+)?|" + "|".join(NUMS) + r")\s*(?:s|sec|secs|seconds)\b", low))
        if dd:
            v = dd.group(1)
            b["dur"] = float(NUMS.get(v, v))
        if WILD.search(s):
            b["feel"] = 0.85
        elif CALM.search(s):
            b["feel"] = 0.15
        scene["blocks"].append(b)
        prev = b
    return clean(scene), notes


# ---------------------------------------------------------------- into making
def block_words(b: dict, presets: dict[str, dict], still: bool = False) -> str:
    p = presets.get(b["preset"])
    if not p:
        return ""
    mom = b.get("moment") or (next((m["name"] for m in p["moments"] if m["star"]), "") if still else "")
    return MO.sentence(p, b["who"], b["feel"], mom)


def background(scene: dict, active: list[dict], presets: dict[str, dict]) -> str:
    busy_names = {n for b in active for n in b["who"].values()}
    rest = [n for n in scene["people"] if n not in busy_names]
    if not rest:
        return ""
    bits = []
    for n in rest:
        idle = presets.get(scene["idle"].get(n) or "")
        bits.append(MO.fill(idle["words"], {"A": n}).rstrip(". ") + " in the background" if idle else f"{n} in the background, carrying on")
    return "; ".join(bits)


def camera_at(scene: dict, t0: float, t1: float, presets: dict[str, dict], active: list[dict]) -> str:
    c = next((c for c in scene["camera"] if c["start"] < t1 and c["start"] + c["dur"] > t0), None)
    if c:
        return c["move"]
    return next(((presets.get(b["preset"]) or {}).get("camera", "") for b in active if (presets.get(b["preset"]) or {}).get("camera") not in ("", "still")), "")


def stills(scene: dict, presets: dict[str, dict]) -> list[dict]:
    """Picture making: one still per block — its ⭐ key moment (or the moment he picked), with its pose frame."""
    out = []
    for b in resolve(scene):
        p = presets.get(b["preset"])
        if not p:
            continue
        mom = next((m for m in p["moments"] if m["name"] == b.get("moment")), None) or next((m for m in p["moments"] if m["star"]), {})
        others = [x for x in resolve(scene) if x["id"] != b["id"] and x["t0"] <= b["t0"] < x["t1"]]
        words = "; ".join([block_words(b, presets, still=True)] + [block_words(x, presets) for x in others])
        bg = background(scene, [b] + others, presets)
        out.append({"block": b["id"], "preset": p["id"], "name": p["name"], "moment": mom.get("name", ""), "pose": mom.get("pose", ""),
                    "who": list(b["who"].values()) + [n for x in others for n in x["who"].values()],
                    "words": words + (f". {bg}" if bg else ""), "camera": camera_at(scene, b["t0"], b["t1"], presets, [b])})
    return out


def clips(scene: dict, presets: dict[str, dict], max_s: float, cfg: dict | None = None) -> list[dict]:
    """Video making: the timeline cut into clips no longer than the model allows, at block edges where it can.
    Each clip: {t0, t1, secs, words, camera, who, blocks}."""
    end = length(scene)
    if end <= 0:
        return []
    edges = sorted({0.0, end} | {b["t0"] for b in resolve(scene)} | {b["t1"] for b in resolve(scene)} |
                   {a for a, _ in shots(scene, cfg)})
    out, t = [], 0.0
    while t < end - 0.05:
        cands = [e for e in edges if t < e <= t + max_s + 1e-6]
        nxt = max(cands) if cands else min(t + max_s, end)
        active = busy(scene, t, nxt)
        words = "; ".join(w for w in (block_words(b, presets) for b in active) if w)
        bg = background(scene, active, presets)
        out.append({"t0": round(t, 2), "t1": round(nxt, 2), "secs": max(1, int(round(nxt - t))),
                    "words": words + (f". {bg}" if bg else ""), "camera": camera_at(scene, t, nxt, presets, active),
                    "who": sorted({n for b in active for n in b["who"].values()}), "blocks": [b["id"] for b in active]})
        t = nxt
    return out


def split_busy(scene: dict, cfg: dict | None = None) -> dict:
    """✂️ Split into shots: a block that would make one moment too busy waits for the earliest-ending block before it
    (its pinned time is dropped, it chains with "then"). Repeats until no moment has more than ~3 actions."""
    s = clean(scene)
    lim = max_actions(cfg)
    for _ in range(len(s["blocks"]) * 2):
        hot = None
        for b in resolve(s):
            live = [x for x in busy(s, b["t0"], b["t0"] + 0.01)]
            if len(live) > lim:
                hot = (b, live)
                break
        if not hot:
            break
        b, live = hot
        last = max(live, key=lambda x: (x["t0"], x["id"]))
        first_end = min((x for x in live if x["id"] != last["id"]), key=lambda x: x["t1"])
        for x in s["blocks"]:
            if x["id"] == last["id"]:
                x["start"], x["after"] = None, first_end["id"]
    return s
