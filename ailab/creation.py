"""🧩 Creation types (2026-11-24, Scott: "select category/categories of creations before prompt and build").

Chips above the task box: 🌐 Website · 📱 Android · 🪟 Windows · 🐧 Linux · 🎮 Game · 📝 Text · 🔧 Edit existing ·
🖼 Image · 🎬 Video. More than one can be on. The Lab puts a ⭐ on its guess from the words typed; Scott taps to change.

Each type is one small setup — which model to suggest, which robot test, which questions are worth asking, where it
ships, and a few lines for the agent. A new type = a new entry here, or in <lab home>/creation_types.json (same keys;
an entry with an existing id replaces it, {"id": "x", "off": true} hides one). No code change needed.

🖼 Image → picture run (picture.py) · 🎬 Video (+ 🖼) → video run (video.py, Hermes video_make / Venice) · 📝 Text
→ document run (docrun.py, uncensored writer, pictures on request, Word + PDF). With an app/game/site chip on, the agent builds it and the
🎭 art/code split (content.py) makes the story, words and pictures first (2026-11-24, Scott: art in every form).
"""
from __future__ import annotations

import json
import re

from . import config

# robot: "play" = press start + keys (games) · "page" = open + click, a still screen is fine · "none" = no page to test
# ship: platforms for 📦 Make it an app · handoff: Hermes page path when the Lab can't make it itself
TYPES: list[dict] = [
    {"id": "website", "icon": "🌐", "label": "Website", "use": "💻 coding", "robot": "page", "ship": [],
     "words": ["website", "web site", "web page", "webpage", "landing page", "homepage", "home page", "site", "html", "portfolio", "blog"],
     "guide": "A website: index.html at the top of the project, plain HTML/CSS/JS, works offline, fits a phone (390 wide) and a desktop.",
     "questions": [["Look?", ["Warm and calm ⭐", "Bold and bright", "Plain and simple"]],
                   ["How many pages?", ["One page ⭐", "A few pages", "Not sure yet"]]]},
    {"id": "android", "icon": "📱", "label": "Android", "use": "💻 coding", "robot": "page", "ship": ["android"],
     "words": ["android", "apk", "phone app", "mobile app", "for my phone", "s24", "pixel"],
     "guide": "An Android app: build it as a web app (index.html at the top) that fits a phone screen, big touch targets (44 px+), "
              "no hover-only controls. When it works, Scott taps 📦 Make it an app → Hermes App Builder makes the APK. Never claim the APK is built.",
     "questions": [["Which way up?", ["Upright (portrait) ⭐", "Sideways (landscape)", "Both"]]]},
    {"id": "windows", "icon": "🪟", "label": "Windows", "use": "💻 coding", "robot": "page", "ship": ["windows"],
     "words": ["windows", "exe", "pc app", "desktop app", "for windows", ".msi"],
     "guide": "A Windows app: build it as a web app (index.html at the top) sized for a desktop window. When it works, Scott taps "
              "📦 Make it an app → Hermes builds it and tests it in the Windows VM first. Never claim the .exe is built.",
     "questions": [["Window size?", ["Normal window ⭐", "Full screen", "Small helper window"]]]},
    {"id": "linux", "icon": "🐧", "label": "Linux", "use": "💻 coding", "robot": "page", "ship": ["linux"],
     "words": ["linux", "mint", "ubuntu", ".deb", "debian", "for gandalf"],
     "guide": "A Linux app. In connected mode prefer the Hermes linux_app_* tools (describe → change → build → package). "
              "Otherwise build a web app with index.html at the top and Scott ships it with 📦 Make it an app.",
     "questions": [["How should it run?", ["Its own window ⭐", "In the browser", "In the terminal"]]]},
    {"id": "game", "icon": "🎮", "label": "Game", "use": "💻 coding", "robot": "play", "ship": [],
     "words": ["game", "tetris", "mario", "pidima", "level", "platformer", "puzzle", "arcade", "snake", "pong", "player", "score"],
     "guide": "A game: a start button the robot can find (Start / Play), keyboard keys on desktop, touch buttons on a phone that fit "
              "on one screen with the play area. The robot presses start and some keys — the screen must move.",
     "questions": [["Controls?", ["Keys + touch buttons ⭐", "Touch only", "Keys only"]],
                   ["How hard?", ["Easy start, gets harder ⭐", "Hard from the start", "Relaxed, no losing"]]]},
    {"id": "text", "icon": "📝", "label": "Text", "use": "💬 general", "robot": "none", "ship": [],
     "words": ["write", "essay", "letter", "story", "article", "post", "email", "readme", "notes", "summary", "poem",
               "words", "description", "manual", "guide"],
     "guide": "Writing, not code: put it in a .md file in docs/ (one file unless told otherwise). Short paragraphs, plain words. "
              "No page test runs — Scott reads it beside the old version.",
     "questions": [["How long?", ["Short — one screen ⭐", "Medium — a page or two", "Long and full"]],
                   ["Tone?", ["Plain and direct ⭐", "Warm and friendly", "Formal"]]]},
    {"id": "edit", "icon": "🔧", "label": "Edit existing", "use": "🧠 hardest work", "robot": "page", "ship": [],
     "words": ["hermes", "iris", "ailab", "the lab", "fix", "change the", "edit the", "existing", "my app", "repo", "bug", "broken"],
     "guide": "Changing something that already exists: find the real code first (repo find / read), change one spot at a time, "
              "match the code around it, check each changed file. Changes to linked code go to Scott as a proposal — never applied by you.",
     "questions": []},
    {"id": "image", "icon": "🖼", "label": "Image", "use": "💬 general", "robot": "none", "ship": [], "art": True,
     "handoff": {"path": "/models", "name": "Image Studio", "file": "image_brief.md", "label": "🖌 Edit it in Image Studio"},
     "words": ["image", "picture", "photo", "drawing", "art", "artwork", "painting", "logo", "icon", "poster", "wallpaper", "illustration"],
     "guide": "A picture. On its own the 🖼 chip runs a picture run (Hermes image_make). Together with a page or app: "
              "in connected mode make each picture with hermes image_make {\"prompt\",\"aspect_ratio\"} → job_wait {\"key\"} "
              "(the Lab saves it); otherwise draw it with SVG or CSS shapes.",
     "questions": [["Style?", ["Painted / illustrated ⭐", "Photo-real", "Flat and simple"]],
                   ["Shape?", ["Square ⭐", "Wide (screen)", "Tall (phone)"]]]},
    {"id": "video", "icon": "🎬", "label": "Video", "use": "💬 general", "robot": "none", "ship": [], "art": True,
     "handoff": {"path": "/media", "name": "Media Studio", "file": "video_brief.md"},
     "words": ["video", "clip", "film", "movie", "animation", "reel", "youtube", "tiktok", "footage", "edit my video"],
     "guide": "A video. On its own (or with 🖼) the 🎬 chip runs a video run: Hermes video_make (Venice, uncensored Wan 2.7), "
              "price shown first. Together with a page or app: write video_brief.md (length, one line per shot with seconds, "
              "music feel) and Scott makes the clip with a 🎬 run.",
     "questions": [["Length?", ["Under 30 seconds ⭐", "About a minute", "Longer"]],
                   ["Shape?", ["Tall (phone) ⭐", "Wide (screen)", "Square"]]]},
]
CAPTURE = {"id": "capture", "icon": "🎥", "label": "Capture", "use": "💬 general", "robot": "none", "ship": [],
           "words": ["screenshot", "screenshots", "screen shot", "screen shots", "capture", "walk-through", "walkthrough",
                     "screen recording", "record the screen", "demo clip", "portfolio shot", "portfolio shots", "phone shots"],
           "guide": "Screenshots and clips of Scott's apps (Lab capture C2): the Lab plans the shots, captures the test phone, "
                    "its own browser or the test VM through Hermes capture tools, checks each with 👁 Eyes and saves them in "
                    "captures/. His real desktop only after his ✋ in Hermes.",
           "questions": []}
TYPES.append(CAPTURE)
KEYS = ("id", "icon", "label", "use", "robot", "ship", "words", "guide", "questions", "art", "handoff")
ROBOT_ORDER = {"play": 3, "page": 2, "none": 1}


def _extra() -> list[dict]:
    try:
        f = config.home() / "creation_types.json"
        d = json.loads(f.read_text()) if f.is_file() else []
        return [x for x in (d if isinstance(d, list) else d.get("types", [])) if isinstance(x, dict) and x.get("id")]
    except Exception:                                             # noqa: BLE001 — a bad file never breaks the Lab
        return []


def all_types() -> list[dict]:
    out = {t["id"]: dict(t) for t in TYPES}
    for x in _extra():
        if x.get("off"):
            out.pop(x["id"], None)
        else:
            out[x["id"]] = {**out.get(x["id"], {"icon": "🧩", "label": x["id"], "use": "💻 coding", "robot": "page", "ship": [],
                                                  "words": [], "guide": "", "questions": []}),
                            **{k: v for k, v in x.items() if k in KEYS}}
    return list(out.values())


def public() -> list[dict]:
    """What the page needs (the chips + guessing words + model hints)."""
    return [{k: t.get(k) for k in ("id", "icon", "label", "use", "words", "ship", "art", "handoff", "robot")} for t in all_types()]


def pick(ids) -> list[dict]:
    by = {t["id"]: t for t in all_types()}
    seen, out = set(), []
    for i in ids or []:
        i = str(i)
        if i in by and i not in seen:
            seen.add(i)
            out.append(by[i])
    return out[:6]


def guess(text: str) -> list[str]:
    """The ⭐ guess: types whose words show up in the task, best match first (max 3). Same rule as the page's guess."""
    t = " " + re.sub(r"\s+", " ", (text or "").lower()) + " "
    scored = []
    for n, ty in enumerate(all_types()):
        hits = sum(1 for w in ty.get("words", []) if re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", t))
        if hits:
            scored.append((-hits, n, ty["id"]))
    return [i for _, _, i in sorted(scored)[:3]]


PAGE_TYPES = ("website", "android", "windows", "linux", "game", "edit")


def picture_mode(ids) -> bool:
    """🖼 on, nothing page/app-like or video on → a picture run (no agent steps, no page test)."""
    ids = [t["id"] for t in pick(ids)]
    return "image" in ids and not any(t in ids for t in PAGE_TYPES + ("video",))


ART_ONLY = ("image", "video", "text")


def art_route(idea: str, ids) -> list[str]:
    """2026-11-24 live (Scott: "the model … is not the right one … I need something more neutral and uncensored"): an
    art idea with NO chip picked — often a 🧱 build prompt — went to the step-by-step coding agent, which refused,
    "toned it down" and hand-drew an SVG. With no chip on and every ⭐ guess an art type, route it to the art run
    (🎬 video → 🖼 picture → 📝 writing), where the uncensored writer + Lustify / Wan do the work. Chips Scott picked
    always win; anything app-like in the guess leaves the run as it was."""
    picked = [t["id"] for t in pick(ids)]
    if picked:
        return picked
    g = guess(idea)
    if not g or any(t not in ART_ONLY for t in g):
        return picked
    return ["video"] if "video" in g else ["image"] if "image" in g else ["text"]


def video_mode(ids) -> bool:
    """🎬 on (🖼 may be on too), nothing page/app-like → a video run (video.py)."""
    ids = [t["id"] for t in pick(ids)]
    return "video" in ids and not any(t in ids for t in PAGE_TYPES)


def capture_mode(ids) -> bool:
    """🎥 on → a capture run (capturerun.py). It wins over 🎬/🖼/📝: "a clip of my app" is a recording, not a made video."""
    return "capture" in [t["id"] for t in pick(ids)]


def doc_mode(ids) -> bool:
    """📝 on, nothing page/app-like, video or picture → a document run (docrun.py; it asks about pictures itself)."""
    ids = [t["id"] for t in pick(ids)]
    return "text" in ids and not any(t in ids for t in PAGE_TYPES + ("video", "image"))


def robot_mode(ids) -> str:
    """The strongest test any picked type asks for. No types = "play" (the Lab's test before chips existed)."""
    ts = pick(ids)
    if not ts:
        return "play"
    return max((t.get("robot", "page") for t in ts), key=lambda r: ROBOT_ORDER.get(r, 2))


def ship_targets(ids) -> list[str]:
    out: list[str] = []
    for t in pick(ids):
        out += [p for p in t.get("ship", []) if p not in out]
    return out


def handoffs(ids) -> list[dict]:
    return [dict(t["handoff"], icon=t["icon"], type=t["id"]) for t in pick(ids) if t.get("handoff")]


def brief(ids, ask_first: bool = False) -> str:
    """Lines for the agent's system prompt: what Scott is making, how each type is built, and the questions worth asking."""
    ts = pick(ids)
    if not ts:
        return ""
    lines = ["", "Scott picked what he is making: " + " + ".join(f"{t['icon']} {t['label']}" for t in ts) + "."]
    lines += [f"- {t['icon']} {t['guide']}" for t in ts if t.get("guide")]
    if len(ts) > 1:
        lines.append("Make them work together (e.g. a website + its pictures).")
    qs = [q for t in ts for q in t.get("questions", [])][:3]
    if ask_first and qs:
        lines.append("Questions worth asking for this kind of creation (choices, ⭐ = usual pick) — skip any his memory "
                     "already answers, and add your own if the task leaves something bigger open:")
        lines += [f"  · {q} " + " / ".join(c) for q, c in qs]
    return "\n".join(lines)
