"""📦 Make it an app (lab-ship M3, 2026-11-24): a Lab project → Hermes `app_ship` → Android / Linux / Windows builds.

The Lab has no SDK and no network by design; gandalf does. This packs the project's files (a web app with an
index.html at the top, or a Godot project folder with project.godot) and hands them to Hermes over MCP. Hermes checks
Godot scripts with the real engine, builds each platform and puts them on the 🧪 test shelf (Iris 📦 Apps, Hermes
/downloads, Drive → Apps). Releasing and sharing stay with Scott in Hermes/Iris (⬆ Release). Connected mode only.
"""
from __future__ import annotations

import base64
from pathlib import Path

from . import preview, store
from .secretscan import has_secret

TEXT_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".md", ".txt", ".xml", ".webmanifest",
            ".gd", ".tscn", ".tres", ".godot", ".cfg", ".gdshader", ".csv"}
SKIP_DIRS = {".godot", ".import", "node_modules", ".git"}
MAX_TOTAL = 8 << 20                                         # Hermes refuses over 8 MB (MCP body is 10 MB)
PLATFORMS = ("android", "linux", "windows")


def _err(msg: str, code: str = "bad_args", icon: str = "📦") -> preview.PreviewError:
    return preview.PreviewError(msg, code, icon)


def _title(f: Path, rx: str) -> str:
    import html as _h
    import re as _re
    try:
        m = _re.search(rx, f.read_text(errors="replace")[:200_000], _re.I | _re.S | _re.M)
    except OSError:
        return ""
    return _re.sub(r"\s+", " ", _h.unescape(m.group(1))).strip()[:60] if m else ""


def options(pid: str) -> list[dict]:
    """What can be shipped from this project: the top folder (web app) and any folder holding project.godot.
    Each carries its own name (page <title> / Godot config/name) so two apps from one project never share a shelf."""
    root = preview.ensure_site(pid).resolve()
    out = []
    if (root / "index.html").is_file():
        out.append({"folder": "", "kind": "web", "label": "🌐 Web app (index.html)",
                    "name": _title(root / "index.html", r"<title[^>]*>(.*?)</title>")})
    for pg in sorted(root.rglob("project.godot")):
        rel = pg.parent.relative_to(root).as_posix()
        if any(p.startswith(".") or p in SKIP_DIRS for p in Path(rel).parts):
            continue
        out.append({"folder": "" if rel == "." else rel, "kind": "godot", "label": f"🎮 Godot game ({rel or 'top'})",
                    "name": _title(pg, r'^config/name="([^"]*)"')})
    return out


def package(pid: str, folder: str = "") -> dict:
    p = store.project(pid)
    if not p:
        raise _err("No such project.", "bad_args", "❓")
    if p.get("sensitive"):
        raise _err("This project is marked sensitive — it isn't shipped as an app.", "sensitive", "🔒")
    root = preview.ensure_site(pid).resolve()
    base = (root / folder).resolve() if folder else root
    if not base.is_relative_to(root) or not base.is_dir():
        raise _err("That folder isn't in the project.", "outside", "🚧")
    files, total = {}, 0
    for f in sorted(base.rglob("*")):
        rel = f.relative_to(base).as_posix()
        if not f.is_file() or f.is_symlink() or any(s.startswith(".") or s in SKIP_DIRS for s in rel.split("/")):
            continue
        data = f.read_bytes()
        total += len(data)
        if total > MAX_TOTAL:
            raise _err(f"Over {MAX_TOTAL >> 20} MB — too big to send. Ship it from a folder on gandalf instead.",
                       "too_big")
        if f.suffix.lower() in TEXT_EXT:
            text = data.decode("utf-8", "replace")
            if has_secret(text):
                raise _err(f"Something that looks like a key is in {rel}. Remove it first.", "secret", "🔑")
            files[rel] = text
        else:
            files[rel] = {"b64": base64.b64encode(data).decode()}
    if "index.html" not in files and "project.godot" not in files:
        raise _err("Needs an index.html (web app) or project.godot (Godot game) at the top of the folder.")
    return {"files": files, "bytes": total, "name": p.get("name") or pid}


HOMES = ("Hermes", "Tools", "Media & fun", "Gifts")      # Hermes library groups (2026-11-24); "" = Hermes decides


def start(lab, cfg: dict, pid: str, name: str = "", folder: str = "", platforms: list | None = None,
          orientation: str = "any", home_group: str = "") -> dict:
    if cfg.get("mode") != "connected":
        raise _err("Making real apps needs Hermes — switch the Lab to connected mode.", "no_hermes", "🔌")
    pkg = package(pid, folder)
    plats = [x for x in (platforms or PLATFORMS) if x in PLATFORMS] or list(PLATFORMS)
    args = {"name": (name or pkg["name"]).strip()[:60], "files": pkg["files"], "platforms": plats,
            "orientation": orientation if orientation in ("any", "landscape", "portrait") else "any"}
    if home_group in HOMES:
        args["home_group"] = home_group
    r = lab.mcp.call("app_ship", args)
    return {"ok": True, "key": r.get("key"), "app": r.get("app"), "files": len(pkg["files"]), "bytes": pkg["bytes"],
            "where": r.get("where", ""), "library_group": r.get("library_group", "Testing"),
            "home_group": r.get("home_group") or home_group or ""}


def wait(lab, cfg: dict, key: str) -> dict:
    if cfg.get("mode") != "connected":
        raise _err("Needs Hermes (connected mode).", "no_hermes", "🔌")
    if not str(key).startswith("ship:"):
        raise _err("Bad job key.")
    r = lab.mcp.call("job_wait", {"key": key, "max_s": 25})
    return {"ok": True, "key": key, "state": r.get("state"), "finished": bool(r.get("finished")),
            "notes": (r.get("detail") or {}).get("notes", [])[-8:], "result": r.get("result"), "error": r.get("error")}
