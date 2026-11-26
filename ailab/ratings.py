"""⭐ Ratings + 🔁 change verdicts + ✅ accepted (Scott 2026-11-25, picks Q1-1 · Q2 source pool · Q3-1).

<project>/.shelf/ratings.json
  files    {path: {stars 1–5, reasons [...], run, task, sources [...], accepted, from [...], at}}
  changes  [{run, parent, change, before [...], after [...], verdict better|same|worse, kind, at}]

⭐ stars credit the 🗂 sources that made the picture (refs.credit — a re-rate replaces, never counts twice).
The 🪄 improver reads the best- and worst-rated prompts, and the change words that did / didn't work."""
from __future__ import annotations

import json
import time
from pathlib import Path

REASONS = {"nailed": "👍 Nailed it", "style": "🎨 Style off", "body": "🧍 Face/body off", "count": "🔢 Wrong count",
           "words": "📝 Ignored my words"}
VERDICTS = ("better", "same", "worse")
MAX_CHANGES = 500


def _file(root) -> Path:
    return Path(root) / ".shelf" / "ratings.json"


def _load(root) -> dict:
    try:
        d = json.loads(_file(root).read_text())
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    return {"files": d.get("files") if isinstance(d.get("files"), dict) else {},
            "changes": d.get("changes") if isinstance(d.get("changes"), list) else []}


def _save(root, d: dict) -> None:
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    tmp.replace(f)


def _safe(root, rel: str) -> bool:
    from . import shelf
    p = shelf._safe(root, rel)
    return bool(p and p.is_file())


def _paths(root, xs) -> list[str]:
    return [str(x) for x in (xs if isinstance(xs, list) else []) if isinstance(x, str) and _safe(root, x)][:12]


def rate(root, path: str, stars: int, reasons=None, run: str = "", task: str = "", sources=None) -> dict:
    """⭐ 1–5 (0 clears). Re-rating replaces. Returns the file's row."""
    from . import refs
    path = str(path or "")
    if not _safe(root, path):
        return {"ok": False, "icon": "⭐", "message": "Only something in this project can be rated."}
    try:
        stars = max(0, min(5, int(stars)))
    except (TypeError, ValueError):
        return {"ok": False, "icon": "⭐", "message": "Stars are 1 to 5."}
    d = _load(root)
    row = d["files"].get(path) or {}
    old = int(row.get("stars") or 0)
    srcs = _paths(root, sources) or row.get("sources") or _paths(root, refs.made_from(root, path))
    row.update(stars=stars, reasons=[r for r in (reasons or []) if r in REASONS][:5], at=time.time(), sources=srcs)
    if run:
        row["run"] = str(run)[:40]
    if task:
        row["task"] = str(task)[:600]
    if not row.get("model"):
        row["model"] = refs.made_by(root, path)
    d["files"][path] = row
    _save(root, d)
    if srcs and (stars or old):
        refs.credit(root, srcs, stars, old)
    return {"ok": True, "row": row}


def accept(root, path: str, run: str = "", task: str = "", sources=None) -> dict:
    """✅ Accept: marked as a winner. Nothing on screen is cleared (the page keeps the prompts)."""
    path = str(path or "")
    if not _safe(root, path):
        return {"ok": False, "icon": "✅", "message": "Only something in this project can be accepted."}
    d = _load(root)
    row = d["files"].get(path) or {}
    row.update(accepted=time.time(), run=str(run or row.get("run") or "")[:40])
    if task:
        row["task"] = str(task)[:600]
    from . import refs
    srcs = _paths(root, sources) or _paths(root, refs.made_from(root, path))
    if srcs:
        row["from"] = srcs
        row.setdefault("sources", srcs)
    d["files"][path] = row
    _save(root, d)
    return {"ok": True, "row": row}


def verdict(root, run: str, parent: str, change: str, before, after, v: str, kind: str = "") -> dict:
    """🔁 Did the change work? One verdict per change run — saying it again replaces it."""
    if v not in VERDICTS:
        return {"ok": False, "icon": "🔁", "message": "Better, same or worse."}
    d = _load(root)
    row = {"run": str(run)[:40], "parent": str(parent or "")[:40], "change": str(change or "")[:400],
           "before": _paths(root, before), "after": _paths(root, after), "verdict": v, "kind": str(kind)[:20], "at": time.time()}
    d["changes"] = [c for c in d["changes"] if c.get("run") != row["run"]] + [row]
    d["changes"] = d["changes"][-MAX_CHANGES:]
    _save(root, d)
    return {"ok": True, "row": row, "tally": tally(d)}


def tally(d: dict) -> dict:
    t = {v: 0 for v in VERDICTS}
    for c in d["changes"]:
        if c.get("verdict") in t:
            t[c["verdict"]] += 1
    return t


def view(root) -> dict:
    d = _load(root)
    return {"files": d["files"], "changes": d["changes"][-50:], "tally": tally(d), "reasons": REASONS}


def taste(root) -> dict:
    """For the 🪄 improver: prompts behind ★★★★+ and ★★- results, and change words that worked / didn't."""
    d = _load(root)
    rows = sorted(d["files"].values(), key=lambda r: r.get("at") or 0)
    first = lambda t: str(t or "").split("\n")[0].strip()[:200]                       # noqa: E731
    uniq = lambda xs: list(dict.fromkeys(x for x in xs if x))                        # noqa: E731
    loved = uniq(first(r.get("task")) for r in rows if int(r.get("stars") or 0) >= 4 or r.get("accepted"))[-5:]
    low = uniq((first(r.get("task")) + (" [" + ", ".join(REASONS[x] for x in r.get("reasons") or [] if x in REASONS) + "]"
                                         if r.get("reasons") else "")) for r in rows if 0 < int(r.get("stars") or 0) <= 2)[-5:]
    good = uniq(c.get("change") for c in d["changes"] if c.get("verdict") == "better")[-5:]
    bad = uniq(c.get("change") for c in d["changes"] if c.get("verdict") == "worse")[-5:]
    return {k: v for k, v in (("loved", loved), ("low", low), ("good_changes", good), ("bad_changes", bad)) if v}


MIN_N = 3


def model_stats(root) -> dict:
    """{model: {"avg", "n"}} from his star ratings in this project (only rated files with a known model)."""
    acc: dict = {}
    for r in _load(root)["files"].values():
        m, st = str(r.get("model") or ""), int(r.get("stars") or 0)
        if m and st:
            a = acc.setdefault(m, [0, 0])
            a[0] += st
            a[1] += 1
    return {m: {"avg": round(t / n, 1), "n": n} for m, (t, n) in acc.items()}


def steer(models: list[str], stats: dict) -> tuple[list[str], str]:
    """⭐ ratings steer the route, inside the same side only (local stays local, Venice stays Venice):
    ≥ MIN_N ratings and ≥ 4.0★ → tried first on its side; ≤ 2.0★ → tried last on its side. Returns (order, why)."""
    side = lambda m: m.split("/")[0]                                                  # noqa: E731
    def score(m):
        s = stats.get(m) or stats.get(m.split("/")[-1]) or {}
        if int(s.get("n") or 0) < MIN_N:
            return 0
        return 1 if s["avg"] >= 4.0 else -1 if s["avg"] <= 2.0 else 0
    out, why = list(models), []
    for sd in dict.fromkeys(side(m) for m in models):
        idx = [i for i, m in enumerate(out) if side(m) == sd]
        group = [out[i] for i in idx]
        new = sorted(group, key=lambda m: -score(m))
        for i, m in zip(idx, new):
            out[i] = m
        for m in group:
            sc = score(m)
            if sc:
                s = stats.get(m) or stats.get(m.split("/")[-1])
                why.append(f"{m.split('/')[-1]} {s['avg']}★ ×{s['n']} → {'first' if sc > 0 else 'last'}")
    return out, ("⭐ your ratings here: " + " · ".join(why)) if why and out != models else ""
