"""🎥 Capture runs (Lab capture C2, BUILD_PROMPT_2026-11-25_lab-capture.md).

Scott types one sentence ("phone walk-through of Epochron's Family view") with the 🎥 Capture chip on:

  1. ✍️ the uncensored writer turns it into a SHOT PLAN — steps of target · open · tap/scroll · wait · shot or record N s
     (📓 Craft Book "capture" notes ride along). A writer that fails → a one-step plan from the known pages.
  2. 🗺 the plan shows as the usual plan card (▶ Start ⭐ · or type what to change → rewritten, up to 3 times).
  3. ✋ any desktop step: a plain card first (which window, how long, sound) — the real OK is Scott's ✋ in Hermes
     Needs You; the Lab can't approve itself. Skipping desktop steps is the ⭐.
  4. ▶ each step runs through Hermes capture_shot / capture_clip_start (C1), live line from the job ("📱 tapping…").
  5. 👁 Eyes asks "does this frame show X?"; a miss retries once with a fix (longer wait, top of page), then asks
     with numbered options. Clips get their poster frame from Hermes.
  6. Results land in the project (captures/ — the Keep loop), plus Hermes's own copy in the picture / Media library.

$0: capturing and looking both run on gandalf. Test surfaces never wait for Scott; nothing leaves the machine.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from . import eyes, makers, picture
from .mcp_client import HermesRefused

TARGETS = ("argus", "browser", "vm", "desktop")
ICON = {"argus": "📱", "browser": "🌐", "vm": "🪟", "desktop": "🖥"}
MAX_STEPS = 8
MAX_REPLANS = 3
JOB_WAIT_S = 20
HARD = ("refused", "not_enabled", "needs_approval")

PLAN_SYS = (
    "You plan screen captures for Scott's apps. Reply ONLY with JSON: {\"steps\": [...]} — 1 to 8 steps. Each step:\n"
    "{\"target\": \"argus\"|\"browser\"|\"vm\"|\"desktop\", \"url\": \"http://127.0.0.1:…\" (pages on this computer only), "
    "\"viewport\": \"phone\"|\"desktop\" (browser), \"theme\": \"light\"|\"dark\", "
    "\"do\": [{\"click\": \"text=Family\"} | {\"scroll\": 600} | {\"wait\": 1.5}] (browser), "
    "[{\"swipe\": [540,1600,540,600]} | {\"wait\": 1.5}] (argus), "
    "\"shot\": true OR \"record\": <seconds 3-60>, \"expect\": \"what the picture must show, in plain words\", "
    "\"label\": \"3-6 word step name\"}.\n"
    "Rules: phone shots that need clicks → browser with viewport phone (clicks by visible text: \"text=…\"). "
    "argus = the real test phone: open + scroll only. vm = the Windows test VM (no url). desktop = Scott's real screen — "
    "only when he asks for his desktop or a window by name. Use only the pages listed below; never invent a host. "
    "Give exactly the number of shots and clips he asks for.")


# ---------------------------------------------------------------- plan

def pages(run) -> dict[str, str]:
    """Pages the writer may use: config `capture_pages` {name: url} + this project's own preview."""
    out = {str(k): str(v) for k, v in (run.cfg.get("capture_pages") or {}).items() if str(v).startswith("http://127.0.0.1")}
    port = int(run.cfg.get("port") or 8850)
    out.setdefault("this project (preview)", f"http://127.0.0.1:{port}/preview/{run.project['id']}/")
    return out


def _json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else None
    except ValueError:
        return None


def norm(steps, known: dict[str, str]) -> list[dict]:
    """Keep only what the C1 tools accept: known targets, local pages, bounded clips, ≤ 8 steps."""
    out = []
    for s in steps if isinstance(steps, list) else []:
        if not isinstance(s, dict):
            continue
        t = str(s.get("target") or "browser").lower()
        if t not in TARGETS:
            continue
        st = {"target": t, "label": str(s.get("label") or s.get("expect") or t)[:60],
              "expect": str(s.get("expect") or "")[:160]}
        url = str(s.get("url") or "")
        if t in ("argus", "browser"):
            if not url.startswith(("http://127.0.0.1", "http://localhost")):
                url = next(iter(known.values()), "")
            st["url"] = url
        if t == "browser":
            st["viewport"] = "desktop" if str(s.get("viewport")) == "desktop" else "phone"
            st["theme"] = "light" if str(s.get("theme")) == "light" else "dark"
        do = [d for d in (s.get("do") or []) if isinstance(d, dict)][:10]
        if do:
            st["do"] = do
        rec = s.get("record")
        try:
            rec = int(rec) if rec not in (None, False, "", True) else 0
        except (TypeError, ValueError):
            rec = 0
        if rec:
            st["record"] = max(3, min(rec, 180))
        else:
            st["shot"] = True
        if t == "desktop":
            for k in ("window_id", "box", "display"):
                if s.get(k):
                    st[k] = s[k]
            st["sound"] = bool(s.get("sound"))
        out.append(st)
    return out[:MAX_STEPS]


def line(s: dict) -> str:
    what = f"🎥 record {s['record']} s" if s.get("record") else "📸 shot"
    where = s.get("url", "").split("127.0.0.1", 1)[-1] if s.get("url") else ""
    taps = f" · {len(s['do'])} tap/scroll" if s.get("do") else ""
    return f"{ICON[s['target']]} {s['label']} — {s['target']}{(' ' + where) if where else ''}{taps} · {what}"


def make_plan(run, words: str, change: str = "", old: list[dict] | None = None) -> tuple[list[dict], str]:
    known = pages(run)
    user = (f"Scott's words: {words}\n\nPages on this computer:\n" + "\n".join(f"- {k}: {v}" for k, v in known.items()))
    if old:
        user += f"\n\nThe plan so far:\n{json.dumps({'steps': old})}\nScott wants this changed: {change}\nSend the whole new plan."
    text, who = makers.write(run, PLAN_SYS, user, 1200, "Planning the shots", "lab-capture",
                             craft="capture")
    steps = norm((_json(text) or {}).get("steps"), known)
    if steps:
        return steps, who
    if old:
        return old, f"kept the old plan ({who})"
    # writer failed: one phone shot of the first known page — still zero manual steps
    return norm([{"target": "browser", "viewport": "phone", "shot": True, "label": "the page", "expect": words[:120]}],
                known), f"a simple plan ({who})"


# ---------------------------------------------------------------- run one step

def _args(run, s: dict, n: int, retry: bool) -> dict:
    a = {"target": s["target"], "project": run.project["id"], "what": s.get("label", "")}
    for k in ("url", "viewport", "theme", "window_id", "box", "display", "sound"):
        if k in s:
            a[k] = s[k]
    steps = [dict(d) for d in s.get("do") or []]
    if retry:                                     # the one fix: give the page longer, start from the top
        steps = [{"wait": 2.5}] + [{**d, "wait": max(float(d.get("wait", 0.8)), 1.5)} for d in steps]
        if s["target"] == "browser":
            steps = [{"scroll": -5000, "wait": 0.5}] + steps
    if steps:
        a["steps"] = steps
    if s.get("record"):
        a["seconds"] = s["record"]
    return a


def capture(run, s: dict, n: int, total: int, retry: bool = False) -> dict:
    """One capture through Hermes. → job result {path, thumb, …} or {"error", "fix", "code"}."""
    tool = "capture_clip_start" if s.get("record") else "capture_shot"
    try:
        start = run.lab.mcp.call(tool, _args(run, s, n, retry))
    except HermesRefused as e:
        return {"error": e.message, "fix": e.fix, "code": e.code}
    t0 = time.time()
    while True:
        run._check_stop()
        try:
            res = run.lab.mcp.call("job_wait", {"key": start["key"], "max_s": JOB_WAIT_S})
        except HermesRefused as e:
            return {"error": e.message, "fix": e.fix, "code": e.code}
        if res.get("finished") or res.get("state") in ("done", "failed", "cancelled"):
            break
        phase = (res.get("detail") or {}).get("phase") or "working"
        picture.stage(run, ICON[s["target"]], f"{n}/{total} · {phase} — {int(time.time() - t0)} s")
        if time.time() - t0 > 300 + int(s.get("record") or 0):
            try:
                run.lab.mcp.call("job_cancel", {"key": start["key"]})
            except HermesRefused:
                pass
            return {"error": "Nothing came back after 5 minutes.", "fix": "Check the target is running, then try again."}
    if res.get("state") != "done":
        err = res.get("error") or {}
        return {"error": err.get("message") or "The capture didn't finish.", "fix": err.get("fix", ""), "code": err.get("code", "")}
    return res.get("result") or {}


def _into_project(run, res: dict, n: int, s: dict) -> dict:
    """Copy into the project (captures/ — the Keep loop sees it) + the poster frame."""
    src = Path(res["path"])
    rel = picture.claim(run.root, f"captures/{makers.stamp()}-{n}-{makers.slug(s.get('label', ''), 30, 'capture')}{src.suffix}")
    shutil.copy2(src, run.root / rel)
    item = {"path": rel, "target": s["target"], "kind": "clip" if s.get("record") else "shot", "w": res.get("w"),
            "h": res.get("h"), "hermes": res.get("path"), "library": res.get("library", ""), "usd": 0.0,
            "prompt": s.get("expect") or s.get("label", "")}
    if res.get("thumb") and Path(res["thumb"]).is_file():
        prel = rel.rsplit(".", 1)[0] + ".poster.jpg"
        shutil.copy2(res["thumb"], run.root / prel)
        item["poster"] = prel
    return item


def look(run, item: dict, s: dict) -> dict:
    """👁 does the frame show what the step expects? (and isn't a sign-in or error page)."""
    p = run.root / item["path"]
    raw = eyes.frame(p) if item["kind"] == "clip" else p.read_bytes()
    pts = [{"q": "Is this a sign-in page, an error page, or a blank screen?", "what": "not a sign-in / error / blank screen",
            "kind": "screen", "want": False}]
    if s.get("expect"):
        pts.insert(0, {"q": f"Does this screen show {s['expect']}?", "what": s["expect"], "kind": "subject", "want": True})
    e = eyes.ask(run, raw, pts, s.get("label", "the capture"))
    if not e.get("error"):
        e["low"] = e.get("score") is not None and e["score"] < 100 and bool(e.get("missing"))
    return e


# ---------------------------------------------------------------- the run

def _desktop_ok(run, steps: list[dict]) -> list[dict]:
    desk = [s for s in steps if s["target"] == "desktop"]
    if not desk:
        return steps
    what = "; ".join(f"{s['label']} ({'window ' + str(s['window_id']) if s.get('window_id') else 'box' if s.get('box') else 'screen'}"
                     f", {str(s['record']) + ' s clip' if s.get('record') else 'one picture'}, sound {'on' if s.get('sound') else 'off'})"
                     for s in desk)
    ch = makers.ask(run, "capture-desktop", [{
        "q": f"✋ {len(desk)} step{'s' if len(desk) > 1 else ''} film your real desktop: {what}. Mic stays off.",
        "choices": ["Skip the desktop steps", "I'll tap ✋ Allow in Hermes Needs You — go on"], "best": 0,
        "why": "test surfaces need no OK; the desktop needs your ✋ in Hermes (one tap, 2 h)"}], always=True)
    ans = " ".join(ch.values()).lower()
    if "skip" in ans:
        run._record({"action": "capture", "why": "✋ desktop steps skipped", "result": {"skipped": len(desk)}, "usd": 0.0})
        return [s for s in steps if s["target"] != "desktop"]
    return steps


def _on_fail(run, s: dict, n: int, why: str, can_keep: bool = True) -> str:
    choices = ["Skip this step", "Keep it anyway", "Stop here"] if can_keep else ["Skip this step", "Stop here"]
    ch = makers.ask(run, f"capture-fail-{n}", [{"q": f"Step {n} ({s['label']}) didn't come out right: {why[:160]}",
                                               "choices": choices, "best": 0,
                                               "why": "the rest of the plan still runs"}], always=True)
    a = " ".join(ch.values()).lower()
    return "keep" if "keep" in a else "stop" if "stop" in a else "skip"


def run(run) -> None:
    if not run.connected or not getattr(run.lab, "mcp", None):
        run.state, run.why = "failed", "🎥 Captures run through Hermes — switch the Lab to connected mode."
        return
    words = picture.picture_words(run.task).strip()
    run.cap_usd = max(run.cap_usd, 0.10)
    steps, who = make_plan(run, words)
    for i in range(MAX_REPLANS + 1):
        picture.stage(run, "🗺", "Your shot plan")
        run.question = {"kind": "plan", "title": "🎥 Shot plan", "go": "▶ Start ⭐", "text": "Here is the shot plan. Start?",
                        "choices": ["▶ Start", "✏️ Change it"], "plan": [line(s) for s in steps]}
        ans = run._wait()
        if re.sub(r"[^a-z]", "", ans.lower()).startswith(("go", "start")):
            break
        if i == MAX_REPLANS:
            run.state, run.why = "failed", "🎥 No plan agreed after 3 changes — type the shots you want in your own words and start again."
            return
        steps, who = make_plan(run, words, ans, steps)
    run._record({"action": "capture", "why": f"🗺 shot plan ({makers.short(who)})", "result": {"steps": steps}, "usd": 0.0})
    steps = _desktop_ok(run, steps)
    if not steps:
        run.state, run.why = "done", "🎥 Nothing to capture (desktop steps skipped)."
        return
    got, failed, tips = [], 0, []
    for n, s in enumerate(steps, 1):
        run._check_stop()
        res = capture(run, s, n, len(steps))
        e, item = {}, None
        for attempt in (1, 2):
            if res.get("error"):
                break
            item = _into_project(run, res, n, s)
            e = look(run, item, s)
            eyes.record(run, item["path"], e)
            if e.get("error") or not e.get("low") or attempt == 2:
                break
            tips.append(f"{s['target']}: '{s.get('label')}' needed a longer wait / start at the top")
            picture.stage(run, "🔁", f"{n}/{len(steps)} · trying once more with a longer wait")
            (run.root / item["path"]).unlink(missing_ok=True)
            res = capture(run, s, n, len(steps), retry=True)
        if res.get("error"):
            why = res["error"] + (f" 👉 {res['fix']}" if res.get("fix") else "")
            run._record({"action": "capture", "why": f"{ICON[s['target']]} {s['label']}", "result": {"error": why}, "usd": 0.0})
            failed += 1
            # a refusal / target not running already says what to do — no question; the next step may work
            if res.get("code") not in HARD and n < len(steps) and _on_fail(run, s, n, why, can_keep=False) == "stop":
                break
            continue
        if e.get("low") and _on_fail(run, s, n, "👁 missing: " + ", ".join(e.get("missing") or [])) != "keep":
            (run.root / item["path"]).unlink(missing_ok=True)
            failed += 1
            continue
        item["eyes"] = {k: e.get(k) for k in ("score", "missing", "caption")} if not e.get("error") else {}
        (run.pictures if item["kind"] == "shot" else run.videos).append(item)
        got.append(item)
        run._record({"action": "picture" if item["kind"] == "shot" else "video", "path": item["path"],
                     "why": f"{ICON[s['target']]} {s['label']}", "result": {k: v for k, v in item.items() if k != "prompt"},
                     "usd": 0.0})
        picture._craft_seen(run, "capture", e, s.get("expect") or words, compare=False)
    run.capture_tips = tips
    shots = sum(1 for g in got if g["kind"] == "shot")
    clips = len(got) - shots
    run.state = "done" if got else "failed"
    run.why = (f"🎥 {shots} shot{'s' if shots != 1 else ''} + {clips} clip{'s' if clips != 1 else ''} in captures/"
               + (f" · {failed} step{'s' if failed != 1 else ''} didn't make it" if failed else "")
               + " · also in Hermes's picture / Media library ($0, on gandalf).")
    picture.stage(run, "✅" if got else "⚠️", "Done" if got else "Nothing came out")
