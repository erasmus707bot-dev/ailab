"""⚖️ Compare (M8, flag `compare`): one task, 2–4 models, side by side.

Each model ("lane") runs the agent loop in its OWN copy of the project, under srt, one after another.
The whole comparison has one $ cap (config `compare_cap_usd`, default $0.50), split evenly across the
lanes and always inside the Lab's daily cap. Each lane is measured: time, cost, tokens, steps, and the
checks Scott wrote (shell commands run in the sandbox; exit 0 = pass). A 📸 per lane comes from the
browser. The result is saved as result.json + result.html (a static page) and can go to 📋 Review.

Store: ~/.config/ailab/projects/<pid>/compare/<cid>/{meta.json,result.json,result.html,lanes/<k>/{site/,shot.png,*.jsonl}}
"""
from __future__ import annotations

import base64
import html
import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from . import agent, config, preview, privacy, review, store
from .secretscan import has_secret

CID = re.compile(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}")
MIN_LANES, MAX_LANES, MAX_CHECKS = 2, 4, 8
CHECK_TIMEOUT_S = 30


class CompareError(Exception):
    def __init__(self, message: str, code: str = "compare", icon: str = "⚖️"):
        super().__init__(message)
        self.message, self.code, self.icon = message, code, icon


def cdir(pid: str, cid: str) -> Path:
    if not preview.PID.fullmatch(pid or "") or not CID.fullmatch(cid or ""):
        raise CompareError("Bad comparison id.", "bad_args", "❓")
    return config.home() / "projects" / pid / "compare" / cid


def lane_dir(pid: str, cid: str, k) -> Path:
    if str(k) not in ("0", "1", "2", "3"):
        raise CompareError("Bad lane.", "bad_args", "❓")
    return cdir(pid, cid) / "lanes" / str(k)


def lane_key(pid: str, cid: str, k) -> str:
    return f"{pid}--c{cid}-{k}"                       # sandbox key (srt config file name)


def _write_json(f: Path, data) -> None:
    tmp = f.with_name(f".{f.name}.{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_text(json.dumps(data, indent=1, default=str))
    os.replace(tmp, f)


class Comparison:
    def __init__(self, lab, cfg: dict, project: dict, task: str, lanes: list, checks: list | None = None):
        task = str(task or "").strip()[:4000]
        if not task:
            raise CompareError("Write the task first — every model gets the same one.", "bad_args", "✏️")
        pairs = []
        for ln in lanes if isinstance(lanes, list) else []:
            prov, model = str((ln or {}).get("provider") or "").strip(), str((ln or {}).get("model") or "").strip()
            if prov and model and (prov, model) not in pairs:
                pairs.append((prov, model))
        if not MIN_LANES <= len(pairs) <= MAX_LANES:
            raise CompareError(f"Pick {MIN_LANES}–{MAX_LANES} different models.", "bad_args", "⚖️")
        for prov, _ in pairs:                             # privacy before anything is copied or sent
            privacy.check(project, lab.provider(prov))
        checks = [str(c).strip()[:300] for c in (checks or []) if str(c).strip()][:MAX_CHECKS]
        self.lab, self.cfg, self.project, self.task, self.checks = lab, cfg, project, task, checks
        self.id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.cap_usd = float(cfg.get("compare_cap_usd", 0.50))
        self.lane_cap = round(self.cap_usd / len(pairs), 6)
        self.state, self.why, self.created = "running", "", time.time()
        self.stop_flag, self.cur, self._lock = threading.Event(), None, threading.Lock()
        self.dir = cdir(project["id"], self.id)
        src = preview.ensure_site(project["id"])
        self.lanes = []
        for k, (prov, model) in enumerate(pairs):
            d = self.dir / "lanes" / str(k)
            d.mkdir(parents=True)
            shutil.copytree(src, d / "site", symlinks=True,
                            ignore=lambda _d, names: [n for n in names if n.startswith(".")])
            self.lanes.append({"k": k, "provider": prov, "model": model, "state": "waiting", "why": "",
                               "secs": None, "usd": 0.0, "tokens_in": 0, "tokens_out": 0, "steps": 0,
                               "checks": [], "passed": 0, "shot": False, "run": ""})
        _write_json(self.dir / "meta.json", {"task": task, "checks": checks, "created": self.created,
                                             "lanes": [{"provider": p, "model": m} for p, m in pairs]})
        self.save()

    def view(self) -> dict:
        cur = self.cur
        if cur is not None:                               # live numbers for the lane that is working now
            for ln in self.lanes:
                if ln["state"] == "running" and ln["run"] == cur.id:
                    v = cur.view()
                    last = v["steps"][-1] if v["steps"] else {}
                    ln.update(steps=len(v["steps"]), usd=round(v["usd"], 6), tokens_in=v["tokens_in"],
                              tokens_out=v["tokens_out"],
                              why=(f"🟠 stuck — nothing new for {v['quiet_s'] // 60} min" if v.get("stuck") else
                                   f"⏳ step {len(v['steps']) + 1} of {v['step_cap']} — last: {last.get('action', 'thinking…')}"))
        return {"id": self.id, "project": self.project["id"], "task": self.task, "checks": self.checks,
                "state": self.state, "why": self.why, "cap_usd": self.cap_usd, "lane_cap_usd": self.lane_cap,
                "usd": round(sum(ln["usd"] for ln in self.lanes), 6), "created": self.created,
                "lanes": self.lanes}

    def save(self) -> None:
        with self._lock:
            save_result(self.project["id"], self.view())

    def stop(self, why: str = "⏹ Stopped by you") -> None:
        self.why = why
        self.stop_flag.set()
        if self.cur is not None:
            self.cur.stop(why)

    def _run_checks(self, root: Path) -> list[dict]:
        out = []
        for cmd in self.checks:
            try:
                r = agent.run_in_sandbox(root, cmd, CHECK_TIMEOUT_S)
            except preview.PreviewError as e:
                r = {"exit": None, "output": f"{e.icon} {e.message}"}
            out.append({"cmd": cmd, "ok": r.get("exit") == 0, "output": str(r.get("output") or "")[-600:]})
        return out

    def loop(self) -> None:
        pid = self.project["id"]
        try:
            for ln in self.lanes:
                if self.stop_flag.is_set():
                    ln["state"], ln["why"] = "skipped", "⏹ not run (stopped)"
                    continue
                left = round(self.cap_usd - sum(x["usd"] for x in self.lanes), 6)
                if left <= 0:
                    ln["state"], ln["why"] = "skipped", f"💲 comparison cap (${self.cap_usd:.2f}) used up"
                    continue
                d = self.dir / "lanes" / str(ln["k"])
                run = agent.Run(self.lab, self.cfg, self.project, ln["provider"], ln["model"], self.task,
                                root=d / "site", log_dir=d, cap_usd=min(self.lane_cap, left),
                                autosave_field="compare-lane")
                self.cur, ln["state"], ln["run"] = run, "running", run.id
                self.save()
                t0 = time.monotonic()
                run.loop()
                v = run.view()
                ln.update(secs=round(time.monotonic() - t0, 1), usd=round(v["usd"], 6), tokens_in=v["tokens_in"],
                          tokens_out=v["tokens_out"], steps=len(v["steps"]), state=v["state"], why=v["why"][:600])
                self.cur = None
                if not self.stop_flag.is_set():
                    ln["checks"] = self._run_checks(d / "site")
                    ln["passed"] = sum(1 for c in ln["checks"] if c["ok"])
                    if ln["state"] == "done" and ln["checks"] and ln["passed"] < len(ln["checks"]):   # fix 5: checks decide
                        ln["state"] = "unproven"
                        ln["why"] = (f"⚠️ Said it finished, but {len(ln['checks']) - ln['passed']} of {len(ln['checks'])} "
                                     "of your checks failed. " + ln["why"])[:600]
                self.save()
            self.state = "stopped" if self.stop_flag.is_set() else "done"
            if self.state == "done":
                ok = sum(1 for ln in self.lanes if ln["state"] == "done")
                self.why = (("✅ Every model finished and passed your checks." if self.checks else
                             "✅ Every model finished and proved its own work (you gave no checks).") if ok == len(self.lanes) else
                            f"⚠️ {ok} of {len(self.lanes)} models finished — open ℹ️ on each card." if ok else
                            "⚠️ No model finished the task — open ℹ️ on each card.")
        except Exception as e:                                      # noqa: BLE001 — report, never crash the Lab
            self.state, self.why = "failed", f"⚠️ {type(e).__name__}: {str(e)[:300]}"
        finally:
            self.cur = None
            self.save()
            store.autosave(pid, "compare-last", json.dumps({"id": self.id, "state": self.state})[:2000])


class Comparisons:
    def __init__(self):
        self.runs: dict[str, Comparison] = {}
        self.lock = threading.Lock()

    def start(self, lab, cfg, project, task, lanes, checks) -> Comparison:
        with self.lock:
            if any(c.state == "running" and c.project["id"] == project["id"] for c in self.runs.values()):
                raise CompareError("A comparison is already running on this project. Stop it first.", "busy", "⏳")
            c = Comparison(lab, cfg, project, task, lanes, checks)
            self.runs[c.id] = c
        threading.Thread(target=c.loop, daemon=True, name=f"compare-{c.id}").start()
        return c

    def get(self, cid: str) -> Comparison | None:
        return self.runs.get(cid)

    def stop_all(self) -> None:
        for c in self.runs.values():
            c.stop("⏹ Lab shutting down")


# ------------------------------------------------------------------ saved results
def save_result(pid: str, res: dict) -> None:
    d = cdir(pid, res["id"])
    _write_json(d / "result.json", res)
    tmp = d / f".result.html.{uuid.uuid4().hex[:6]}.tmp"
    tmp.write_text(page_html(res, shots=_shots(pid, res)))
    os.replace(tmp, d / "result.html")


def load(pid: str, cid: str) -> dict:
    f = cdir(pid, cid) / "result.json"
    if not f.exists():
        raise CompareError("No such comparison.", "not_found", "❓")
    res = json.loads(f.read_text())
    if res.get("state") == "running":                   # Lab restarted mid-run: it's not running any more
        res["state"], res["why"] = "stopped", "🔁 The Lab restarted during this comparison."
    return res


def listing(pid: str) -> list[dict]:
    d = config.home() / "projects" / pid / "compare"
    out = []
    if preview.PID.fullmatch(pid or "") and d.is_dir():
        for f in sorted(d.glob("*/result.json"), reverse=True)[:50]:
            try:
                r = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            out.append({"id": r["id"], "task": r["task"][:120], "state": r["state"], "usd": r.get("usd", 0),
                        "created": r.get("created"), "models": [f"{x['provider']}/{x['model']}" for x in r["lanes"]]})
    return out


def _shots(pid: str, res: dict) -> dict:
    out = {}
    for ln in res.get("lanes", []):
        f = cdir(pid, res["id"]) / "lanes" / str(ln["k"]) / "shot.png"
        if f.exists():
            out[ln["k"]] = f.read_bytes()
    return out


def save_capture(pid: str, cid: str, k, data_url: str, live: Comparison | None = None) -> dict:
    m = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", data_url or "")
    raw = base64.b64decode(m.group(1)) if m else b""
    if len(raw) > review.MAX_SHOT or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise CompareError("The capture must be a PNG under 4 MB.", "bad_args", "📸")
    d = lane_dir(pid, cid, k)
    if not d.is_dir():
        raise CompareError("No such lane.", "not_found", "❓")
    tmp = d / ".shot.png.tmp"
    tmp.write_bytes(raw)
    os.replace(tmp, d / "shot.png")
    if live is not None:
        live.lanes[int(k)]["shot"] = True
        live.save()
    else:
        res = load(pid, cid)
        res["lanes"][int(k)]["shot"] = True
        save_result(pid, res)
    return {"ok": True, "lane": int(k), "bytes": len(raw)}


# ------------------------------------------------------------------ the page
STATE = {"waiting": "⏳ waiting", "running": "⏳ working", "done": "✅ done", "stopped": "⏹ stopped",
         "capped": "🧢 hit a limit", "refused": "🔒 refused", "failed": "⚠️ failed", "skipped": "⏭ skipped",
         "unproven": "⚠️ not proven"}


def page_html(res: dict, shots: dict | None = None, demo_links: bool = True) -> str:
    """Static comparison page. Escapes everything; the only script is the theme toggle."""
    e = html.escape
    shots = shots or {}
    nchk = len(res.get("checks") or [])
    cards = []
    for ln in res["lanes"]:
        k = ln["k"]
        rows = [("⏱ Time", f"{ln['secs']} s" if ln.get("secs") is not None else "—"),
                ("💲 Cost", f"${ln['usd']:.4f}"),
                ("🔤 Tokens", f"{ln['tokens_in']:,} in · {ln['tokens_out']:,} out"),
                ("👣 Steps", str(ln["steps"])),
                ("🧪 Checks", f"{ln['passed']}/{nchk} passed" if nchk else "none set")]
        chk = "".join(f"<li>{'✅' if c['ok'] else '❌'} <code>{e(c['cmd'])}</code></li>" for c in ln.get("checks", []))
        shot = (f'<img alt="Screenshot of {e(ln["model"])}" src="data:image/png;base64,{base64.b64encode(shots[k]).decode()}">'
                if k in shots else '<p class="dim">📸 no screenshot</p>')
        link = f'<p><a href="lanes/{k}/index.html">👁 Open this demo</a></p>' if demo_links else ""
        cards.append(
            f'<article class="lane"><h2>{e(ln["provider"])} · <span>{e(ln["model"])}</span></h2>'
            f'<p class="st">{e(STATE.get(ln["state"], ln["state"]))}</p>'
            + "".join(f"<p><b>{a}</b> {e(b)}</p>" for a, b in rows)
            + (f"<ul>{chk}</ul>" if chk else "") + shot + link
            + (f'<details><summary>ℹ️ How it ended</summary><p>{e(ln.get("why") or "")}</p></details>'
               if ln.get("why") else "") + "</article>")
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(res.get("created") or time.time()))
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>⚖️ Model comparison — {e(res['task'][:60])}</title>
<script>try{{var t=localStorage.getItem('ailab.cmp.theme');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<style>
:root{{font-size:17px}}
[data-theme=light]{{--bg:#f5f2ec;--panel:#fbf9f4;--line:#d6cdbb;--text:#1d2a3a;--dim:#5d6672;--accent:#8a6a1f}}
[data-theme=dark]{{--bg:#0d1520;--panel:#142133;--line:#2a3d57;--text:#e8dfc8;--dim:#a9a08c;--accent:#c9a54a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;line-height:1.5}}
nav{{position:sticky;top:0;display:flex;align-items:center;gap:8px;padding:8px 14px;background:var(--panel);border-bottom:1px solid var(--line)}}
nav b{{flex:1}}button{{font:inherit;color:inherit;background:none;border:1px solid var(--line);border-radius:10px;min-height:40px;padding:0 12px}}
main{{padding:14px;max-width:1300px;margin:auto}}.task{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px}}
.grid{{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));margin-top:12px}}
.lane{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px}}
.lane h2{{font-size:1.05rem;margin:0 0 4px}}.lane h2 span{{color:var(--accent)}}.lane p{{margin:4px 0}}
.st{{font-weight:600}}.dim{{color:var(--dim)}}ul{{padding-left:1.1em;margin:6px 0}}code{{font-size:.9em;word-break:break-all}}
img{{width:100%;border:1px solid var(--line);border-radius:10px;margin-top:6px}}a{{color:var(--accent)}}
</style></head><body>
<nav><b>⚖️ Model comparison</b><button id="th" aria-label="Light or dark mode">🌙</button></nav>
<main><section class="task"><p><b>Task</b></p><p>{e(res['task'])}</p>
<p class="dim">{e(when)} · {len(res['lanes'])} models · total ${res.get('usd', 0):.4f} of ${res.get('cap_usd', 0):.2f} cap
· {e(STATE.get(res['state'], res['state']))}</p></section>
<div class="grid">{''.join(cards)}</div>
<p class="dim">Each model got the same task and its own copy of the project, in a sandbox with no internet. Built with AI Lab.</p>
</main>
<script>(function(){{var b=document.getElementById('th'),d=document.documentElement;function p(){{b.textContent=d.dataset.theme==='dark'?'☀️':'🌙'}}p();
b.onclick=function(){{d.dataset.theme=d.dataset.theme==='dark'?'light':'dark';try{{localStorage.setItem('ailab.cmp.theme',d.dataset.theme)}}catch(e){{}}p()}}}})();</script>
</body></html>"""


# ------------------------------------------------------------------ 📋 Review
def to_review(lab, cfg: dict, pid: str, cid: str, title: str, writeup: str, live: Comparison | None = None) -> dict:
    p = store.project(pid)
    if not p:
        raise CompareError("No such project.", "bad_args", "❓")
    if p.get("sensitive"):
        raise CompareError("This project is marked sensitive — it stays private and can't go to Review.", "sensitive", "🔒")
    res = live.view() if live is not None else load(pid, cid)
    if res["state"] == "running":
        raise CompareError("Wait until the comparison finishes (or ⏹ Stop it).", "busy", "⏳")
    title, writeup = (title or "").strip()[:80], (writeup or "").strip()[:8000]
    if not title:
        raise CompareError("Give it a title.", "bad_args", "❓")
    if len(writeup) < 20:
        raise CompareError("Write at least a sentence about it (20+ characters).", "bad_args", "❓")
    files = {"index.html": page_html(res, shots=None)}
    for ln in res["lanes"]:
        root = cdir(pid, cid) / "lanes" / str(ln["k"]) / "site"
        for f in preview.list_root(root):
            if Path(f["path"]).suffix.lower() in review.TEXT_EXT:
                text = (root / f["path"]).read_text(errors="replace")
                if len(text.encode()) > review.MAX_FILE:
                    raise CompareError(f"lane {ln['k']}: {f['path']} is over {review.MAX_FILE // 1000} KB.", "too_big", "📦")
                files[f"lanes/{ln['k']}/{f['path']}"] = text
    total = sum(len(v.encode()) for v in files.values())
    if len(files) > review.MAX_FILES or total > review.MAX_TOTAL:
        raise CompareError(f"Too big for Review (max {review.MAX_FILES} files, {review.MAX_TOTAL // 1_000_000} MB).",
                           "too_big", "📦")
    hits = [k for k, v in files.items() if has_secret(v)] + (["write-up"] if has_secret(writeup) else [])
    if hits:
        raise CompareError("Something that looks like a key is in: " + ", ".join(hits[:5]) + ". Remove it first.",
                           "secret", "🔑")
    shots = _shots(pid, res)
    best = sorted(res["lanes"], key=lambda ln: (-ln["passed"], ln["usd"]))
    shot = next((shots[ln["k"]] for ln in best if ln["k"] in shots), b"")
    pkg = {"title": title, "project": pid, "writeup": writeup,
           "models": [f"{ln['provider']}/{ln['model']}"[:80] for ln in res["lanes"]], "files": files,
           "screenshot_b64": base64.b64encode(shot).decode() if shot else "", "sensitive": False}
    rec = {"at": time.time(), "project": pid, "title": title, "models": pkg["models"], "files": sorted(files),
           "has_shot": bool(shot), "comparison": cid}
    if cfg.get("mode") == "connected":
        r = lab.mcp.call("review_submit", pkg)
        rec.update(where="hermes", hermes_id=r.get("id"), state=r.get("state", "waiting"))
    else:
        lid = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        d = config.home() / "review" / "kept" / lid
        d.mkdir(parents=True)
        (d / "package.json").write_text(json.dumps(pkg))
        rec.update(where="kept", local_id=lid, state="kept",
                   note="Standalone mode: kept here. Publishing goes through Hermes Review (connected mode).")
    (config.home() / "review").mkdir(parents=True, exist_ok=True)
    with open(config.home() / "review" / "sent.jsonl", "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return {"ok": True, **rec}
