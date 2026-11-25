"""🏃 Motion Presets M5 — make it (Scott 2026-11-25). One Lab run kind ("motion") over the project's timeline
(<project>/.shelf/motion_scene.json):
  🖼 picture — one still per block: its ⭐ key moment (or the one he picked), the people in it named, everyone else "in
     the background", the 🎭 cast anchors of who is in it as references (faces hold), and the moment's pose skeleton
     guiding a local SDXL picture when Hermes has the pose model — otherwise words only, and the run says so.
  🎬 video — the timeline cut into clips no longer than the model allows (local Wan 5 s; Venice up to 10 s); the first
     clip starts from a picture (picture-first path), every next clip starts from the LAST FRAME of the one before;
     after N links a fresh still is made from the cast references so faces don't drift; clips stitched with ffmpeg.
     Venice: one price card for every clip before ▶ (the $5/day video cap holds). 🆓 pan-and-zoom never spends.
His idea words lead every prompt exactly as typed; the motion words follow."""
from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path

from . import motions as MO, timeline as TL

MAKES = {"picture": "🖼 Pictures (one per motion)", "video": "🎬 Video (chained clips)"}
CLIPS = {"local": "🏠 AI motion on this computer ($0, slow)", "venice": "🔓 Venice AI motion (price first)",
         "free": "🆓 Pan-and-zoom ($0, no AI motion)"}
LOCAL_MAX_S, VENICE_MAX_S = 5, 10
DRIFT_LINKS = 3                 # fresh still from the cast every N chained clips (config motion.drift_links)


def norm(raw) -> dict | None:
    r = raw if isinstance(raw, dict) else {}
    make = r.get("make") if r.get("make") in MAKES else ""
    if not make:
        return None
    return {"make": make, "clips": r.get("clips") if r.get("clips") in CLIPS else "local",
            "shape": r.get("shape") if r.get("shape") in ("Tall (phone)", "Wide (screen)", "Square") else "Tall (phone)"}


def presets_for(scene: dict) -> dict[str, dict]:
    out = {}
    for b in scene["blocks"]:
        p = MO.get(b["preset"])
        if p:
            out[p["id"]] = p
    return out


def anchors(cast: dict[str, dict], names: list[str]) -> list[str]:
    out = []
    for n in names:
        c = cast.get(str(n).lower())
        if c and c.get("anchor_path") and Path(c["anchor_path"]).is_file() and c["anchor_path"] not in out:
            out.append(c["anchor_path"])
    return out[:4]


def pose_abs(p: dict, rel: str) -> str:
    f = MO.asset(p["id"], rel) if rel else None
    return str(f) if f else ""


def last_frame(clip: Path, out: Path) -> bool:
    ff = shutil.which("ffmpeg")
    if not ff:
        return False
    try:
        subprocess.run([ff, "-y", "-loglevel", "error", "-sseof", "-0.2", "-i", str(clip), "-frames:v", "1", "-q:v", "2", str(out)],
                       capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.is_file() and out.stat().st_size > 500


def drift_links(cfg: dict | None) -> int:
    try:
        return max(1, int(((cfg or {}).get("motion") or {}).get("drift_links") or DRIFT_LINKS))
    except (TypeError, ValueError):
        return DRIFT_LINKS


def plan(scene: dict, make: str, clips_mode: str, cfg: dict | None = None) -> dict:
    """What a run would make — for the price card and the tests. Spends nothing."""
    P = presets_for(scene)
    if make == "picture":
        st = TL.stills(scene, P)
        return {"make": make, "items": st, "n": len(st), "warn": TL.too_busy(scene, cfg)}
    max_s = LOCAL_MAX_S if clips_mode == "local" else VENICE_MAX_S
    cl = TL.clips(scene, P, max_s, cfg)
    links = drift_links(cfg)
    for i, c in enumerate(cl):
        c["start"] = "picture" if i == 0 or i % links == 0 else "last frame"
    return {"make": make, "items": cl, "n": len(cl), "max_s": max_s, "warn": TL.too_busy(scene, cfg),
            "seconds": round(sum(c["t1"] - c["t0"] for c in cl), 1)}


def _still(run, words: str, who: list[str], cast: dict, pose: str, shape: str, label: str) -> dict | None:
    """One picture via the normal picture run (references + pose ride on run.batch). → the picture dict or None."""
    from . import picture
    b = run.batch
    b["refs_abs"] = anchors(cast, who)
    b["pose_abs"] = pose
    base = run.task
    try:
        run.task = f"{words}\nShape: {shape}"
        run.state, run.why = "running", ""
        before = len(run.pictures)
        try:
            picture.run(run)
        except Exception as e:                                   # noqa: BLE001
            if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
                raise
        return run.pictures[-1] if len(run.pictures) > before else None
    finally:
        run.task = base
        b.pop("refs_abs", None)
        b.pop("pose_abs", None)


def _idea(run) -> str:
    from . import picture
    return picture.own_words(picture.picture_words(run.task)).strip()


def run(run) -> None:
    from . import makers, picture, story, video
    b = run.batch
    mk = b["motion"]
    root = Path(run.root)
    scene = TL.load(root)
    P = presets_for(scene)
    if not scene["blocks"] or not P:
        run.state, run.why = "failed", "🏃 The timeline is empty — tap a motion under the idea box first."
        return
    if not run.connected:
        run.state, run.why = "failed", "🔌 Pictures and clips are Hermes's — switch the Lab to connected mode."
        return
    run._picture_answer = ""
    cast = story.load_cast(run)
    idea = _idea(run)
    pl = plan(scene, mk["make"], mk["clips"], run.cfg)
    b["plan"] = {"n": pl["n"], "make": pl["make"]}
    if pl["warn"]:
        run._record({"action": "route", "why": f"⚠️ {pl['warn'][0][1]} separate actions at {pl['warn'][0][0]:g} s — video models get "
                     "shaky past ~3; the timeline offers ✂️ Split into shots.", "result": {"warn": pl["warn"]}, "usd": 0.0})
    for p in P.values():
        MO.used(p["id"])
    if mk["make"] == "picture":
        for i, s in enumerate(pl["items"]):
            run._check_stop()
            b["now"] = i
            p = P.get(s["preset"]) or {}
            pose = pose_abs(p, s.get("pose", ""))
            words = (f"{idea}. " if idea else "") + s["words"] + (f". Camera: {s['camera']}" if s["camera"] not in ("", "still") else "")
            pic = _still(run, words, s["who"], cast, pose, mk["shape"], s["name"])
            b["items"].append({"path": (pic or {}).get("path", ""), "k": i, "kind": "picture", "usd": (pic or {}).get("usd", 0),
                               "variation": f"🏃 {s['name']} · {s['moment']}" + ("" if pic else " ❌")})
            run.save()
        made = sum(1 for x in b["items"] if x.get("path"))
        run.state, run.why = ("done" if made else "failed"), f"🏃 {made} of {pl['n']} pictures made."
        return
    # ---- 🎬 video: chained clips
    mode = mk["clips"]
    model = ""
    if mode == "local":
        model = next((p.get("model", "") for p in video.all_paths() if p["kind"] == "local" and p["on"]), "")
        if not model:
            run._record({"action": "route", "why": "🏠 no local video path is switched on — 🆓 pan-and-zoom instead", "result": {}, "usd": 0.0})
            mode = "free"
    aspect = video._aspect(mk["shape"])
    if mode == "venice":
        try:
            q = run.lab.mcp.call("video_quote", {"duration": "5s", "resolution": str(run.cfg.get("video_resolution") or "720p")})
            each, today, cap = float(q.get("usd") or 0), float(q.get("today_usd") or 0), float(q.get("daily_cap") or 5)
        except Exception as e:                                   # noqa: BLE001
            if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
                raise
            each, today, cap, mode = 0.0, 0.0, 5.0, "free"
        if mode == "venice":
            tot = sum(each * max(1.0, c["secs"] / 5) for c in pl["items"])
            over = today + tot > cap
            ch = ([] if over else [f"▶ Make {pl['n']} clips (≈ ${tot:.2f})"]) + ["🆓 Pan-and-zoom instead ($0)", "✋ Don't make it"]
            ans = makers.ask(run, "motion-price", [{"q": f"{pl['n']} Venice clips, {pl['seconds']:g} s in all ≈ ${tot:.2f}. "
                                                        f"Video spend today ${today:.2f} of ${cap:.2f}." + (" Over the cap." if over else ""),
                                                   "choices": ch, "best": 0, "why": "price first"}], always=True)
            ans = next(iter(ans.values()), "")
            if ans.startswith("✋"):
                run.state, run.why = "done", "🏃 Not made — nothing spent."
                return
            mode = "venice" if ans.startswith("▶") else "free"
            if mode == "venice":
                run.cap_usd = max(run.cap_usd, run.usd + tot + 0.05)
    work = root / "videos" / "motion" / f"run-{run.id}"
    work.mkdir(parents=True, exist_ok=True)
    pieces, start_pic, link = [], None, 0
    for i, c in enumerate(pl["items"]):
        run._check_stop()
        b["now"] = i
        words = (f"{idea}. " if idea else "") + c["words"]
        if start_pic is None or c["start"] == "picture":
            first = next((P[x["preset"]] for x in TL.resolve(scene) if x["id"] in c["blocks"]), None)
            mom = next((m for m in (first or {}).get("moments", []) if m.get("pose")), {}) if first else {}
            pic = _still(run, words, c["who"], cast, pose_abs(first, mom.get("pose", "")) if first else "", mk["shape"], f"clip {i + 1}")
            if not pic:
                run._record({"action": "route", "why": f"🖼 clip {i + 1}: the starting picture didn't come back — stopping here", "result": {}, "usd": 0.0})
                break
            start_pic, link = root / pic["path"], 0
            if i:
                run._record({"action": "route", "why": f"🎭 fresh start picture for clip {i + 1} (every {drift_links(run.cfg)} links) so faces don't drift",
                             "result": {}, "usd": 0.0})
        rel = ""
        if mode in ("local", "venice"):
            shot = {"k": i, "action": words + (f". Camera: {c['camera']}" if c["camera"] else ""), "camera": c["camera"] or "steady"}
            rel, _ = story._clip_ai(run, start_pic, shot, model if mode == "local" else "", aspect)
            if not rel:
                run._record({"action": "route", "why": f"🎞 clip {i + 1}: AI motion didn't come back — 🆓 pan-and-zoom for this one", "result": {}, "usd": 0.0})
        if not rel:
            rel = picture.claim(root, f"videos/motion/run-{run.id}/clip-{i + 1:02d}-panzoom.mp4")
            why = video.pan_zoom(start_pic, root / rel, c["secs"], aspect)
            if why:
                run._record({"action": "route", "why": f"🎞 clip {i + 1}: {why}", "result": {}, "usd": 0.0})
                continue
        seg = work / f"seg-{i + 1:02d}.mp4"
        err = story.segment(root / rel, None, c["secs"], aspect, seg)
        if err:
            run._record({"action": "route", "why": f"🎞 clip {i + 1}: {err}", "result": {}, "usd": 0.0})
            continue
        pieces.append(seg)
        b["items"].append({"path": rel, "k": i, "kind": "video", "variation": f"🏃 clip {i + 1} · {c['t0']:g}–{c['t1']:g} s"})
        nxt = work / f"last-{i + 1:02d}.jpg"
        link += 1
        if mode != "free" and last_frame(root / rel, nxt):
            start_pic = nxt                                      # ⛓ the next clip starts where this one ended
        run.save()
    if not pieces:
        run.state, run.why = "failed", "🏃 No clip came back — nothing to join. 👉 Try 🆓 pan-and-zoom, or check the video paths in ⚙️ Settings."
        return
    film = picture.claim(root, f"videos/motion/motion-{makers.stamp()}.mp4")
    err = story.join(pieces, root / film)
    if err:
        run.state, run.why = "failed", f"🏃 The clips were made but joining them failed: {err}"
        return
    run.videos.append({"path": film, "usd": round(run.usd, 4), "model": model or mode})
    run.state, run.why = "done", f"🏃 {len(pieces)} clip{'s' if len(pieces) > 1 else ''} joined into {film} (${run.usd:.2f})."
