"""🎬 Video runs (2026-11-24, Scott: "the same kind of work … so I may make my art in video"; video cap separate, $5/day).

A run whose chips are 🎬 Video (optionally + 🖼 Image), with nothing app-like on, skips the step-by-step agent:
❓ length · shape · start from → ✍️ an uncensored writer adds motion detail AFTER Scott's exact words → 💲 Hermes
video_quote (free) → a card shows the price and today's video spend → ▶ Make it → Hermes video_make (Venice, the
🔓 Wan 2.7 enhanced models) → job_wait → the .mp4 lands in this project's videos/ folder and in Media Studio.
Start from: words only · a new picture first (Lustify, then brought to life) · the newest picture in this project.
🆓 Free choice on the price card: a slow pan-and-zoom across a picture made with ffmpeg on gandalf — no AI motion,
no cost, no content rules. Pictures are never given text, captions or watermarks.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
from pathlib import Path

from . import config, makers, picture
from .mcp_client import HermesRefused

VIDEO_SYS = ("You help write prompts for a text-to-video model. " + makers.KEEP_WORDS + " Reply ONLY with extra detail to "
             "put after his words: how things move, camera movement (slow push-in, pan, orbit, handheld), pacing, light, "
             "setting, sound feel — 20–60 words, plain description, no lists, no quotes, no extra talk. Match his choices. "
             "Never ask for text, captions, subtitles, titles, logos or watermarks on screen.")
MOTION_SYS = ("You help write prompts for an image-to-video model that brings Scott's picture to life. " + makers.KEEP_WORDS +
              " Reply ONLY with extra detail to put after his words describing MOTION, not what the picture shows: who or "
              "what moves and how, camera movement, pace — 15–45 words, plain description, no lists, no extra talk. "
              "Never ask for text, captions or watermarks.")
NO_TEXT_VIDEO = "text, words, letters, captions, subtitles, titles, watermark, logo, signature, frame, border"
QUESTIONS = [["Length?", ["5 seconds ⭐", "8 seconds", "10 seconds"]],
             ["Shape?", ["Tall (phone) ⭐", "Wide (screen)", "Square"]]]

# 🛤 Video paths (2026-11-24, Scott: "make [picture first] default but plan for other paths to be built in … so as future
# methods are found they can be added as a switch/toggle"). Each path = one way to get a video. Switch them on/off and
# pick the ⭐ default in ⚙️ Settings → 🎬 Video paths (saved in <lab home>/video_paths.json). The "Start from?" card lists
# the paths that are on. A new MODEL for an existing kind is a JSON entry only, e.g.
#   {"id": "kling-words", "label": "Kling v4 from my words", "kind": "words", "model": "kling-v4-text-to-video", "on": true}
# A new METHOD (local ComfyUI video, another service…) = one new handler in KINDS below + its entry.
KINDS = {
    "picture_first": "Lustify draws the first frame, then a 🔓 image-to-video model adds motion",
    "words": "a 🔓 text-to-video model makes it from your words alone",
    "newest": "your newest picture in this project is brought to life",
    "free": "🆓 slow pan-and-zoom of your newest picture, made on this computer (ffmpeg) — no AI motion, $0",
}
DEFAULT_PATHS = [
    {"id": "picture_first", "label": "Make a picture first, then bring it to life", "kind": "picture_first", "on": True, "star": True,
     "why": "Lustify is proven uncensored for the first frame; the video model only adds motion"},
    {"id": "words", "label": "Just my words", "kind": "words", "on": True},
    {"id": "newest", "label": "My newest picture in this project", "kind": "newest", "on": True},
    {"id": "free", "label": "🆓 Free moving picture of my newest picture (no AI)", "kind": "free", "on": True},
]
PATH_KEYS = ("id", "label", "kind", "on", "star", "model", "why")


def _paths_file() -> Path:
    return config.home() / "video_paths.json"


def all_paths() -> list[dict]:
    """Built-in paths + video_paths.json (same id → its fields replace; new id with a known kind → added). Exactly one ⭐."""
    out = {p["id"]: dict(p) for p in DEFAULT_PATHS}
    order = [p["id"] for p in DEFAULT_PATHS]
    try:
        d = json.loads(_paths_file().read_text()) if _paths_file().is_file() else {}
    except (OSError, ValueError):
        d = {}
    for x in (d.get("paths") if isinstance(d, dict) else d) or []:
        if not isinstance(x, dict) or not re.fullmatch(r"[a-z0-9_-]{2,40}", str(x.get("id") or "")):
            continue
        base = out.get(x["id"], {"on": False})
        row = {**base, **{k: x[k] for k in PATH_KEYS if k in x}}
        if row.get("kind") not in KINDS or not row.get("label"):
            continue
        if x["id"] not in out:
            order.append(x["id"])
        out[x["id"]] = row
    star = (d.get("star") if isinstance(d, dict) else None) or next((i for i in order if out[i].get("star") and out[i].get("on")), "")
    if not out.get(star, {}).get("on"):
        star = next((i for i in order if out[i].get("on")), "")
    rows = [out[i] for i in order]
    for r in rows:
        r["star"] = r["id"] == star
        r["what"] = KINDS[r["kind"]]
    return rows


def set_path(body: dict) -> dict:
    """⚙️ Settings: {"id", "on"} switches a path; {"star": id} makes it the default. Keeps added custom paths."""
    try:
        d = json.loads(_paths_file().read_text()) if _paths_file().is_file() else {}
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {"paths": d}
    rows = [x for x in d.get("paths") or [] if isinstance(x, dict)]
    known = {p["id"] for p in all_paths()}
    if body.get("star"):
        if body["star"] not in known:
            raise ValueError("no such video path")
        d["star"] = body["star"]
        row = next((x for x in rows if x.get("id") == body["star"]), None)
        (row.update(on=True) if row else rows.append({"id": body["star"], "on": True}))
    if "id" in body:
        if body["id"] not in known:
            raise ValueError("no such video path")
        row = next((x for x in rows if x.get("id") == body["id"]), None)
        (row.update(on=bool(body.get("on"))) if row else rows.append({"id": body["id"], "on": bool(body.get("on"))}))
    d["paths"] = rows
    _paths_file().parent.mkdir(parents=True, exist_ok=True)
    tmp = _paths_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    tmp.replace(_paths_file())
    ps = all_paths()
    if not any(p["on"] for p in ps):
        raise ValueError("keep at least one video path on")
    return {"ok": True, "paths": ps}


def path_question(rows: list[dict]) -> list:
    on = [r for r in rows if r["on"]]
    return [["Start from?", [r["label"] + (" ⭐" if r["star"] else "") for r in on]]] if len(on) > 1 else []
SHAPE_AR = {"tall": "9:16", "wide": "16:9", "square": "1:1"}
MAKE, FREE, CANCEL = "▶ Make it", "🆓 Free moving picture instead (pan and zoom, no AI motion)", "✖ Don't make it"
MAX_WAIT_S = 16 * 60


def _secs(choice: str) -> int:
    m = re.search(r"\d+", choice or "")
    return max(3, min(10, int(m.group()))) if m else 5


def _aspect(choice: str) -> str:
    c = (choice or "").lower()
    return next((v for k, v in SHAPE_AR.items() if k in c), "9:16")


def newest_picture(root: Path) -> Path | None:
    pics = [p for p in (root / "pictures").glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")] \
        if (root / "pictures").is_dir() else []
    return max(pics, key=lambda p: p.stat().st_mtime) if pics else None


def _prompt(run, words: str, sys: str, extra: str) -> str:
    mine = picture.own_words(words)
    add, who = makers.write(run, sys, words + extra, 300, "Adding motion detail to your words", "lab-video")
    add = re.sub(r"^\s*(prompt|details?)\s*:\s*", "", add, flags=re.I).strip().strip('"').strip()
    if add.lower().startswith(mine.lower()):
        add = add[len(mine):].lstrip(" ,.;:-").strip()
    text = f"{mine.rstrip('.')}. {add}" if add else mine
    run._record({"action": "prompt", "why": (f"✍️ your words kept exactly + motion from {makers.short(who)}" if add
                                            else "✍️ used your own words (the writer didn't help)"),
                 "result": {"text": text, "yours": mine, "added": add, "writer": who if add else ""}, "usd": 0.0})
    return text[:2500]


def pan_zoom(src: Path, out: Path, secs: int, aspect: str) -> str:
    """🆓 A slow push-in across one picture with ffmpeg. '' = made; otherwise why not."""
    ff = shutil.which("ffmpeg")
    if not ff:
        return "ffmpeg isn't installed on this computer (sudo apt install ffmpeg)"
    w, h = {"9:16": (720, 1280), "16:9": (1280, 720)}.get(aspect, (1080, 1080))
    fr = 30
    vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
          f"zoompan=z='min(zoom+0.0012,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={secs * fr}:s={w}x{h}:fps={fr}")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-i", str(src), "-vf", vf, "-t", str(secs),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                           capture_output=True, text=True, timeout=240)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"ffmpeg failed: {e}"
    return "" if r.returncode == 0 and out.is_file() and out.stat().st_size > 1000 else f"ffmpeg failed: {r.stderr[-200:]}"


def _done(run, vid: dict, note: str) -> None:
    run.videos = (getattr(run, "videos", None) or []) + [vid]
    run._record({"action": "video", "path": vid["path"], "why": "🎬 made the video",
                 "result": {k: v for k, v in vid.items() if k != "prompt"}, "usd": vid.get("usd", 0.0)})
    run.state, run.why = "done", note
    picture.stage(run, "✅", "Done")


def _fail(run, why: str) -> None:
    run._record({"action": "video", "why": "🎬 make the video", "result": {"error": why}, "usd": 0.0})
    run.state, run.why = "failed", f"🎬 {why}"


def _free(run, pic: Path | None, secs: int, aspect: str, words: str) -> None:
    if not pic:
        return _fail(run, "The free moving picture needs a picture — make one first (🖼) or pick \"Make a picture first\".")
    picture.stage(run, "🆓", "Making the free moving picture on this computer (ffmpeg)")
    rel = f"videos/{makers.stamp()}-{makers.slug(words, default='video')}-panzoom.mp4"
    why = pan_zoom(pic, run.root / rel, secs, aspect)
    if why:
        return _fail(run, why)
    _done(run, {"path": rel, "model": "ffmpeg pan-and-zoom", "usd": 0.0, "seconds": secs, "from_picture": str(pic.name)},
          f"🎬 Free moving picture made from {pic.name} ({secs} s, $0). Saved in {rel}.")


def run(run) -> None:
    """The whole video run. Raises Stopped / SpendBlocked like the agent loop (handled by Run.loop)."""
    words = picture.picture_words(run.task)
    rows = all_paths()
    on = [r for r in rows if r["on"]] or rows[:1]
    ch = makers.ask(run, "video", makers.items_from(QUESTIONS + path_question(rows)))
    secs, aspect = _secs(ch.get("length", "")), _aspect(ch.get("shape", ""))
    pick = ch.get("start from", "")
    path = next((r for r in on if r["label"] == pick), None) or next((r for r in on if r["star"]), on[0])
    run.video_path = path["id"]
    run._record({"action": "route", "why": f"🛤 video path: {path['label']}", "result": {"path": path["id"], "kind": path["kind"]}, "usd": 0.0})
    run._check_stop()
    pic: Path | None = None
    if path["kind"] in ("newest", "free"):
        pic = newest_picture(run.root)
        if not pic:
            return _fail(run, "There is no picture in this project yet — make one with 🖼, or use \"Make a picture first\".")
        if path["kind"] == "free":
            return _free(run, pic, secs, aspect, words)
    elif path["kind"] == "picture_first":
        if not run.connected:
            return _fail(run, "🔌 Pictures are made by Hermes — switch the Lab to connected mode.")
        p = picture.write_prompt(run, words + f"\nShape: {ch.get('shape', '')}")
        made = makers.make_picture(run, p, aspect, f"pictures/{makers.stamp()}-{makers.slug(words, default='picture')}",
                                   "the first frame")
        if made.get("error"):
            return _fail(run, f"The first picture failed: {made['error']}")
        pic = run.root / made["path"]
    run._check_stop()
    if not run.connected:                                    # only the free path works without Hermes
        return _free(run, pic, secs, aspect, words)
    prompt = _prompt(run, words, MOTION_SYS if pic else VIDEO_SYS, f"\nLength: {secs} s\nShape: {aspect}")
    args = {"prompt": prompt, "duration": f"{secs}s", "resolution": str(run.cfg.get("video_resolution") or "720p"),
            "negative_prompt": NO_TEXT_VIDEO, "name": picture.own_words(words)[:40], "task": f"lab-video:{run.project['id']}"}
    if path.get("model") or run.cfg.get("video_model"):
        args["model"] = str(path.get("model") or run.cfg["video_model"])
    if pic:
        if pic.stat().st_size > 12_000_000:
            return _fail(run, f"{pic.name} is over 12 MB — too big to send as the first frame.")
        args["image_b64"] = base64.b64encode(pic.read_bytes()).decode()
    else:
        args["aspect_ratio"] = aspect
    picture.stage(run, "💲", "Asking Venice what this clip costs (free)")
    try:
        q = run.lab.mcp.call("video_quote", {k: v for k, v in args.items() if k in ("model", "duration", "aspect_ratio",
                                                                                   "resolution", "image_b64")})
    except HermesRefused as e:
        return _fail(run, f"Couldn't price the clip: {e.message}" + (f" — {e.fix}" if e.fix else ""))
    usd, today, cap = float(q.get("usd") or 0), float(q.get("today_usd") or 0), float(q.get("daily_cap") or 5)
    over = not q.get("fits", True)
    choices = ([] if over else [f"{MAKE} (${usd:.2f})"]) + [FREE, CANCEL]
    head = (f"This {secs}-second clip costs ${usd:.2f} with {makers.short(q.get('model', ''))}. "
            f"Video spend today: ${today:.2f} of ${cap:.2f}." + (" That's over the video cap — the free one still works." if over else ""))
    pick = makers.ask(run, "video-price", [{"q": head, "choices": choices, "best": 0, "why": "price first"}], always=True)
    pick = next(iter(pick.values()), "")
    if pick.startswith(CANCEL[:1]) or "don't" in pick.lower():
        run.state, run.why = "done", "🎬 Not made — nothing spent."
        picture.stage(run, "✅", "Stopped before spending")
        return
    if pick.startswith("🆓"):
        return _free(run, pic, secs, aspect, words)
    run.cap_usd = max(run.cap_usd, run.usd + usd + 0.05)
    picture.stage(run, "🎬", "Asking Hermes to make the video")
    try:
        st = run.lab.mcp.call("video_make", args)
    except HermesRefused as e:
        return _fail(run, f"Hermes couldn't make the video: {e.message}" + (f" — {e.fix}" if e.fix else ""))
    res = makers.wait_job(run, st["key"], "🎬", f"Making the video with {makers.short(st.get('model', ''))}",
                          float(st.get("est_usd") or usd), "1–5 min", MAX_WAIT_S)
    out = res.get("result") or {}
    if res.get("state") != "done" or not out.get("path"):
        return _fail(run, (res.get("error") or {}).get("message") or "no video came back")
    picture.stage(run, "💾", "Saving the video")
    rel = f"videos/{makers.stamp()}-{makers.slug(words, default='video')}.mp4"
    dst = run.root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(out["path"], dst)
    except OSError as e:
        return _fail(run, f"The video was made (Media Studio has it) but couldn't be copied here: {e}")
    usd = float(out.get("usd") or usd)
    run.usd += usd
    _done(run, {"path": rel, "model": out.get("model", ""), "usd": round(usd, 4), "seconds": int(out.get("seconds") or 0),
                "duration": out.get("duration", f"{secs}s"), "media_item": out.get("media_item", ""), "prompt": prompt,
                "from_picture": pic.name if pic else ""},
          f"🎬 Video made with {makers.short(out.get('model', ''))} in {int(out.get('seconds') or 0)} s for ${usd:.2f}. "
          f"Saved in {rel}" + (" and in Media Studio." if out.get("media_item") else "."))
