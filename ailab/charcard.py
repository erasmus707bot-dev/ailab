"""⭐ Make a character + 📇 Characters shelf (asset library M1, Scott 2026-11-25 — OUTLINE_2026-11-24_asset-library-build.md).

Any picture the Lab made in a project → name + age + a few words → a character card in Hermes's global cast library
(MCP cast_make; the store is <hermes-data>/assets/c-*/, no second copy here). Optionally the new character joins this
project's cast at once, so the next picture keeps that face (the 📌 cast route that won the M0 identity probe).

Rules: invented characters only (Hermes refuses real people until the M8 permissions review); age is required and
must be 18 or over (checked here before anything is sent, and again by Hermes). Nothing here spends.
"""
from __future__ import annotations

from pathlib import Path

from . import cast

PIC_EXT = (".png", ".jpg", ".jpeg", ".webp")
NAME_MAX, BRIEF_MAX = 40, 600


class CharError(Exception):
    def __init__(self, message: str, icon: str = "🎭"):
        super().__init__(message)
        self.message, self.icon = message, icon


def _picture(root: Path, rel: str) -> Path:
    rel = str(rel or "").lstrip("/")
    if not rel or any(part.startswith(".") for part in rel.split("/")) or not rel.lower().endswith(PIC_EXT):
        raise CharError("Pick a picture from this project.", "🖼")
    root = Path(root).resolve()
    p = (root / rel).resolve()
    if root not in p.parents or not p.is_file():
        raise CharError("That picture isn't in this project.", "🖼")
    return p


def check(name, age, brief) -> tuple[str, int, str]:
    name = " ".join(str(name or "").split())[:NAME_MAX]
    if not name:
        raise CharError("Give the character a name.", "✏️")
    try:
        age = int(str(age).strip())
    except (TypeError, ValueError):
        raise CharError("Every character needs an age — 18 or over.", "🔞") from None
    if age < 18 or age > 120:
        raise CharError("Characters are adults only — age 18 or over.", "🔞")
    return name, age, " ".join(str(brief or "").split())[:BRIEF_MAX]


def make_from(mcp, root, project_id: str, rel: str, name, age, brief="", use_here: bool = True) -> dict:
    """⭐ This picture → a new character card (anchor = the picture). use_here: join this project's cast too."""
    name, age, brief = check(name, age, brief)
    p = _picture(root, rel)
    r = mcp.call("cast_make", {"name": name, "age": age, "brief": brief or f"{name}, {age}.",
                               "anchor_b64": cast._b64(p), "project": project_id,
                               "source": f"ailab result:{project_id}/{rel}"[:200]})
    out = {"ok": True, "id": r["id"], "name": r["name"], "anchor_path": r.get("anchor_path", ""), "joined": False}
    if use_here:
        out.update(join(root, r["id"], r["name"]))
    return out


def join(root, cid: str, name: str) -> dict:
    """Add one character to this project's cast (max cast.MAX_N faces at once)."""
    ch = cast.chosen(root)
    ids = list(ch["ids"])
    if cid in ids:
        return {"joined": True, "cast": ch["cast"], "ids": ids}
    if len(ids) >= cast.MAX_N:
        return {"joined": False, "cast": ch["cast"], "ids": ids,
                "note": f"This project's cast is full ({cast.MAX_N}) — take someone off to add {name}."}
    ids.append(cid)
    d = cast.choose(root, ch["cast"] or name, ids)
    return {"joined": True, "cast": d["cast"], "ids": d["ids"]}


def use(mcp, root, project_id: str, cid: str) -> dict:
    """📌 Use a saved character in this project: pinned in Hermes (uses.json links back) + added to the cast."""
    cid = str(cid or "")
    if not cid.startswith("c-"):
        raise CharError("Pick a character first.")
    r = mcp.call("cast_pin", {"id": cid, "project": project_id})
    return {"ok": True, "id": r["id"], "name": r["name"], **join(root, r["id"], r["name"])}


def leave(root, cid: str) -> dict:
    """✕ Take one character off this project's cast (the card stays in the library)."""
    ch = cast.chosen(root)
    ids = [x for x in ch["ids"] if x != cid]
    d = cast.choose(root, ch["cast"] if ids else "", ids)
    return {"ok": True, "cast": d["cast"], "ids": d["ids"]}


def one(mcp, cid: str) -> dict:
    """📇 One card in full: brief, age, sheet, which projects use it."""
    r = mcp.call("cast_get", {"id": str(cid or "")})
    return {"ok": True, "character": r}
