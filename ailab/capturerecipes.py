"""🧭 Capture recipes in the AI Lab (Lab capture C4, 2026-11-25) — thin glue over Hermes capture_recipes / capture_recipe /
capture_use. The recipes themselves (portfolio refresh, demo clip) live in Hermes so Night Shift can run them too.

  GET  /api/capture/recipes        → recipes + what the portfolio refresh would take now (run / desktop / unknown)
  POST /api/capture/recipe {recipe, app?, url?, title?} → {key}   (a job in Hermes — poll /api/capture/job)
  GET  /api/capture/job?key=…      → the job (state, phase, result)
  POST /api/capture/use {path, shot} → copied into the portfolio inbox (never published)
"""
from __future__ import annotations

from .mcp_client import HermesRefused
from .transport import HttpError


def _err(msg: str, fix: str = "", code: str = "failed", status: int = 400) -> tuple[int, dict]:
    return status, {"ok": False, "code": code, "icon": "🧭", "message": msg, "fix": fix}


def _call(app, tool: str, args: dict) -> tuple[int, dict]:
    if app.cfg.get("mode") != "connected" or not getattr(app.lab, "mcp", None):
        return _err("🧭 Recipes run through Hermes.", "Switch the Lab to connected mode.", "not_connected")
    try:
        return 200, {"ok": True, **app.lab.mcp.call(tool, args)}
    except HermesRefused as e:
        return _err(e.message, e.fix or "", e.code or "refused")
    except HttpError as e:
        return _err(f"Hermes didn't answer: {e.body}", "Check hermes-mcp is running, then try again.", "no_hermes", 502)


def listing(app, q: dict) -> tuple[int, dict]:
    code, out = _call(app, "capture_recipes", {})
    if code == 200:
        c2, apps = _call(app, "capture_apps", {})
        out["apps"] = apps.get("apps") if c2 == 200 else None
        out["apps_note"] = "" if c2 == 200 else apps.get("message", "")
    return code, out


def run(app, b: dict) -> tuple[int, dict]:
    rid = str(b.get("recipe") or "")
    args = {"recipe": rid}
    for k in ("app", "url", "title", "project"):
        if b.get(k):
            args[k] = str(b[k])[:200]
    return _call(app, "capture_recipe", args)


def job(app, q: dict) -> tuple[int, dict]:
    key = str((q.get("key") or [""])[0])
    if not key.startswith("cap:"):
        return _err("No such recipe run.", "", "bad_args")
    return _call(app, "job_wait", {"key": key, "max_s": 1})


def use(app, b: dict) -> tuple[int, dict]:
    return _call(app, "capture_use", {"path": str(b.get("path") or ""), "shot": str(b.get("shot") or "")})


def thumb_bytes(q: dict) -> bytes | None:
    """📸 A capture's thumbnail for the recipe grid — only files under ~/hermes-data/captures, only .thumb.jpg / .ba.jpg."""
    from pathlib import Path
    from . import config
    root = (config.files_home().parent / "captures").resolve()
    p = Path(str((q.get("path") or [""])[0])).expanduser()
    p = p.with_suffix(".thumb.jpg") if p.suffix in (".png", ".mp4") else p
    try:
        p = p.resolve()
    except OSError:
        return None
    if root not in p.parents or not p.name.endswith((".thumb.jpg", ".ba.jpg")) or not p.is_file():
        return None
    return p.read_bytes()
