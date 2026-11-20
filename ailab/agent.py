"""Agent loop (flag `agent`): plan → write → run in the sandbox → read the output → repeat.

The model answers with ONE JSON action per step. Limits: step cap, a per-run $ cap (on top of the Lab's
daily cap), the ⏹ Stop button, and — connected mode — Hermes's STOP_SHIFTS kill switch, checked before
every step. Writes land only inside the project folder; any other write becomes an approval item for Scott.
Commands run under srt with no network, writing only inside the project folder.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from . import config, preview, store
from .mcp_client import HermesRefused
from .privacy import PrivacyRefused
from .spend import SpendBlocked

# Hermes tools the agent may call (connected mode). Studio jobs show up in the Hermes ⏳ Running list.
AGENT_TOOLS = ("jobs_list", "job_get", "job_wait", "addon_build", "print3d_submit", "capabilities_list",
               "recipes_search", "lessons_search")
MAX_OUT = 4000
RUN_TIMEOUT_S = 60
SYSTEM = """You are the AI Lab agent. You work on ONE small web project folder. Reply with exactly ONE JSON
object per turn and nothing else. Actions:
{"action":"list"}
{"action":"read","path":"index.html"}
{"action":"write","path":"index.html","content":"<full file text>"}
{"action":"run","cmd":"grep -c footer index.html"}      (sh, inside the folder, no network, 60 s)
{"action":"hermes","tool":"addon_build","args":{"template":"hello"}}   (connected mode only)
{"action":"done","summary":"what changed and how you checked it"}
Add "why" (one short line) to every action. Paths are relative to the project folder. Check your work with
"run" before "done"."""


class Stopped(Exception):
    pass


def _approvals() -> Path:
    d = config.home() / "approvals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def hold_for_approval(pid: str, run_id: str, path: str, content: str) -> dict:
    """A write outside the project folder: kept, not applied. Scott decides (📋 Review, M6)."""
    aid = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    (_approvals() / f"{aid}.txt").write_text(content)
    item = {"id": aid, "at": time.time(), "kind": "write_outside_project", "project": pid, "run": run_id,
            "path": path[:300], "bytes": len(content.encode()), "state": "waiting"}
    with open(_approvals() / "items.jsonl", "a") as fh:
        fh.write(json.dumps(item) + "\n")
    return item


def approvals(state: str = "waiting") -> list[dict]:
    f = _approvals() / "items.jsonl"
    rows = []
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not state or r.get("state") == state:
                rows.append(r)
    return rows[-200:]


def parse_action(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    i = t.find("{")
    if i < 0:
        raise ValueError("no JSON object")
    obj, _ = json.JSONDecoder().raw_decode(t[i:])
    if not isinstance(obj, dict) or "action" not in obj:
        raise ValueError("JSON has no \"action\"")
    return obj


def run_in_sandbox(root: Path, cmd: str, timeout: int = RUN_TIMEOUT_S) -> dict:
    kind = preview.sandbox_kind()
    if kind == "missing":
        raise preview.PreviewError("The sandbox (srt) isn't installed, so nothing was run.", "no_sandbox", "🧱")
    scratch = Path(tempfile.mkdtemp(prefix="ailab-run-", dir="/tmp"))
    argv = ["sh", "-c", cmd]
    if kind == "srt":
        s = preview.srt_settings(root, scratch)
        s["filesystem"]["allowWrite"].append(str(root))         # the agent may build inside its folder
        s["filesystem"]["denyWrite"] = []
        cfg = scratch / "srt.json"
        cfg.write_text(json.dumps(s))
        argv = ["srt", "-s", str(cfg), *argv]
    try:
        r = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL, start_new_session=True)
        out = (r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr.strip() else ""))
        return {"exit": r.returncode, "output": out[-MAX_OUT:]}
    except subprocess.TimeoutExpired:
        return {"exit": None, "output": f"⏱ stopped after {timeout} s"}


class Run:
    def __init__(self, lab, cfg: dict, project: dict, provider: str, model: str, task: str):
        self.id = uuid.uuid4().hex[:10]
        self.lab, self.cfg, self.project = lab, cfg, project
        self.provider, self.model, self.task = provider, model, task.strip()[:4000]
        self.root = preview.ensure_site(project["id"]).resolve()
        self.step_cap = int(cfg.get("agent_step_cap", 12))
        self.cap_usd = float(cfg.get("agent_cap_usd", 0.50))
        self.usd, self.steps, self.state, self.why = 0.0, [], "running", ""
        self.stop_flag = threading.Event()
        self.log = config.home() / "projects" / project["id"] / "agent" / f"{self.id}.jsonl"
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.connected = cfg.get("mode") == "connected"

    # ---- public view ----
    def view(self) -> dict:
        return {"id": self.id, "state": self.state, "why": self.why, "task": self.task, "steps": self.steps,
                "step_cap": self.step_cap, "usd": round(self.usd, 6), "cap_usd": self.cap_usd,
                "project": self.project["id"], "provider": self.provider, "model": self.model}

    def stop(self, why: str = "⏹ Stopped by you") -> None:
        self.why = why
        self.stop_flag.set()

    # ---- loop ----
    def _check_stop(self) -> None:
        if self.stop_flag.is_set():
            raise Stopped(self.why or "⏹ Stopped")
        if self.connected:
            try:
                r = self.lab.mcp.call("shifts_stopped")
            except HermesRefused as e:                                # can't see the kill switch → don't run
                raise Stopped(f"🔌 Can't check Hermes STOP_SHIFTS ({e.code}) — stopped to be safe.") from None
            if r.get("stopped"):
                raise Stopped("🛑 Hermes STOP_SHIFTS is on — agent stopped.")

    def _record(self, step: dict) -> None:
        step["n"], step["at"] = len(self.steps) + 1, time.time()
        self.steps.append(step)
        with open(self.log, "a") as fh:
            fh.write(json.dumps(step, default=str) + "\n")

    def _inside(self, rel: str) -> Path | None:
        if not rel or rel.startswith(("/", "~")) or "\\" in rel:
            return None
        p = (self.root / rel)
        try:
            p.parent.resolve().relative_to(self.root)
        except ValueError:
            return None
        if p.is_symlink() or any(s.startswith(".") for s in Path(rel).parts):
            return None
        return p

    def act(self, a: dict) -> dict:
        kind = str(a.get("action"))
        if kind == "list":
            return {"files": [f["path"] for f in preview.list_files(self.project["id"])]}
        if kind == "read":
            p = self._inside(str(a.get("path") or ""))
            if not p or not p.is_file():
                return {"error": "No such file inside the project."}
            return {"text": p.read_text(errors="replace")[:20000]}
        if kind == "write":
            rel, content = str(a.get("path") or ""), str(a.get("content") or "")
            p = self._inside(rel)
            if not p:
                item = hold_for_approval(self.project["id"], self.id, rel, content)
                return {"held": True, "approval": item["id"],
                        "note": "Outside the project folder — held for Scott's approval, not written."}
            if len(content.encode()) > preview.MAX_EDIT:
                return {"error": "File too big."}
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(f".{p.name}.agent")
            tmp.write_text(content)
            tmp.replace(p)
            return {"wrote": rel, "bytes": len(content.encode())}
        if kind == "run":
            return run_in_sandbox(self.root, str(a.get("cmd") or "true")[:2000])
        if kind == "hermes":
            if not self.connected:
                return {"error": "Hermes tools need connected mode (🔌). This Lab is standalone."}
            tool = str(a.get("tool") or "")
            if tool not in AGENT_TOOLS:
                return {"error": f"{tool!r} isn't on the agent's Hermes list: {', '.join(AGENT_TOOLS)}"}
            try:
                return self.lab.mcp.call(tool, a.get("args") if isinstance(a.get("args"), dict) else {})
            except HermesRefused as e:
                return {"error": f"Hermes refused ({e.code}): {e.message}"}
        if kind == "done":
            return {"done": True}
        return {"error": f"Unknown action {kind!r}."}

    def loop(self) -> None:
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Task: {self.task}\nFiles: "
                 + ", ".join(f["path"] for f in preview.list_files(self.project["id"]))}]
        try:
            while True:
                self._check_stop()
                if len(self.steps) >= self.step_cap:
                    self.state, self.why = "capped", f"🔢 Step cap reached ({self.step_cap})."
                    return
                left = self.cap_usd - self.usd
                if left <= 0:
                    self.state, self.why = "capped", f"💲 Run cap reached (${self.cap_usd:.2f})."
                    return
                r = self.lab.chat(self.project, self.provider, self.model, msgs, 2048, cap_usd=left,
                                  task=f"lab-agent:{self.project['id']}")
                self.usd += float(r.usd or 0)
                self._check_stop()                                    # Stop pressed while the model thought
                msgs.append({"role": "assistant", "content": r.text})
                try:
                    a = parse_action(r.text)
                except ValueError as e:
                    res = {"error": f"Reply was not one JSON action ({e})."}
                    self._record({"action": "bad_reply", "why": "", "result": res, "usd": r.usd})
                    msgs.append({"role": "user", "content": "RESULT: " + json.dumps(res)})
                    continue
                res = self.act(a)
                shown = {k: v for k, v in a.items() if k != "content"}
                if "content" in a:
                    shown["bytes"] = len(str(a["content"]).encode())
                self._record({**shown, "result": res, "usd": r.usd})
                if res.get("done"):
                    self.state, self.why = "done", str(a.get("summary") or "✅ Done")[:600]
                    return
                msgs.append({"role": "user", "content": "RESULT: " + json.dumps(res, default=str)[:MAX_OUT + 500]})
        except Stopped as e:
            self.state, self.why = "stopped", str(e)
        except SpendBlocked as e:
            self.state, self.why = "capped", f"💲 {e}"
        except PrivacyRefused as e:
            self.state, self.why = "refused", f"🔒 {e}"
        except preview.PreviewError as e:
            self.state, self.why = "failed", f"{e.icon} {e.message}"
        except Exception as e:                                        # noqa: BLE001 — report, never crash the Lab
            self.state, self.why = "failed", f"⚠️ {type(e).__name__}: {str(e)[:300]}"
        finally:
            store.autosave(self.project["id"], "agent-last", json.dumps(self.view())[:100_000])


class Agents:
    def __init__(self):
        self.runs: dict[str, Run] = {}
        self.lock = threading.Lock()

    def start(self, lab, cfg, project, provider, model, task) -> Run:
        if not task.strip():
            raise ValueError("Tell the agent what to do.")
        with self.lock:
            if any(r.state == "running" and r.project["id"] == project["id"] for r in self.runs.values()):
                raise ValueError("An agent is already working on this project. Stop it first.")
            run = Run(lab, cfg, project, provider, model, task)
            self.runs[run.id] = run
        threading.Thread(target=run.loop, daemon=True, name=f"agent-{run.id}").start()
        return run

    def get(self, rid: str) -> Run:
        r = self.runs.get(rid)
        if not r:
            raise KeyError("No such run.")
        return r

    def stop_all(self) -> None:
        for r in self.runs.values():
            r.stop("⏹ Lab shutting down")
