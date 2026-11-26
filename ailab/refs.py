"""🎭 Characters and references (prompt #1 M2, Scott 2026-11-25 — no training).

📌 Use as reference: 1–4 pictures per project (<project>/.shelf/refs.json, the "cast strip"). Every picture run in that
project sends them to Hermes image_make as reference_images, so the face holds (local FLUX.2 Klein ReferenceLatent, $0,
or Venice's uncensored edit model). Hermes keeps each route OFF until its identity probe passes — then the Lab says so
once and makes the picture without references.
🎭 Character sheet: one picture → front / side / three-quarter / back / face-expressions, each made with that picture as
the reference, then 👁 compares each view with the original side by side ("same person?")."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

MAX_REFS = 4
PIC = (".png", ".jpg", ".jpeg", ".webp")
REF_MODELS = ("local/flux2-klein-4b", "venice/qwen-edit-uncensored")     # Hermes LOCAL_REF_MODELS + 🔓 Venice edit
SHEET_VIEWS = [
    "front view, standing, facing the camera, full body, plain light-grey background",
    "side view in profile, full body, plain light-grey background",
    "three-quarter view, upper body, plain light-grey background",
    "back view, full body, plain light-grey background",
    "close-up of the face, head and shoulders, a gentle smile, plain light-grey background",
]
# live 2026-11-25: with only "the person in this picture", 3 of 5 views of an anime girl came back as photo-real strangers
# (and the four-expressions view as six different people). The sheet now names who she is and keeps the art style.
SHEET_WORDS = "the same character as in the reference picture — same face, hair, body, clothes and the same art style"
SAME_Q = ["Do the two pictures side by side show the same person — the same face, hair colour and hair style?",
          "Is the person on the right wearing the same clothes as the person on the left?"]


def _file(root) -> Path:
    return Path(root) / ".shelf" / "refs.json"


def _ok(root, rel: str) -> bool:
    from . import shelf
    p = shelf._safe(root, rel)
    return bool(p and p.suffix.lower() in PIC and p.is_file())


MAX_ACTIVE = 12                       # 🗂 M4: pictures in use at once; each run still sends ≤ MAX_REFS (Venice ≤ 3)
ROLES = ("start", "who", "style", "scene", "auto")
ROLE_NAME = {"start": "🖼 Start from", "who": "👤 Who", "style": "🎨 Style", "scene": "🧱 Scene", "auto": "❔ Lab decides"}
ROLE_ORDER = {"start": 0, "who": 1, "style": 2, "scene": 3, "auto": 4}


def _load(root) -> dict:
    try:
        d = json.loads(_file(root).read_text())
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    pool = d.get("pool") if isinstance(d.get("pool"), dict) else {}
    return {"refs": [x for x in d.get("refs") or [] if isinstance(x, str)], "pool": pool}


def get(root) -> list[str]:
    return [x for x in _load(root)["refs"] if _ok(root, x)][:MAX_ACTIVE]


def _save(root, xs: list[str], pool: dict | None = None) -> list[str]:
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    d = _load(root)
    for x in xs:                                                  # every picture ever in use stays in the 🗂 pool
        d["pool"].setdefault(x, {"role": "auto", "at": time.time()})
    if pool is not None:
        d["pool"] = pool
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"refs": xs, "pool": d["pool"]}))
    tmp.replace(f)
    return xs


def pin(root, rel: str, role: str = "", frm: str = "") -> dict:
    rel = str(rel or "")
    if not _ok(root, rel):
        return {"ok": False, "icon": "🖼", "message": "Only a picture in this project can be a reference."}
    xs, d = get(root), _load(root)
    pool = d["pool"]
    e = pool.setdefault(rel, {"role": "auto", "at": time.time()})
    if frm:
        e["from"] = frm
    if role in ROLES:
        if role == "start":                                       # only one 🖼 Start from — the old one goes back to ❔
            for k, v in pool.items():
                if k != rel and v.get("role") == "start":
                    v["role"] = "auto"
        e["role"] = role
    if rel not in xs and len(xs) >= MAX_ACTIVE:
        return {"ok": False, "icon": "🎭", "message": f"Up to {MAX_ACTIVE} pictures in use — take one off first.", "refs": xs}
    xs = xs if rel in xs else xs + [rel]
    return {"ok": True, "refs": _save(root, xs, pool), "pool": pool_view(root)}


def unpin(root, rel: str) -> dict:
    """✕ Off: no longer used by new pictures. It stays in the 🗂 pool (with its ★ record) to switch back on."""
    return {"ok": True, "refs": _save(root, [x for x in get(root) if x != str(rel or "")]), "pool": pool_view(root)}


def set_role(root, rel: str, role: str) -> dict:
    if role not in ROLES:
        return {"ok": False, "icon": "❓", "message": "Unknown role."}
    d = _load(root)
    if rel not in d["pool"]:
        return {"ok": False, "icon": "🗂", "message": "That picture isn't in the source pool."}
    if role == "start":
        for v in d["pool"].values():
            if v.get("role") == "start":
                v["role"] = "auto"
    d["pool"][rel]["role"] = role
    d["pool"][rel]["by"] = "scott"
    _save(root, get(root), d["pool"])
    return {"ok": True, "refs": get(root), "pool": pool_view(root)}


def credit(root, rels: list[str], stars: int, old: int = 0) -> None:
    """⭐ → the sources that made it: a re-rate replaces the old stars, never counts twice."""
    d, hit = _load(root), False
    for r in rels or []:
        e = d["pool"].get(r)
        if not e:
            continue
        hit = True
        if old:
            e["stars_sum"] = max(0, int(e.get("stars_sum") or 0) - old)
            e["stars_n"] = max(0, int(e.get("stars_n") or 0) - 1)
        if stars:
            e["stars_sum"] = int(e.get("stars_sum") or 0) + stars
            e["stars_n"] = int(e.get("stars_n") or 0) + 1
    if hit:
        _save(root, get(root), d["pool"])


def avg(e: dict) -> float | None:
    n = int(e.get("stars_n") or 0)
    return round(int(e.get("stars_sum") or 0) / n, 1) if n else None


def pool_view(root) -> list[dict]:
    d, on = _load(root), set(get(root))
    rows = [{"path": k, "role": v.get("role") or "auto", "by": v.get("by") or "", "from": v.get("from") or "",
             "on": k in on, "avg": avg(v), "n": int(v.get("stars_n") or 0), "at": v.get("at") or 0}
            for k, v in d["pool"].items() if _ok(root, k)]
    return sorted(rows, key=lambda r: (not r["on"], -(r["at"] or 0)))


def pick(rels: list[str], pool: dict, cap: int = MAX_REFS) -> list[str]:
    """🗂 Smart pick: ≤ 1 🖼 Start from first, then 👤 Who, 🎨 Style, 🧱 Scene, ❔ — inside a role, the best ★ record
    first (no record counts as 3★), then the newest. Never more than `cap`."""
    def key(r):
        e = pool.get(r) or {}
        a = avg(e)
        return (ROLE_ORDER.get(e.get("role") or "auto", 4), -(a if a is not None else 3.0), -(e.get("at") or 0))
    out, start = [], False
    for r in sorted(rels, key=key):
        if (pool.get(r) or {}).get("role") == "start":
            if start:
                continue
            start = True
        out.append(r)
    return out[:cap]


def start_source(root) -> str:
    """The 🖼 Start from picture in use, or ""."""
    d, on = _load(root), set(get(root))
    return next((k for k, v in d["pool"].items() if k in on and v.get("role") == "start"), "")


EDIT_WORDS = ("Edit the given picture: keep the same subject, its shape, details, colours, light and layout. "
              "Change only this: ")


def note_made(root, rel: str, sources: list[str]) -> None:
    """🗂 Which sources made this picture — so a ⭐ from 📚 Library (no run on screen) still credits them."""
    f = Path(root) / ".shelf" / "made_from.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    d[str(rel)] = [str(x) for x in sources][:MAX_REFS]
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    tmp.replace(f)


def made_from(root, rel: str) -> list[str]:
    try:
        d = json.loads((Path(root) / ".shelf" / "made_from.json").read_text())
    except (OSError, ValueError):
        return []
    xs = d.get(str(rel)) if isinstance(d, dict) else None
    return [x for x in xs or [] if isinstance(x, str)]


GUESS_PTS = [{"q": "Is one person or character the clear main subject, shown large?", "what": "person", "kind": "role", "want": True},
             {"q": "Is this mostly a place, room or landscape?", "what": "place", "kind": "role", "want": True}]


def guess_roles(run, root, rels: list[str]) -> None:
    """❔ → a role, by the local 👁 ($0), once per picture (Scott 2026-11-25 pick 1: the Lab guesses, he can change it)."""
    from . import eyes                                            # noqa: PLC0415
    d, changed = _load(root), False
    for r in rels:
        e = d["pool"].get(r)
        if not e or e.get("role") != "auto" or e.get("guessed"):
            continue
        try:
            res = eyes.ask(run, (Path(root) / r).read_bytes(), GUESS_PTS, label=f"source {Path(r).name}, to choose its job")
        except Exception as x:                                    # noqa: BLE001
            if type(x).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
                raise
            res = {"error": str(x)}
        e["guessed"] = True
        changed = True
        if res.get("error"):
            continue
        ok = {p["what"]: p["ok"] for p in res.get("points") or []}
        e["role"] = "who" if ok.get("person") else "scene" if ok.get("place") else "style"
    if changed:
        _save(root, get(root), d["pool"])


MAX_SOURCE = 8_000_000
_MAGIC = ((b"\xff\xd8\xff", ".jpg"), (b"\x89PNG\r\n\x1a\n", ".png"))


def upload(root, data_url: str) -> dict:
    """📥 Source (Scott 2026-11-25): his own picture from his computer → <project>/sources/ → 📌 pinned as a reference, so
    the next 🖼 picture starts from it (local FLUX.2 Klein / 🔓 Venice edit). The page shrinks it to ≤ 2048 px first."""
    import base64
    import time
    m = re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", str(data_url or ""))
    if not m:
        return {"ok": False, "icon": "🖼", "message": "That isn't a picture the Lab can use (PNG, JPEG or WebP)."}
    raw = base64.b64decode(m.group(1))
    ext = next((e for sig, e in _MAGIC if raw.startswith(sig)), ".webp" if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" else "")
    if not ext or len(raw) > MAX_SOURCE:
        return {"ok": False, "icon": "🖼", "message": "That picture is too big or not a real picture file."}
    xs = get(root)
    if len(xs) >= MAX_ACTIVE:
        return {"ok": False, "icon": "🎭", "message": f"Up to {MAX_ACTIVE} pictures in use — take one off first.", "refs": xs}
    d = Path(root) / "sources"
    d.mkdir(parents=True, exist_ok=True)
    stem, n = time.strftime("source-%Y%m%d-%H%M%S"), 2
    f = d / (stem + ext)
    while f.exists():
        f, n = d / f"{stem}-{n}{ext}", n + 1
    f.write_bytes(raw)
    r = pin(root, f"sources/{f.name}", role="start", frm="upload")
    if r.get("ok"):
        r["path"] = f"sources/{f.name}"
    return r


def unpin(root, rel: str) -> dict:
    return {"ok": True, "refs": _save(root, [x for x in get(root) if x != str(rel or "")])}


def for_run(run) -> list[str]:
    """Absolute paths of the references this run sends: a character sheet's own source, else the project's cast strip."""
    root = Path(run.root)
    b = getattr(run, "batch", None) or {}
    if isinstance(b.get("refs_abs"), list):                     # 📖 M3 story shot: the cast anchors of who is in it
        return [str(x) for x in b["refs_abs"] if Path(str(x)).is_file()][:MAX_REFS]
    if b.get("sheet") and _ok(root, b["sheet"]):
        rels = [b["sheet"]]
    else:
        rels = get(root)
        if len(rels) > 1:
            guess_roles(run, root, rels)
        pool = _load(root)["pool"]
        rels = pick(rels, pool)
        run.src_roles = {r: (pool.get(r) or {}).get("role") or "auto" for r in rels}     # 🗂 named on the Steps line
    return [str((root / r).resolve()) for r in rels]


def queue(models: list[str], local_ok: bool, venice_ok: bool, edit_first: bool = False) -> list[str]:
    """Reference-capable models first — local FLUX.2 only when the plan already has a local model (ComfyUI up), the
    Venice edit model only when the plan already allows Venice. Neither → the plan unchanged (words only).
    edit_first (🖼 Start from in use, Scott 2026-11-25 pick 1): the Venice edit model changes the picture it is given,
    FLUX.2 only takes it as a hint — so it goes first."""
    loc, ven = ([REF_MODELS[0]] if local_ok else []), ([REF_MODELS[1]] if venice_ok else [])
    front = ven + loc if edit_first else loc + ven
    return front + [m for m in models if m not in front]


# ---------- 🎭 character sheet ----------
def sheet_task(base: str, k: int, who: str = "", look: str = "") -> tuple[str, str]:
    """One view's task. `who` (from describe()) replaces the run's own first line; `look` adds a Look: line."""
    v = SHEET_VIEWS[k % len(SHEET_VIEWS)]
    first, _, rest = (base or "").partition("\n")
    who = (who or first).strip() or "the character"
    lines = [x for x in rest.split("\n") if x.strip() and not (look and x.startswith("Look:"))]
    if look:
        lines.append(f"Look: {look}")
    return f"{who}, {SHEET_WORDS}, {v}" + ("\n" + "\n".join(lines) if lines else ""), v.split(",")[0]


_VERB = re.compile(r"\s+(?:who\s+)?(?:stands|sits|is|are|holds|holding|standing|sitting|walks|walking|lies|lying|leans|"
                   r"leaning|poses|posing|kneels|kneeling|looks|looking)\b.*$", re.I)


def from_caption(caption: str) -> str:
    """"A single anime-style girl with dark hair stands under… She wears a white top and a black skirt." →
    "a single anime-style girl with dark hair, wearing a white top and a black skirt"."""
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", str(caption or "")) if x.strip()]
    if not sents:
        return ""
    who = _VERB.sub("", sents[0].rstrip(".")).strip(" ,")
    who = re.sub(r"^(the|this) (image|picture|illustration) (shows|depicts|displays)\s+", "", who, flags=re.I)
    wear = next((x for x in sents if re.search(r"\bwear(s|ing)\b", x, re.I)), "")
    m = re.search(r"\bwear(?:s|ing)\s+(.+?)[.;]?$", wear, re.I)
    out = who[:1].lower() + who[1:] + (f", wearing {m.group(1).strip()}" if m else "")
    return out[:300]


def describe(run, rel: str) -> tuple[str, str]:
    """Who is in the sheet's source picture → (who, look). His own words + Look line when the picture was ✅ kept or
    made by a run the shelf knows; otherwise the local eyes describe it ($0). ("", "") when neither works."""
    from . import eyes, shelf                                     # noqa: PLC0415
    root = Path(run.root)
    try:
        v = shelf.view(root)
        rows = list(v.get("kept") or []) + list(v.get("tossed") or [])
    except Exception:                                            # noqa: BLE001
        rows = []
    for x in reversed(rows):
        if rel in (x.get("files") or []):
            task = str(x.get("task") or "")
            look = next((ln[5:].strip() for ln in task.split("\n") if ln.startswith("Look:")), "")
            own = task.split("\n")[0].strip()
            if own:
                return own, look
    try:
        raw = (root / rel).read_bytes()
    except OSError:
        return "", ""
    e = eyes.ask(run, raw, [], label="the source picture, to describe who is in it")
    return from_caption(e.get("caption", "")), ""


def side_by_side(a: bytes, b: bytes, h: int = 512) -> bytes:
    """The two pictures next to each other, same height, as one JPEG (ffmpeg — the Lab has no Python picture library)."""
    import shutil
    import subprocess
    import tempfile
    ff = shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("ffmpeg isn't installed")
    with tempfile.TemporaryDirectory() as d:
        pa, pb, out = Path(d) / "a", Path(d) / "b", Path(d) / "pair.jpg"
        pa.write_bytes(a)
        pb.write_bytes(b)
        flt = f"[0:v]scale=-2:{h},pad=iw+16:ih:0:0:white[l];[1:v]scale=-2:{h}[r];[l][r]hstack=inputs=2"
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(pa), "-i", str(pb), "-filter_complex", flt,
                            "-frames:v", "1", "-q:v", "3", str(out)], capture_output=True, timeout=40, check=False)
        if not out.exists() or out.stat().st_size < 200:
            raise RuntimeError((r.stderr or b"").decode(errors="replace")[:160] or "no picture came out")
        return out.read_bytes()


def same_face(run, src: bytes, view: bytes, label: str) -> dict:
    """👁 the original on the left, the new view on the right → {"score", "same", "missing", ...} or {"error"}."""
    from . import eyes
    try:
        pair = side_by_side(src, view)
    except Exception as e:                                       # noqa: BLE001
        return {"error": f"Couldn't put the two pictures side by side: {e}"[:200]}
    pts = [{"q": SAME_Q[0], "want": True, "what": "the same face and hair", "kind": "face"},
           {"q": SAME_Q[1], "want": True, "what": "the same clothes", "kind": "outfit"}]
    e = eyes.ask(run, pair, pts, label)
    if not e.get("error"):
        e["same"] = bool(e["points"] and e["points"][0].get("ok"))
    return e
