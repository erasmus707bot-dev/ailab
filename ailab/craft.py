"""📓 Craft Book (Scott 2026-11-25: "teach my system as you build with it so it gets better … anything done these past
few days or in the future must be built into the ai lab system").

🧠 Memory knows Scott. The Craft Book knows the WORK: short notes on what makes a picture / clip / story come out as
asked, each with its evidence. Makers hand the fitting notes to the writer model; 👁 Eyes scores, ✅ Keep / 🗑 Throw
away and 🔁 fixes that worked feed back, so notes earn their place or get proposed for retirement.

    note = {id, kind, when[], model, do, why, cat, source, status, added, base, used, helped, kept, tossed, examples[]}
    kind   picture | video | story | motion | rebuild | doc | build | any
    when   words that must appear in his words ("#count" = he gave a number of things); empty = always
    source seed | handoff | scott → start `proposed` (Scott's one batch review) · measured → goes live by itself
    status proposed | live | retired          (flag `retire` = used 6×, helped 0 → Scott is asked)

Rules: a note never overrides his own words; nothing here spends, raises into a run, or stores sensitive info
(memory.sensitive gate). Every change is logged whole so ↶ undo works. Store: ~/.config/ailab/craft/. Flag: `craft`.
Switch: config.json "craft": {"on": false, "max": 6, "holdout": 0}  (holdout n = every nth run goes without notes).
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import re
import time
from contextlib import contextmanager
from pathlib import Path

from . import config

KINDS = ("picture", "video", "story", "motion", "rebuild", "doc", "build", "any")
SOURCES = ("seed", "handoff", "scott", "measured")
MAX_NOTES_IN_PROMPT = 6
MAX_CHARS = 1100
MAX_DO = 400
RETIRE_USED = 6
LOW = 70
CAT_WINDOW, CAT_MIN, CAT_MISSES = 10, 5, 3
HEAD = ("\n\nCraft notes — what has worked in this Lab before. Follow them quietly, never mention them, and never let "
        "them change or outrank his own words:")
COUNT_RX = re.compile(r"\b(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a pair of|a couple of)"
                      r"\s+(?:[a-z'-]+\s+){0,2}?[a-z'-]+?s\b", re.I)
# Written once, asleep until Eyes measures the need (CAT_MISSES misses in the last CAT_WINDOW checks of that kind of point).
AUTO = {
    "count": "When he gives a number of things, say 'exactly N' and place them apart, each whole and in view "
             "(in a row or evenly spaced), so they can be counted. Add no extra ones in the background.",
    "look": "Name the Look's medium and style in the first words of your detail and give one defining trait of it "
            "(brushwork, line, paper, grain). No words from a different medium.",
    "notext": "Describe nothing that carries writing: no signs, posters, screens, labels, open books, printed shirts, "
              "captions or signatures.",
    "show": "Every thing he named appears once more in your detail with one visible trait; leave nothing he named implied.",
}
BLOCK_RX = re.compile(r"```craft\s*\n(.*?)```", re.S)


def root() -> Path:
    d = config.home() / "craft"
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def _lock():
    with open(root() / ".lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _empty() -> dict:
    return {"notes": [], "stats": {}, "cats": {}, "runs": {}, "low": {}, "n": 0}


def _load() -> dict:
    try:
        d = json.loads((root() / "notes.json").read_text())
    except (OSError, ValueError):
        return _empty()
    return {**_empty(), **(d if isinstance(d, dict) else {})}


def _save(d: dict, why: str = "", before: list | None = None) -> None:
    """Whole file or nothing. `why` set = a change Scott can ↶ undo (the notes before it are logged)."""
    if why and before is not None and before != d["notes"]:
        with open(root() / "changes.jsonl", "a") as fh:
            fh.write(json.dumps({"t": time.time(), "why": why, "before": before}) + "\n")
    tmp = root() / ".notes.json.tmp"
    tmp.write_text(json.dumps(d, indent=1))
    tmp.replace(root() / "notes.json")


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9#]+", " ", str(text).lower()).split())


def nid(kind: str, do: str) -> str:
    return hashlib.sha1(f"{kind}|{norm(do)}".encode()).hexdigest()[:10]


def _clean(n: dict) -> dict | None:
    kind = str(n.get("kind") or "any").strip().lower()
    do = re.sub(r"\s+", " ", str(n.get("do") or "")).strip()[:MAX_DO]
    if kind not in KINDS or len(do) < 8:
        return None
    when = n.get("when") or []
    if isinstance(when, str):
        when = re.split(r"[,;|]", when)
    when = [w for w in (norm(x) for x in when) if w][:12]
    return {"id": nid(kind, do), "kind": kind, "when": when, "model": str(n.get("model") or "").strip().lower()[:60],
            "do": do, "why": re.sub(r"\s+", " ", str(n.get("why") or "")).strip()[:400], "cat": str(n.get("cat") or "")[:12]}


def _sensitive(text: str) -> str:
    try:
        from . import memory                                      # noqa: PLC0415
        return memory.sensitive(text)
    except Exception:                                             # noqa: BLE001
        return ""


def _mean(d: dict, kind: str) -> float | None:
    s = (d["stats"].get(kind) or {})
    n = sum(int((s.get(k) or {}).get("n") or 0) for k in ("on", "off"))
    return round(sum(float((s.get(k) or {}).get("sum") or 0) for k in ("on", "off")) / n, 1) if n >= 3 else None


def _add(d: dict, n: dict, source: str, status: str | None = None) -> tuple[dict | None, bool]:
    c = _clean(n)
    if not c or _sensitive(c["do"] + " " + c["why"]):
        return None, False
    old = next((x for x in d["notes"] if x["id"] == c["id"]), None)
    if old:
        return old, False
    source = source if source in SOURCES else "scott"
    st = status or ("live" if source == "measured" else "proposed")
    row = {**c, "source": source, "status": st, "added": time.strftime("%Y-%m-%dT%H:%M"), "base": _mean(d, c["kind"]),
           "used": 0, "helped": 0, "kept": 0, "tossed": 0, "examples": [], "flag": ""}
    d["notes"].append(row)
    return row, True


def add(note: dict, source: str = "scott", status: str | None = None) -> dict:
    with _lock():
        d = _load()
        before = json.loads(json.dumps(d["notes"]))
        row, new = _add(d, note, source, status)
        if row is None:
            return {"saved": False, "why": "needs a kind and a 'do' line of 8+ letters, and nothing sensitive"}
        if new:
            _save(d, f"add:{source}", before)
        return {"saved": new, "note": row}


def add_many(notes: list[dict], source: str, why: str) -> dict:
    with _lock():
        d = _load()
        before = json.loads(json.dumps(d["notes"]))
        got = [_add(d, n, source) for n in notes]
        new = [r for r, isnew in got if isnew]
        if new:
            _save(d, why, before)
        return {"added": len(new), "known": sum(1 for r, isnew in got if r and not isnew),
                "skipped": sum(1 for r, _ in got if r is None), "ids": [r["id"] for r in new]}


def notes(status: str = "") -> list[dict]:
    return [n for n in _load()["notes"] if not status or n["status"] == status]


def set_status(ids: list[str], status: str) -> dict:
    """Scott's ✅ / 🗑 on the Craft page. ids ["*proposed"] = every proposed note at once (his one batch review)."""
    if status not in ("live", "proposed", "retired"):
        return {"changed": 0}
    with _lock():
        d = _load()
        before = json.loads(json.dumps(d["notes"]))
        allp = "*proposed" in ids
        hit = 0
        for n in d["notes"]:
            if n["id"] in ids or (allp and n["status"] == "proposed"):
                if n["status"] != status or n.get("flag"):
                    if status == "live" and n["status"] != "live":
                        n["base"] = _mean(d, n["kind"])           # score before this note: what "helped" is measured against
                    n["status"], n["flag"] = status, ""
                    if status == "live":
                        n["used"] = n["helped"] = 0              # a kept note starts a fresh count
                    hit += 1
        if hit:
            _save(d, f"status:{status}", before)
        return {"changed": hit}


def edit(i: str, do: str = "", when=None, why: str = "") -> dict:
    with _lock():
        d = _load()
        before = json.loads(json.dumps(d["notes"]))
        n = next((x for x in d["notes"] if x["id"] == i), None)
        if not n:
            return {"saved": False, "why": "no such note"}
        c = _clean({"kind": n["kind"], "do": do or n["do"], "when": n["when"] if when is None else when, "why": why or n["why"]})
        if not c or _sensitive(c["do"] + " " + c["why"]):
            return {"saved": False, "why": "not a usable note"}
        n.update(do=c["do"], when=c["when"], why=c["why"], source="scott")      # the id stays: it names the note, not its words
        _save(d, "edit", before)
        return {"saved": True, "note": n}


def undo_last() -> dict:
    with _lock():
        f = root() / "changes.jsonl"
        rows = [x for x in (f.read_text().splitlines() if f.exists() else []) if x.strip()]
        if not rows:
            return {"undone": False, "why": "nothing to undo"}
        last = json.loads(rows[-1])
        d = _load()
        d["notes"] = last["before"]
        _save(d)
        f.write_text("".join(r + "\n" for r in rows[:-1]))
        return {"undone": True, "why": last.get("why", "")}


# ---------- use: the fitting notes for one job ----------
def settings(cfg: dict | None) -> dict:
    flags = (cfg or {}).get("flags") or {}
    c = (cfg or {}).get("craft")
    c = c if isinstance(c, dict) else {}
    return {"on": bool(flags.get("craft")) and c.get("on", True) is not False,
            "max": max(1, min(12, int(c.get("max") or MAX_NOTES_IN_PROMPT))), "holdout": max(0, int(c.get("holdout") or 0))}


def _fits(n: dict, kind: str, text: str, model: str) -> int:
    """0 = no · 1 = always-note · 2 = his words call for it."""
    if n["status"] != "live" or n["kind"] not in (kind, "any"):
        return 0
    if n.get("model") and n["model"] not in (model or "").lower():
        return 0
    if not n["when"]:
        return 1
    for w in n["when"]:
        if (w == "#count" and COUNT_RX.search(text)) or (w != "#count" and re.search(rf"(?<![a-z0-9]){re.escape(w)}", text)):
            return 2
    return 0


def pick(kind: str, words: str, model: str = "", limit: int = MAX_NOTES_IN_PROMPT, rows: list[dict] | None = None) -> list[dict]:
    text = norm(words)
    rows = _load()["notes"] if rows is None else rows
    got = [(f, n) for n in rows if (f := _fits(n, kind, text, model))]
    got.sort(key=lambda x: (-x[0], -(x[1]["helped"] + x[1]["kept"]) / (x[1]["used"] + 2), x[1]["added"]))
    out, size = [], 0
    for _, n in got[:limit]:
        size += len(n["do"]) + 3
        if size > MAX_CHARS and out:
            break
        out.append(n)
    return out


def text_for(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = HEAD
    for n in rows:
        out += "\n- " + n["do"]
        if n.get("examples"):
            out += " (wording that fixed this before: " + " | ".join(n["examples"][-2:]) + ")"
    return out


def for_run(run, kind: str, words: str, model: str = "") -> str:
    """The note block for a writer's system prompt ('' when off / nothing fits). Remembers which notes this run used.
    Never raises — craft is a bonus, never a blocker."""
    try:
        s = settings(getattr(run, "cfg", None))
        if not s["on"]:
            return ""
        with _lock():
            d = _load()
            d["n"] = int(d.get("n") or 0) + 1
            held = bool(s["holdout"]) and d["n"] % s["holdout"] == 0
            rows = [] if held else pick(kind, words, model, s["max"], d["notes"])
            rid = str(getattr(run, "id", "") or "")
            if rid:
                cur = d["runs"].get(rid) or {"ids": [], "kind": kind, "t": time.time()}
                cur["ids"] = list(dict.fromkeys(cur["ids"] + [n["id"] for n in rows]))
                cur["held"] = held
                d["runs"][rid] = cur
                for k in sorted(d["runs"], key=lambda k: d["runs"][k].get("t", 0))[:-300]:
                    d["runs"].pop(k, None)
            _save(d)
        used = list(dict.fromkeys(list(getattr(run, "craft_used", []) or []) + [n["id"] for n in rows]))
        try:
            run.craft_used = used
        except Exception:                                         # noqa: BLE001
            pass
        if rows or held:
            run._record({"action": "craft", "usd": 0.0,
                         "why": ("📓 this one went without craft notes (a comparison run)" if held else
                                 f"📓 used {len(rows)} craft note{'s' if len(rows) != 1 else ''}: " + " · ".join(n["do"][:60] for n in rows)),
                         "result": {"ids": [n["id"] for n in rows], "kind": kind, "held": held}})
        return text_for(rows)
    except Exception:                                             # noqa: BLE001
        return ""


# ---------- learn: what Eyes saw, what Scott kept, what fixed it ----------
def _key(words: str) -> str:
    own = re.split(r"\n(?:Style|Shape|Look|Change|Variation):", str(words or ""), maxsplit=1)[0]
    return hashlib.sha1(norm(own).encode()).hexdigest()[:12]


def _change(words: str) -> str:
    m = re.search(r"^Change:\s*(.+)$", str(words or ""), re.M)
    return m.group(1).strip()[:160] if m else ""


def observe(run, kind: str, e: dict | None, words: str = "", compare: bool = True) -> dict:
    """One 👁 check → counts on the notes this run used, the running score with/without notes, miss counts per kind of
    point; a measured need wakes its note; a 🔁 fix that raised the score keeps its wording. Never raises.
    compare=False (prompts built in code, e.g. batch): misses + fix wording count, the with/without score does not."""
    out = {"learned": [], "flagged": []}
    try:
        if not e or e.get("error") or e.get("score") is None or not settings(getattr(run, "cfg", None))["on"]:
            return out
        score, pts = int(e["score"]), [p for p in e.get("points") or [] if p.get("ok") is not None]
        with _lock():
            d = _load()
            before = json.loads(json.dumps(d["notes"]))
            rid = str(getattr(run, "id", "") or "")
            ids = set((d["runs"].get(rid) or {}).get("ids") or getattr(run, "craft_used", []) or [])
            base_all = _mean(d, kind)
            side = "on" if ids else "off"
            if compare:
                st = d["stats"].setdefault(kind, {}).setdefault(side, {"n": 0, "sum": 0})
                st["n"], st["sum"] = st["n"] + 1, st["sum"] + score
            missed = {p["kind"] for p in pts if p["ok"] is False}
            asked = {p["kind"] for p in pts}
            for n in d["notes"]:
                if n["id"] not in ids:
                    continue
                n["used"] += 1
                bar = max(LOW, n["base"] or 0)
                good = (n["cat"] in asked and n["cat"] not in missed) if n.get("cat") else score >= bar
                n["helped"] += bool(good)
                if n["used"] >= RETIRE_USED and n["helped"] == 0 and n["status"] == "live" and not n.get("flag"):
                    n["flag"] = "retire"
                    out["flagged"].append(n["id"])
            cats = d["cats"].setdefault(kind, {})
            for c in asked:
                cats[c] = (cats.get(c) or [])[-(CAT_WINDOW - 1):] + [int(c in missed)]
                if c in AUTO and len(cats[c]) >= CAT_MIN and sum(cats[c]) >= CAT_MISSES:
                    why = f"measured: 👁 missed '{c}' in {sum(cats[c])} of the last {len(cats[c])} {kind} checks"
                    note = {"kind": kind, "do": AUTO[c], "cat": c, "why": why, "when": ["#count"] if c == "count" else []}
                    old = next((x for x in d["notes"] if x["id"] == nid(kind, AUTO[c])), None)
                    if old is None:
                        row, _ = _add(d, note, "measured")
                        if row:
                            out["learned"].append(row["do"])
                    elif old["status"] == "proposed":             # a seed the numbers now ask for → live without waiting
                        old.update(status="live", source="measured", why=(old["why"] + " · " + why)[:400], base=base_all,
                                   cat=old.get("cat") or c)
                        out["learned"].append(old["do"])
            key, ch = _key(words), _change(words)
            prev = d["low"].get(key)
            if prev and ch and score > int(prev.get("score") or 0):               # the fix worked — keep its wording
                fixed = set(prev.get("cats") or []) - missed
                for n in d["notes"]:
                    if n.get("cat") in fixed and n["kind"] in (kind, "any") and ch not in n["examples"]:
                        n["examples"] = (n["examples"] + [ch])[-4:]
                d["low"].pop(key, None)
            elif score < LOW or missed:
                d["low"][key] = {"score": score, "cats": sorted(missed), "t": time.time()}
                for k in sorted(d["low"], key=lambda k: d["low"][k].get("t", 0))[:-200]:
                    d["low"].pop(k, None)
            _save(d, "measured" if (out["learned"] or out["flagged"]) else "", before)
        if out["learned"]:
            run._record({"action": "craft", "usd": 0.0, "result": {"learned": out["learned"]},
                         "why": "📓 learned from the checks — now a craft note: " + " · ".join(x[:70] for x in out["learned"])})
    except Exception:                                             # noqa: BLE001
        pass
    return out


def verdict(run_id: str, keep: bool) -> int:
    """✅ Keep / 🗑 Throw away on a run → the notes it used. Never raises."""
    try:
        with _lock():
            d = _load()
            ids = set((d["runs"].get(str(run_id)) or {}).get("ids") or [])
            hit = 0
            for n in d["notes"]:
                if n["id"] in ids:
                    n["kept" if keep else "tossed"] += 1
                    hit += 1
            if hit:
                _save(d)
            return hit
    except Exception:                                             # noqa: BLE001
        return 0


# ---------- teach: ```craft blocks in handoffs (how every later Claude session teaches the Lab) ----------
def parse_blocks(text: str) -> list[dict]:
    """```craft
    kind: picture
    when: watercolor, comic
    do: one instruction to the writer
    why: the evidence
    ```   — several notes per block, a blank line or a new `kind:` starts the next."""
    out = []
    for body in BLOCK_RX.findall(text or ""):
        cur: dict = {}
        for ln in body.splitlines() + [""]:
            m = re.match(r"^\s*(kind|when|do|why|model)\s*:\s*(.*)$", ln, re.I)
            if m and m.group(1).lower() == "kind" and cur.get("do"):
                out.append(cur)
                cur = {}
            if m:
                cur[m.group(1).lower()] = m.group(2).strip()
            elif not ln.strip() and cur.get("do"):
                out.append(cur)
                cur = {}
    return out


def handoff_dirs() -> list[Path]:
    return [config.REPO / "docs", Path.home() / "hermes" / "docs"]


def import_handoffs(dirs: list[Path] | None = None) -> dict:
    """Read every HANDOFF_*.md once (by name + size) and file its craft blocks as proposed notes. Reads only."""
    seen_f = root() / "handoffs_seen.json"
    try:
        seen = json.loads(seen_f.read_text())
    except (OSError, ValueError):
        seen = {}
    found, files = [], 0
    for d in dirs or handoff_dirs():
        for f in sorted(Path(d).glob("HANDOFF_*.md")) if Path(d).is_dir() else []:
            try:
                sig = f"{f.stat().st_size}"
                if seen.get(str(f)) == sig:
                    continue
                txt = f.read_text(errors="replace")[:200_000]
                seen[str(f)] = sig
            except OSError:
                continue
            blocks = parse_blocks(txt)
            files += bool(blocks)
            for b in blocks:
                b["why"] = (b.get("why", "") + f" [{f.name}]").strip()
                found.append(b)
    rep = add_many(found, "handoff", "import:handoffs") if found else {"added": 0, "known": 0, "skipped": 0, "ids": []}
    seen_f.write_text(json.dumps(seen))
    return {**rep, "files": files}


def seed() -> dict:
    """The lessons of 2026-11-22..25, written by Claude from the handoffs and commits → proposed, for Scott's one review."""
    try:
        rows = json.loads((Path(__file__).parent / "craft_seed.json").read_text())["notes"]
    except (OSError, ValueError, KeyError):
        return {"added": 0, "known": 0, "skipped": 0, "ids": []}
    return add_many(rows, "seed", "seed")


# ---------- the page ----------
def view() -> dict:
    d = _load()
    order = {"proposed": 0, "live": 1, "retired": 2}
    rows = sorted(d["notes"], key=lambda n: (0 if n.get("flag") else 1, order.get(n["status"], 3), n["kind"], n["added"]))
    scores = {}
    for kind, s in d["stats"].items():
        on, off = s.get("on") or {}, s.get("off") or {}
        scores[kind] = {"with": round(on["sum"] / on["n"]) if on.get("n") else None, "with_n": int(on.get("n") or 0),
                        "without": round(off["sum"] / off["n"]) if off.get("n") else None, "without_n": int(off.get("n") or 0)}
    return {"notes": rows, "scores": scores, "kinds": list(KINDS),
            "counts": {k: sum(1 for n in rows if n["status"] == k) for k in order},
            "can_undo": (root() / "changes.jsonl").exists() and bool((root() / "changes.jsonl").read_text().strip())}


def review_md() -> str:
    """⬇ one file to read on the phone or hand to a chatbot. Tick [x] = make live · [-] = retire · leave [ ] = later."""
    out = ["# 📓 Craft Book review", "", "Tick `[x]` to make a note live, `[-]` to retire it, leave `[ ]` to decide later. "
           "Upload the file back on the Craft page.", ""]
    for n in view()["notes"]:
        if n["status"] == "retired":
            continue
        out += [f"- [{'x' if n['status'] == 'live' else ' '}] `{n['id']}` **{n['kind']}**"
                + (f" · when: {', '.join(n['when'])}" if n["when"] else " · always") + f" — {n['do']}",
                f"  - why: {n['why'] or '—'} · used {n['used']} · helped {n['helped']} · kept {n['kept']} · thrown {n['tossed']}"
                + (" · ⚠ asked to retire" if n.get("flag") else "")]
    return "\n".join(out) + "\n"


def apply_review(text: str) -> dict:
    marks = dict((i, m) for m, i in re.findall(r"^- \[([ xX-])\] `([0-9a-f]{10})`", text or "", re.M))
    live = [i for i, m in marks.items() if m in "xX"]
    gone = [i for i, m in marks.items() if m == "-"]
    cur = {n["id"]: n["status"] for n in notes()}
    a = set_status([i for i in live if cur.get(i) == "proposed" or False], "live")["changed"] if live else 0
    b = set_status([i for i in gone if cur.get(i) in ("proposed", "live")], "retired")["changed"] if gone else 0
    return {"live": a, "retired": b, "read": len(marks)}
