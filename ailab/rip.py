"""🎞 Video breakdown in the Lab (prompt #1 M4, Scott 2026-11-25). The work is Hermes's (MCP video_breakdown /
breakdown_get / breakdown_list / breakdown_search — local, $0, restart-safe); the Lab shows the sheet and turns a scene
into making: 🎬 Make one like this (the shot recipe → Lab words, person A/B swapped for this project's chosen cast) ·
📌 Use frame as reference (copied into the project, then pinned). Each "make" lands on the project's recipe shelf
(<project>/.shelf/recipes.json) so the improver can draw on it."""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

RECIPE_KEYS = ("subject", "setting", "motion", "framing", "camera", "light")
SHELF_MAX = 40


def data() -> Path:
    return Path(os.environ.get("HERMES_DATA", str(Path.home() / "hermes-data"))).expanduser()


def frame_file(path: str) -> Path | None:
    """A breakdown frame, only from <hermes-data>/breakdowns/bd-*/frames/*.jpg."""
    try:
        rp, root = Path(path).resolve(strict=True), (data() / "breakdowns").resolve()
    except (OSError, RuntimeError):
        return None
    parts = rp.relative_to(root).parts if root in rp.parents else ()
    if len(parts) != 3 or not re.fullmatch(r"bd-[0-9a-f]{16}", parts[0]) or parts[1] != "frames" or rp.suffix.lower() != ".jpg":
        return None
    return rp


def prompt_from(r: dict, cast: list[str] | None = None) -> str:
    """Same rule as Hermes mcp_breakdown.prompt_from (kept here so the Lab needs no Hermes import)."""
    subj = str((r or {}).get("subject") or "")
    for i, name in enumerate(cast or []):
        subj = re.sub(rf"\bperson {'ABCD'[i]}\b", name, subj, flags=re.I)
    parts = [subj, r.get("setting"), r.get("framing"), f"camera {r['camera']}" if r.get("camera") else "", r.get("motion"), r.get("light")]
    return ", ".join(str(p).strip().rstrip(".") for p in parts if str(p or "").strip())


def cast_names(mcp, root) -> list[str]:
    from . import cast
    names = []
    for cid in cast.chosen(root)["ids"]:
        try:
            names.append(mcp.call("cast_get", {"id": cid})["name"])
        except Exception:                                        # noqa: BLE001 — a missing card just isn't swapped in
            continue
    return names


def shelf(root) -> list[dict]:
    try:
        xs = json.loads((Path(root) / ".shelf" / "recipes.json").read_text())
    except (OSError, ValueError):
        xs = []
    return [x for x in xs if isinstance(x, dict)][-SHELF_MAX:]


def shelve(root, item: dict) -> list[dict]:
    xs = [x for x in shelf(root) if not (x.get("id") == item.get("id") and x.get("scene") == item.get("scene"))] + [item]
    f = Path(root) / ".shelf" / "recipes.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(xs[-SHELF_MAX:]))
    return xs[-SHELF_MAX:]


def scene_of(mcp, bid: str, n: int) -> tuple[dict, dict]:
    bd = mcp.call("breakdown_get", {"id": bid})
    s = next((x for x in bd.get("scenes") or [] if int(x.get("i", -1)) == int(n)), None)
    if s is None:
        raise ValueError("That scene isn't in the breakdown.")
    return bd, s


def make_like(mcp, root, bid: str, n: int) -> dict:
    """🎬 Make one like this → the words for a Lab picture run (the page starts it, so nothing spends without his tap)."""
    bd, s = scene_of(mcp, bid, n)
    names = cast_names(mcp, root)
    words = prompt_from(s.get("recipe") or {}, names)
    if not words:
        return {"ok": False, "icon": "🎞", "message": "That scene has no shot recipe yet — let the breakdown finish."}
    shelve(root, {"id": bid, "scene": n, "title": bd.get("title") or bd.get("name"), "recipe": s.get("recipe"), "words": words,
                  "at": time.time()})
    return {"ok": True, "task": words, "cast": names, "seconds": round(float(s["end"]) - float(s["start"]), 1)}


def use_frame(mcp, root, bid: str, n: int) -> dict:
    """📌 Copy the scene's keyframe into the project's pictures/ and pin it as a reference."""
    from . import refs
    bd, s = scene_of(mcp, bid, n)
    src = frame_file(s.get("frame_path") or "")
    if src is None:
        return {"ok": False, "icon": "🖼", "message": "That frame isn't there any more."}
    rel = f"pictures/frame-{bid[3:11]}-s{int(n) + 1:02d}.jpg"
    dst = Path(root) / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    r = refs.pin(root, rel)
    return {**r, "path": rel}
