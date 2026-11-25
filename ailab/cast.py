"""🎭 Global cast + 🎲 Design a cast (build prompt #2 R1, Scott 2026-11-25).

"The Lab designs the characters itself and makes them visually distinct on purpose (hair, build, outfit colours) so the
video model and the 👁 check can tell them apart." · "The cast library is shared and global." · Starting a story or a
rebuild asks "reuse a cast or make a new one".

The store is Hermes's (asset-library characters, MCP cast_list / cast_get / cast_make / cast_pin) — the Lab keeps no
second copy. A project only remembers which cast it chose: <project>/.shelf/cast.json {"cast", "ids"}.

🎲 Design a cast (N = 2–4): code picks traits that differ on purpose on every axis (validated) → the uncensored writer
names them → one anchor picture each (words only, never the project's 📌 references) → 👁 "can you tell them apart?" on
each pair side by side, the closest pair redesigned (≤ 2 rounds) → prompt #1 M2 character sheet per person (anchor as
the reference, 👁 same-face per view) → each saved into the global cast. Invented adults only; no text on the art.
"""
from __future__ import annotations

import base64
import json
import random
import re
import time
from itertools import combinations
from pathlib import Path

MIN_N, MAX_N, DEFAULT_N = 2, 4, 2
REDESIGN_ROUNDS = 2
POOLS = {
    "hair_colour": ["jet black", "platinum blonde", "copper red", "chestnut brown", "silver grey", "honey blonde", "teal-dyed"],
    "hair_length": ["a buzz cut", "shoulder-length hair", "a long braid", "short curly hair", "a high ponytail",
                    "an undercut with a long top"],
    "skin_tone": ["deep brown", "pale", "olive", "warm tan", "light brown", "freckled fair"],
    "build": ["broad and muscular", "slim and wiry", "stocky", "lanky", "curvy", "athletic"],
    "height": ["very tall", "short", "average height", "tall", "petite"],
    "outfit_colour": ["red", "royal blue", "forest green", "mustard yellow", "black", "white", "purple", "orange"],
    "signature": ["round glasses", "a red bandana", "a yellow headband", "fingerless gloves", "a striped scarf",
                  "a baseball cap", "big hoop earrings", "a chunky wristwatch"],
}
AXES = tuple(POOLS)
MUST_DIFFER = ("hair_colour", "outfit_colour")       # never shared — the two things a video model mixes up first
MIN_DIFF = 5                                         # of the 7 axes, per pair
WHO = ["woman", "man"]
NAMES = ["Mara", "Jun", "Tess", "Kofi", "Ines", "Rafe", "Lena", "Omar", "Suki", "Dax", "Nell", "Arlo"]
PICTURE_WORDS = ("full body, standing, facing the camera, arms relaxed, plain light-grey background, even soft light, "
                 "realistic photo")
APART_PTS = [
    {"q": "Are these clearly two different people, with different hair colour, different body build and different clothes?",
     "want": True, "what": "two clearly different people", "kind": "apart"},
    {"q": "Could someone easily mistake the person on the left for the person on the right?",
     "want": False, "what": "not easy to mix up", "kind": "apart"},
]


# ---------- briefs ----------
def design(n: int = DEFAULT_N, seed: int | None = None) -> list[dict]:
    """N briefs whose traits differ on purpose: every axis drawn without repeats across the cast."""
    n = max(MIN_N, min(MAX_N, int(n or DEFAULT_N)))
    rnd = random.Random(seed)
    cols = {ax: rnd.sample(POOLS[ax], n) for ax in AXES}
    names = rnd.sample(NAMES, n)
    who = [WHO[(i + rnd.randrange(2)) % 2] for i in range(n)]
    if n >= 2 and len(set(who)) == 1:
        who[-1] = WHO[1 - WHO.index(who[0])]
    return [{"name": names[i], "who": who[i], "age": rnd.randint(22, 45),
             "traits": {ax: cols[ax][i] for ax in AXES}} for i in range(n)]


def diff(a: dict, b: dict) -> int:
    return sum(a["traits"].get(ax) != b["traits"].get(ax) for ax in AXES)


def validate(briefs: list[dict]) -> list[str]:
    """Plain problems; [] = the cast is distinct enough on paper."""
    out = []
    if not MIN_N <= len(briefs) <= MAX_N:
        out.append(f"a cast is {MIN_N} to {MAX_N} people")
    for b in briefs:
        if int(b.get("age") or 0) < 18:
            out.append(f"{b.get('name', '?')} must be an adult")
        miss = [ax for ax in AXES if not b.get("traits", {}).get(ax)]
        if miss:
            out.append(f"{b.get('name', '?')} has no {', '.join(miss)}")
    if len({b.get("name") for b in briefs}) < len(briefs):
        out.append("two people share a name")
    for a, b in combinations(briefs, 2):
        same = [ax for ax in MUST_DIFFER if a["traits"].get(ax) == b["traits"].get(ax)]
        if same:
            out.append(f"{a['name']} and {b['name']} share {' and '.join(x.replace('_', ' ') for x in same)}")
        elif diff(a, b) < MIN_DIFF:
            out.append(f"{a['name']} and {b['name']} differ on only {diff(a, b)} of {len(AXES)} traits")
    return out


def redesign(briefs: list[dict], i: int, seed: int | None = None) -> list[dict]:
    """Person i gets new traits on every axis, each unused by the rest of the cast (name, who and age kept)."""
    rnd = random.Random(seed)
    others = [b for k, b in enumerate(briefs) if k != i]
    new = dict(briefs[i])
    t = {}
    for ax in AXES:
        taken = {b["traits"][ax] for b in others} | {briefs[i]["traits"][ax]}
        free = [v for v in POOLS[ax] if v not in taken] or [v for v in POOLS[ax] if v not in {b["traits"][ax] for b in others}]
        t[ax] = rnd.choice(free)
    new["traits"] = t
    new["redesigned"] = int(briefs[i].get("redesigned") or 0) + 1
    out = list(briefs)
    out[i] = new
    return out


def brief_text(b: dict) -> str:
    t = b["traits"]
    return (f"{b['name']}: a {b['age']}-year-old {b.get('who', 'person')}, {t['height']}, {t['build']} build, "
            f"{t['skin_tone']} skin, {t['hair_colour']} hair in {t['hair_length']}, wearing a {t['outfit_colour']} "
            f"outfit, with {t['signature']}")


def picture_prompt(b: dict) -> str:
    return f"{brief_text(b).split(': ', 1)[1]}, {PICTURE_WORDS}"


def cast_name(briefs: list[dict]) -> str:
    return " & ".join(b["name"] for b in briefs)[:40]


# ---------- the project's chosen cast ----------
def _file(root) -> Path:
    return Path(root) / ".shelf" / "cast.json"


def chosen(root) -> dict:
    try:
        d = json.loads(_file(root).read_text())
    except (OSError, ValueError):
        d = {}
    return {"cast": str(d.get("cast") or ""), "ids": [x for x in d.get("ids") or [] if isinstance(x, str)][:MAX_N]}


def choose(root, name: str, ids: list[str]) -> dict:
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    d = {"cast": str(name or "")[:40], "ids": [str(x) for x in ids or []][:MAX_N], "at": time.time()}
    f.write_text(json.dumps(d))
    return d


def pull(mcp, root, project_id: str, name: str, ids: list[str]) -> dict:
    """♻️ Reuse a cast: each character is pinned to this project in the global store, then remembered here."""
    ids = [str(x) for x in ids or [] if str(x).startswith("c-")][:MAX_N]
    if not ids:
        return {"ok": False, "icon": "🎭", "message": "Pick a cast first."}
    got = []
    for cid in ids:
        r = mcp.call("cast_pin", {"id": cid, "project": project_id})
        got.append({"id": r["id"], "name": r["name"]})
    return {"ok": True, "chosen": choose(root, name or " & ".join(g["name"] for g in got), [g["id"] for g in got]),
            "characters": got}


def import_refs(mcp, root, project_id: str) -> dict:
    """⬆ This project's 📌 reference pictures → the global cast, by copy (the originals stay where they are)."""
    from . import refs
    rels = refs.get(root)
    if not rels:
        return {"ok": False, "icon": "📌", "message": "This project has no 📌 reference pictures to copy."}
    out = []
    for rel in rels:
        stem = re.sub(r"[^A-Za-z0-9]+", " ", Path(rel).stem).strip().title()[:30] or "Character"
        r = mcp.call("cast_make", {"name": stem, "age": 18, "anchor_b64": base64.b64encode((Path(root) / rel).read_bytes()).decode(),
                                   "brief": f"Copied from 📌 references in project {project_id} ({rel}). Age: please check.",
                                   "project": project_id, "source": f"ailab refs:{project_id}/{rel}"})
        out.append({"id": r["id"], "name": r["name"], "from": rel})
    return {"ok": True, "copied": out}


def assets_root() -> Path:
    import os
    return Path(os.environ.get("HERMES_DATA", str(Path.home() / "hermes-data"))).expanduser() / "assets"


def picture(path: str) -> tuple[bytes, str]:
    """A cast thumbnail for the page: (bytes, type) only for a picture inside <hermes-data>/assets/c-*/, else (b'', '')."""
    try:
        rp, root = Path(path).resolve(strict=True), assets_root().resolve()
    except (OSError, RuntimeError):
        return b"", ""
    ct = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(rp.suffix.lower())
    rel = rp.relative_to(root).parts if root in rp.parents else ()
    if not ct or len(rel) < 3 or not rel[0].startswith("c-") or rp.stat().st_size > 12 * 1024 * 1024:
        return b"", ""
    return rp.read_bytes(), ct


# ---------- 🎲 the design run ----------
def _names_from_writer(run, briefs: list[dict]) -> list[dict]:
    from . import makers
    want = "\n".join(f"{i + 1}. {brief_text(b).split(': ', 1)[1]}" for i, b in enumerate(briefs))
    text, _ = makers.write(run, "You name invented characters. Reply with one short, distinct first name per line, "
                                "numbered, nothing else. Each name must start with a different letter.",
                           want, 60, "Naming the cast", "lab-cast")
    names = [re.sub(r"^[\s\d.)-]+", "", ln).strip().split(" ")[0].strip(",.;:*") for ln in (text or "").splitlines()]
    names = [x for x in names if re.fullmatch(r"[A-Za-z][A-Za-z'-]{1,15}", x or "")]
    if len(names) >= len(briefs) and len({x[0].lower() for x in names[:len(briefs)]}) == len(briefs):
        return [{**b, "name": names[i].title()} for i, b in enumerate(briefs)]
    return briefs


def _anchor(run, b: dict, folder: str) -> dict:
    from . import makers
    return makers.make_picture(run, picture_prompt(b), "2:3", f"{folder}/{makers.slug(b['name'])}-anchor-{b.get('redesigned', 0)}",
                               name=f"{b['name']} anchor")


def _apart(run, pa: dict, pb: dict, a: dict, b: dict) -> dict:
    from . import eyes, refs
    try:
        pair = refs.side_by_side((run.root / pa["path"]).read_bytes(), (run.root / pb["path"]).read_bytes())
    except Exception as e:                                       # noqa: BLE001
        return {"error": f"Couldn't put {a['name']} and {b['name']} side by side: {e}"[:200]}
    e = eyes.ask(run, pair, APART_PTS, f"{a['name']} next to {b['name']}")
    if not e.get("error"):
        e["apart"] = bool(e["points"]) and all(p.get("ok") is not False for p in e["points"]) and e["points"][0].get("ok") is True
    return e


def run(run) -> None:
    """The whole 🎲 Design a cast run (Run.loop handles Stopped / SpendBlocked / PrivacyRefused)."""
    from . import eyes, picture, refs
    b = run.batch
    if not run.connected:
        run.state, run.why = "failed", "🔌 Pictures and the cast library are Hermes's — switch the Lab to connected mode."
        return
    seed = int(b.get("seed") or time.time())
    b["seed"] = seed
    folder = f"pictures/cast-{time.strftime('%Y%m%d-%H%M%S')}"
    picture.stage(run, "🎲", f"Designing a cast of {b['n']} — different on purpose")
    briefs = b.get("briefs") or design(b["n"], seed)
    if not b.get("briefs"):
        try:
            briefs = _names_from_writer(run, briefs)
        except Exception as e:                                   # noqa: BLE001 — names are a nicety
            if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
                raise
    probs = validate(briefs)
    rounds = 0
    while probs and rounds < 6:                                  # only odd writer names can trip this — fix on paper
        briefs, rounds = redesign(briefs, len(briefs) - 1, seed + rounds), rounds + 1
        probs = [p for p in validate(briefs) if "name" not in p]
    b["briefs"] = briefs
    run._record({"action": "cast", "why": "🎲 cast on paper: " + " · ".join(brief_text(x) for x in briefs),
                 "result": {"briefs": briefs, "problems": probs}, "usd": 0.0})
    run.save()

    # 1 · one anchor each
    anchors: dict[int, dict] = {}
    for i, br in enumerate(briefs):
        b["now"] = i
        pic = _anchor(run, br, folder)
        if pic.get("error"):
            run.state, run.why = "failed", f"🎨 {br['name']}'s picture didn't come back: {pic['error']}"
            return
        anchors[i] = pic
        b["items"].append({"path": pic["path"], "k": i, "variation": f"🎭 {br['name']} — anchor", "usd": pic.get("usd", 0), "kind": "picture"})
        run.save()

    # 2 · 👁 can you tell them apart? closest pair first, redesign the second person of a failing pair
    checks = []
    if eyes.on(run):
        pairs = sorted(combinations(range(len(briefs)), 2), key=lambda p: diff(briefs[p[0]], briefs[p[1]]))
        for i, j in pairs:
            for rnd_ in range(REDESIGN_ROUNDS + 1):
                e = _apart(run, anchors[i], anchors[j], briefs[i], briefs[j])
                if e.get("error"):
                    eyes.record(run, "cast", e)
                    checks.append({"pair": [briefs[i]["name"], briefs[j]["name"]], "error": e["error"]})
                    break
                checks.append({"pair": [briefs[i]["name"], briefs[j]["name"]], "apart": e["apart"], "score": e.get("score"),
                               "round": rnd_})
                if e["apart"] or rnd_ == REDESIGN_ROUNDS:
                    break
                briefs = redesign(briefs, j, seed + 100 + rnd_)
                b["briefs"] = briefs
                run._record({"action": "cast", "why": f"🎲 👁 mixed up {briefs[i]['name']} and {briefs[j]['name']} — redesigned "
                             f"{briefs[j]['name']}: {brief_text(briefs[j]).split(': ', 1)[1]}", "result": {"brief": briefs[j]}, "usd": 0.0})
                pic = _anchor(run, briefs[j], folder)
                if pic.get("error"):
                    break
                anchors[j] = pic
                b["items"].append({"path": pic["path"], "k": j, "variation": f"🎭 {briefs[j]['name']} — anchor (redesign {rnd_ + 1})",
                                   "usd": pic.get("usd", 0), "kind": "picture"})
                run.save()
    else:
        checks.append({"skipped": "👁 is off — the tell-apart check didn't run"})
    b["apart"] = checks
    final: dict[tuple, dict] = {}                                # the last look at each pair decides it
    for c in checks:
        if "pair" in c and "apart" in c:
            final[tuple(c["pair"])] = c
    ok_pairs = [c for c in final.values() if c["apart"]]
    bad_pairs = [c for c in final.values() if not c["apart"]]
    run._record({"action": "eyes", "why": f"🎭 tell-apart check: {len(ok_pairs)} of {len(ok_pairs) + len(bad_pairs)} pairs pass"
                 + (f" — still too alike: {', '.join(' & '.join(c['pair']) for c in bad_pairs)}" if bad_pairs else ""),
                 "result": {"checks": checks}, "usd": 0.0})

    # 3 · character sheet per person (prompt #1 M2: anchor as the reference, 👁 same face per view)
    sheets: dict[int, list[str]] = {}
    same: dict[int, int] = {}
    base = run.task
    try:
        for i, br in enumerate(briefs):
            sheets[i], same[i] = [], 0
            b["sheet"] = anchors[i]["path"]
            src = (run.root / anchors[i]["path"]).read_bytes()
            for k in range(len(refs.SHEET_VIEWS)):
                task_k, v = refs.sheet_task(brief_text(br).split(": ", 1)[1], k)
                run.task, run.state, run.why = task_k, "running", ""
                before = len(run.pictures)
                try:
                    picture.run(run)
                except Exception as e:                           # noqa: BLE001 — one view lost never ends the cast
                    if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
                        raise
                if len(run.pictures) <= before:
                    continue
                pic = run.pictures[-1]
                it = {"path": pic["path"], "k": i, "variation": f"🎭 {br['name']} — {v}", "usd": pic.get("usd", 0), "kind": "picture"}
                if eyes.on(run):
                    e = refs.same_face(run, src, (run.root / pic["path"]).read_bytes(), f"{br['name']} {v} next to the anchor")
                    it["eyes"] = {x: e.get(x) for x in ("score", "missing", "same", "error") if e.get(x) is not None}
                    same[i] += bool(e.get("same"))
                b["items"].append(it)
                sheets[i].append(pic["path"])
                run.save()
    finally:
        run.task = base
        b.pop("sheet", None)

    # 4 · into the global cast (Hermes store), and this project remembers its cast
    name = cast_name(briefs)
    saved, failed = [], []
    for i, br in enumerate(briefs):
        try:
            r = run.lab.mcp.call("cast_make", {
                "name": br["name"], "age": br["age"], "brief": brief_text(br), "traits": br["traits"],
                "anchor_b64": base64.b64encode((run.root / anchors[i]["path"]).read_bytes()).decode(),
                "sheet_b64": [base64.b64encode((run.root / p).read_bytes()).decode() for p in sheets.get(i, [])][:8],
                "casts": [name], "project": run.project["id"], "source": f"ailab cast design:{run.project['id']}"})
            saved.append({"id": r["id"], "name": br["name"], "views": len(sheets.get(i, [])), "same": same.get(i, 0)})
        except Exception as e:                                   # noqa: BLE001
            if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
                raise
            failed.append(f"{br['name']}: {getattr(e, 'message', '') or e}"[:160])
    if saved:
        choose(run.root, name, [s["id"] for s in saved])
    b["saved"] = saved
    b["now"] = b["n"]
    cost = sum(float(x.get("usd") or 0) for x in b["items"])
    if not saved:
        run.state, run.why = "failed", "🎭 The cast pictures were made but none reached the global cast: " + "; ".join(failed)
        picture.stage(run, "❌", "Not saved")
        return
    run.state = "done"
    run.why = (f"🎭 Cast “{name}” designed and saved to the global cast (every project can reuse it): "
               + " · ".join(f"{s['name']} ({s['views']} sheet views, 👁 same face {s['same']}/{s['views']})" for s in saved)
               + f". Tell-apart: {len(ok_pairs)}/{len(ok_pairs) + len(bad_pairs)} pairs pass. ${cost:.3f}."
               + (f" ⚠️ Still too alike: {', '.join(' & '.join(c['pair']) for c in bad_pairs)}." if bad_pairs else "")
               + (f" Not saved: {'; '.join(failed)}" if failed else ""))
    picture.stage(run, "✅", "Cast ready")
