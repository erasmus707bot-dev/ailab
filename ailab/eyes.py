"""👁 Eyes (eyes+story+rip M1, Scott 2026-11-25): after a picture or clip is made, a local vision model on gandalf
looks at it (Hermes vision_check — $0, nothing leaves the machine) and the Lab says how well it matches his words.

his words → simple yes/no points (what is shown · how many · the Look · no writing on the art) → match score + a plain
list of what is missing → 🔁 Fix and try again (his own words kept exactly; the misses go in a `Change:` line, the
Style / Shape / Look lines are kept). A check never spends, never fails a run, and never starts anything by itself.
Switch: config.json "eyes": {"on": false} turns it off.
"""
from __future__ import annotations

import base64
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

MAX_POINTS = 8
WAIT_S = 25
MAX_WAIT_S = 240
LOW = 70                       # under this the card offers the fix first (config "eyes": {"low": n})
NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "a pair of": 2, "a couple of": 2}
_NUM = r"(?:\d{1,2}|" + "|".join(sorted(NUMS, key=len, reverse=True)) + r")"
COUNT = re.compile(rf"\b({_NUM})\s+((?:[a-z'-]+\s+){{0,2}}?[a-z'-]+?s)\b", re.I)      # "three red foxes", "2 cats"
LAB_LINE = re.compile(r"^(Style|Shape|Look|Change|Variation):\s*(.*)$", re.M)
NO_TEXT_Q = "Is there any written text, caption, logo or watermark anywhere on the picture?"
NO_TEXT_WHAT = "no writing on the art"
# a camera MOVE can't be seen in one still or one frame — live 2026-11-25 a story shot was marked "missing: slow push-in,
# tracking shot". Framing (close-up, wide, from above) is visible and stays.
CAMERA_MOVE = re.compile(r"\b(?:(?:very |slow(?:ly)? |quick(?:ly)? |fast |gentle |smooth )?(?:push[- ]?in|pull[- ]?(?:out|back)|"
                         r"dolly(?:[- ](?:in|out|zoom))?|zoom(?:s|ing)?(?:[- ](?:in|out))?|pan(?:s|ning)?(?: (?:left|right|across|over))?|"
                         r"tilt(?:s|ing)?(?: (?:up|down))?|tracking(?: shot)?|track(?:s)? (?:alongside|with|behind)|crane(?: shot| up| down)?|"
                         r"orbit(?:s|ing)?(?: shot)?|handheld(?: shot)?|whip[- ]pan|rack focus|slow[- ]motion)\b)(?: (?:camera|shot|move|movement))?", re.I)
# what fix_words() writes into a Change: line — those parts restate his own words, so they never become new points
OWN_FIX = re.compile(r"(?:there must be [^;]*?— count them|clearly show [^;]+|give it the [^;]+ look|"
                     r"no written text, captions, logos or watermarks anywhere)\s*;?\s*", re.I)


def settings(cfg: dict | None) -> dict:
    e = (cfg or {}).get("eyes")
    e = e if isinstance(e, dict) else {}
    return {"on": e.get("on", True) is not False, "low": int(e.get("low") or LOW)}


def on(run) -> bool:
    return bool(getattr(run, "connected", False)) and settings(getattr(run, "cfg", None))["on"]


def split_task(task: str) -> tuple[str, dict[str, str]]:
    """(his own words exactly as typed, {"Style": …, "Shape": …, "Look": …, "Change": …})."""
    lines = {k: v.strip() for k, v in LAB_LINE.findall(task or "")}
    own = LAB_LINE.sub("", task or "")
    return re.sub(r"\n{2,}", "\n", own).strip(), lines


def _clauses(text: str) -> list[str]:
    parts = re.split(r"[,;.\n]+|\s+(?:and|with)\s+", text)
    out = []
    for p in parts:
        p = re.sub(r"[*`#\"]+", "", p).strip(" -–—:")
        p = re.sub(r"\s{2,}", " ", CAMERA_MOVE.sub("", p)).strip(" ,-–—:")
        if re.fullmatch(r"(?:camera|shot|the camera|a shot)?", p, re.I):
            continue
        if len(p) >= 4 and p.lower() not in {x.lower() for x in out}:
            out.append(p)
    return out


def points(task: str, look: list[str] | None = None, moving: bool = False) -> list[dict]:
    """His words as yes/no points: [{"q", "want", "what", "kind"}]. kind: show | count | look | notext."""
    own, lines = split_task(task)
    change = OWN_FIX.sub("", lines.get("Change", "")).strip(" ;")
    text = own + (". " + change if change else "")
    pts: list[dict] = []
    for c in _clauses(text)[:MAX_POINTS - 2]:
        m = COUNT.search(c)
        if m:
            n = NUMS.get(m.group(1).lower()) or int(m.group(1))
            noun = m.group(2).strip()
            pts.append({"q": f"Are there exactly {n} {noun} in the picture? Count them.", "want": True,
                        "what": f"exactly {n} {noun}", "kind": "count"})
            rest = (c[:m.start()] + c[m.end():]).strip(" ,")
            if len(rest.split()) >= 3:
                pts.append({"q": f"Does the picture show this: {rest}?", "want": True, "what": rest, "kind": "show"})
        else:
            pts.append({"q": f"Does the picture show this: {c}?", "want": True, "what": c, "kind": "show"})
    seen_what: set[str] = set()
    pts = [p for p in pts if not (p["what"].lower() in seen_what or seen_what.add(p["what"].lower()))]
    names = [str(x) for x in (look or []) if str(x).strip()] or ([lines["Look"]] if lines.get("Look") else [])
    if names:
        what = " · ".join(names)
        pts.append({"q": f"Does the picture have this look or style: {what}?", "want": True, "what": f"the {what} look", "kind": "look"})
    pts = pts[:MAX_POINTS - 1]
    pts.append({"q": NO_TEXT_Q.replace("picture", "video frame") if moving else NO_TEXT_Q, "want": False,
                "what": NO_TEXT_WHAT, "kind": "notext"})
    return pts


def score(pts: list[dict], answers: list) -> dict:
    """answers[i] is True / False / None (the model didn't say). None is left out — never counted as a miss."""
    rows, ok, said = [], 0, 0
    for i, p in enumerate(pts):
        a = answers[i] if i < len(answers) else None
        good = None if a is None else (bool(a) == bool(p["want"]))
        said += good is not None
        ok += good is True
        rows.append({"what": p["what"], "kind": p["kind"], "ok": good})
    return {"score": round(100 * ok / said) if said else None, "points": rows,
            "missing": [r["what"] for r in rows if r["ok"] is False], "unsure": [r["what"] for r in rows if r["ok"] is None]}


def fix_words(rows: list[dict]) -> str:
    out = []
    for r in rows:
        if r.get("ok") is not False:
            continue
        w = r["what"]
        out.append({"count": f"there must be {w} — count them", "look": f"give it {w}",
                    "notext": "no written text, captions, logos or watermarks anywhere"}.get(r["kind"], f"clearly show {w}"))
    return "; ".join(out)


def fix_task(task: str, rows: list[dict]) -> str:
    """The same task with the misses in the Change line. His own words are not touched; Style / Shape / Look are kept."""
    fix = fix_words(rows)
    if not fix:
        return ""
    own, lines = split_task(task)
    change = "; ".join(x for x in (lines.get("Change", ""), fix) if x)
    keep = "".join(f"\n{k}: {lines[k]}" for k in ("Variation", "Style", "Shape", "Look") if lines.get(k))
    return f"{own}\nChange: {change}{keep}"


def frame(video: Path) -> bytes:
    """One frame from the middle of a clip (ffmpeg). b'' when it can't be taken."""
    ff = shutil.which("ffmpeg")
    if not ff:
        return b""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "f.jpg"
        for at in ("2", "0"):
            try:
                subprocess.run([ff, "-y", "-loglevel", "error", "-ss", at, "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out)],
                               capture_output=True, timeout=40, check=False)
            except (OSError, subprocess.SubprocessError):
                return b""
            if out.exists() and out.stat().st_size > 500:
                return out.read_bytes()
    return b""


def check(run, raw: bytes, task: str, look: list[str] | None = None, moving: bool = False, label: str = "") -> dict:
    """Look at one picture (or clip frame) → {"score", "missing", "unsure", "points", "caption", "model", "seconds",
    "refused", "fix", "fix_task", "low"} or {"error", "fix"}. Never raises except the run's own Stopped."""
    if not raw:
        return {"error": "There was no picture to look at."}
    pts = points(task, look, moving)
    s = ask(run, raw, pts, label)
    if s.get("error"):
        return s
    s.update(fix=fix_words(s["points"]), fix_task=fix_task(task, s["points"]))
    s["low"] = s["score"] is not None and s["score"] < settings(getattr(run, "cfg", None))["low"]
    return s


def ask(run, raw: bytes, pts: list[dict], label: str = "") -> dict:
    """🎭 M2: any yes/no points about one picture → score dict + caption, model, seconds, refused — or {"error", "fix"}."""
    from . import picture                                        # noqa: PLC0415 — picture imports eyes
    t0 = time.time()
    try:
        st = run.lab.mcp.call("vision_check", {"image_b64": base64.b64encode(raw).decode(), "points": [p["q"] for p in pts]})
        key = (st or {}).get("key")
        if not key:
            return {"error": "Hermes didn't start the look."}
        while True:
            run._check_stop()
            picture.stage(run, "👁", f"Looking at {label or 'it'} to check it matches your words — {int(time.time() - t0)} s ($0, on gandalf)")
            res = run.lab.mcp.call("job_wait", {"key": key, "max_s": WAIT_S})
            if res.get("finished") or res.get("state") in ("done", "failed", "cancelled"):
                break
            if time.time() - t0 > MAX_WAIT_S:
                return {"error": f"The vision model gave no answer after {MAX_WAIT_S} s."}
    except Exception as e:                                       # noqa: BLE001 — eyes are a bonus, never a blocker
        if type(e).__name__ in ("Stopped", "SpendBlocked", "PrivacyRefused"):
            raise
        return {"error": str(getattr(e, "message", "") or e)[:240], "fix": str(getattr(e, "fix", "") or "")[:200]}
    out = res.get("result") or {}
    if res.get("state") != "done":
        return {"error": str((res.get("error") or {}).get("message") or "The vision model didn't answer.")[:240]}
    s = score(pts, [a.get("yes") for a in out.get("answers") or []])
    s.update(caption=str(out.get("caption") or "")[:600], model=str(out.get("model") or st.get("model") or ""),
             seconds=int(time.time() - t0), refused=bool(out.get("refused")))
    return s


def record(run, what: str, e: dict) -> None:
    if e.get("error"):
        why = f"👁 couldn't check the {what}: {e['error']}" + (f" 👉 {e['fix']}" if e.get("fix") else "")
    elif e.get("score") is None:
        why = f"👁 looked at the {what} — the vision model didn't answer the points" + (" (it refused to describe it)" if e.get("refused") else "")
    else:
        why = f"👁 {e['score']}% match" + (f" — missing: {', '.join(e['missing'])}" if e.get("missing") else " — nothing missing")
    run._record({"action": "eyes", "why": why, "result": {k: v for k, v in e.items() if k != "fix_task"}, "usd": 0.0})


def seen(pics: list[dict]) -> dict | None:
    """What the shelf remembers about a kept / thrown run: the newest checked picture's score + caption."""
    for p in reversed(pics or []):
        e = p.get("eyes") or {}
        if e.get("caption") or e.get("score") is not None:
            return {"score": e.get("score"), "caption": str(e.get("caption") or "")[:300], "missing": list(e.get("missing") or [])[:6]}
    return None
