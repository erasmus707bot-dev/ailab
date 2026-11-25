"""🎬 Video Rebuild (build prompt #2 R3, Scott 2026-11-25: "take a video and rebuild it with my own characters").

Input: a 🎞 breakdown (prompt #1 M4 — Hermes video_breakdown). Busy scenes are split into **beats** of one clear action,
2–4 s each; every beat carries a shot recipe (subject as person A/B · setting · motion · framing · camera · light ·
seconds) — never the source people's looks. Per beat: a still with his cast (their anchors as references, the official
style's Look) → 👁 checks it against the recipe **plus a multi-character identity check** (right count, each person's
hair + outfit where it belongs, no swapped traits, no merged limbs) → a $0 remake once if it scored low → a clip by the
chosen path (🆓 pan-and-zoom ⭐ · 🏠 local AI motion · Venice after one price card) → AI clips get the identity check
on 3 frames → joined into one film, with the chosen sound.

Switches (Gate A1 defaults ⭐): mode 🔁 whole video ⭐ / 🎯 pick scenes · level 2 "same shots" ⭐ / 3 "same movement"
(hosted motion transfer — no host wired yet, says so, never spends; a 🔒 private source never leaves gandalf) · audio
✍️ new words + narrator ⭐ / 🔊 keep original / 🔇 silent · voice 🎙 narrator ⭐ / 🗣 one per character / 👄 lip sync
(hosted — not available yet, falls back to one voice per character, says so).
⚖️ Review: original and rebuild side by side, synced through the beat table, a score per shot, 🔁 retry one shot.
Results are 🔒 personal (personal use and practice). Record: <project>/.shelf/rebuild/<breakdown id>.json.
"""
from __future__ import annotations

import base64
import json
import math
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

BEAT_MIN, BEAT_MAX = 2.0, 4.0
MODES = {"whole": "🔁 Whole video", "pick": "🎯 Pick scenes"}
LEVELS = {2: "🎯 Same shots", 3: "🏃 Same movement (hosted)"}
AUDIO = {"narrate": "✍️ New words + narrator", "keep": "🔊 Keep the original sound", "silent": "🔇 Silent"}
VOICES = {"narrator": "🎙 One narrator", "each": "🗣 A voice per character", "lipsync": "👄 Talking, lip sync (hosted)"}
CLIPS = {"free": "🆓 Pan-and-zoom ($0)", "local": "🏠 AI motion on this computer ($0, slow)", "venice": "💲 Venice AI motion (price first)"}
LETTERS = "ABCD"
RETRIES = 1
LOOKS = re.compile(r"\s*,?\s*\b(?:with |who has |having )?(?:(?:(?:long|short|curly|straight|wavy|red|black|brown|grey|gray|blond|blonde|dark|light)[- ])+hair(?:ed)?|"
                   r"blonde?|brunette|redhead|ginger|bald|bearded|freckled|(?:black|brown|white|pale|dark)[- ]skinned)\b", re.I)
REWRITE_SYS = ("You re-tell a video's spoken words in completely new words for Scott's remake, same meaning and timing. "
               "Reply with JSON only: a list of strings, exactly one per numbered beat, each short enough to say in that "
               "beat's seconds (about 2.5 words per second). An empty beat may get a short new line or \"\".")
NOT_YET_L3 = "🏃 Same movement needs a hosted motion-transfer service — none is wired into Hermes yet, so this rebuild uses 🎯 same shots."
NOT_YET_LIPS = "👄 Lip sync needs a hosted service that isn't wired in yet — each character gets their own voice instead."


# ---------------------------------------------------------------- pure pieces (tested)
def norm(s) -> dict | None:
    if not isinstance(s, dict) or not re.fullmatch(r"bd-[0-9a-f]{16}", str(s.get("bd") or "")):
        return None
    try:
        level = 3 if int(s.get("level") or 2) == 3 else 2
    except (TypeError, ValueError):
        level = 2
    picks = sorted({int(x) for x in s.get("picks") or [] if str(x).lstrip("-").isdigit() and int(x) >= 0})[:200]
    retry = s.get("retry")
    retry = int(retry) if isinstance(retry, int) or str(retry or "").isdigit() else None
    return {"bd": s["bd"], "mode": s.get("mode") if s.get("mode") in MODES else "whole", "picks": picks, "level": level,
            "audio": s.get("audio") if s.get("audio") in AUDIO else "narrate",
            "voice": s.get("voice") if s.get("voice") in VOICES else "narrator",
            "clips": s.get("clips") if s.get("clips") in CLIPS else "free", "retry": retry, "fresh": bool(s.get("fresh"))}


def clean_recipe(r: dict) -> dict:
    out = {k: str((r or {}).get(k) or "").strip()[:240] for k in ("subject", "in_frame", "pose", "setting", "motion", "framing", "camera", "light")}
    for k in ("subject", "pose"):
        out[k] = re.sub(r"\s{2,}", " ", LOOKS.sub("", out[k])).strip(" ,")
    return out


def has_looks(r: dict) -> bool:
    return bool(LOOKS.search(str((r or {}).get("subject") or "")))


def beats(scenes: list[dict], picks: list[int] | None = None) -> list[dict]:
    """Scenes → beats of one action, BEAT_MIN–BEAT_MAX s (a long scene is split evenly). picks = scene indices to keep."""
    out = []
    for s in scenes or []:
        if picks and int(s["i"]) not in picks:
            continue
        a, b = float(s["start"]), float(s["end"])
        n = max(1, math.ceil((b - a) / BEAT_MAX - 1e-9))
        while n > 1 and (b - a) / n < BEAT_MIN:
            n -= 1
        step = (b - a) / n
        rec = clean_recipe(s.get("recipe") or {})
        for j in range(n):
            st, en = round(a + j * step, 2), round(a + (j + 1) * step, 2)
            out.append({"k": len(out), "scene": int(s["i"]), "part": j + 1, "parts": n, "start": st, "end": en,
                        "seconds": max(2, min(5, int(round(en - st)))), "recipe": rec, "said": _said_in(s, st, en, a, b),
                        "frame_path": s.get("frame_path", "")})
    return out


def _said_in(s: dict, st: float, en: float, a: float, b: float) -> str:
    words = str(s.get("said") or "").split()
    if not words or b <= a:
        return ""
    i, j = round(len(words) * (st - a) / (b - a)), round(len(words) * (en - a) / (b - a))
    return " ".join(words[i:j])


def people_in(recipe: dict) -> list[str]:
    """Letters of the people a recipe names, in order: ["A", "B"]. The in_frame line wins (live R4 2026-11-25: a close-up
    of one face was drawn with both women because the subject line still said "A arm-wrestles B")."""
    inf = str(recipe.get("in_frame") or "")
    got = []
    for m in re.finditer(r"\bperson ([A-D])\b", inf, re.I):
        if m.group(1).upper() not in got:
            got.append(m.group(1).upper())
    n = re.match(r"\s*(\d)", inf)
    if got and (not n or int(n.group(1)) == len(got)):
        return got
    seen = []
    for m in re.finditer(r"\bperson ([A-D])\b", str(recipe.get("subject") or "") + " " + str(recipe.get("motion") or ""), re.I):
        L = m.group(1).upper()
        if L not in seen:
            seen.append(L)
    return seen


def cast_for(beat: dict, cast: list[dict]) -> list[dict]:
    """The cast members in this beat: person A → cast[0], person B → cast[1] … (no people named → the whole cast)."""
    ls = people_in(beat["recipe"]) or list(LETTERS[:len(cast)])
    return [cast[LETTERS.index(L)] for L in ls if LETTERS.index(L) < len(cast)]


def words_for(beat: dict, cast: list[dict]) -> str:
    """The still's words: person A/B → name (look), then setting · framing · camera · light. Never the source looks."""
    r = beat["recipe"]
    subj = r["subject"] or ", ".join(c["name"] for c in cast_for(beat, cast))
    for i, c in enumerate(cast):
        look = str(c.get("brief") or "").split(": ", 1)[-1]
        subj = re.sub(rf"\bperson {LETTERS[i]}\b", f"{c['name']} ({look})" if look else c["name"], subj, count=1, flags=re.I)
        subj = re.sub(rf"\bperson {LETTERS[i]}\b", c["name"], subj, flags=re.I)
    pose = r.get("pose", "")
    for i, c in enumerate(cast):
        pose = re.sub(rf"\bperson {LETTERS[i]}\b", c["name"], pose, flags=re.I)
    who = cast_for(beat, cast)
    only = f"only {' and '.join(c['name'] for c in who)} in the frame" if 0 < len(who) < len(people_in({"subject": r["subject"]}) or LETTERS[:len(cast)]) else ""
    parts = [subj, only, pose, r["setting"], r["framing"], r["light"]]
    return ", ".join(p.strip().rstrip(".") for p in parts if p.strip())


def identity_points(people: list[dict]) -> list[dict]:
    """👁 multi-character identity: count, each person's own hair + outfit, no swapped traits, no merged limbs, no onlooker copies."""
    from . import eyes
    pts = []
    if people:
        n = len(people)
        who = "person" if n == 1 else "people"          # live clip 2026-11-25: a crowd watches the arm-wrestle
        pts.append({"q": f"Are there exactly {n} main {who} taking part in the action? Do not count anyone watching in the background.",
                    "want": True, "what": f"exactly {n} main {who}", "kind": "count"})
    for c in people[:3]:
        t = c.get("traits") or {}
        if t.get("hair_colour") and t.get("outfit_colour"):
            pts.append({"q": f"Is there a person with {t['hair_colour']} hair wearing {t['outfit_colour']} clothes?", "want": True,
                        "what": f"{c['name']} ({t['hair_colour']} hair, {t['outfit_colour']})", "kind": "identity"})
    if len(people) >= 2:
        a, b = (people[0].get("traits") or {}), (people[1].get("traits") or {})
        if a.get("hair_colour") and b.get("outfit_colour"):
            pts.append({"q": f"Does any one person have {a['hair_colour']} hair AND wear {b['outfit_colour']} clothes?", "want": False,
                        "what": f"no swap ({people[0]['name']}'s hair with {people[1]['name']}'s clothes)", "kind": "swap"})
        pts.append({"q": "Are any arms, legs or bodies merged or fused together in an impossible way?", "want": False,
                    "what": "no merged limbs", "kind": "limbs"})
    onl = eyes.onlooker_point([((c.get("traits") or {}).get("hair_colour", ""), (c.get("traits") or {}).get("outfit_colour", ""))
                               for c in people], len(people))          # R4 shot 7: the spectator copied Dina
    return pts + ([onl] if onl else [])


def check_points(beat: dict, cast: list[dict]) -> list[dict]:
    from . import eyes
    rec = [p for p in eyes.points(words_for(beat, cast)) if p["kind"] in ("show", "notext")][:5]
    pose = beat["recipe"].get("pose", "")
    for i, c in enumerate(cast):
        pose = re.sub(rf"\bperson {LETTERS[i]}\b", c["name"], pose, flags=re.I)
    pp = ([{"q": f"Are the people placed like this: {pose}?", "want": True, "what": f"pose: {pose[:80]}", "kind": "show"}] if pose else [])
    return (identity_points(cast_for(beat, cast)) + pp + rec)[:12]


def identity_failed(rows: list[dict]) -> list[str]:
    return [r["what"] for r in rows or [] if r.get("kind") in ("count", "identity", "swap", "limbs", "onlooker") and r.get("ok") is False]


def table(bs: list[dict]) -> list[dict]:
    """Sync table for ⚖️ review: each beat's place in the rebuild (out) and in the original (src)."""
    t, out = 0.0, []
    for b in bs:
        if not (b.get("clip") or b.get("still")):
            continue
        out.append({"k": b["k"], "out_start": round(t, 2), "out_end": round(t + b["seconds"], 2), "src_start": b["start"], "src_end": b["end"]})
        t += b["seconds"]
    return out


def src_time(tab: list[dict], t: float) -> float:
    """Rebuild time → original time (each beat stretched/squeezed linearly)."""
    for r in tab:
        if r["out_start"] <= t < r["out_end"] or r is tab[-1]:
            span = (r["out_end"] - r["out_start"]) or 1
            f = max(0.0, min(1.0, (t - r["out_start"]) / span))
            return round(r["src_start"] + f * (r["src_end"] - r["src_start"]), 2)
    return 0.0


def motion_host() -> dict:
    """🏃 What Hermes's free motion probe found: {"model", "usd_5s"} or {} (probe not run / nothing priced)."""
    from . import rip
    try:
        d = json.loads((rip.data() / "settings" / "motion_probe.json").read_text())
    except (OSError, ValueError):
        return {}
    ms = [m for m in d.get("models") or [] if m.get("usd_5s") is not None]
    ms.sort(key=lambda m: ("standard" not in m["id"], m["usd_5s"]))           # standard (cheaper) first
    return {"model": ms[0]["id"], "usd_5s": ms[0]["usd_5s"]} if d.get("ok") and ms else {}


def level3_block(private: bool, host: dict | None = None) -> str:
    """Why level 3 can't run ('' = it can): a private source never leaves gandalf; no probed host = not yet."""
    if private:
        return "🔒 This video is private, so it never leaves gandalf — 🏃 same movement (hosted) is off for it; using 🎯 same shots."
    if not host:
        return NOT_YET_L3 + " 👉 On gandalf: cd ~/hermes && python3 -m forge.projects.probe_motion (free, spends nothing)."
    return ""


def cut_clip(src: Path, a: float, b: float, out: Path) -> bool:
    """The source beat as a small mp4 (the driving clip for motion control). ≤ 720p, no sound."""
    ff = _ff()
    if not ff:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{a:.2f}", "-t", f"{max(1.0, b - a):.2f}", "-i", str(src), "-an",
                        "-vf", "scale='min(720,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-movflags", "+faststart",
                        str(out)], capture_output=True, timeout=180, check=False)
    return r.returncode == 0 and out.is_file() and 1000 < out.stat().st_size <= 50_000_000


# ---------------------------------------------------------------- record
def _file(root, bd: str) -> Path:
    return Path(root) / ".shelf" / "rebuild" / f"{bd}.json"


def record(root, bd: str) -> dict | None:
    try:
        return json.loads(_file(root, bd).read_text())
    except (OSError, ValueError):
        return None


def save(root, rec: dict) -> None:
    f = _file(root, rec["bd"])
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec))
    tmp.replace(f)


def records(root) -> list[dict]:
    d = Path(root) / ".shelf" / "rebuild"
    out = []
    for f in sorted(d.glob("bd-*.json")) if d.is_dir() else []:
        try:
            r = json.loads(f.read_text())
            out.append({k: r.get(k) for k in ("bd", "title", "film", "made", "personal", "settings")} | {"shots": len(r.get("beats") or [])})
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda r: -float(r.get("made") or 0))


# ---------------------------------------------------------------- gandalf helpers
def _ff() -> str:
    return shutil.which("ffmpeg") or ""


def cut_audio(src: Path, a: float, b: float, out: Path) -> bool:
    ff = _ff()
    if not ff:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{a:.2f}", "-t", f"{max(0.1, b - a):.2f}", "-i", str(src), "-vn",
                        "-ac", "1", "-ar", "24000", str(out)], capture_output=True, timeout=120, check=False)
    return r.returncode == 0 and out.is_file() and out.stat().st_size > 500


def frames_at(clip: Path, n: int = 3) -> list[bytes]:
    ff = _ff()
    if not ff:
        return []
    out = []
    with tempfile.TemporaryDirectory() as d:
        for i, at in enumerate((0.3, 1.5, 3.5)[:n]):
            f = Path(d) / f"f{i}.jpg"
            subprocess.run([ff, "-y", "-loglevel", "error", "-ss", str(at), "-i", str(clip), "-frames:v", "1", "-q:v", "3", str(f)],
                           capture_output=True, timeout=40, check=False)
            if f.is_file() and f.stat().st_size > 500:
                out.append(f.read_bytes())
    return out


def _hard(e) -> bool:
    return type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused")


def load_cast(run) -> list[dict]:
    """The project's chosen cast, in order (person A = first), with traits for the identity check."""
    from . import cast as castmod
    out = []
    for cid in castmod.chosen(run.root)["ids"]:
        try:
            c = run.lab.mcp.call("cast_get", {"id": cid})
            out.append({"id": cid, "name": c.get("name", ""), "brief": c.get("brief", ""), "traits": c.get("traits") or {},
                        "anchor_path": c.get("anchor_path", "")})
        except Exception as e:                                   # noqa: BLE001
            if _hard(e):
                raise
    return out


def _aspect(frame_path: str) -> str:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                            frame_path], capture_output=True, text=True, timeout=20, check=False)
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        return "9:16" if h > w else "16:9"
    except Exception:                                            # noqa: BLE001
        return "16:9"


# ---------------------------------------------------------------- the run
def _motion(run, rec: dict, bs: list[dict], cast: list[dict], host: dict, notes: list[str]) -> None:
    """🏃 Kling motion control per beat: still (who) + the source beat (how they move). Price card first; nothing spends
    without the tap; a beat that fails falls back to the level-2 clip path."""
    import shutil as _sh
    from . import eyes, makers, picture
    root, src = Path(run.root), Path(str(rec.get("source") or ""))
    todo = [x for x in bs if x.get("still") and not (x.get("clip") and (root / x["clip"]).is_file())]
    if not todo:
        return
    if not src.is_file():
        notes.append("🏃 The original video isn't on disk any more — same movement skipped.")
        return
    drivers = {}
    for x in todo:
        rel = f"videos/rebuild/driver-{rec['bd'][3:11]}-{x['k'] + 1}.mp4"
        if cut_clip(src, x["start"], x["end"], root / rel):
            drivers[x["k"]] = rel
    quotes, model = {}, host["model"]
    for x in todo:
        if x["k"] not in drivers:
            continue
        try:
            q = run.lab.mcp.call("video_quote", {"model": model, "duration": f"{x['seconds']}s"})
            quotes[x["k"]] = (float(q.get("usd") or 0), float(q.get("today_usd") or 0), float(q.get("daily_cap") or 5))
        except Exception as e:                                   # noqa: BLE001
            if _hard(e):
                raise
            notes.append(f"🏃 Couldn't price same movement ({getattr(e, 'message', e)}) — using 🎯 same shots.")
            return
    if not quotes:
        return
    tot = sum(q[0] for q in quotes.values())
    today, cap = next(iter(quotes.values()))[1:]
    each = " · ".join(f"shot {k + 1} ${q[0]:.2f}" for k, q in quotes.items())
    over = today + tot > cap
    ans = makers.ask(run, f"rebuild-motion-{rec['bd']}-{len(quotes)}", [{
        "q": f"🏃 Same movement (hosted {model}): {each} — ${tot:.2f} total. Your clip's moves leave gandalf for Venice. "
             f"Video spend today ${today:.2f} of ${cap:.2f}." + (" Over the cap." if over else ""),
        "choices": ([] if over else [f"▶ Copy the movement (${tot:.2f})"]) + ["🎯 Same shots instead ($0)"], "best": 0,
        "why": "price first, nothing spent without your tap"}], always=True)
    if not next(iter(ans.values()), "").startswith("▶"):
        notes.append("🏃 Same movement not bought — 🎯 same shots used.")
        return
    run.cap_usd = max(run.cap_usd, run.usd + tot + 0.05)
    for x in todo:
        if x["k"] not in quotes:
            continue
        run._check_stop()
        try:
            stt = run.lab.mcp.call("video_make", {
                "model": model, "prompt": words_for(x, cast)[:1500], "duration": f"{x['seconds']}s", "name": f"rebuild shot {x['k'] + 1}",
                "task": f"lab-video:{run.project['id']}", "image_b64": base64.b64encode((root / x["still"]).read_bytes()).decode(),
                "video_b64": base64.b64encode((root / drivers[x["k"]]).read_bytes()).decode()})
            res = makers.wait_job(run, stt["key"], "🏃", f"Shot {x['k'] + 1} copying the movement", float(stt.get("est_usd") or 0), "2–6 min", 20 * 60)
        except Exception as e:                                   # noqa: BLE001
            if _hard(e):
                raise
            res = {"state": "failed", "error": {"message": str(getattr(e, "message", "") or e)}}
        out = res.get("result") or {}
        if res.get("state") != "done" or not out.get("path"):
            x["motion_error"] = str((res.get("error") or {}).get("message") or "no clip came back")[:200]
            run._record({"action": "route", "why": f"🏃 shot {x['k'] + 1}: {x['motion_error']} — level-2 clip instead", "result": {}, "usd": 0.0})
            continue
        rel = picture.claim(root, f"videos/rebuild/shot-{x['k'] + 1}-{makers.stamp()}-motion.mp4")
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        _sh.copyfile(out["path"], root / rel)
        usd = float(out.get("usd") or 0)
        run.usd += usd
        fails = []
        for i, raw in enumerate(frames_at(root / rel)):
            e = eyes.ask(run, raw, identity_points(cast_for(x, cast)), f"shot {x['k'] + 1} frame {i + 1}")
            fails += identity_failed(e.get("points"))
        x.update(clip=rel, level=3, usd=float(x.get("usd") or 0) + usd, clip_identity=sorted(set(fails)))
        save(root, rec)
        run.save()


def run(run) -> None:
    from . import eyes, makers, picture, story, video
    b, root = run.batch, Path(run.root)
    st = b["rebuild"]
    if not run.connected:
        run.state, run.why = "failed", "🔌 Rebuilds use Hermes (breakdown, pictures, voices) — switch the Lab to connected mode."
        return
    try:
        bd = run.lab.mcp.call("breakdown_get", {"id": st["bd"]})
    except Exception as e:                                       # noqa: BLE001
        if _hard(e):
            raise
        run.state, run.why = "failed", f"🎞 No breakdown for that video: {getattr(e, 'message', e)} 👉 Open the video and tap 🎞 Break it down first."
        return
    if bd.get("state") != "done" or not bd.get("scenes"):
        run.state, run.why = "failed", "🎞 That breakdown isn't finished yet 👉 open 🎞 Video breakdowns and let it finish."
        return
    cast = load_cast(run)
    if not cast:
        run.state, run.why = "failed", "🎭 Pick a cast first 👉 📚 Library → 🎭 Global cast → ♻️ Reuse a cast or 🆕 Make a new one."
        return
    notes = []
    host = {}
    if st["level"] == 3:
        host = motion_host()
        why = level3_block(bool(bd.get("private")), host)
        if why:
            host = {}
            notes.append(why)
            run._record({"action": "route", "why": why, "result": {"level": 2}, "usd": 0.0})
    voice = st["voice"]
    if voice == "lipsync":
        notes.append(NOT_YET_LIPS)
        voice = "each"
    rec = record(root, st["bd"])
    fresh = rec is None or st.get("fresh") or st["retry"] is None and (rec.get("settings") or {}).get("picks") != st["picks"]
    if fresh:
        bs = beats(bd["scenes"], st["picks"] if st["mode"] == "pick" else None)
        rec = {"bd": st["bd"], "title": bd.get("title") or bd.get("name"), "source": bd.get("path"), "private": bool(bd.get("private")),
               "personal": True, "beats": bs, "made": 0, "aspect": _aspect(bs[0]["frame_path"]) if bs else "16:9"}
    rec["settings"] = {**st, "voice_used": voice, "cast": [c["name"] for c in cast]}
    bs = rec["beats"]
    if not bs:
        run.state, run.why = "failed", "🎯 No scenes picked 👉 tick at least one scene."
        return
    if st["retry"] is not None:
        if not 0 <= st["retry"] < len(bs):
            run.state, run.why = "failed", "🔁 That shot isn't in this rebuild."
            return
        for x in ("still", "clip", "eyes", "identity", "clip_identity"):
            bs[st["retry"]].pop(x, None)
        bs[st["retry"]]["retries"] = int(bs[st["retry"]].get("retries") or 0) + 1
    save(root, rec)
    b["n"] = len(bs)
    run._record({"action": "rebuild", "why": f"🎬 {len(bs)} beats from {len(set(x['scene'] for x in bs))} scenes · cast "
                 + " & ".join(c["name"] for c in cast) + f" · {CLIPS[st['clips']]} · {AUDIO[st['audio']]}",
                 "result": {"beats": len(bs)}, "usd": 0.0})
    look = []
    try:
        from . import styles
        look = styles.project_look(root)
    except Exception:                                            # noqa: BLE001
        pass
    from . import looks
    shape = "Tall (phone)" if rec["aspect"] == "9:16" else "Wide (screen)"
    retries = int(((run.cfg or {}).get("rebuild") or {}).get("retries", RETRIES))
    base = run.task

    # 1 · stills + 👁 recipe + identity
    try:
        for x in bs:
            b["now"] = x["k"]
            if x.get("still") and (root / x["still"]).is_file():
                continue
            words = words_for(x, cast)
            b["refs_abs"] = [c["anchor_path"] for c in cast_for(x, cast) if c.get("anchor_path")][:4]
            task, tries = words + f"\nShape: {shape}" + (f"\nLook: {looks.SEP.join(look)}" if look else ""), 0
            while True:
                run.task, run.state, run.why = task, "running", ""
                before = len(run.pictures)
                try:
                    picture.run(run)
                except Exception as e:                           # noqa: BLE001
                    if _hard(e):
                        raise
                why_pic, run.state, run.why = run.why, "running", ""     # live R4: picture.run's "done" ended the watcher early
                if len(run.pictures) <= before:
                    x["error"] = why_pic or "no picture came back"
                    break
                pic = run.pictures[-1]
                x.update(still=pic["path"], words=words, usd=float(x.get("usd") or 0) + float(pic.get("usd") or 0))
                x.pop("error", None)
                if not eyes.on(run):
                    break
                e = eyes.ask(run, (root / pic["path"]).read_bytes(), check_points(x, cast), f"shot {x['k'] + 1}")
                if e.get("error"):
                    x["eyes"] = {"error": e["error"]}
                    break
                x["eyes"] = {"score": e.get("score"), "missing": e.get("missing")}
                x["identity"] = identity_failed(e.get("points"))
                low = e.get("score") is not None and e["score"] < eyes.settings(run.cfg)["low"]
                if (low or x["identity"]) and tries < retries and not float(pic.get("usd") or 0):
                    tries += 1
                    fix = eyes.fix_words(e.get("points") or [])
                    run._record({"action": "eyes", "why": f"👁 shot {x['k'] + 1} {e.get('score')}%"
                                 + (f" — identity: {', '.join(x['identity'])}" if x["identity"] else "") + f" — remaking once ($0): {fix}",
                                 "result": x["eyes"], "usd": 0.0})
                    task = words + (f"\nChange: {fix}" if fix else "") + f"\nShape: {shape}" + (f"\nLook: {looks.SEP.join(look)}" if look else "")
                    continue
                break
            save(root, rec)
            run.save()
    finally:
        run.task = base
        b.pop("refs_abs", None)

    # 2a · 🏃 level 3: the source beat drives the cast's movement (hosted, one price card, his tap)
    if host:
        _motion(run, rec, bs, cast, host, notes)
    # 2 · clips
    mode = st["clips"]
    todo = [x for x in bs if x.get("still") and not (x.get("clip") and (root / x["clip"]).is_file())]
    model = ""
    if mode == "local":
        model = next((p.get("model", "") for p in video.all_paths() if p["kind"] == "local" and p["on"]), "")
        if not model:
            notes.append("🏠 No local video path is switched on — 🆓 pan-and-zoom instead.")
            mode = "free"
    if mode == "venice" and todo:
        try:
            q = run.lab.mcp.call("video_quote", {"duration": "5s", "resolution": str(run.cfg.get("video_resolution") or "720p"),
                                                 "image_b64": base64.b64encode((root / todo[0]["still"]).read_bytes()).decode()})
            each, today, cap = float(q.get("usd") or 0), float(q.get("today_usd") or 0), float(q.get("daily_cap") or 5)
            tot = each * len(todo)
            over = today + tot > cap
            choices = ([] if over else [f"▶ Make {len(todo)} clips (${tot:.2f})"]) + ["🆓 Pan-and-zoom instead ($0)"]
            ans = makers.ask(run, f"rebuild-price-{st['bd']}-{len(todo)}", [{"q": f"{len(todo)} Venice clips ≈ ${tot:.2f} (${each:.2f} each). "
                                                                       f"Video spend today ${today:.2f} of ${cap:.2f}." + (" Over the cap." if over else ""),
                                                                       "choices": choices, "best": 0, "why": "price first"}], always=True)
            mode = "venice" if next(iter(ans.values()), "").startswith("▶") else "free"
            if mode == "venice":
                run.cap_usd = max(run.cap_usd, run.usd + tot + 0.05)
        except Exception as e:                                   # noqa: BLE001
            if _hard(e):
                raise
            notes.append(f"💲 Couldn't price Venice clips ({getattr(e, 'message', e)}) — 🆓 pan-and-zoom.")
            mode = "free"
    for x in todo:
        run._check_stop()
        still, rel, usd = root / x["still"], "", 0.0
        shot = {"k": x["k"], "action": (x["recipe"].get("motion") or words_for(x, cast))[:300], "camera": x["recipe"].get("camera", ""),
                "seconds": x["seconds"]}
        if mode in ("local", "venice"):
            rel, usd = story._clip_ai(run, still, shot, model if mode == "local" else "", rec["aspect"])
        if rel:
            fr = frames_at(root / rel)
            fails = []
            for i, raw in enumerate(fr):
                e = eyes.ask(run, raw, identity_points(cast_for(x, cast)), f"shot {x['k'] + 1} frame {i + 1} of {len(fr)}")
                fails += identity_failed(e.get("points"))
            x["clip_identity"] = sorted(set(fails))
        if not rel:
            picture.stage(run, "🆓", f"Shot {x['k'] + 1} — pan-and-zoom ($0)")
            rel = picture.claim(root, f"videos/rebuild/shot-{x['k'] + 1}-{makers.stamp()}-panzoom.mp4")
            why = video.pan_zoom(still, root / rel, x["seconds"], rec["aspect"])
            if why:
                x["clip_error"] = why
                continue
        x.update(clip=rel, usd=float(x.get("usd") or 0) + usd)
        save(root, rec)
        run.save()

    # 3 · sound
    lines = [""] * len(bs)
    if st["audio"] == "narrate":
        said = [x.get("said", "") for x in bs]
        if any(said):
            try:
                text, _ = makers.write(run, REWRITE_SYS, "\n".join(f"{i + 1}. ({x['seconds']} s) {s or '—'}" for i, (x, s) in enumerate(zip(bs, said))),
                                       900, "Re-telling the words", "lab-rebuild")
                got = story._json(text, list)
                lines = [str(g or "")[:240] for g in got][:len(bs)] + [""] * max(0, len(bs) - len(got))
            except Exception as e:                               # noqa: BLE001
                if _hard(e):
                    raise
        voices = []
        if voice == "each":
            try:
                voices = [v if isinstance(v, str) else v.get("id", "") for v in run.lab.mcp.call("narrate_status", {}).get("voices") or []]
            except Exception:                                    # noqa: BLE001
                voices = []
        off = ""
        for x, line in zip(bs, lines):
            x["line"] = line
            if not line or off or (x.get("wav") and (root / x["wav"]).is_file() and x.get("wav_line") == line):
                continue
            who = cast_for(x, cast)
            args = {"text": line}
            if voice == "each" and voices and who:
                args["voice"] = voices[cast.index(who[0]) % len(voices)]
            try:
                r = run.lab.mcp.call("narrate", args)
                rel = f"audio/rebuild/{st['bd']}-shot-{x['k'] + 1}.wav"
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes(base64.b64decode(r["b64"]))
                x.update(wav=rel, wav_line=line)
            except Exception as e:                               # noqa: BLE001
                if _hard(e):
                    raise
                off = (getattr(e, "message", "") or str(e))[:200] + (f" 👉 {e.fix}" if getattr(e, "fix", "") else "")
        if off:
            notes.append(f"🔇 Narration skipped: {off}")
    elif st["audio"] == "keep":
        src = Path(str(rec.get("source") or ""))
        for x in bs:
            rel = f"audio/rebuild/{st['bd']}-orig-{x['k'] + 1}.wav"
            if src.is_file() and cut_audio(src, x["start"], x["end"], root / rel):
                x["wav"] = rel

    # 4 · join
    picture.stage(run, "🎞", "Joining the shots into one film")
    pieces = []
    with tempfile.TemporaryDirectory() as d:
        for x in bs:
            src = x.get("clip") or x.get("still")
            if not src or not (root / src).is_file():
                continue
            wav = root / x["wav"] if x.get("wav") and st["audio"] != "silent" and (root / x["wav"]).is_file() else None
            out = Path(d) / f"p{x['k']:03d}.mp4"
            if not story.segment(root / src, wav, x["seconds"], rec["aspect"], out):
                pieces.append(out)
        film = ""
        if pieces:
            film = picture.claim(root, f"videos/rebuild-{makers.slug(rec['title'] or 'video', default='video')}-{makers.stamp()}.mp4")
            why = story.join(pieces, root / film)
            if why:
                notes.append(f"🎞 Couldn't join the film: {why}")
                film = ""
    rec.update(film=film, table=table(bs), made=time.time(), notes=notes)
    save(root, rec)
    b["now"] = b["n"]
    b["items"] = [{"path": x["still"], "k": x["k"], "kind": "picture", "usd": x.get("usd", 0),
                   "variation": f"🎬 shot {x['k'] + 1} · scene {x['scene'] + 1} · {x['seconds']} s",
                   **({"eyes": x["eyes"]} if x.get("eyes") else {})} for x in bs if x.get("still")]
    b["rebuild_view"] = {"bd": st["bd"], "film": film}
    if film:
        secs = sum(r["out_end"] - r["out_start"] for r in rec["table"])
        run.videos = (getattr(run, "videos", None) or []) + [{"path": film, "model": "🎬 rebuild (ffmpeg join)", "seconds": int(secs),
                                                              "usd": round(sum(float(x.get("usd") or 0) for x in bs), 4), "personal": True}]
    scored = [x["eyes"]["score"] for x in bs if (x.get("eyes") or {}).get("score") is not None]
    ids = [x for x in bs if x.get("identity") or x.get("clip_identity")]
    cost = sum(float(x.get("usd") or 0) for x in bs)
    run.state = "done" if film else "failed"
    run.why = ((f"🎬 🔒 Rebuild of “{rec['title']}” — {len(rec['table'])} of {len(bs)} shots"
                + (f", 👁 average {round(sum(scored) / len(scored))}%" if scored else "")
                + (f", ⚠️ identity trouble in shot {', '.join(str(x['k'] + 1) for x in ids)}" if ids else "")
                + f", ${cost:.3f}. Open ⚖️ Review to compare side by side and 🔁 retry any shot.")
               if film else "🎬 No film came out — " + ("; ".join(notes) or "no shot was made"))
    if notes and film:
        run.why += " " + " ".join(notes)
    picture.stage(run, "✅" if film else "❌", "Rebuild ready" if film else "No film")
