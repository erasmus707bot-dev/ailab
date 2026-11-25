"""📖 Story — long and short (eyes+story+rip M3, Scott 2026-11-25).

One run = one chapter, its steps shown as cards:
  1 · 📚 story bible (people, places, rules, tone, facts) — saved in the project, editable, fed to every later step
  2 · 🗒 outline → 🎬 shot list (who · where · action · camera · seconds · spoken line)
  3 · 🖼 a still per shot — the chosen 🎭 cast's anchors as references, the Look applied, 👁 checked against its shot line
      (a low score on a $0 picture is remade once with the misses — a score changes something, it is not just a badge)
  4 · 🎞 a clip per still — 🆓 pan-and-zoom ⭐ · 🏠 local AI motion · Venice (one price card for all shots, a tap)
  5 · 🎙 narration (Hermes `narrate`, local Kokoro) → joined into one film with ffmpeg. No captions (his rule).
  🔗 continuity: after a chapter the writer lists what changed into the bible; before the next chapter a checker flags
     contradictions → he picks: fix the text ⭐ / fix the bible / keep both.
Presets: ⚡ Short 15–30 s (6 shots, hook first, loop-friendly end) · 📚 Long (chapters, each its own run, so a restart
never loses the lot — finished shots are on disk and skipped) · ✍️ Words only (bible + outline + prose).

Files: <project>/.shelf/story/bible.json · chapter-<n>.json (outline, shots, stills, clips, film).
Uncensored writer by default, his words kept exactly (makers.KEEP_WORDS). Invented adults only.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

FORMS = {"short": "⚡ Short (15–30 s)", "long": "📚 Long (one chapter per run)", "words": "✍️ Words only"}
CLIPS = {"free": "🆓 Pan-and-zoom ($0, instant)", "local": "🏠 AI motion on this computer ($0, slow)",
         "venice": "🔓 Venice AI motion (price first)", "none": "🖼 Stills only"}
SHORT_SHOTS, LONG_SHOTS = 6, 8
SHORT_MIN_S, SHORT_MAX_S = 15, 30
SHOT_MIN_S, SHOT_MAX_S = 2, 8
RETRIES = 1                                       # $0 remakes of a low-scoring still (config "story": {"retries": n})
FIX_TEXT, FIX_BIBLE, KEEP_BOTH = "✏️ Fix the chapter (keep the bible)", "📚 Fix the bible (the chapter is right)", "↔️ Keep both as they are"
SIZE = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (1080, 1080)}

BIBLE_SYS = ("You write the story bible for Scott's story. {keep} Reply with JSON only: {{\"title\": str, \"tone\": str, \"when\": str, "
             "\"people\": [{{\"name\": str, \"who\": str}}], \"places\": [str], \"rules\": [str]}}. Use the cast he gives "
             "with their names and looks exactly; everyone is an adult. when = the time of day, light and weather the story "
             "happens in (e.g. \"night, neon light, light rain\"). Short plain lines.")
SHOTS_SYS = ("You plan a {form} told in shots. {keep} Reply with JSON only: {{\"outline\": str, \"shots\": [{{\"who\": "
             "[names], \"where\": str, \"action\": str, \"camera\": str, \"when\": str, \"seconds\": int, \"line\": str}}]}}. Exactly {n} "
             "shots. One clear action per shot, shown not told. camera = framing + move (wide, close-up, slow push-in…). "
             "when = time of day + light for that shot — the bible's When unless the story moves on in time. "
             "line = one short spoken narration sentence for that shot, or \"\". {extra} Never put text, captions, signs "
             "or writing in a shot. Stay true to the bible and its facts.")
SHORT_EXTRA = ("Total 15–30 seconds. Shot 1 is the hook — the strongest, most striking picture, it grabs in the first 2 "
               "seconds. The last shot leads back into the first so it loops.")
LONG_EXTRA = "This is chapter {ch}; carry on from the facts so far."
PROSE_SYS = "You write fiction prose. {keep} Follow the bible and the outline. Plain, vivid, readable."
FACTS_SYS = ("List what CHANGED in this chapter that later chapters must respect: who knows what, who is where, what is "
             "broken, worn, lost or gained, who is hurt or gone. JSON only: [\"one fact per line\"]. 3–10 short lines.")
CHECK_SYS = ("You check a new chapter against the story bible's facts — his idea for the chapter and the plan made from it. "
             "List only real contradictions: something his idea or the plan says that a listed fact rules out. Things the facts "
             "don't cover are not contradictions. Each flag names both sides in one plain line, like: \"Fact (ch 2): Ben took the "
             "flooded tunnel — but his idea says Ben never went near a tunnel.\" JSON only: [\"flag\", ...], or [] if none.")


# ---------------------------------------------------------------- files
def _dir(root) -> Path:
    d = Path(root) / ".shelf" / "story"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(p: Path, default):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def _write(p: Path, d) -> None:
    tmp = p.with_name("." + p.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    os.replace(tmp, p)


def bible(root) -> dict:
    b = _read(_dir(root) / "bible.json", {})
    return clean_bible(b) if b else {}


def clean_bible(b) -> dict:
    b = b if isinstance(b, dict) else {}
    s = lambda x, n=300: str(x or "").strip()[:n]                                   # noqa: E731
    ppl = [{"name": s(p.get("name"), 40), "who": s(p.get("who"))} for p in b.get("people") or [] if isinstance(p, dict) and s(p.get("name"))]
    facts = [{"ch": int(f.get("ch") or 0), "fact": s(f.get("fact"))} for f in b.get("facts") or [] if isinstance(f, dict) and s(f.get("fact"))]
    return {"title": s(b.get("title"), 80), "tone": s(b.get("tone")), "when": s(b.get("when"), 120), "people": ppl[:12],
            "places": [s(x, 120) for x in b.get("places") or [] if s(x)][:20],
            "rules": [s(x) for x in b.get("rules") or [] if s(x)][:20], "facts": facts[-80:],
            "updated": float(b.get("updated") or 0)}


def save_bible(root, b: dict) -> dict:
    b = clean_bible({**b, "updated": time.time()})
    _write(_dir(root) / "bible.json", b)
    return b


def chapter(root, n: int) -> dict:
    return _read(_dir(root) / f"chapter-{int(n)}.json", {})


def save_chapter(root, n: int, d: dict) -> None:
    _write(_dir(root) / f"chapter-{int(n)}.json", {**d, "n": int(n), "updated": time.time()})


def chapters(root) -> list[dict]:
    out = []
    for p in sorted(_dir(root).glob("chapter-*.json"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0)):
        c = _read(p, {})
        if c:
            out.append({"n": c.get("n"), "form": c.get("form"), "outline": c.get("outline", ""), "film": c.get("film", ""),
                        "prose": c.get("prose", ""), "shots": c.get("shots", [])})
    return out


def resume_or_next(root, form: str) -> int:
    """An unfinished chapter of the same form is carried on (a restart never loses the lot); else the next number."""
    n = next_chapter(root) - 1
    c = chapter(root, n) if n else {}
    return n if c and not c.get("done") and c.get("form") == form else n + 1


def next_chapter(root) -> int:
    ns = [int(re.sub(r"\D", "", p.stem) or 0) for p in _dir(root).glob("chapter-*.json")]
    return max(ns, default=0) + 1


def view(root) -> dict:
    return {"bible": bible(root), "chapters": chapters(root), "next": next_chapter(root), "forms": FORMS, "clips": CLIPS}


# ---------------------------------------------------------------- the request
def norm(s) -> dict | None:
    if not isinstance(s, dict):
        return None
    form = s.get("form") if s.get("form") in FORMS else "short"
    clips = s.get("clips") if s.get("clips") in CLIPS else ("none" if form == "words" else "free")
    try:
        ch = int(s.get("chapter") or 0)
    except (TypeError, ValueError):
        ch = 0
    return {"form": form, "clips": clips, "narrate": s.get("narrate", True) is not False, "chapter": max(0, min(500, ch)),
            "new": bool(s.get("new"))}


def shots_for(form: str) -> int:
    return 0 if form == "words" else SHORT_SHOTS if form == "short" else LONG_SHOTS


# ---------------------------------------------------------------- parsing (models answer loosely)
def _json(text: str, want):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    opener = "[" if want is list else "{"
    i = t.find(opener)
    if i < 0:
        return want()
    depth, q, esc = 0, False, False
    for j in range(i, len(t)):
        c = t[j]
        if q:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                q = False
            continue
        if c == '"':
            q = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                try:
                    v = json.loads(t[i:j + 1])
                    return v if isinstance(v, want) else want()
                except ValueError:
                    return want()
    return want()


def clean_shots(raw, names: list[str], form: str) -> list[dict]:
    """Whatever the writer sent → shots with every field, seconds clamped; Short totals 15–30 s."""
    names_l = {n.lower(): n for n in names}
    out = []
    for s in (raw if isinstance(raw, list) else [])[:12]:
        if not isinstance(s, dict) or not str(s.get("action") or "").strip():
            continue
        who = s.get("who") if isinstance(s.get("who"), list) else [s.get("who")] if s.get("who") else []
        who = [names_l.get(str(w).strip().lower(), str(w).strip()) for w in who if str(w or "").strip()][:4]
        # live 2026-11-25: "Ben looks back, seeing Aria with the package" came with who=[Ben] → no reference for Aria,
        # no 👁 check of her look → the model drew a stranger in Ben's colours. A name in the action is in the shot.
        seen_l = {w.lower() for w in who}
        for low, name in names_l.items():
            if low not in seen_l and len(who) < 4 and re.search(rf"\b{re.escape(low)}\b", str(s["action"]).lower()):
                who.append(name)
                seen_l.add(low)
        try:
            sec = int(float(s.get("seconds") or 4))
        except (TypeError, ValueError):
            sec = 4
        out.append({"who": who, "where": str(s.get("where") or "").strip()[:160], "action": str(s["action"]).strip()[:300],
                    "camera": str(s.get("camera") or "").strip()[:120], "when": str(s.get("when") or "").strip()[:120],
                    "seconds": max(SHOT_MIN_S, min(SHOT_MAX_S, sec)),
                    "line": re.sub(r"\s+", " ", str(s.get("line") or "")).strip()[:300]})
    if form == "short" and out:
        tot = sum(s["seconds"] for s in out)
        if tot < SHORT_MIN_S or tot > SHORT_MAX_S:
            want = SHORT_MIN_S if tot < SHORT_MIN_S else SHORT_MAX_S
            for s in out:
                s["seconds"] = max(SHOT_MIN_S, min(SHOT_MAX_S, round(s["seconds"] * want / tot)))
    for k, s in enumerate(out):
        s["k"] = k
    return out


def shot_prompt(shot: dict, b: dict, cast: dict[str, dict], looks: bool = True) -> str:
    """One still's words: who (with their look, so the picture model can tell them apart) · action · where · framing."""
    who = []
    for w in shot["who"]:
        c = cast.get(w.lower())
        p = next((p for p in b.get("people", []) if p["name"].lower() == w.lower()), None)
        look = (c or {}).get("brief", "") or (p or {}).get("who", "")
        look = look.split(": ", 1)[-1]
        who.append(f"{w} ({look})" if look and looks else w if looks else seen_as(look))
    where = shot["where"]
    if where and not where.lower().startswith(("in ", "at ", "on ", "by ", "inside ", "under ")):
        where = "in " + where
    when = shot.get("when") or b.get("when", "")                 # live 2026-11-25: a night market drifted to daylight
    action = shot["action"] if looks else unname(shot["action"], b, cast)
    bits = [", ".join(who), action, where, when, shot["camera"]]
    return ", ".join(x for x in bits if x)


def unname(action: str, b: dict, cast: dict[str, dict]) -> str:
    """👁 live 2026-11-25: "missing: Aria rides her bike through the rain" — the people were checked by look, but the action
    still named them. Names in the action become what a picture shows: "the woman rides her bike through the rain"."""
    out = str(action or "")
    names = {str(p.get("name") or ""): (cast.get(str(p.get("name") or "").lower()) or {}).get("brief", "") or p.get("who", "")
             for p in b.get("people", []) if p.get("name")}
    names.update({str(c.get("name") or k): c.get("brief", "") for k, c in cast.items() if isinstance(c, dict)})
    for name, look in sorted(names.items(), key=lambda kv: -len(kv[0])):
        if not name.strip():
            continue
        role = re.search(r"\b(woman|man|person)\b", look or "")
        out = re.sub(rf"\b{re.escape(name)}\b", "the " + (role.group(1) if role else "person"), out, flags=re.I)
    return out


def seen_as(look: str) -> str:
    """👁 can't know a name — "Aria" becomes what a picture shows: "a woman with copper red hair in a royal blue outfit"."""
    who = re.search(r"\b(woman|man|person)\b", look or "")
    hair = re.search(r"([a-z-]+(?: [a-z-]+)?) hair\b", look or "")
    outfit = re.search(r"wearing an? (.+?) outfit", look or "")
    out = "a " + (who.group(1) if who else "person")
    if hair:
        out += f" with {hair.group(1)} hair"
    if outfit:
        out += f" in a {outfit.group(1)} outfit"
    return out


WRITING_PT = {"q": "Look closely at every sign, shop front, wall, the ground, vehicles and clothing. Are there any letters, "
                   "words or numbers anywhere in the picture?", "want": False,
              "what": "no letters or words anywhere (signs, ground, walls)", "kind": "notext"}


def writing_check(run, raw: bytes, e: dict, task: str, k: int) -> dict:
    """👁 a second, closer look for writing (live 2026-11-25: painted letters on the ground and sign text slipped past the
    one-line no-text point). Writing found → it counts as a miss and the $0 remake gets the fix — and the remake keeps the
    shot's real words + looks (the first fix was built from the name-free 👁 words)."""
    from . import eyes
    if e.get("error"):
        return e
    w = eyes.ask(run, raw, [WRITING_PT], f"shot {k + 1} — any writing?")
    rows = list(e.get("points") or [])
    if not w.get("error") and w.get("points") and w["points"][0].get("ok") is False:
        rows.append(w["points"][0])
        run._record({"action": "eyes", "why": f"👁 shot {k + 1}: writing found — {WRITING_PT['what']} is missing",
                     "result": {"caption": w.get("caption", "")[:200]}, "usd": 0.0})
        e = {**e, "missing": list(e.get("missing") or []) + [WRITING_PT["what"]], "low": True,
             "score": round(100 * sum(1 for r in rows if r.get("ok")) / max(1, sum(1 for r in rows if r.get("ok") is not None)))}
    e["fix_task"] = eyes.fix_task(task, rows)
    e["fix"] = eyes.fix_words(rows)
    return e


def anchors_for(shot: dict, cast: dict[str, dict]) -> list[str]:
    return [cast[w.lower()]["anchor_path"] for w in shot["who"] if w.lower() in cast and cast[w.lower()].get("anchor_path")][:4]


def bible_text(b: dict) -> str:
    lines = [f"Title: {b.get('title', '')}", f"Tone: {b.get('tone', '')}", f"When: {b.get('when', '')}"]
    lines += [f"Person: {p['name']} — {p['who']}" for p in b.get("people", [])]
    lines += [f"Place: {x}" for x in b.get("places", [])] + [f"Rule: {x}" for x in b.get("rules", [])]
    lines += [f"Fact (ch {f['ch']}): {f['fact']}" for f in b.get("facts", [])]
    return "\n".join(lines)


def check_flags(text: str) -> list[str]:
    """One flag per fact (live 2026-11-25: 2 facts came back as 4 flags, each fact said twice), at most 3."""
    out, seen = [], set()
    for x in _json(text, list):
        if not isinstance(x, str) or not x.strip():
            continue
        f = re.sub(r"\s+", " ", x).strip()[:240]
        key = re.split(r"\s+[—–-]\s+but\b", f, maxsplit=1)[0].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out[:3]


def new_facts(text: str, ch: int) -> list[dict]:
    return [{"ch": ch, "fact": re.sub(r"\s+", " ", str(x)).strip()[:240]} for x in _json(text, list) if isinstance(x, str) and x.strip()][:10]


# ---------------------------------------------------------------- the cast this project chose (Hermes store)
def load_cast(run) -> dict[str, dict]:
    from . import cast as castmod
    ch = castmod.chosen(run.root)
    out = {}
    for cid in ch["ids"]:
        try:
            c = run.lab.mcp.call("cast_get", {"id": cid})
            out[str(c.get("name", "")).lower()] = {"id": cid, "name": c.get("name", ""), "brief": c.get("brief", ""),
                                                   "anchor_path": c.get("anchor_path", "")}
        except Exception as e:                                   # noqa: BLE001 — a missing character never stops the story
            if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
                raise
    return out


# ---------------------------------------------------------------- media helpers (ffmpeg; the Lab has no media library)
def _ff() -> str:
    return shutil.which("ffmpeg") or ""


def segment(clip: Path, wav: Path | None, secs: int, aspect: str, out: Path) -> str:
    """One shot → a same-size, same-rate piece with its voice (or silence), exactly `secs` long. '' = made."""
    ff = _ff()
    if not ff:
        return "ffmpeg isn't installed on this computer"
    w, h = SIZE.get(aspect, SIZE["9:16"])
    still = clip.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    cmd = [ff, "-y", "-loglevel", "error"] + (["-loop", "1"] if still else []) + ["-i", str(clip)]
    cmd += ["-i", str(wav)] if wav else ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono"]
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
    if not still:
        vf += ",tpad=stop_mode=clone:stop_duration=30"                    # a short AI clip holds its last frame
    cmd += ["-filter_complex", f"[0:v]{vf}[v];[1:a]apad,aresample=24000[a]", "-map", "[v]", "-map", "[a]", "-t", str(secs),
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ar", "24000", "-ac", "1", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"ffmpeg failed: {e}"
    return "" if r.returncode == 0 and out.is_file() and out.stat().st_size > 1000 else f"ffmpeg failed: {r.stderr[-200:]}"


def join(pieces: list[Path], out: Path) -> str:
    ff = _ff()
    if not ff:
        return "ffmpeg isn't installed on this computer"
    with tempfile.TemporaryDirectory() as d:
        lst = Path(d) / "list.txt"
        lst.write_text("".join(f"file '{str(p).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for p in pieces))
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                                "-movflags", "+faststart", str(out)], capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"ffmpeg failed: {e}"
    return "" if r.returncode == 0 and out.is_file() and out.stat().st_size > 1000 else f"ffmpeg failed: {r.stderr[-200:]}"


# ---------------------------------------------------------------- the run
def _hard(e) -> bool:
    return type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused")


def _write_json(run, sys: str, user: str, want, tokens: int, label: str):
    from . import makers
    shots = label.startswith(("Planning chapter", "Fixing the chapter"))      # 📓 craft notes ride only where shots are written
    text, who = makers.write(run, sys, user, tokens, label, "lab-story", craft="story" if shots else "")
    return _json(text, want), text, who


def run(run) -> None:
    """The whole 📖 Story chapter (Run.loop handles Stopped / SpendBlocked / PrivacyRefused)."""
    from . import cast as castmod, eyes, looks, makers, picture
    b = run.batch
    st = b["story"]
    root = Path(run.root)
    if not run.connected:
        run.state, run.why = "failed", "🔌 The writer, pictures and voice are Hermes's — switch the Lab to connected mode."
        return
    idea = picture.own_words(picture.picture_words(run.task)) or run.task.strip()
    form = st["form"]
    run._picture_answer = ""                                     # stills never stop to ask (choices come from the bible)
    cast = load_cast(run)
    names = [c["name"] for c in cast.values()]

    # 1 · 📚 bible
    bib = {} if st["new"] else bible(root)
    if not bib.get("title"):
        picture.stage(run, "📚", "Writing the story bible")
        castlines = "\n".join(f"- {c['name']}: {c['brief']}" for c in cast.values()) or "- none chosen: invent 2–3 adults"
        d, _, who = _write_json(run, BIBLE_SYS.format(keep=makers.KEEP_WORDS), f"His idea (his words, keep them):\n{idea}\n\nCast:\n{castlines}", dict, 900,
                                "Writing the story bible")
        bib = save_bible(root, {**clean_bible(d), "title": clean_bible(d)["title"] or idea[:60],
                                "people": clean_bible(d)["people"] or [{"name": c["name"], "who": c["brief"]} for c in cast.values()],
                                "facts": []})
        if st["new"]:
            for p in _dir(root).glob("chapter-*.json"):                # a new story starts at chapter 1; old ones kept aside
                p.rename(p.with_name(f"old-{int(time.time())}-{p.name}"))
        run._record({"action": "story", "why": f"📚 story bible: “{bib['title']}” — {len(bib['people'])} people, "
                     f"{len(bib['places'])} places, {len(bib['rules'])} rules", "result": {"bible": bib, "writer": who}, "usd": 0.0})
    else:
        run._record({"action": "story", "why": f"📚 using the story bible “{bib['title']}” ({len(bib['facts'])} facts so far)",
                     "result": {"bible": bib}, "usd": 0.0})
    ch_n = st["chapter"] or resume_or_next(root, form)
    chap = chapter(root, ch_n)
    b["chapter"] = ch_n
    run.save()

    # 2 · 🗒 outline → 🎬 shots (or ✍️ prose)
    n = shots_for(form) or SHORT_SHOTS
    if not chap.get("shots") and not chap.get("prose"):
        picture.stage(run, "🗒", f"Planning chapter {ch_n}" + ("" if form == "words" else f" — {n} shots"))
        sys = SHOTS_SYS.format(keep=makers.KEEP_WORDS, form="short vertical video" if form == "short" else "story chapter",
                               n=n, extra=SHORT_EXTRA if form == "short" else LONG_EXTRA.format(ch=ch_n))
        user = f"Story bible:\n{bible_text(bib)}\n\nHis idea (his words):\n{idea}"
        d, _, who = _write_json(run, sys, user, dict, 1600, f"Planning chapter {ch_n}")
        shots = clean_shots(d.get("shots"), names + [p["name"] for p in bib["people"]], form)
        if not shots:
            run.state, run.why = "failed", "🗒 The writer didn't send a shot list I can read. 👉 Try ▶ Start again, or pick another writer model."
            return
        chap = {"form": form, "outline": str(d.get("outline") or "").strip()[:2000], "shots": shots, "idea": idea}
        # 🔗 continuity check before anything is made
        if bib["facts"]:
            picture.stage(run, "🔗", "Checking the plan against the story so far")
            text, _ = makers.write(run, CHECK_SYS, f"Facts:\n{bible_text({'facts': bib['facts']})}\n\nHis idea for this chapter: {idea}\n\nNew plan:\n"
                                   + chap["outline"] + "\n" + "\n".join(f"{s['k'] + 1}. {', '.join(s['who'])} — {s['action']} ({s['where']})"
                                                                        for s in shots), 500, "Continuity check", "lab-story")
            flags = check_flags(text)
            chap["flags"] = flags
            run._record({"action": "story", "why": "🔗 continuity: " + ("no contradictions" if not flags else f"{len(flags)} flag(s) — " + " · ".join(flags)),
                         "result": {"flags": flags}, "usd": 0.0})
            if flags:
                pick = makers.ask(run, f"story-flag-{ch_n}", [{"q": "🔗 This chapter breaks the story so far: " + " · ".join(flags) + " What now?",
                                                                "choices": [FIX_TEXT, FIX_BIBLE, KEEP_BOTH], "best": 0, "why": "keep the story straight"}], always=True)
                pick = next(iter(pick.values()), FIX_TEXT)
                chap["flag_pick"] = pick
                if pick.startswith(FIX_TEXT[:1]):
                    d2, _, _ = _write_json(run, sys, user + "\n\nFix these contradictions with the facts:\n" + "\n".join(flags), dict, 1600, "Fixing the chapter")
                    fixed = clean_shots(d2.get("shots"), names + [p["name"] for p in bib["people"]], form)
                    if fixed:
                        chap.update(outline=str(d2.get("outline") or chap["outline"])[:2000], shots=fixed)
                elif pick.startswith(FIX_BIBLE[:1]):
                    bib = save_bible(root, {**bib, "facts": bib["facts"] + [{"ch": ch_n, "fact": f"Changed in chapter {ch_n}: {f}"} for f in flags]})
        if form == "words":
            picture.stage(run, "✍️", f"Writing chapter {ch_n}")
            prose, _ = makers.write(run, PROSE_SYS.format(keep=makers.KEEP_WORDS),
                                    f"Story bible:\n{bible_text(bib)}\n\nOutline:\n{chap['outline']}\n\nShots:\n"
                                    + "\n".join(f"- {s['action']} ({s['where']})" for s in chap["shots"]), 3000, f"Writing chapter {ch_n}", "lab-story")
            rel = picture.claim(root, f"docs/story-{makers.slug(bib['title'], default='story')}-ch{ch_n}.md")
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(f"# {bib['title']} — chapter {ch_n}\n\n{prose}\n")
            chap["prose"] = rel
            run.docs = (getattr(run, "docs", None) or []) + [{"path": rel}]
        save_chapter(root, ch_n, chap)
        run._record({"action": "story", "why": f"🗒 chapter {ch_n}: " + (chap["outline"][:200] or f"{len(chap['shots'])} shots"),
                     "result": {"shots": chap["shots"]}, "usd": 0.0})
    b["shots"] = chap["shots"]
    run.save()

    if form != "words":
        _stills(run, chap, ch_n, bib, cast)
        clips = _clips(run, chap, ch_n, st["clips"])
        if clips:
            _film(run, chap, ch_n, bib, st["narrate"])

    # 🔗 what changed → the bible (once per chapter)
    if not chap.get("facts_done"):
        try:
            text, _ = makers.write(run, FACTS_SYS, f"Bible:\n{bible_text(bib)}\n\nChapter {ch_n}:\n{chap.get('outline', '')}\n"
                                   + "\n".join(f"- {', '.join(s['who'])}: {s['action']} ({s['where']})" for s in chap["shots"]),
                                   500, "Noting what changed", "lab-story")
            facts = new_facts(text, ch_n)
            if facts:
                bib = save_bible(root, {**bib, "facts": bib["facts"] + facts})
            chap["facts_done"] = True
            save_chapter(root, ch_n, chap)
            run._record({"action": "story", "why": f"🔗 {len(facts)} new fact(s) into the bible" + (": " + " · ".join(f["fact"] for f in facts[:4]) if facts else ""),
                         "result": {"facts": facts}, "usd": 0.0})
        except Exception as e:                                   # noqa: BLE001 — facts are a bonus
            if _hard(e):
                raise
    _finish(run, chap, ch_n, bib)


def _stills(run, chap: dict, ch_n: int, bib: dict, cast: dict) -> None:
    from . import eyes, looks, picture
    b, root = run.batch, Path(run.root)
    aspect = "Tall (phone)" if chap["form"] == "short" else "Wide (screen)"
    look = []
    try:
        from . import styles
        look = styles.project_look(root)
    except Exception:                                            # noqa: BLE001
        pass
    retries = int(((run.cfg or {}).get("story") or {}).get("retries", RETRIES))
    base = run.task
    try:
        for s in chap["shots"]:
            b["now"] = s["k"]
            if s.get("still") and (root / s["still"]).is_file():          # restart: finished shots are skipped
                continue
            words = shot_prompt(s, bib, cast)
            b["refs_abs"] = anchors_for(s, cast)
            tries = 0
            task = words + f"\nShape: {aspect}" + (f"\nLook: {looks.SEP.join(look)}" if look else "")
            while True:
                run.task, run.state, run.why = task, "running", ""
                before = len(run.pictures)
                try:
                    picture.run(run)
                except Exception as e:                           # noqa: BLE001 — one lost shot never ends the chapter
                    if _hard(e):
                        raise
                run.state = "running"                            # picture.run marks it done — a restart now must say "interrupted", not "done"
                if len(run.pictures) <= before:
                    s["error"] = run.why or "no picture came back"
                    break
                pic = run.pictures[-1]
                s.update(still=pic["path"], usd=float(s.get("usd") or 0) + float(pic.get("usd") or 0), refs=len(b["refs_abs"]))
                s.pop("error", None)
                if not eyes.on(run):
                    break
                e = eyes.check(run, (root / pic["path"]).read_bytes(), shot_prompt(s, bib, cast, looks=False), look,
                               label=f"shot {s['k'] + 1}")          # 👁 grades what a picture can show, not the bracketed looks
                eyes.record(run, f"shot {s['k'] + 1}", e)
                picture._craft_seen(run, "story", e, shot_prompt(s, bib, cast, looks=False))
                e = writing_check(run, (root / pic["path"]).read_bytes(), e, task, s["k"])
                s["eyes"] = {x: e.get(x) for x in ("score", "missing", "error") if e.get(x) is not None}
                if e.get("low") and e.get("fix_task") and tries < retries and not float(pic.get("usd") or 0):
                    tries += 1
                    run._record({"action": "eyes", "why": f"👁 shot {s['k'] + 1} {e['score']}% — remaking it once ($0) with: {e['fix']}",
                                 "result": s["eyes"], "usd": 0.0})
                    task = e["fix_task"]
                    continue
                break
            b["items"].append({"path": s.get("still", ""), "k": s["k"], "kind": "picture", "usd": s.get("usd", 0),
                               "variation": f"📖 shot {s['k'] + 1} · {s['seconds']} s · {s['action'][:80]}",
                               **({"eyes": s["eyes"]} if s.get("eyes") else {})} if s.get("still") else
                              {"path": "", "k": s["k"], "kind": "picture", "variation": f"📖 shot {s['k'] + 1} ❌ {s.get('error', '')[:100]}"})
            save_chapter(root, ch_n, chap)
            run.save()
    finally:
        run.task = base
        b.pop("refs_abs", None)


def _clip_ai(run, still: Path, s: dict, model: str, aspect: str) -> tuple[str, float]:
    """(clip path or '', usd). Hermes video_make from the still; '' when it didn't come back."""
    from . import makers, picture, video
    args = {"prompt": f"{s['action']}. Camera: {s['camera'] or 'slow push-in'}.", "duration": "5s",
            "resolution": str(run.cfg.get("video_resolution") or "720p"), "negative_prompt": video.NO_TEXT_VIDEO,
            "name": f"story shot {s['k'] + 1}", "task": f"lab-video:{run.project['id']}",
            "image_b64": base64.b64encode(still.read_bytes()).decode()}
    if model:
        args["model"] = model
    try:
        stt = run.lab.mcp.call("video_make", args)
    except Exception as e:                                       # noqa: BLE001
        if _hard(e):
            raise
        return "", 0.0
    local = model.startswith("local/")
    res = makers.wait_job(run, stt["key"], "🎞", f"Shot {s['k'] + 1} moving" + (" on this computer" if local else ""),
                          float(stt.get("est_usd") or 0), "many minutes" if local else "1–5 min",
                          video.LOCAL_WAIT_S if local else video.MAX_WAIT_S)
    out = res.get("result") or {}
    if res.get("state") != "done" or not out.get("path"):
        return "", 0.0
    rel = picture.claim(run.root, f"videos/story/shot-{s['k'] + 1}-{makers.stamp()}.mp4")
    (run.root / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out["path"], run.root / rel)
    usd = float(out.get("usd") or 0)
    run.usd += usd
    return rel, usd


def _clips(run, chap: dict, ch_n: int, mode: str) -> bool:
    from . import makers, picture, video
    root = Path(run.root)
    if mode == "none":
        return any(s.get("still") for s in chap["shots"])         # the film can still be made from the stills
    aspect = "9:16" if chap["form"] == "short" else "16:9"
    todo = [s for s in chap["shots"] if s.get("still") and not (s.get("clip") and (root / s["clip"]).is_file())]
    model = ""
    if mode == "local":
        model = next((p.get("model", "") for p in video.all_paths() if p["kind"] == "local" and p["on"]), "")
        if not model:
            run._record({"action": "route", "why": "🏠 no local video path is switched on — 🆓 pan-and-zoom instead", "result": {}, "usd": 0.0})
            mode = "free"
    if mode == "venice" and todo:
        try:
            q = run.lab.mcp.call("video_quote", {"duration": "5s", "resolution": str(run.cfg.get("video_resolution") or "720p"),
                                                 "image_b64": base64.b64encode((root / todo[0]["still"]).read_bytes()).decode()})
            each, today, cap = float(q.get("usd") or 0), float(q.get("today_usd") or 0), float(q.get("daily_cap") or 5)
        except Exception as e:                                   # noqa: BLE001
            if _hard(e):
                raise
            each, today, cap = 0.0, 0.0, 5.0
            run._record({"action": "route", "why": f"💲 couldn't price Venice clips ({getattr(e, 'message', e)}) — 🆓 pan-and-zoom", "result": {}, "usd": 0.0})
            mode = "free"
        if mode == "venice":
            tot = each * len(todo)
            over = today + tot > cap
            choices = ([] if over else [f"▶ Make {len(todo)} clips (${tot:.2f})"]) + ["🆓 Pan-and-zoom instead ($0)", "🖼 Stills only"]
            ans = makers.ask(run, f"story-price-{ch_n}", [{"q": f"{len(todo)} Venice clips ≈ ${tot:.2f} (${each:.2f} each). Video spend "
                                                                f"today ${today:.2f} of ${cap:.2f}." + (" Over the cap." if over else ""),
                                                           "choices": choices, "best": 0, "why": "price first"}], always=True)
            ans = next(iter(ans.values()), "")
            mode = "venice" if ans.startswith("▶") else "free" if ans.startswith("🆓") else "none"
            if mode == "venice":
                run.cap_usd = max(run.cap_usd, run.usd + tot + 0.05)
            if mode == "none":
                return any(s.get("still") for s in chap["shots"])
    for s in todo:
        run._check_stop()
        still = root / s["still"]
        rel, usd = "", 0.0
        if mode in ("local", "venice"):
            rel, usd = _clip_ai(run, still, s, model if mode == "local" else "", aspect)
            if not rel:
                run._record({"action": "route", "why": f"🎞 shot {s['k'] + 1}: AI motion didn't come back — 🆓 pan-and-zoom for this one", "result": {}, "usd": 0.0})
        if not rel:
            picture.stage(run, "🆓", f"Shot {s['k'] + 1} — pan-and-zoom ($0)")
            rel = picture.claim(root, f"videos/story/shot-{s['k'] + 1}-{makers.stamp()}-panzoom.mp4")
            why = video.pan_zoom(still, root / rel, s["seconds"], aspect)
            if why:
                s["clip_error"] = why
                continue
        s.update(clip=rel, usd=float(s.get("usd") or 0) + usd)
        save_chapter(root, ch_n, chap)
        run.save()
    return any(s.get("clip") or s.get("still") for s in chap["shots"])


def _film(run, chap: dict, ch_n: int, bib: dict, narrate: bool) -> None:
    from . import makers, picture
    root = Path(run.root)
    aspect = "9:16" if chap["form"] == "short" else "16:9"
    voice_off = ""
    if narrate:
        for s in chap["shots"]:
            if not s.get("line") or (s.get("wav") and (root / s["wav"]).is_file()):
                continue
            picture.stage(run, "🎙", f"Narrating shot {s['k'] + 1}")
            try:
                r = run.lab.mcp.call("narrate", {"text": s["line"]})
                rel = f"audio/story/ch{ch_n}-shot-{s['k'] + 1}.wav"
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes(base64.b64decode(r["b64"]))
                s["wav"] = rel
            except Exception as e:                               # noqa: BLE001 — no voice → the film is made silent
                if _hard(e):
                    raise
                voice_off = (getattr(e, "message", "") or str(e))[:200] + (f" 👉 {e.fix}" if getattr(e, "fix", "") else "")
                break
        if voice_off:
            run._record({"action": "story", "why": f"🔇 narration skipped: {voice_off}", "result": {}, "usd": 0.0})
    picture.stage(run, "🎞", "Joining the shots into one film")
    pieces = []
    with tempfile.TemporaryDirectory() as d:
        for s in chap["shots"]:
            src = s.get("clip") or s.get("still")
            if not src or not (root / src).is_file():
                continue
            wav = root / s["wav"] if s.get("wav") and (root / s["wav"]).is_file() else None
            out = Path(d) / f"p{s['k']:02d}.mp4"
            why = segment(root / src, wav, s["seconds"], aspect, out)
            if why:
                run._record({"action": "story", "why": f"🎞 shot {s['k'] + 1} left out of the film: {why}", "result": {}, "usd": 0.0})
                continue
            pieces.append(out)
        if not pieces:
            chap["film_error"] = "no shot could be put into the film"
            return
        rel = picture.claim(root, f"videos/story-{makers.slug(bib['title'], default='story')}-ch{ch_n}-{makers.stamp()}.mp4")
        why = join(pieces, root / rel)
    if why:
        chap["film_error"] = why
        run._record({"action": "story", "why": f"🎞 couldn't join the film: {why}", "result": {}, "usd": 0.0})
        return
    secs = sum(s["seconds"] for s in chap["shots"] if s.get("clip") or s.get("still"))
    chap["film"] = rel
    chap["voice"] = not voice_off and any(s.get("wav") for s in chap["shots"])
    save_chapter(root, ch_n, chap)
    vid = {"path": rel, "model": "📖 story film (ffmpeg join)", "usd": round(sum(float(s.get("usd") or 0) for s in chap["shots"]), 4),
           "seconds": secs, "duration": f"{secs}s"}
    run.videos = (getattr(run, "videos", None) or []) + [vid]
    run._record({"action": "video", "path": rel, "why": f"🎞 joined {len(pieces)} shots into one {secs}-second film"
                 + (" with narration" if chap["voice"] else " (no voice)"), "result": vid, "usd": 0.0})


def _finish(run, chap: dict, ch_n: int, bib: dict) -> None:
    from . import picture
    b = run.batch
    b["now"] = b["n"] = len(chap.get("shots") or []) or 1
    made = [s for s in chap.get("shots", []) if s.get("still")]
    cost = sum(float(s.get("usd") or 0) for s in chap.get("shots", []))
    scores = [s["eyes"]["score"] for s in made if (s.get("eyes") or {}).get("score") is not None]
    if chap.get("form") == "words":
        ok = bool(chap.get("prose"))
        run.state = "done" if ok else "failed"
        run.why = (f"📖 “{bib['title']}” chapter {ch_n} written — {chap['prose']}. ${run.usd:.3f}." if ok
                   else "📖 The writer didn't send the chapter. 👉 ▶ Start again.")
    elif not made:
        run.state, run.why = "failed", "📖 No shot pictures came back. " + (chap["shots"][0].get("error", "") if chap.get("shots") else "")
    else:
        low = [s["k"] + 1 for s in made if (s.get("eyes") or {}).get("score") is not None and s["eyes"]["score"] < 70]
        run.state = "done"
        run.why = (f"📖 “{bib['title']}” chapter {ch_n}: {len(made)} of {len(chap['shots'])} shots"
                   + (f", 👁 avg {round(sum(scores) / len(scores))}% match" if scores else "")
                   + (f" (weak: shot {', '.join(map(str, low))})" if low else "")
                   + (f". 🎞 Film: {chap['film']}" + ("" if chap.get("voice") else " (no voice)") if chap.get("film") else
                      f". 🎞 No film: {chap.get('film_error', 'clips off')}")
                   + f". Spend: ${cost:.3f}" + (" — all on this computer, $0." if not cost else "."))
    chap["done"] = run.state == "done"
    save_chapter(run.root, ch_n, chap)
    picture.stage(run, "✅" if run.state == "done" else "❌", "Story chapter ready" if run.state == "done" else "Story didn't finish")
