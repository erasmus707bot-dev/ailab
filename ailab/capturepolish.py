"""✨ Polish a 🎥 capture from its result card (Lab capture C3.3, 2026-11-25).

  polish(app, {project, path, frame, zoom, rings, title}) → Hermes capture_edit → the edited copy + ↔️ Before | After
      land in the project under captures/polished/ (visible in the card at once)
  drop(app, {project, path}) → ✕ Not this: removes that copy (and its Before | After) from the project

The original capture is never touched. Hermes keeps its own copy, labelled "✂️ edited by the Lab", in the library.
$0: the render runs on gandalf through Creator Kit.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from . import preview, store
from .mcp_client import HermesRefused
from .transport import HttpError

WAIT_S = 600
FRAMES = ("9:16", "1:1", "4:5", "16:9", "none")


def _err(msg: str, fix: str = "", code: str = "failed", status: int = 400) -> tuple[int, dict]:
    return status, {"ok": False, "code": code, "icon": "✨", "message": msg, "fix": fix}


def _site(app, b: dict) -> Path:
    proj = store.project(app._pid(b.get("project")))
    return preview.ensure_site(proj["id"]).resolve()


def _inside(site: Path, rel: str) -> Path | None:
    p = (site / str(rel or "")).resolve()
    return p if site in p.parents and p.is_file() else None


def _hermes_path(site: Path, b: dict) -> str:
    """The capture's own file in ~/hermes-data/captures (the card carries it as `hermes`)."""
    h = str(b.get("hermes") or "")
    return h if "/captures/" in h else ""


def polish(app, b: dict) -> tuple[int, dict]:
    if app.cfg.get("mode") != "connected" or not getattr(app.lab, "mcp", None):
        return _err("✨ Polish runs through Hermes.", "Switch the Lab to connected mode.", "not_connected")
    site = _site(app, b)
    src = _hermes_path(site, b)
    if not src:
        return _err("This isn't a 🎥 capture, so there's nothing to polish.", "Polish works on 🎥 Capture results.",
                    "bad_args")
    frame = str(b.get("frame") or "9:16")
    if frame not in FRAMES:
        return _err(f"Shape must be one of {', '.join(FRAMES)}.", "Pick a shape.", "bad_args")
    args = {"capture": src, "frame": frame, "zoom": bool(b.get("zoom")), "rings": bool(b.get("rings")),
            "title": " ".join(str(b.get("title") or "").split())[:60]}
    try:
        start = app.lab.mcp.call("capture_edit", args)
        end, res, drops = time.monotonic() + WAIT_S, {}, 0
        while time.monotonic() < end:
            try:
                res = app.lab.mcp.call("job_wait", {"key": start["key"], "max_s": 20})
            except HttpError:                                   # the job keeps running in Hermes — ask again
                drops += 1
                if drops > 3:
                    raise
                time.sleep(2)
                continue
            if res.get("finished") or res.get("state") in ("done", "failed", "cancelled"):
                break
    except HermesRefused as e:
        return _err(e.message, e.fix or "", e.code or "refused")
    except HttpError as e:
        return _err(f"Hermes didn't answer: {e.body}", "Check hermes-mcp is running, then try again.", "no_hermes", 502)
    if res.get("state") != "done":
        er = res.get("error") or {}
        return _err(er.get("message") or "The polish didn't finish.", er.get("fix") or "Try again, or open it in Quick Cut.")
    r = res.get("result") or {}
    out = Path(str(r.get("path") or ""))
    if not out.is_file():
        return _err("The polished file wasn't found.", "Try again.")
    dest_dir = site / "captures" / "polished"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / out.name
    shutil.copy2(out, dest)
    item = {"path": str(dest.relative_to(site)), "kind": r.get("kind") or ("clip" if out.suffix == ".mp4" else "shot"),
            "hermes": str(out), "library": r.get("library", ""), "notes": r.get("notes") or [], "recipe": args}
    ba = Path(str(r.get("before_after") or ""))
    if ba.is_file():
        shutil.copy2(ba, dest_dir / ba.name)
        item["before_after"] = str((dest_dir / ba.name).relative_to(site))
    th = Path(str(r.get("thumb") or ""))
    if th.is_file():
        shutil.copy2(th, dest_dir / th.name)
        item["poster"] = str((dest_dir / th.name).relative_to(site))
    return 200, {"ok": True, "item": item}


def drop(app, b: dict) -> tuple[int, dict]:
    """✕ Not this — only files under captures/polished/ can go."""
    site = _site(app, b)
    p = _inside(site, str(b.get("path") or ""))
    if not p or (site / "captures" / "polished") not in p.parents:
        return _err("Only a polished copy can be removed here.", "", "bad_args")
    for q in (p, p.with_suffix(".ba.jpg"), p.with_suffix(".thumb.jpg")):
        q.unlink(missing_ok=True)
    return 200, {"ok": True}
