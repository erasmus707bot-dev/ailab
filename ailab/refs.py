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


def get(root) -> list[str]:
    try:
        d = json.loads(_file(root).read_text())
    except (OSError, ValueError):
        d = {}
    xs = d.get("refs") if isinstance(d, dict) else None
    return [x for x in xs or [] if isinstance(x, str) and _ok(root, x)][:MAX_REFS]


def _save(root, xs: list[str]) -> list[str]:
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"refs": xs}))
    return xs


def pin(root, rel: str) -> dict:
    rel = str(rel or "")
    if not _ok(root, rel):
        return {"ok": False, "icon": "🖼", "message": "Only a picture in this project can be a reference."}
    xs = get(root)
    if rel in xs:
        return {"ok": True, "refs": xs}
    if len(xs) >= MAX_REFS:
        return {"ok": False, "icon": "🎭", "message": f"Up to {MAX_REFS} reference pictures — take one off first.", "refs": xs}
    return {"ok": True, "refs": _save(root, xs + [rel])}


def unpin(root, rel: str) -> dict:
    return {"ok": True, "refs": _save(root, [x for x in get(root) if x != str(rel or "")])}


def for_run(run) -> list[str]:
    """Absolute paths of the references this run sends: a character sheet's own source, else the project's cast strip."""
    root = Path(run.root)
    b = getattr(run, "batch", None) or {}
    if isinstance(b.get("refs_abs"), list):                     # 📖 M3 story shot: the cast anchors of who is in it
        return [str(x) for x in b["refs_abs"] if Path(str(x)).is_file()][:MAX_REFS]
    rels = [b["sheet"]] if b.get("sheet") and _ok(root, b["sheet"]) else get(root)
    return [str((root / r).resolve()) for r in rels]


def queue(models: list[str], local_ok: bool, venice_ok: bool) -> list[str]:
    """Reference-capable models first — local FLUX.2 only when the plan already has a local model (ComfyUI up), the
    Venice edit model only when the plan already allows Venice. Neither → the plan unchanged (words only)."""
    front = ([REF_MODELS[0]] if local_ok else []) + ([REF_MODELS[1]] if venice_ok else [])
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
