"""🏃 Motion Presets M2 — three ways to fill the library (Scott 2026-11-25). One Lab run kind ("motionfill"):
  ⭐ pull  — a clip + time range → Hermes motion_pull (frames · poses · camera · preview cut from the clip, $0, local)
             → the uncensored writer words it with role slots and names the key moments → a draft he names and saves
  write    — his words, roles and feel → the writer drafts the key moments → draft (stick-figure preview, $0;
             a priced test render only if he taps it)
  result   — ⭐ on a made picture/video: its prompt + the poses pulled from the result itself → draft
Drafts: <lab home>/motions/_drafts/<run id>.json — the 🏃 card on the run shows it with a name box and 💾 Save.
His words are never changed (makers.KEEP_WORDS); the writer only turns "person A/B" descriptions into {A}/{B} slots."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import motions as MO

MODES = ("pull", "write", "result")
PULL_WAIT_S = 20 * 60
FILL_SYS = ("You turn a description of people moving into a reusable motion preset. {keep} Reply with JSON only: "
            "{{\"name\": short name (2–4 words), \"words\": one sentence using role slots {{A}}, {{B}} … for the people "
            "(never names, never looks — no hair, skin, clothes, body), \"roles\": [{{\"label\": what that person does}}], "
            "\"moments\": [{{\"name\": 2–4 words, \"words\": what the people look like at that instant, with slots}}] "
            "— exactly {n} moments in time order, \"star\": index of the most striking moment, \"shelves\": from "
            "[{shelves}]}}.")


def draft_file(rid: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{6,32}", str(rid or "")):
        raise ValueError("bad run id")
    return MO.home() / "_drafts" / f"{rid}.json"


def save_draft(rid: str, d: dict) -> None:
    f = draft_file(rid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1, ensure_ascii=False))


def load_draft(rid: str) -> dict | None:
    try:
        return json.loads(draft_file(rid).read_text())
    except (OSError, ValueError):
        return None


def norm(raw) -> dict | None:
    r = raw if isinstance(raw, dict) else {}
    mode = r.get("mode") if r.get("mode") in MODES else ""
    if not mode:
        return None
    out = {"mode": mode, "path": str(r.get("path") or "")[:500], "name": str(r.get("name") or "")[:40],
           "words": str(r.get("words") or "")[:400], "roles": [str(x)[:30] for x in (r.get("roles") or [])][:MO.MAX_PEOPLE],
           "shelves": [s for s in (r.get("shelves") or []) if s in MO.SHELVES][:4], "camera": str(r.get("camera") or ""),
           "from_run": str(r.get("from_run") or "")[:32], "prompt": str(r.get("prompt") or "")[:1500]}
    try:
        out.update(start=max(0.0, float(r.get("start") or 0)), end=max(0.0, float(r.get("end") or 0)),
                   moments=max(2, min(MO.MAX_MOMENTS, int(r.get("moments") or 4))),
                   feel=max(0.0, min(1.0, float(r.get("feel") if r.get("feel") is not None else 0.5))))
    except (TypeError, ValueError):
        return None
    if mode in ("pull", "result") and not out["path"]:
        return None
    if mode == "write" and not out["words"]:
        return None
    return out


def slots_from(text: str) -> str:
    """'person A' / 'Person B' → {A} / {B} (the writer's fallback)."""
    return re.sub(r"\bperson ([A-J])\b", lambda m: "{" + m.group(1).upper() + "}", str(text or ""), flags=re.I)


def abs_path(run, raw: str) -> Path | None:
    """A project file (relative) or an absolute path Hermes can open; never a path outside the project or hermes-data."""
    p = Path(raw)
    root = Path(run.root).resolve()
    try:
        p = (root / raw).resolve(strict=True) if not p.is_absolute() else p.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    from . import rip
    ok = root in p.parents or (rip.data().resolve() in p.parents)
    return p if ok and p.is_file() else None


def draft_from(pull: dict, words: dict, n_roles: int, feel: float, camera: str, src: dict) -> tuple[dict, dict]:
    """(preset draft, files rel → absolute source) from a motion_pull result + the writer's JSON."""
    frames = pull.get("frames") or []
    names = [m for m in (words.get("moments") or []) if isinstance(m, dict)]
    star = words.get("star") if isinstance(words.get("star"), int) else len(frames) // 2
    files, moments = {}, []
    for i, f in enumerate(frames):
        w = names[i] if i < len(names) else {}
        m = {"name": str(w.get("name") or f"moment {i + 1}")[:50], "words": slots_from(w.get("words") or words.get("words") or ""),
             "star": i == min(star, len(frames) - 1), "t": f.get("t")}
        if f.get("frame_path"):
            m["frame"] = f"frames/k{i:02d}.jpg"
            files[m["frame"]] = f["frame_path"]
        if f.get("skeleton_path"):
            m["pose"] = f"poses/pose{i:02d}.png"
            files[m["pose"]] = f["skeleton_path"]
        if f.get("people"):
            m["people"] = f["people"]
        moments.append(m)
    roles = [{"label": str((x or {}).get("label") if isinstance(x, dict) else x)[:30]} for x in (words.get("roles") or [])]
    want = max(n_roles, len(set(re.findall(r"\{([A-J])\}", slots_from(words.get("words") or "")))), 1)
    roles = (roles + [{"label": f"person {MO.ROLE_KEYS[i]}"} for i in range(len(roles), want)])[:want]
    d = {"name": str(words.get("name") or "")[:40], "words": slots_from(words.get("words") or pull.get("words") or ""),
         "roles": roles, "moments": moments, "camera": camera or pull.get("camera") or "still", "feel": feel,
         "seconds": max(1.0, float(pull.get("end") or 0) - float(pull.get("start") or 0)) if not pull.get("picture") else 3.0,
         "shelves": [s for s in (words.get("shelves") or []) if s in MO.SHELVES], "source": src}
    if pull.get("preview_path"):
        d["preview"] = "preview.mp4"
        files["preview.mp4"] = pull["preview_path"]
    return d, files


def _writer(run, desc: str, n: int, people: int, extra: str) -> dict:
    from . import makers, story
    sys = FILL_SYS.format(keep=makers.KEEP_WORDS, n=n, shelves=", ".join(MO.SHELVES))
    user = f"People: {people or 'unknown'}\nWhat happens: {desc}\n{extra}".strip()
    text, who = makers.write(run, sys, user, 500, "Wording the motion", "lab-motion")
    d = story._json(text, dict) if text else {}
    run._record({"action": "writer", "why": f"✍️ motion worded by {who.split('/')[-1]}" if d else f"✍️ no writer helped ({who}) — plain words kept",
                 "result": {"name": d.get("name", "")}, "usd": 0.0})
    return d


def run(run) -> None:
    """The motionfill run (Run.loop handles Stopped / SpendBlocked)."""
    from . import makers, picture
    f = run.batch["fill"]
    if not run.connected:
        run.state, run.why = "failed", "🔌 Pulling and wording a motion are Hermes's jobs — switch the Lab to connected mode."
        return
    if f["mode"] == "write":
        picture.stage(run, "✍️", "Drafting the key moments")
        d = _writer(run, f["words"], 3, len(f["roles"]), "Keep these words as the motion words, adding {A}/{B} slots only "
                    "where the people are: " + f["words"])
        roles = [{"label": x} for x in f["roles"]] or d.get("roles") or []
        draft = {"name": f["name"] or d.get("name", ""), "words": slots_from(f["words"]) if "{" in slots_from(f["words"]) else slots_from(d.get("words") or f["words"]),
                 "roles": roles, "moments": [m for m in d.get("moments") or [] if isinstance(m, dict)] or
                 [{"name": "the motion", "words": slots_from(f["words"]), "star": True}],
                 "feel": f["feel"], "camera": f["camera"] or "still", "shelves": f["shelves"] or d.get("shelves") or [],
                 "source": {"kind": "written"}}
        if isinstance(d.get("star"), int) and draft["moments"]:
            for i, m in enumerate(draft["moments"]):
                m["star"] = i == min(d["star"], len(draft["moments"]) - 1)
        save_draft(run.id, {"preset": draft, "files": {}})
        run.batch["draft"] = MO.card(MO.clean(draft))
        run.state, run.why = "done", "🏃 Draft ready — check the words, name it and 💾 Save. (🧪 a test render is priced first.)"
        return
    src = abs_path(run, f["path"])
    if src is None:
        run.state, run.why = "failed", "🏃 That file isn't in this project any more — pick the clip again."
        return
    args = {"path": str(src), "moments": f["moments"] if f["mode"] == "pull" else 4}
    if f["mode"] == "pull":
        args.update(start=f["start"], end=f["end"] or 0)
    picture.stage(run, "🏃", "Asking Hermes to pull the motion (on this computer, $0)")
    st = run.lab.mcp.call("motion_pull", args)
    res = {"state": "done", "result": st.get("result")} if st.get("state") == "done" else \
        makers.wait_job(run, st["key"], "🏃", "Finding the poses and the camera move", 0.0, "1–3 min", PULL_WAIT_S)
    pull = res.get("result") or {}
    if res.get("state") != "done" or not pull.get("frames"):
        run.state, run.why = "failed", "🏃 Pulling the motion stopped: " + ((res.get("error") or {}).get("message") or "no frames came back") \
            + " 👉 Try again — finished frames are kept."
        return
    if not pull.get("poses"):
        run._record({"action": "route", "why": "🦴 no poses this time — " + (pull.get("poses_note") or "the pose tools didn't answer")
                     + ". The motion is saved as words; pictures follow the words only.", "result": {}, "usd": 0.0})
    extra = f"Camera: {pull.get('camera', '')}"
    if f["mode"] == "result" and f["prompt"]:
        extra += f"\nThe prompt that made it (his words, for context only): {f['prompt']}"
    d = _writer(run, pull.get("words") or f["prompt"], len(pull["frames"]), int(pull.get("people") or 0), extra)
    srcinfo = {"kind": "video" if f["mode"] == "pull" else "result", "path": f["path"], "start": f["start"], "end": f["end"],
               "run": f["from_run"]}
    draft, files = draft_from(pull, d, int(pull.get("people") or 0), f["feel"], f["camera"], srcinfo)
    if f["name"]:
        draft["name"] = f["name"]
    save_draft(run.id, {"preset": draft, "files": files})
    run.batch["draft"] = MO.card(MO.clean(draft))
    run.batch["pull"] = {k: pull.get(k) for k in ("id", "camera", "people", "poses", "poses_note", "words")}
    n = len(pull["frames"])
    run.state, run.why = "done", (f"🏃 Pulled {n} key moment{'s' if n > 1 else ''}, {pull.get('people') or '?'} people, camera: "
                                  f"{pull.get('camera')}. Name it and 💾 Save.")


def save(rid: str, edits: dict) -> dict:
    """💾 Save a draft into the library with his edits (name, words, roles, star, shelves, feel, camera)."""
    try:
        dr = load_draft(rid)
    except ValueError:
        dr = None
    if not dr:
        return {"ok": False, "icon": "🏃", "message": "That draft isn't there any more — pull or write it again."}
    p = dict(dr["preset"])
    for k in ("name", "words", "camera", "feel", "shelves", "aliases", "feel_range"):
        if edits.get(k) not in (None, ""):
            p[k] = edits[k]
    if isinstance(edits.get("roles"), list) and edits["roles"]:
        p["roles"] = [{"label": str(x)[:30]} if not isinstance(x, dict) else x for x in edits["roles"]]
    if isinstance(edits.get("star"), int) and p.get("moments"):
        for i, m in enumerate(p["moments"]):
            m["star"] = i == edits["star"]
    if isinstance(edits.get("moment_names"), list):
        for m, nm in zip(p.get("moments") or [], edits["moment_names"]):
            if str(nm or "").strip():
                m["name"] = str(nm).strip()[:50]
    out = MO.save(p, {k: Path(v) for k, v in (dr.get("files") or {}).items()})
    if out.get("ok"):
        try:
            draft_file(rid).unlink()
        except OSError:
            pass
    return out
