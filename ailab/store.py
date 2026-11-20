"""Projects list + autosave recovery log. Both live outside the repo (~/.config/ailab).

Autosave rule (Scott, 2026-11-15): typing goes to an append-only recovery log so a power cut loses
almost nothing; real project files only change on an explicit Save (later modules).
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

from . import config

MAX_DRAFT = 200_000
KEEP_LINES = 500                     # per project; older lines are trimmed on write


def _dir() -> Path:
    d = config.home()
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def _lock(name: str):
    with open(_dir() / f"{name}.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return s or "project"


def projects() -> list[dict]:
    f = _dir() / "projects.json"
    rows = json.loads(f.read_text() or "[]") if f.exists() else []
    if not rows:
        rows = [{"id": "scratch", "name": "Scratch", "sensitive": False, "created": time.time()}]
    return rows


def save_project(name: str, sensitive: bool = False) -> dict:
    name = (name or "").strip()[:60]
    if not name:
        raise ValueError("A project needs a name.")
    with _lock("projects"):
        rows = projects()
        pid, n = _slug(name), 2
        while any(r["id"] == pid for r in rows):
            pid, n = f"{_slug(name)}-{n}", n + 1
        row = {"id": pid, "name": name, "sensitive": bool(sensitive), "created": time.time()}
        rows.append(row)
        tmp = _dir() / "projects.tmp"
        tmp.write_text(json.dumps(rows, indent=1))
        os.replace(tmp, _dir() / "projects.json")
    return row


def project(pid: str) -> dict | None:
    return next((p for p in projects() if p["id"] == pid), None)


def _log(pid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{1,48}", pid or ""):
        raise ValueError("bad project id")
    d = _dir() / "recovery"
    d.mkdir(exist_ok=True)
    return d / f"{pid}.jsonl"


def autosave(pid: str, field: str, text: str) -> dict:
    if len(text) > MAX_DRAFT:
        raise ValueError(f"Draft is over {MAX_DRAFT} characters.")
    f = _log(pid)
    rec = {"at": time.time(), "field": field[:40], "text": text}
    with _lock(f"recovery-{pid}"):
        with open(f, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        lines = f.read_text().splitlines()
        if len(lines) > KEEP_LINES * 2:
            tmp = f.with_suffix(".tmp")
            tmp.write_text("\n".join(lines[-KEEP_LINES:]) + "\n")
            os.replace(tmp, f)
    return {"ok": True, "at": rec["at"]}


def recover(pid: str) -> dict:
    """Latest text per field — survives a half-written last line."""
    f, out = _log(pid), {}
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            out[r["field"]] = {"text": r["text"], "at": r["at"]}
    return out
