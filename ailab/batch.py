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

from . import creation, eyes, looks, makers, picture

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
SCENES = ["a dreamlike world", "a far-future city", "an ancient ruin", "an underwater world", "deep space", "a stormy sea",
          "a snowy winter night", "a lantern-lit festival", "a giant library", "a floating island", "a jungle temple",
          "a steampunk workshop"]
# 🔴 Wild pictures: the drawn style, light and mood go as a 🎨 Look line (catalog names, ailab/looks.json), so a
# non-photo medium also pushes "photo" away — live 2026-11-24: as plain words Lustify v8 drew all 4 Wild ones as photos.
WILD_LOOK = ["Charcoal", "Oil painting", "Anime", "Pixel art", "3D render", "Watercolor", "Comic book", "Art Nouveau",
             "Ukiyo-e", "Cyberpunk", "Storybook", "Pop art"]
WILD_LIGHT = ["Golden hour", "Moonlight", "Backlit", "Neon light", "Chiaroscuro", "God rays", "Blue hour", "Candlelight",
              "Rim light", "Low-key", "High-key", "Overcast"]
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
    if lv == "wild":                                     # style/light/mood ride in the Look line (wild_look)
        parts.append(f"set in {_pick(SCENES, k, 5)}" if dial >= 80 else _pick(SETTINGS, k, 5))
        return ", ".join(parts) + " — keep the same main subject"
    if dial >= 45:
        parts.append(_pick(LIGHTS, k, 7))
    if dial >= 56:
        parts.append(_pick(SETTINGS, k, 5))
    return ", ".join(parts) + " — keep the same main subject"


def wild_look(dial: int, k: int) -> list[str]:
    """🔴 Wild pictures: a Look (catalog names) — drawn style always, light from 67, mood from 90."""
    if level(dial) != "wild":
        return []
    names = [_pick(WILD_LOOK, k, 7), _pick(WILD_LIGHT, k, 5)]
    if dial >= 90:
        names.append(_pick(MOODS, k, 7).capitalize())
    return names


# How each Wild style is said at the very front of the prompt (live A/B 2026-11-24, Lustify v8: style words AFTER his
# words → 0 of 4 drawn; style words FIRST → pixel art, storybook, watercolor drawn, charcoal half-way).
WILD_LEAD = {"Charcoal": "Charcoal drawing", "Oil painting": "Oil painting", "Anime": "Anime illustration",
             "Pixel art": "Pixel art", "3D render": "3D render", "Watercolor": "Watercolor painting",
             "Comic book": "Comic book illustration", "Art Nouveau": "Art Nouveau illustration",
             "Ukiyo-e": "Ukiyo-e woodblock print", "Cyberpunk": "Cyberpunk digital art", "Storybook": "Storybook illustration",
             "Pop art": "Pop art print"}


def picture_task(base: str, dial: int, k: int) -> tuple[str, str, list[str]]:
    """(task for this one, what to show on the tile, Look names added).
    Wild: the style + pose/scene go in FRONT of his words ("Pixel art, seen from above, set in …: <his words>") — his
    words follow exactly as typed — and the Look line still adds light/mood and pushes photo away. If he set his own
    Look, it wins: only pose/scene go in front."""
    v = variation(dial, k, "picture")
    names = wild_look(dial, k)
    if not names:
        return with_variation(base, v), v, []
    change = v[: v.rfind(" — ")] if " — " in v else v
    own = looks.from_task(base)
    lead = f"{change}: " if own else f"{WILD_LEAD.get(names[0], names[0])}, {change}: "
    first, _, rest = base.partition("\n")
    t = lead + first + ("\n" + rest if rest else "")
    if own:
        return t, lead.rstrip(": "), []
    return t + "\n" + looks.line(names), lead.rstrip(": "), names


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
    if isinstance(b.get("cast"), dict):                        # 🎲 R1 Design a cast: N people, its own run (cast.run)
        if kind != "picture":
            return None
        from . import cast
        try:
            cn = max(cast.MIN_N, min(cast.MAX_N, int(b["cast"].get("n") or cast.DEFAULT_N)))
        except (TypeError, ValueError):
            return None
        return {"kind": "cast", "n": cn, "dial": 0, "start": 0, "earlier": [], "items": [], "failed": 0, "now": 0}
    sheet = str(b.get("sheet") or "")                          # 🎭 M2 character sheet: the source picture (project path)
    if sheet:
        if kind != "picture":
            return None
        from . import refs
        n, dial, start = len(refs.SHEET_VIEWS), 0, 0
    if not kind or n < 2 and not start:
        return None
    out = {"kind": kind, "n": n, "dial": dial, "start": start, "earlier": [], "items": [], "failed": 0, "now": 0}
    if sheet:
        out["sheet"] = sheet
    return out


CAST_PICTURES = 8          # per person: anchor + 5 sheet views + room for one redesign and a retry


def price(kind: str, cfg: dict) -> float:
    if kind == "cast":
        return float(cfg.get("batch_picture_usd", PICTURE_USD)) * CAST_PICTURES
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
            "next_start": b["start"] + b["n"], "kept": kept(run.root),
            **({"briefs": b.get("briefs", []), "apart": b.get("apart", []), "saved": b.get("saved", [])} if b["kind"] == "cast" else {})}


def stage_prefix(run) -> str:
    b = getattr(run, "batch", None)
    if b and b.get("kind") == "cast":
        return f"🎭 person {min(b['now'] + 1, b['n'])} of {b['n']} · " if run.state == "running" else ""
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
            if b.get("sheet"):
                from . import refs
                (task_k, v), look = refs.sheet_task(base, k), []
            else:
                task_k, v, look = picture_task(base, b["dial"], k)
            run.task, run.state, run.why = task_k, "running", ""
            before = len(run.pictures)
            try:
                picture.run(run)                  # Stopped / SpendBlocked / PrivacyRefused → Run.loop handles them
            except Exception as e:                # noqa: BLE001 — live 2026-11-24: hermes-mcp dropped one call
                if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):   # (RemoteDisconnected) and
                    raise                                                           # it ended the whole batch
                run.state, run.why = "failed", f"⚠️ {type(e).__name__}: {str(e)[:200]}"
                run._record({"action": "picture", "why": f"🎨 picture {k + 1}", "result": {"error": run.why}, "usd": 0.0})
            if len(run.pictures) > before:
                pic = run.pictures[-1]
                shown = v + (f" · 🎨 {looks.SEP.join(look)}" if look else "")
                pic.update(k=k, variation=shown)
                b["items"].append({"path": pic["path"], "k": k, "variation": shown, "usd": pic.get("usd", 0), "kind": "picture"})
            else:
                b["failed"] += 1
                if not run.connected or "cap" in (run.why or "").lower() or b["failed"] >= 3 and not b["items"]:
                    stop_reason = run.why
                    break
            run.save()
    finally:
        run.task = base
    try:
        look_at(run)
    except Exception as e:                                       # noqa: BLE001 — the pictures are made; eyes never lose them
        if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
            raise
    _finish(run, "picture", stop_reason)


def look_at(run) -> None:
    """👁 M1: after the batch is made, the vision model checks each picture against its own words; best = ⭐."""
    b = run.batch
    if not eyes.on(run) or not b["items"]:
        return
    if b.get("sheet"):
        return same_faces(run)
    by = {p["path"]: p for p in run.pictures}
    for i, it in enumerate(b["items"]):
        pic = by.get(it["path"])
        if it.get("kind") != "picture" or pic is None or it.get("eyes"):
            continue
        task_k = picture_task(run.task, b["dial"], it["k"])[0]
        try:
            raw = (run.root / it["path"]).read_bytes()
        except OSError:
            continue
        e = eyes.check(run, raw, task_k, pic.get("look"), label=f"picture {i + 1} of {len(b['items'])}")
        pic["eyes"] = e
        it["eyes"] = {k: e.get(k) for k in ("score", "missing", "caption", "error", "fix", "fix_task", "low", "refused") if e.get(k) is not None}
        if e.get("error"):                                       # the vision model is off or broken: don't ask 15 more times
            eyes.record(run, "batch", e)
            break
        run.save()
    scored = [it for it in b["items"] if (it.get("eyes") or {}).get("score") is not None]
    for it in b["items"]:
        it.pop("best", None)
    if scored:
        top = max(scored, key=lambda it: it["eyes"]["score"])
        top["best"] = True
        run._record({"action": "eyes", "why": f"👁 checked {len(scored)} pictures — best match #{top['k'] + 1} at {top['eyes']['score']}%",
                     "result": {"scores": {str(it["k"] + 1): it["eyes"]["score"] for it in scored}}, "usd": 0.0})


# ---- 📝 docs: one reply per variation, saved as docs/<time>-<words>-<k>.md ----
DOC_SYS = ("Write what Scott asked for, in Markdown. Keep to his topic and every fact he gave. If a 'Variation:' line is "
           "there, follow it for tone, angle and shape. Reply with the document only — no notes before or after.")


def same_faces(run) -> None:
    """🎭 M2: each sheet view next to the source picture — 👁 "same person?" ($0). Drift is named, never hidden."""
    from . import refs
    b = run.batch
    try:
        src = (run.root / b["sheet"]).read_bytes()
    except OSError:
        return
    same, drift = 0, []
    for i, it in enumerate(b["items"]):
        if it.get("kind") != "picture" or it.get("eyes"):
            continue
        try:
            raw = (run.root / it["path"]).read_bytes()
        except OSError:
            continue
        e = refs.same_face(run, src, raw, f"view {i + 1} of {len(b['items'])} next to the original")
        it["eyes"] = {k: e.get(k) for k in ("score", "missing", "caption", "error", "same", "refused") if e.get(k) is not None}
        if e.get("error"):
            eyes.record(run, "sheet", e)
            break
        same += bool(e.get("same"))
        if not e.get("same"):
            drift.append(it.get("variation") or f"view {i + 1}")
        run.save()
    run._record({"action": "eyes", "why": f"🎭 same-face check: {same} of {len(b['items'])} views match the original"
                 + (f" — drifted: {', '.join(drift)}" if drift else ""), "result": {"same": same, "drift": drift}, "usd": 0.0})


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
        # 2026-11-24 art in every form: the uncensored writer chain first (Venice), refusals skipped, then the run's model
        before = run.usd
        text, who = makers.write(run, DOC_SYS + " " + makers.KEEP_WORDS, with_variation(base, v), 3000,
                                 "Writing" + (f" — {v[:60]}" if v else ""), "lab-batch")
        usd = run.usd - before
        if len(text) < 20:
            b["failed"] += 1
            run._record({"action": "doc", "why": f"📝 doc {k + 1}", "result": {"error": who or "the model didn't write it"}, "usd": usd})
            if b["failed"] >= 3 and not b["items"]:
                stop_reason = f"⚠️ {who}"
                break
            continue
        rel = picture.claim(run.root, f"docs/{stamp}-{slug}-{k + 1}.md")
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
