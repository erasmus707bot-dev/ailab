"""🗄 Shelf (remodel M2, Scott 2026-11-25): ✅ Keep / 🗑 Throw away for what a run made.

Kept = a numbered entry (#1, #2 …) in <project>/.shelf/shelf.json. Thrown away = the files the run CREATED move to
<project>/.shelf/trash/<run>/ — hidden, not deleted — and ↩ come back for 30 days (Scott's pick: "hide it, recoverable
for 30 days"). After that the hidden copy is removed. Dot-folders never show in the file list or the 📚 Library."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

KEEP_DAYS = 30
DAY = 86400


def _dir(root) -> Path:
    return Path(root) / ".shelf"


def _load(root) -> dict:
    try:
        d = json.loads((_dir(root) / "shelf.json").read_text())
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    return {"kept": [x for x in d.get("kept") or [] if isinstance(x, dict)],
            "tossed": [x for x in d.get("tossed") or [] if isinstance(x, dict)],
            "done_at": float(d.get("done_at") or 0)}


def _save(root, d: dict) -> None:
    f = _dir(root) / "shelf.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(".shelf.json.tmp")
    tmp.write_text(json.dumps(d, indent=1))
    tmp.replace(f)


def _safe(root, rel: str) -> Path | None:
    """A real path inside the project, never a dot-folder, never outside it."""
    rel = str(rel or "")
    if not rel or rel.startswith("/") or any(s in ("", "..") or s.startswith(".") for s in rel.split("/")):
        return None
    root = Path(root).resolve()
    p = (root / rel).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        return None
    return p


def purge(root, now: float | None = None) -> int:
    """Hidden copies older than 30 days go for good. Returns how many entries were removed."""
    now = time.time() if now is None else now
    d = _load(root)
    old = [x for x in d["tossed"] if now - float(x.get("at") or 0) > KEEP_DAYS * DAY]
    if not old:
        return 0
    for x in old:
        shutil.rmtree(_dir(root) / "trash" / str(x.get("run") or "-"), ignore_errors=True)
    d["tossed"] = [x for x in d["tossed"] if x not in old]
    _save(root, d)
    return len(old)


def view(root, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    purge(root, now)
    d = _load(root)
    for x in d["tossed"]:
        x["days_left"] = max(0, KEEP_DAYS - int((now - float(x.get("at") or 0)) // DAY))
    return d


def keep(root, run_id: str, task: str, made: list[dict], seen: dict | None = None, facts: dict | None = None) -> dict:
    """✅ Keep: the run gets the next number. Keeping twice returns the same entry."""
    d = _load(root)
    if any(x.get("run") == run_id for x in d["tossed"]):
        raise ValueError("That one was thrown away — ↩ bring it back first.")
    for x in d["kept"]:
        if x.get("run") == run_id:
            return x
    item = {"n": max([int(x.get("n") or 0) for x in d["kept"]] or [0]) + 1, "run": run_id, "task": str(task)[:300],
            "files": [m["path"] for m in made if _safe(root, m.get("path"))], "at": time.time()}
    if seen:                                                     # 👁 M1: the vision model's caption + match score
        item["seen"] = seen
    if facts:                                                    # 🎨 R2: Look + model, so the Lab can spot a style
        item.update({k: facts[k] for k in ("look", "model") if facts.get(k)})
    d["kept"].append(item)
    _save(root, d)
    return item


def toss(root, run_id: str, task: str, made: list[dict], undone: list[str] | None = None, seen: dict | None = None) -> dict:
    """🗑 Throw away: files the run created are hidden under .shelf/trash/<run>/. Files it only changed are not moved
    (the caller puts them back with the run's own undo and lists them in `undone`)."""
    d = _load(root)
    if any(x.get("run") == run_id for x in d["tossed"]):
        raise ValueError("Already thrown away.")
    trash = _dir(root) / "trash" / run_id
    moved = []
    for m in made:
        src = _safe(root, m.get("path"))
        if not m.get("new") or src is None or not src.is_file():
            continue
        dst = trash / m["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved.append(m["path"])
    d["kept"] = [x for x in d["kept"] if x.get("run") != run_id]
    item = {"run": run_id, "task": str(task)[:300], "files": moved, "undone": list(undone or []), "at": time.time()}
    if seen:
        item["seen"] = seen
    d["tossed"].append(item)
    _save(root, d)
    return item


def restore(root, run_id: str) -> dict:
    """↩ Bring back: every hidden file returns to where it was. A name that is taken comes back as '<name> (restored)'."""
    d = _load(root)
    item = next((x for x in d["tossed"] if x.get("run") == run_id), None)
    if item is None:
        raise ValueError("Nothing to bring back — it may be older than 30 days.")
    trash, back = _dir(root) / "trash" / run_id, []
    for rel in item.get("files") or []:
        src, dst = trash / rel, _safe(root, rel)
        if dst is None or not src.is_file():
            continue
        if dst.exists():
            dst = dst.with_name(f"{dst.stem} (restored){dst.suffix}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        back.append(dst.relative_to(Path(root).resolve()).as_posix())
    shutil.rmtree(trash, ignore_errors=True)
    d["tossed"] = [x for x in d["tossed"] if x.get("run") != run_id]
    _save(root, d)
    return {"run": run_id, "files": back, "undone": item.get("undone") or []}


def set_done(root, done: bool) -> float:
    """🏁 Project done (remodel M4): a mark only — nothing is locked, moved or removed."""
    d = _load(root)
    d["done_at"] = time.time() if done else 0.0
    _save(root, d)
    return d["done_at"]
