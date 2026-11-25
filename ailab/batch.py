"""🎛 Batch create (2026-11-24, Scott: "batch create images, videos, documents … all with slight differences, and the
slight should range with a dial or bar that goes from similar to wildly different").

One run makes N pictures or N docs (1–24). The 🎚 dial (0–100) sets how far each one strays from Scott's words:
- Similar (0–33): his exact words; each one is a fresh random start (the model's own seed).
- Middle (34–66): pose, light and setting change — more of them the further right.
- Wild (67–100): style, scene and mood reimagined too. His subject ALWAYS stays (his words are never changed).
Before it runs the total cost is shown and held to the $/day cap. ➕ Make more continues the same series (same words,
same dial, new variations) and carries the earlier results along so the grid shows the whole batch.
Video stays later — the Lab can't make video yet.
"""
from __future__ import annotations

import re
import time

from . import creation, picture

MAX_N = 24
PICTURE_USD = 0.012       # Venice picture ($0.01) + the writer's few hundred tokens — shown as "about"
DOC_USD = 0.01            # one chat reply of up to ~3,000 tokens on a cheap model — shown as "about"

POSES = ["a different pose", "seen from a lower angle", "seen from above", "a closer view", "a wider view",
         "turned to the side", "in motion", "a relaxed stance", "looking toward the viewer", "looking away",
         "from behind, over the shoulder", "a three-quarter view"]
LIGHTS = ["golden-hour light", "soft overcast light", "dramatic side light", "blue-hour light", "warm candlelight",
          "bright midday sun", "moonlight", "backlit glow", "studio softbox light", "neon light", "misty morning light",
          "window light"]
SETTINGS = ["outdoors in nature", "in a city street", "indoors, in a cozy room", "by the water", "in the mountains",
            "in a garden", "on a rooftop", "in a forest", "in a desert", "in a quiet village", "on a beach", "in a studio"]
STYLES = ["oil painting", "watercolor", "anime", "pixel art", "3D render", "charcoal sketch", "comic book", "art nouveau",
          "ukiyo-e woodblock", "cyberpunk", "storybook illustration", "pop art"]
SCENES = ["a dreamlike world", "a far-future city", "an ancient ruin", "underwater", "outer space", "a stormy sea",
          "a snowy winter night", "a lantern-lit festival", "a giant library", "a floating island", "a jungle temple",
          "a steampunk workshop"]
MOODS = ["serene", "joyful", "mysterious", "epic", "melancholy", "whimsical", "eerie", "romantic", "playful",
         "intense", "nostalgic", "cozy"]
NUDGES = ["a slightly different angle", "a slightly different framing", "a little closer", "a little wider"]
# docs: same topic, different take
D_TONES = ["warm and friendly", "plain and direct", "upbeat", "calm and reassuring", "formal", "playful", "persuasive",
           "story-like", "matter-of-fact", "inspiring", "conversational", "careful and precise"]
D_SHAPES = ["short paragraphs", "a numbered list", "questions and answers", "a step-by-step guide", "a short story",
            "a letter", "headed sections", "a one-page summary", "a checklist", "a dialogue", "bullet points", "a poem"]
D_ANGLES = ["for a beginner", "for an expert", "from the reader's point of view", "focused on the why",
            "focused on the how", "with a real-life example", "with a surprising opening", "as a comparison",
            "looking ahead", "looking back", "for a busy person", "with a bit of humour"]


def kind_for(ctypes) -> str:
    """'picture' · 'doc' · '' (no batch for pages, apps, games or video)."""
    ids = [t["id"] for t in creation.pick(ctypes or [])]
    if creation.picture_mode(ids):
        return "picture"
    if "text" in ids and not any(t in ids for t in creation.PAGE_TYPES) and "image" not in ids and "video" not in ids:
        return "doc"
    return ""


def level(dial: int) -> str:
    return "similar" if dial < 34 else "middle" if dial < 67 else "wild"


LEVEL_WORDS = {"similar": "🟢 Similar", "middle": "🟡 Middle", "wild": "🔴 Wild"}


def _pick(pool: list[str], k: int, stride: int) -> str:
    return pool[(k * stride + stride // 2) % len(pool)]


def variation(dial: int, k: int, kind: str = "picture") -> str:
    """The extra line for item k (0-based across the whole series). '' = Scott's words alone."""
    lv = level(dial)
    if kind == "doc":
        if lv == "similar":
            return "" if dial < 17 or k == 0 else "a fresh take — same content, your own wording"
        parts = [f"tone: {_pick(D_TONES, k, 5)}"]
        if dial >= 50:
            parts.append(f"angle: {_pick(D_ANGLES, k, 7)}")
        if lv == "wild":
            parts.append(f"shape: {_pick(D_SHAPES, k, 5)}")
        return "; ".join(parts) + " — same topic and facts as asked"
    if lv == "similar":
        return "" if dial < 17 or k == 0 else _pick(NUDGES, k, 1)
    parts = [_pick(POSES, k, 5)]
    if dial >= 45:
        parts.append(_pick(LIGHTS, k, 7))
    if dial >= 56:
        parts.append(_pick(SETTINGS, k, 5))
    if lv == "wild":
        parts.append(f"as {_pick(STYLES, k, 7)}")
        if dial >= 80:
            parts.append(f"set in {_pick(SCENES, k, 5)}")
        if dial >= 90:
            parts.append(f"a {_pick(MOODS, k, 7)} mood")
    return ", ".join(parts) + " — keep the same main subject"


def with_variation(task: str, v: str) -> str:
    """Scott's words first, untouched; the variation line after his first block (before any Style:/Shape: lines)."""
    if not v:
        return task
    lines = task.split("\n")
    i = next((n for n, ln in enumerate(lines) if re.match(r"^(Style|Shape|Look|Change):", ln)), len(lines))
    return "\n".join(lines[:i] + [f"Variation: {v}"] + lines[i:])


def norm(b, ctypes) -> dict | None:
    """The batch part of a start request, cleaned. None = an ordinary single run."""
    if not isinstance(b, dict):
        return None
    kind = kind_for(ctypes)
    try:
        n = max(1, min(MAX_N, int(b.get("n") or 1)))
        dial = max(0, min(100, int(b.get("dial") or 0)))
        start = max(0, min(10_000, int(b.get("start") or 0)))
    except (TypeError, ValueError):
        return None
    if not kind or n < 2 and not start:
        return None
    return {"kind": kind, "n": n, "dial": dial, "start": start, "earlier": [], "items": [], "failed": 0, "now": 0}


def price(kind: str, cfg: dict) -> float:
    return float(cfg.get("batch_picture_usd", PICTURE_USD) if kind == "picture" else cfg.get("batch_doc_usd", DOC_USD))


def estimate(kind: str, n: int, cfg: dict, spent: float) -> dict:
    per = price(kind, cfg)
    cap = float(cfg.get("daily_cap_usd", 2.0))
    left = max(0.0, cap - spent)
    est = round(per * n, 4)
    return {"kind": kind, "n": n, "per_usd": per, "est_usd": est, "today_usd": round(spent, 4), "cap_usd": cap,
            "left_usd": round(left, 4), "fits": est <= left, "max_n": max(0, min(MAX_N, int(left / per))) if per else MAX_N}


def view(run) -> dict | None:
    b = getattr(run, "batch", None)
    if not b:
        return None
    return {**{k: b[k] for k in ("kind", "n", "dial", "start", "failed", "now")}, "level": level(b["dial"]),
            "level_words": LEVEL_WORDS[level(b["dial"])], "items": b["items"], "earlier": b.get("earlier", []),
            "next_start": b["start"] + b["n"], "kept": kept(run.root)}


def stage_prefix(run) -> str:
    b = getattr(run, "batch", None)
    return f"🎛 {min(b['now'] + 1, b['n'])} of {b['n']} · " if b and run.state == "running" else ""


# ---- 🖼 pictures: the normal picture run, once per variation (choices asked once, then reused) ----
def pictures(run) -> None:
    b, base = run.batch, run.task
    run.cap_usd = max(run.cap_usd, price("picture", run.cfg) * b["n"] * 1.5)
    stop_reason = ""
    try:
        for i in range(b["n"]):
            b["now"] = i
            k = b["start"] + i
            v = variation(b["dial"], k, "picture")
            run.task, run.state, run.why = with_variation(base, v), "running", ""
            before = len(run.pictures)
            picture.run(run)                      # raises Stopped / SpendBlocked → handled by Run.loop
            if len(run.pictures) > before:
                pic = run.pictures[-1]
                pic.update(k=k, variation=v)
                b["items"].append({"path": pic["path"], "k": k, "variation": v, "usd": pic.get("usd", 0), "kind": "picture"})
            else:
                b["failed"] += 1
                if not run.connected or "cap" in (run.why or "").lower() or b["failed"] >= 3 and not b["items"]:
                    stop_reason = run.why
                    break
            run.save()
    finally:
        run.task = base
    _finish(run, "picture", stop_reason)


# ---- 📝 docs: one reply per variation, saved as docs/<time>-<words>-<k>.md ----
DOC_SYS = ("Write what Scott asked for, in Markdown. Keep to his topic and every fact he gave. If a 'Variation:' line is "
           "there, follow it for tone, angle and shape. Reply with the document only — no notes before or after.")


def docs(run) -> None:
    b, base = run.batch, run.task
    run.cap_usd = max(run.cap_usd, price("doc", run.cfg) * b["n"] * 1.5)
    slug = re.sub(r"[^a-z0-9]+", "-", base.split("\n")[0].lower()).strip("-")[:40] or "doc"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run.docs = getattr(run, "docs", []) or []
    stop_reason = ""
    for i in range(b["n"]):
        run._check_stop()
        b["now"] = i
        k = b["start"] + i
        v = variation(b["dial"], k, "doc")
        picture.stage(run, "✍️", f"Writing with {run.model.split('/')[-1]}" + (f" — {v[:60]}" if v else ""))
        try:
            r = run.lab.chat(run.project, run.provider, run.model,
                             [{"role": "system", "content": DOC_SYS}, {"role": "user", "content": with_variation(base, v)}],
                             3000, cap_usd=max(0.0, run.cap_usd - run.usd), task=f"lab-batch:{run.project['id']}")
        except Exception as e:                                   # noqa: BLE001 — one bad reply doesn't end the batch
            if type(e).__name__ in ("SpendBlocked", "PrivacyRefused"):
                raise
            b["failed"] += 1
            run._record({"action": "doc", "why": f"📝 doc {k + 1}", "result": {"error": f"{type(e).__name__}: {str(e)[:200]}"}, "usd": 0.0})
            if b["failed"] >= 3 and not b["items"]:
                stop_reason = f"⚠️ {type(e).__name__}: {str(e)[:200]}"
                break
            continue
        usd = float(r.usd or 0)
        run.usd += usd
        run.tokens_in += int(getattr(r, "tokens_in", 0) or 0)
        run.tokens_out += int(getattr(r, "tokens_out", 0) or 0)
        text = (r.text or "").strip()
        if len(text) < 20 or picture.REFUSAL_RX.search(text[:80]):
            b["failed"] += 1
            run._record({"action": "doc", "why": f"📝 doc {k + 1}", "result": {"error": "the model didn't write it"}, "usd": usd})
            continue
        rel = f"docs/{stamp}-{slug}-{k + 1}.md"
        p = run.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n")
        item = {"path": rel, "k": k, "variation": v, "usd": round(usd, 5), "kind": "doc"}
        run.docs.append(item)
        b["items"].append(item)
        run._record({"action": "doc", "path": rel, "why": f"📝 wrote doc {k + 1}", "result": {"bytes": len(text), "variation": v}, "usd": usd})
        run.save()
    _finish(run, "doc", stop_reason)


def _finish(run, kind: str, stop_reason: str) -> None:
    b = run.batch
    got, want = len(b["items"]), b["n"]
    b["now"] = want
    noun = "picture" if kind == "picture" else "doc"
    where = "pictures/" if kind == "picture" else "docs/"
    cost = sum(float(x.get("usd") or 0) for x in b["items"])
    if not got:
        run.state = "failed"
        run.why = stop_reason or run.why or f"🎛 No {noun}s came back."
    else:
        run.state = "done"
        run.why = (f"🎛 {got} of {want} {noun}s made ({LEVEL_WORDS[level(b['dial'])]}, dial {b['dial']}) for ${cost:.3f}. "
                   f"Saved in {where}" + (" and your Gallery (ai-lab)." if kind == "picture" else ".")
                   + (f" {want - got} didn't come back." if got < want else "") + (f" Stopped: {stop_reason}" if stop_reason else ""))
    picture.stage(run, "✅" if got else "❌", "Done" if got else "Nothing came back")


# ---- ⭐ Keep: a small list in the project folder (kept.json), so the keepers are easy to find ----
def kept(root) -> list[str]:
    import json
    f = root / "kept.json"
    try:
        v = json.loads(f.read_text())
        return [str(x) for x in v if isinstance(x, str)] if isinstance(v, list) else []
    except (OSError, ValueError):
        return []


def set_kept(root, path: str, keep: bool) -> list[str]:
    import json
    import os
    path = str(path or "").strip().lstrip("/")
    if not path or ".." in path.split("/") or not (root / path).is_file():
        raise ValueError("No such file in this project.")
    cur = [x for x in kept(root) if x != path] + ([path] if keep else [])
    f = root / "kept.json"
    tmp = f.with_name(".kept.json.tmp")
    tmp.write_text(json.dumps(cur, indent=1))
    os.replace(tmp, f)
    return cur
