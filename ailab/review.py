"""📋 Review (M6): what the Lab hands to Scott.

Two kinds of item:
  * demos — a project's files + its latest 📸 capture + a write-up + the models used. Connected mode sends them to
    Hermes 📋 Review (MCP `review_submit`); Scott approves there with his owner PIN, and Hermes publishes (dry run
    unless he types "publish"). Standalone mode keeps the package here — there is no publishing without Hermes.
  * held writes — agent writes outside the project folder (M5). Apply needs the typed word "apply" and the hash that
    was on screen; only files under your home folder, never dot-folders or symlinks; an existing file is copied to
    approvals/backups/ first. Reject is a logged state. Nothing is deleted.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from . import agent, config, preview, store
from .secretscan import SECRET_RX, has_secret  # noqa: F401 — SECRET_RX kept importable

TEXT_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".md", ".txt", ".xml", ".webmanifest"}
MAX_FILE, MAX_TOTAL, MAX_FILES, MAX_SHOT = 300_000, 2_000_000, 40, 4_000_000
APPLY_WORD = "apply"


class ReviewError(Exception):
    def __init__(self, message: str, code: str = "review", icon: str = "📋"):
        self.code, self.icon = code, icon
        super().__init__(message)


def _dir() -> Path:
    d = config.home() / "review"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ demos
def models_used(pid: str) -> list[str]:
    """provider/model of every agent run on this project (newest first), from the run .meta.json files."""
    d = config.home() / "projects" / pid / "agent"
    out: list[str] = []
    if d.is_dir():
        for f in sorted(d.glob("*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                m = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            k = f"{m.get('provider')}/{m.get('model')}"
            if k not in out:
                out.append(k)
    return out[:12]


def latest_capture(pid: str) -> Path | None:
    d = preview.site_dir(pid).parent / "captures"
    caps = sorted(d.glob("capture-*.png")) if d.is_dir() else []
    return caps[-1] if caps else None


def package(pid: str, title: str, writeup: str, models: list | None = None) -> dict:
    p = store.project(pid)
    if not p:
        raise ReviewError("No such project.", "bad_args", "❓")
    if p.get("sensitive"):
        raise ReviewError("This project is marked sensitive — it stays private and can't go to Review.", "sensitive", "🔒")
    title, writeup = (title or "").strip()[:80], (writeup or "").strip()[:8000]
    if not title:
        raise ReviewError("Give the demo a title.", "bad_args", "❓")
    if len(writeup) < 20:
        raise ReviewError("Write at least a sentence about it (20+ characters).", "bad_args", "❓")
    root, files, total = preview.ensure_site(pid).resolve(), {}, 0
    for f in preview.list_files(pid):
        if Path(f["path"]).suffix.lower() not in TEXT_EXT:
            continue
        text = (root / f["path"]).read_text(errors="replace")
        n = len(text.encode())
        if n > MAX_FILE:
            raise ReviewError(f"{f['path']} is over {MAX_FILE // 1000} KB.", "too_big", "📦")
        files[f["path"]], total = text, total + n
    if "index.html" not in files:
        raise ReviewError("The project needs an index.html.", "bad_args", "❓")
    if len(files) > MAX_FILES or total > MAX_TOTAL:
        raise ReviewError(f"Too big for Review (max {MAX_FILES} files, {MAX_TOTAL // 1_000_000} MB).", "too_big", "📦")
    hits = [k for k, v in files.items() if has_secret(v)] + (["write-up"] if has_secret(writeup) else [])
    if hits:
        raise ReviewError("Something that looks like a key is in: " + ", ".join(hits[:5]) + ". Remove it first.",
                          "secret", "🔑")
    cap = latest_capture(pid)
    shot = cap.read_bytes() if cap else b""
    if len(shot) > MAX_SHOT:
        raise ReviewError("The latest 📸 capture is over 4 MB — take a smaller one.", "too_big", "📦")
    ms = [str(m)[:80] for m in (models if models is not None else models_used(pid)) if str(m).strip()][:12]
    return {"title": title, "project": pid, "writeup": writeup, "models": ms, "files": files,
            "screenshot_b64": base64.b64encode(shot).decode() if shot else "", "sensitive": False}


def _sent_log() -> Path:
    return _dir() / "sent.jsonl"


def send(lab, cfg: dict, pid: str, title: str, writeup: str, models: list | None = None) -> dict:
    pkg = package(pid, title, writeup, models)
    rec = {"at": time.time(), "project": pid, "title": pkg["title"], "models": pkg["models"],
           "files": sorted(pkg["files"]), "has_shot": bool(pkg["screenshot_b64"])}
    if cfg.get("mode") == "connected":
        r = lab.mcp.call("review_submit", pkg)              # HermesRefused bubbles up with Hermes's reason
        rec.update(where="hermes", hermes_id=r.get("id"), state=r.get("state", "waiting"))
    else:
        lid = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        d = _dir() / "kept" / lid
        d.mkdir(parents=True)
        (d / "package.json").write_text(json.dumps(pkg))
        rec.update(where="kept", local_id=lid, state="kept",
                   note="Standalone mode: kept here. Publishing goes through Hermes Review (connected mode).")
    with open(_sent_log(), "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return {"ok": True, **rec}


def sent(lab=None, cfg: dict | None = None) -> list[dict]:
    rows = []
    if _sent_log().exists():
        for line in _sent_log().read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    rows = rows[-50:][::-1]
    ids = [r["hermes_id"] for r in rows if r.get("hermes_id")]
    if ids and lab is not None and (cfg or {}).get("mode") == "connected":
        try:
            st = {i["id"]: i for i in lab.mcp.call("review_status", {"ids": ids}).get("items", [])}
            for r in rows:
                h = st.get(r.get("hermes_id"))
                if h:
                    r.update(state=h.get("state"), url=h.get("url"), why=h.get("why"))
        except Exception as e:                                  # noqa: BLE001 — Hermes down: show last known state
            for r in rows:
                if r.get("hermes_id"):
                    r["note"] = f"Hermes didn't answer ({type(e).__name__}) — last known state shown."
    return rows


# ------------------------------------------------------------------ held writes (M5 approvals)
def _content(aid: str) -> Path:
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}", aid or ""):
        raise ReviewError("Bad item id.", "bad_args", "❓")
    return config.home() / "approvals" / f"{aid}.txt"


def held(state: str | None = "waiting") -> list[dict]:
    rows = []
    for r in agent.approvals(state):
        f = _content(r["id"])
        text = f.read_text(errors="replace") if f.exists() else ""
        rows.append({**r, "sha": hashlib.sha256(text.encode()).hexdigest(), "preview": text[:4000],
                     "target": str(target(r))})
    return rows


def target(item: dict) -> Path:
    root = preview.site_dir(item["project"]).resolve()
    rel = str(item["path"])
    return Path(os.path.normpath(rel if os.path.isabs(rel) else root / rel))


def _safe_target(t: Path) -> Path:
    home = Path.home().resolve()
    try:
        parts = t.relative_to(home).parts
    except ValueError:
        raise ReviewError("Only files inside your home folder can be applied.", "outside_home", "🚧") from None
    if not parts or any(p.startswith(".") for p in parts):
        raise ReviewError("Dot-folders and dotfiles (settings, keys) are never written from here.", "dotfile", "🚧")
    probe = home
    for p in parts:
        probe = probe / p
        if probe.is_symlink():
            raise ReviewError("The path goes through a link — not applied.", "symlink", "🚧")
    if t.exists() and not t.is_file():
        raise ReviewError("Something that isn't a file is already there.", "not_file", "🚧")
    return t


def apply(aid: str, sha: str, confirm: str) -> dict:
    if str(confirm or "").strip().lower() != APPLY_WORD:
        raise ReviewError(f'Type "{APPLY_WORD}" to write the file.', "confirm", "✋")
    item = next((r for r in agent.approvals("waiting") if r["id"] == aid), None)
    if not item:
        raise ReviewError("That item isn't waiting any more.", "state", "📋")
    text = _content(aid).read_text()
    if hashlib.sha256(text.encode()).hexdigest() != sha:
        raise ReviewError("It changed since you looked — reload and check it again.", "stale", "🔁")
    t = _safe_target(target(item))
    backup = ""
    if t.exists():
        b = config.home() / "approvals" / "backups" / f"{aid}-{t.name}"
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t, b)
        backup = str(b)
    t.parent.mkdir(parents=True, exist_ok=True)
    tmp = t.with_name(f".{t.name}.ailab-{aid}")
    tmp.write_text(text)
    os.replace(tmp, t)
    agent.set_approval_state(aid, "applied", target=str(t), backup=backup)
    return {"ok": True, "id": aid, "state": "applied", "target": str(t), "backup": backup}


def reject(aid: str) -> dict:
    _content(aid)
    if not any(r["id"] == aid for r in agent.approvals("waiting")):
        raise ReviewError("That item isn't waiting any more.", "state", "📋")
    agent.set_approval_state(aid, "rejected")
    return {"ok": True, "id": aid, "state": "rejected"}
