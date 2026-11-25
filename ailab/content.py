"""🎭 Art / code split (2026-11-24, Scott: art in game and software forms, as free as his pictures).

Filtered coding models refuse or water down a task that carries his art. So, before a 🎮 game / 🌐 website /
📱🪟🐧 app run starts, an uncensored writer (Venice first) reads his exact words and splits them:
- the ART: story, dialogue, on-screen words, character and scene descriptions → content/ files, written in full;
- the PICTURES the build needs (characters, backgrounds, items, icons) → made with Lustify (safe mode off, no text on
  them) into assets/; game sprites are drawn on plain magenta (#FF00FF) so the game can key it out to transparent;
- a plain BUILD BRIEF: what software to make (screens, controls, rules) with the art referred to only by file name.
The coding model gets only the build brief + the file list — it never sees, rewrites or judges the art.
Skipped for build prompts with modules, 🔧 Edit existing, standalone mode, or cfg art_split false. Shown on screen.
"""
from __future__ import annotations

import json
import re

from . import creation, makers, picture

SPLIT_TYPES = ("game", "website", "android", "windows", "linux")
MAX_PICS = 6
SPLIT_SYS = ("You prepare Scott's idea for a software build. " + makers.KEEP_WORDS + " Split his idea into three parts and "
             "reply with ONE JSON object only (no markdown fence, no talk):\n"
             '{"build": "...", "content": {"content/<name>.md or .json": "full text"}, '
             '"pictures": [{"file": "assets/<name>", "prompt": "...", "shape": "square|wide|tall", "sprite": true}]}\n'
             "- build: a plain technical brief for a programmer — what to make (screens, controls, rules, layout, how text "
             "and pictures are used), naming content and picture files by path only. It must NOT describe or retell the "
             "story, characters' looks or any adult or mature content; refer to files instead.\n"
             "- content: every word the software shows (story, dialogue, levels' text, labels' wording, descriptions), "
             "written in full in his words and style. Use .json for lists the code loads (e.g. dialogue lines), .md for prose.\n"
             f"- pictures: up to {MAX_PICS} the build truly needs. prompt = his words for that thing + visual detail, never "
             "text in the picture. sprite true for characters/items that move over a background (they get a plain magenta "
             "#FF00FF background), false for backgrounds, scenes and icons.")
CODER_RULES = ("ART RULES (Scott's): the files in content/ and assets/ were made for this build. Use them exactly as they "
               "are — load or show them, never rewrite, shorten, summarise, censor or describe what's in them, and never "
               "replace them with placeholder art. Sprites in assets/ marked (sprite) sit on plain magenta #FF00FF: key "
               "that colour out to transparent when you load them (draw to an offscreen canvas and clear pixels near "
               "#FF00FF). Pictures go in as <img>/canvas images — never redraw them with SVG or CSS shapes.")
SHAPE_AR = {"square": "1:1", "wide": "16:9", "tall": "9:16"}


def wanted(run) -> bool:
    ids = list(getattr(run, "ctypes", []) or [])
    return (run.connected and run.cfg.get("art_split", True) is not False and not getattr(run, "prompt_plan", False)
            and not getattr(run, "is_lane", False) and "edit" not in ids and any(t in ids for t in SPLIT_TYPES)
            and not getattr(run, "split", None))


def parse(text: str) -> dict | None:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    m = re.search(r"\{.*\}", t, re.S)
    try:
        d = json.loads(m.group(0) if m else t)
    except (ValueError, AttributeError):
        return None
    if not isinstance(d, dict) or not str(d.get("build") or "").strip():
        return None
    files = {}
    for k, v in (d.get("content") or {}).items() if isinstance(d.get("content"), dict) else []:
        name = re.sub(r"[^A-Za-z0-9._/-]", "-", str(k)).lstrip("/")
        if not name.startswith("content/"):
            name = "content/" + name.split("/")[-1]
        if ".." in name or not re.search(r"\.(md|json|txt)$", name):
            continue
        files[name] = v if isinstance(v, str) else json.dumps(v, indent=2, ensure_ascii=False)
    pics = []
    for x in (d.get("pictures") or [])[:MAX_PICS] if isinstance(d.get("pictures"), list) else []:
        if isinstance(x, dict) and str(x.get("prompt") or "").strip():
            stem = makers.slug(re.sub(r"\.(png|jpe?g|webp)$", "", str(x.get("file") or "").split("/")[-1]), 30, f"art-{len(pics) + 1}")
            pics.append({"stem": stem, "prompt": str(x["prompt"]).strip()[:1200], "sprite": bool(x.get("sprite")),
                         "aspect": SHAPE_AR.get(str(x.get("shape") or "").lower(), "1:1")})
    return {"build": str(d["build"]).strip()[:3500], "files": files, "pictures": pics}


def prepare(run) -> None:
    """Runs once before the agent's first step. Changes run.task to the plain build brief + file list when it works;
    leaves the task alone (and says so) when no writer helps."""
    if not wanted(run):
        return
    words = run.task
    kinds = " + ".join(f"{t['icon']} {t['label']}" for t in creation.pick(run.ctypes))
    run.cap_usd = max(run.cap_usd, run.usd + 0.25 + 0.012 * MAX_PICS)
    text, who = makers.write(run, SPLIT_SYS, f"He is making: {kinds}\n\nHis idea, exactly:\n{words}", 4000,
                             "🎭 Splitting your art from the code", "lab-split")
    d = parse(text) if text else None
    if not d:
        run.split = {"ok": False, "why": who if not text else "the writer's answer wasn't readable"}
        run._record({"action": "split", "why": "🎭 art/code split skipped — the coder gets your words as typed",
                     "result": run.split, "usd": 0.0})
        return
    for rel, body in d["files"].items():
        p = run.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body.rstrip() + "\n")
        run.docs = (getattr(run, "docs", None) or []) + [{"path": rel, "kind": "doc", "writer": who}]
        run._record({"action": "art", "path": rel, "why": f"🎭 your art, written by {makers.short(who)}",
                     "result": {"bytes": len(body)}, "usd": 0.0})
    made = []
    for n, pic in enumerate(d["pictures"], 1):
        run._check_stop()
        prompt = pic["prompt"] + (", full body, centered, isolated on a plain flat solid magenta #FF00FF background, "
                                  "no shadow on the background" if pic["sprite"] else "")
        r = makers.make_picture(run, prompt, pic["aspect"], f"assets/{pic['stem']}", f"art {n} of {len(d['pictures'])}")
        if r.get("error"):
            run._record({"action": "picture", "why": f"🎨 art {n}", "result": {"error": r["error"]}, "usd": 0.0})
            continue
        made.append((r["path"], pic["sprite"]))
    listing = [f"- {rel}" for rel in d["files"]] + [f"- {p}" + (" (sprite)" if s else "") for p, s in made]
    run.split = {"ok": True, "writer": who, "files": list(d["files"]), "pictures": [p for p, _ in made]}
    run.task_words = words
    run.task = (d["build"] + "\n\nFiles already made for this build (use them as they are):\n" + "\n".join(listing)
                + "\n\n" + CODER_RULES)[:4000]
    run._record({"action": "split", "why": f"🎭 art split from the code: {len(d['files'])} text file(s), {len(made)} picture(s) "
                 f"by {makers.short(who)}; the coder gets a plain brief", "result": {**run.split, "brief": d["build"][:600]}, "usd": 0.0})
    picture.stage(run, "🔨", "Art ready — building the software")
