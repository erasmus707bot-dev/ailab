"""Agent loop (flag `agent`): plan → write → run in the sandbox → read the output → repeat.

The model answers with ONE JSON action per step. Limits: step cap, a per-run $ cap (on top of the Lab's
daily cap), the ⏹ Stop button, and — connected mode — Hermes's STOP_SHIFTS kill switch, checked before
every step. Writes land only inside the project folder; any other write becomes an approval item for Scott.
Commands run under srt with no network, writing only inside the project folder.
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from . import config, memory, preview, repos, secretscan, store
from .mcp_client import HermesRefused
from .transport import HttpError
from .privacy import PrivacyRefused
from .spend import SpendBlocked

# Hermes tools the agent may call (connected mode). Studio jobs show up in the Hermes ⏳ Running list.
AGENT_TOOLS = ("jobs_list", "job_get", "job_wait", "addon_build", "print3d_submit", "capabilities_list",
               "recipes_search", "lessons_search",
               # 2026-11-22 goal tools: a fresh Mario-type level, and a Linux app through Linux App Studio
               "mario_level_spec", "mario_level_check", "mario_level_make",
               "linux_app_describe", "linux_app_change", "linux_app_get", "linux_app_build", "linux_app_package",
               # 2026-11-22 game work: pull Pidima's source into the project, change + test it here, send it back as a proposal
               "pidima_status", "pidima_source", "pidima_propose")
MAX_OUT = 4000
RUN_TIMEOUT_S = 60
STUCK_AFTER_S = 600        # 2026-11-23 fix 5: no new step for this long = stuck (cfg "stuck_after_s")
# Hermes tool results that prove the work (fix 5). Anything else is not a check.
PROOF_TOOLS = {"mario_level_check": lambda r: r.get("playable") is True,
               "mario_level_make": lambda r: not r.get("error") and r.get("ok", True) is not False,
               "linux_app_build": lambda r: str(r.get("verdict")) == "pass"}
CHANGE_ACTIONS = ("write", "edit")
SYSTEM = """You are the AI Lab agent. You work on ONE small web project folder. Reply with exactly ONE JSON
object per turn and nothing else. Actions:
{"action":"list"}
{"action":"read","path":"index.html"}      (big file: add "start":LINE,"lines":N — e.g. around a line "find" gave you)
{"action":"write","path":"index.html","content":"<full file text>"}      (new or small files)
{"action":"edit","path":"game.js","find":"<exact text now in the file, found once>","replace":"<new text>"}   (big files: change one spot)
{"action":"run","cmd":"grep -c footer index.html"}      (sh, inside the folder, no network, 60 s)
{"action":"hermes","tool":"addon_build","args":{"template":"hello"}}   (connected mode only)
{"action":"ask","questions":[{"q":"Which look?","choices":["Classic","Neon","Wood"],"best":0,"why":"matches your other pages"}]}
      (1-3 questions, 2-4 short choices each. "best" = the number of the choice YOU recommend, "why" = a few plain words. Waits for Scott.)
{"action":"plan","steps":["Page layout","Game rules","Controls","Test it"]}   (3-7 short plain steps. Scott sees the list and presses Go. After Go, add "module":"1","2",... = the step you are on.)
{"action":"done","summary":"what changed and how you checked it"}
Add "why" (one short line) to every action. Following a build prompt? Add "module":"M1" (the module you are on). Paths are relative to the project folder. Check your work with
"run" before "done". "done" is refused until a check you ran AFTER your last change exited 0.
Long files: a reply that is too long is CUT OFF and wasted. Put at most about 150 lines in one action — "write" the first
part ending with a marker comment line, then "edit" that marker into the next part.
The page runs in a locked-down preview: localStorage, sessionStorage and cookies THROW there. Wrap every use in try/catch
with a fallback, or the whole script dies. A robot opens the finished page and presses its start button — page errors fail it."""
# 2026-11-24 (Tetris test run): Scott picks first — questions with choices + a recommended pick, then a plan he OKs.
ASK_FIRST = """
Scott chooses before you build. If the task builds something new, or leaves real choices open (look, rules, size, name):
FIRST "ask", THEN "plan", and only then write. Never ask what his memory below already answers — use it. A small exact
change (one spot, nothing to choose) needs neither."""
GATE_NUDGE = ("Scott wants to choose first. If this builds something new or leaves real choices open: \"ask\" (1-3 questions, "
              "choices, your recommended pick), then \"plan\". If it is a small exact change with nothing to choose, send this action again.")
CUT_TIP = ("Your reply was cut off because it was too long. Your next reply gets more room, but parts are still safer: "
           "write the first ~150 lines ending with a marker comment, then use \"edit\" to turn the marker into the next part.")
JSON_TIP = "Reply with ONE JSON object only — no words before or after it."
BAD_ROW_MAX = 3            # this many unreadable replies in a row = the model can't do the job; stop, don't burn money
SNAP_MAX = 20_000_000      # ↔ Before copy of the project page (bytes); bigger projects get no Before picture
SNAP_KEEP = 3
# Added to the system prompt in connected mode only (standalone has no Hermes tools).
HERMES_GUIDE = """
Hermes studio tools (use with {"action":"hermes","tool":...,"args":{...}}):
Mario-type level (for Pidima, Scott's own run-and-jump game): mario_level_spec {} -> rules, squares, example map.
mario_level_check {"rows":[13 strings]} -> playable + problems. mario_level_make {"name":"...","rows":[...]} -> adds the level to
the game after a test bot finishes it (or {"name","seed","length","difficulty"} to have Hermes make one). Design your own map,
check it, fix the problems it lists, then make it.
Linux app: linux_app_describe {"text":"what the app does","name":"..."} -> id. linux_app_change {"id","text":"add a button
called Save"} (plain words, one change per call). linux_app_build {"id"} -> verdict + problems (takes minutes).
linux_app_package {"id"} -> the .deb, only after verdict "pass". Installing is Scott's step, never yours.
Pidima game code: pidima_source {} copies engine.js, game.js, index.html, levels.js and bot.js into this project folder (you get
the file names back, not the text — read what you need). Change the files with "edit". Test with run "node --check game.js" and
run "node bot.js --js 10" (exit 0 = the test bot finished 10 fresh levels on your engine). When the tests pass:
pidima_propose {"files":["engine.js","game.js"],"note":"what changed"} sends those files from this folder to Scott as a proposal.
He applies it; you never do. pidima_status {} -> version, levels, proposals waiting."""


# Added to the system prompt only when Scott has linked code folders (python3 -m ailab link <name> <folder>).
REPO_GUIDE = """
Real code folders (linked by Scott): {names}. You can read them and PROPOSE changes; you never write them.
{{"action":"repo","do":"find","repo":"NAME","pattern":"def complete_task","glob":"*.py"}}   -> paths + matching lines ("dir" narrows it)
{{"action":"repo","do":"list","repo":"NAME","dir":"forge/ailab"}}
{{"action":"repo","do":"pull","repo":"NAME","paths":["forge/ailab/card.py"]}}   -> copies into this project as repos/NAME/forge/ailab/card.py
{{"action":"repo","do":"propose","repo":"NAME","paths":["forge/ailab/card.py"],"note":"what changed and why"}}
Way of working: find the code, pull only the files you need, read them, change your copy with "edit" (one spot at a
time), check it with "run" (python3 -m py_compile repos/NAME/x.py, or node --check), then propose the files you
changed. Scott sees each as a diff and applies it himself. Keep changes small and matching the code around them."""


class Stopped(Exception):
    pass


def _approvals() -> Path:
    d = config.home() / "approvals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def hold_for_approval(pid: str, run_id: str, path: str, content: str, note: str = "") -> dict:
    """A write outside the project folder: kept, not applied. Scott decides (📋 Review, M6)."""
    aid = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    (_approvals() / f"{aid}.txt").write_text(content)
    item = {"id": aid, "at": time.time(), "kind": "write_outside_project", "project": pid, "run": run_id,
            "path": path[:300], "bytes": len(content.encode()), "state": "waiting", **({"note": note[:300]} if note else {})}
    with open(_approvals() / "items.jsonl", "a") as fh:
        fh.write(json.dumps(item) + "\n")
    return item


def approvals(state: str | None = "waiting") -> list[dict]:
    """Latest record per item (M6: Apply / Reject append a new state line; nothing is rewritten)."""
    f = _approvals() / "items.jsonl"
    merged: dict[str, dict] = {}
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("id"):
                merged[r["id"]] = {**merged.get(r["id"], {}), **r}
    rows = [r for r in merged.values() if not state or r.get("state") == state]
    return rows[-200:]


def set_approval_state(aid: str, state: str, **extra) -> None:
    with open(_approvals() / "items.jsonl", "a") as fh:
        fh.write(json.dumps({"id": aid, "state": state, "decided_at": time.time(), **extra}) + "\n")


def make_diff(name: str, before: str | None, after: str, cap: int = 12000) -> str:
    """Unified diff for the workbench's Changes list. before=None means a new file. Never sent to the model."""
    d = "\n".join(difflib.unified_diff((before or "").splitlines(), after.splitlines(),
                                       "/dev/null" if before is None else f"a/{name}", f"b/{name}", lineterm="", n=3))
    return d if len(d) <= cap else d[:cap] + "\n… (diff cut — open the file to see the rest)"


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


READ_CHARS = 20000


def read_range(text: str, start=None, lines=None) -> dict:
    """read: whole file when it fits; otherwise a line range. A cut-off read always says so (2026-11-22: 49 Hermes
    web pages are over 20 KB — a silent cut made the agent edit blind)."""
    all_lines = text.splitlines(keepends=True)
    total = len(all_lines)
    try:
        s = max(1, int(start)) if start is not None else 1
        n = max(1, int(lines)) if lines is not None else total
    except (TypeError, ValueError):
        return {"error": "\"start\" and \"lines\" must be whole numbers."}
    if s > max(total, 1):
        return {"error": f"The file has {total} lines; start {s} is past the end."}
    chunk = "".join(all_lines[s - 1:s - 1 + n])
    cut = len(chunk) > READ_CHARS
    chunk = chunk[:READ_CHARS]
    shown = chunk.count("\n") + (0 if chunk.endswith("\n") or not chunk else 1)
    end = s + shown - 1
    out = {"text": chunk}
    if start is not None or lines is not None or cut:
        out.update(start=s, end=end, total_lines=total)
    if cut or end < total and (start is not None or lines is not None or cut):
        out["truncated"] = cut
        if cut:
            out["tip"] = (f"Only lines {s}–{end} of {total} fit. Use \"find\"/\"run\" grep -n to get a line number, "
                          "then read with \"start\" and \"lines\" (e.g. 150).")
    return out


class Run:
    def __init__(self, lab, cfg: dict, project: dict, provider: str, model: str, task: str,
                 root: Path | None = None, log_dir: Path | None = None, cap_usd: float | None = None,
                 autosave_field: str = "agent-last", step_cap: int | None = None, ask_first: bool = False,
                 selftest=None):
        """root/log_dir/cap_usd: ⚖️ Compare (M8) runs one lane in its own copy of the project."""
        self.id = uuid.uuid4().hex[:10]
        self.lab, self.cfg, self.project = lab, cfg, project
        self.provider, self.model, self.task = provider, model, task.strip()[:4000]
        self.root = (root or preview.ensure_site(project["id"])).resolve()
        self.step_cap = int(step_cap or cfg.get("agent_step_cap", 12))
        self.cap_usd = float(cfg.get("agent_cap_usd", 0.50) if cap_usd is None else cap_usd)
        self.usd, self.steps, self.state, self.why = 0.0, [], "running", ""
        self.tokens_in = self.tokens_out = 0
        self.autosave_field = autosave_field
        self.is_lane = root is not None        # ⚖️ Compare lanes work on copies: they may read linked code, never propose
        self.undo: dict[int, tuple] = {}       # step n -> (path, text before | None, text after); memory only
        self._change = None
        self.stop_flag = threading.Event()
        self.log = (log_dir or config.home() / "projects" / project["id"] / "agent") / f"{self.id}.jsonl"
        self.log.parent.mkdir(parents=True, exist_ok=True)
        # M6: 📋 Review lists the models used from these
        self.log.with_suffix(".meta.json").write_text(json.dumps({"provider": provider, "model": model, "at": time.time()}))
        self.connected = cfg.get("mode") == "connected"
        # fix 5 (2026-11-23): "done" needs proof — a passing check after the last change
        self.changed = 0                      # step number of the last write/edit (0 = none yet)
        self.proved = 0                       # step number of the last passing check
        self.refused_done = 0
        self.stuck_after = float(cfg.get("stuck_after_s", STUCK_AFTER_S))
        self.last_progress = time.time()
        self.memory_used: list[str] = []      # 🧠 M2: memory subjects given to the model (shown as "used: …")
        self.memory_saved: list[str] = []     # 🧠 M2: things Scott stated in the task, saved to memory
        # M5 (2026-11-24): plain progress list from the prompt's "## Module N" headings + on-screen questions
        heads = list(re.finditer(r"^##\s*Module\s+([0-9A-Za-z]+)[ \t]*[—:–.-]*[ \t]*(.*)$", self.task, re.M))[:12]
        self.plan = [m.group(1) for m in heads]
        self.prompt_plan = bool(heads)        # modules came from a build prompt (not the agent's own plan)
        self.module_now = ""
        self.question: dict | None = None
        self._answer = None
        self._answered = threading.Event()
        # 2026-11-24 workflow build (Tetris test run): no dead ends, questions first, plan gate, before/after, robot play-test
        self.ask_first = bool(ask_first) and not self.is_lane
        self.plan_names: dict[str, str] = {m.group(1): f"{m.group(1)} · {m.group(2).strip()[:60]}"
                                           for m in heads if m.group(2).strip()}   # number -> plain name
        self.asked = False
        self.plan_ok = bool(self.plan)        # a build prompt's modules are already the plan
        self.gate_nudged = False
        self.bad = self.bad_row = 0           # unreadable replies: never count against the step limit
        self.long_next = False                # a reply was cut off → the next one may be long (Hermes job)
        self.long_used = 0
        self.cap_kind = ""                    # "steps" → ▶ Continue is possible
        self.msgs: list[dict] | None = None   # kept so ▶ Continue picks up where the run stopped
        self.selftest = None if self.is_lane else selftest
        self.robot: dict | None = None
        self.robot_tries = 0
        self.proof_kind = ""                  # "tool" = a Hermes studio test proved it (e.g. Linux build pass)
        self.before = "" if self.is_lane else self._snapshot()

    # ---- public view ----
    def view(self) -> dict:
        return {"id": self.id, "state": self.state, "why": self.why, "task": self.task, "steps": self.steps,
                "step_cap": self.step_cap, "usd": round(self.usd, 6), "cap_usd": self.cap_usd,
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
                "project": self.project["id"], "provider": self.provider, "model": self.model,
                "proved": self.proof_ok(), "changed": bool(self.changed), **self.stuck_info(),
                "memory_used": self.memory_used, "memory_saved": self.memory_saved,
                "plan": self.plan_view(), "question": self.question,
                "real_steps": len(self.steps) - self.bad, "long_replies": self.long_used, "bad": self.bad, "robot": self.robot, "before": bool(self.before),
                "can_continue": self.state == "capped" and self.cap_kind == "steps" and self.msgs is not None}

    def plan_view(self) -> list[dict]:
        """✅ done / 🔨 doing / ⏳ left for each module of the build prompt."""
        if not self.plan:
            return []
        now = self.plan.index(self.module_now) if self.module_now in self.plan else (0 if self.steps else -1)
        out = []
        for i, m in enumerate(self.plan):
            if i < now or self.state == "done":
                st = "done"
            elif i == now and self.state == "running":
                st = "doing"
            else:
                st = "left"
            out.append({"module": self.plan_names.get(m) or f"Module {m}", "state": st})
        return out

    def _snapshot(self) -> str:
        """↔ Before: a copy of the project page as it was when this run started (shown beside the page now)."""
        try:
            files = [x for x in preview.list_root(self.root) if not x["path"].startswith("repos/")]
            if not files or sum(x["bytes"] for x in files) > SNAP_MAX:
                return ""
            base = self.log.parent / "before"
            dst = base / self.id
            for x in files:
                t = dst / x["path"]
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.root / x["path"], t)
            for old in sorted((d for d in base.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)[:-SNAP_KEEP]:
                shutil.rmtree(old, ignore_errors=True)
            return str(dst)
        except OSError:                                               # a picture is a help, never a blocker
            return ""

    def _wait(self) -> str:
        """Block until Scott answers the on-screen card. Waiting for him is not "stuck"."""
        try:
            while not self._answered.wait(1.0):
                self._check_stop()
                self.last_progress = time.time()
        finally:
            self.question = None
            self._answered.clear()
        self.last_progress = time.time()
        return str(self._answer or "")

    def _selftest(self) -> dict | None:
        """🤖 The robot opens the finished page, presses its main button and some keys. None = nothing to test."""
        if not self.selftest or not self.changed:
            return None
        page = [st.get("path", "") for st in self.steps if st.get("diff") and not st.get("undone")]
        if not any("/" not in p and p.rsplit(".", 1)[-1].lower() in ("html", "htm", "js", "mjs", "css") for p in page):
            if self.proof_kind == "tool":                 # a Hermes studio test already ran it for real
                return None
            self.robot = {"ran": False, "ok": False, "level": "yellow", "good": [], "shots": [], "skipped": True,
                          "why": ["🤖 This build isn't the project's web page, so the robot couldn't play it — "
                                  "nothing here proves it runs. Test it where it runs (phone / its own engine)."]}
            return self.robot
        self.robot_tries += 1
        try:
            self.robot = self.selftest(self)
        except Exception as e:                                        # noqa: BLE001 — can't run = yellow, never green
            self.robot = {"ran": False, "ok": False, "level": "yellow",
                          "why": [f"🤖 Robot play-test did not run: {str(e).splitlines()[0][:200] if str(e) else type(e).__name__}"]}
        self.last_progress = time.time()
        return self.robot

    def _robot_words(self) -> str:
        r = self.robot or {}
        return " ".join(str(x) for x in (r.get("why") or []))[:300]

    def more(self, n: int | None = None) -> None:
        """▶ Continue after the step limit: more steps, same conversation."""
        if not (self.state == "capped" and self.cap_kind == "steps" and self.msgs is not None):
            raise ValueError("This run can't be continued. Start a new one.")
        self.step_cap += max(1, int(n or self.cfg.get("agent_more_steps", 12)))
        note = "Scott pressed Continue: you have more steps. Finish the task, run your check, then say done."
        if self.msgs and self.msgs[-1]["role"] == "user":
            self.msgs[-1]["content"] += "\n" + note
        else:
            self.msgs.append({"role": "user", "content": note})
        self.state, self.why, self.cap_kind = "running", "", ""
        self.stop_flag.clear()
        self.last_progress = time.time()

    def answer(self, text: str) -> None:
        """Scott answered the on-screen question."""
        if not self.question:
            raise ValueError("The agent is not asking anything right now.")
        self._answer = str(text or "").strip()[:500] or "(no answer)"
        self._answered.set()

    def proof_ok(self) -> bool:
        """True when nothing was changed, or a check passed after the last change."""
        return not self.changed or self.proved > self.changed

    def stuck_info(self) -> dict:
        quiet = max(0.0, time.time() - self.last_progress)
        return {"quiet_s": round(quiet), "stuck": self.state == "running" and quiet >= self.stuck_after,
                "stuck_after_s": round(self.stuck_after)}

    def undo_step(self, n: int) -> dict:
        """↩ Undo one write/edit step (workbench Changes). Only if the file still holds exactly what that step wrote.
        A new file is renamed to .<name>.undone (hidden), never deleted."""
        if self.state == "running":
            raise ValueError("The agent is still working. Stop it first, then undo.")
        ch = self.undo.get(n)
        if not ch:
            raise ValueError("That step can't be undone any more (the Lab was restarted, or it wasn't a file change).")
        rel, before, after = ch
        p = self._inside(rel)
        if not p or not p.is_file() or p.read_text(errors="replace") != after:
            raise ValueError("The file changed after this step — not undone. Open it and fix it by hand.")
        if before is None:
            p.replace(p.with_name(f".{p.name}.undone"))
        else:
            tmp = p.with_name(f".{p.name}.agent")
            tmp.write_text(before)
            tmp.replace(p)
        self.steps[n - 1]["undone"] = True
        del self.undo[n]
        return {"path": rel, "new_file": before is None}

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
        self.last_progress = step["at"]
        res = step.get("result") if isinstance(step.get("result"), dict) else {}
        if step.get("action") in CHANGE_ACTIONS and not res.get("error") and not res.get("held"):
            self.changed = step["n"]
        elif step.get("action") == "run" and res.get("exit") == 0:
            self.proved, self.proof_kind = step["n"], "run"
        elif step.get("action") == "hermes" and step.get("tool") in PROOF_TOOLS and not res.get("error"):
            try:
                if PROOF_TOOLS[step["tool"]](res):
                    self.proved, self.proof_kind = step["n"], "tool"
            except Exception:                                        # noqa: BLE001 — odd result = no proof
                pass
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

    def _repo(self, a: dict) -> dict:
        """🔗 linked code folders: find / list / pull are read-only; propose only HOLDS changes for Scott."""
        try:
            name, do = str(a.get("repo") or ""), str(a.get("do") or "")
            root = repos.root_of(self.cfg, name)
            if do == "find":
                res = repos.find(root, str(a.get("pattern") or ""), str(a.get("glob") or ""), str(a.get("dir") or ""))
                if not res.get("matches"):                    # point the model at the program's other folders
                    others = [f for m in repos.programs(self.cfg).values() if name in m for f in m if f != name]
                    if others:
                        res["tip"] = f"Nothing in {name!r}. The same program also has: {', '.join(dict.fromkeys(others))} — try find there."
                return res
            if do == "list":
                return repos.ls(root, str(a.get("dir") or ""))
            if do == "pull":
                return repos.pull(root, name, a.get("paths"), self.root)
            if do != "propose":
                return {"error": "repo \"do\" must be find, list, pull or propose."}
            if self.is_lane:
                return {"error": "Proposing is off in ⚖️ Compare — run the task in the workbench to propose."}
            paths = a.get("paths") if isinstance(a.get("paths"), list) else []
            if not paths:
                return {"error": "paths must be a list of the files you changed (paths inside the linked folder)."}
            note, proposed, skipped = str(a.get("note") or "")[:300], [], []
            waiting = approvals()
            for rel in [str(x) for x in paths][:repos.MAX_PULL]:
                rel = rel.removeprefix(f"repos/{name}/")
                try:
                    target = repos.safe(root, rel)
                except repos.RepoError as e:
                    skipped.append(str(e))
                    continue
                mine = self._inside(f"repos/{name}/{rel}")
                if not mine or not mine.is_file():
                    skipped.append(f"{rel}: no copy in this project (repos/{name}/{rel}) — pull it or write it there first.")
                    continue
                text = mine.read_text(errors="replace")
                if len(text.encode()) > preview.MAX_EDIT or secretscan.has_secret(text):
                    skipped.append(f"{rel}: too big, or it holds something that looks like a key — not proposed.")
                    continue
                if target.is_file() and target.read_text(errors="replace") == text:
                    skipped.append(f"{rel}: same as the real file — nothing to propose.")
                    continue
                for old in waiting:                               # a newer proposal for the same file replaces the waiting one
                    if old.get("path") == str(target) and old.get("project") == self.project["id"]:
                        set_approval_state(old["id"], "superseded")
                item = hold_for_approval(self.project["id"], self.id, str(target), text, note=f"{name}: {note}" if note else name)
                proposed.append({"path": rel, "approval": item["id"]})
            return {"proposed": proposed, "skipped": skipped,
                    "note": "Held for Scott — he sees each as a diff and applies it himself. Nothing was written to the real folder."}
        except repos.RepoError as e:
            return {"error": str(e)}

    def act(self, a: dict) -> dict:
        kind = str(a.get("action"))
        m = str(a.get("module") or "").strip().upper().replace("MODULE", "").strip().lstrip("M")
        if m and m in [x.upper() for x in self.plan]:
            self.module_now = next(x for x in self.plan if x.upper() == m)
        if kind == "ask":                                    # question cards: choices + the model's recommended pick
            raw = a.get("questions") if isinstance(a.get("questions"), list) else \
                [{"q": a.get("question"), "choices": a.get("choices"), "best": a.get("best"), "why": a.get("best_why")}]
            items = []
            for it in raw[:3]:
                if not isinstance(it, dict):
                    continue
                q = str(it.get("q") or it.get("question") or "").strip()[:300]
                ch = [str(c)[:160] for c in (it.get("choices") or []) if str(c).strip()][:4]
                if not q:
                    continue
                try:
                    best = int(it.get("best"))
                except (TypeError, ValueError):
                    best = -1                                        # no pick given → no ⭐ (never invent one)
                items.append({"q": q, "choices": ch, "best": best if 0 <= best < len(ch) else -1,
                              "why": str(it.get("why") or "").strip()[:160]})
            if not items:
                return {"error": "ask needs a question."}
            self.asked = True
            if self.is_lane:
                return {"answer": "(nobody is here to answer — go with the choice you recommend)"}
            self.question = {"kind": "ask", "text": items[0]["q"], "choices": items[0]["choices"], "items": items}
            return {"answer": self._wait()}
        if kind == "plan":                                   # plan gate: Scott sees done / doing / left and presses Go
            steps = [str(x).strip()[:80] for x in (a.get("steps") or []) if str(x).strip()][:8]
            if self.prompt_plan:
                return {"note": "The build prompt already lists its modules — follow those."}
            if len(steps) < 2:
                return {"error": "plan needs 2-8 short plain steps."}
            self.plan = [str(n + 1) for n in range(len(steps))]
            self.plan_names = dict(zip(self.plan, steps))
            self.module_now, self.plan_ok = "", False
            go = "Go. Put \"module\":\"1\" (the number of the step you are on) in every action from now on."
            if self.is_lane:
                self.plan_ok = True
                return {"answer": go}
            self.question = {"kind": "plan", "text": "Here is the plan. Go?", "choices": ["▶ Go", "✏️ Change it"], "plan": steps}
            ans = self._wait()
            if re.sub(r"[^a-z]", "", ans.lower()).startswith("go"):
                self.plan_ok = True
                return {"answer": go}
            self.plan, self.plan_names = [], {}
            return {"answer": ans, "note": "Scott wants the plan changed — send a new plan that fits what he said."}
        if kind in CHANGE_ACTIONS and self.ask_first and not (self.asked or self.plan_ok or self.gate_nudged):
            self.gate_nudged = True                          # once only: a small exact change goes through on the retry
            return {"error": GATE_NUDGE}
        if kind == "list":
            return {"files": [f["path"] for f in preview.list_root(self.root)]}
        if kind == "read":
            p = self._inside(str(a.get("path") or ""))
            if not p or not p.is_file():
                return {"error": "No such file inside the project."}
            return read_range(p.read_text(errors="replace"), a.get("start"), a.get("lines"))
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
            self._change = (rel, p.read_text(errors="replace") if p.is_file() else None, content)
            tmp = p.with_name(f".{p.name}.agent")
            tmp.write_text(content)
            tmp.replace(p)
            return {"wrote": rel, "bytes": len(content.encode())}
        if kind == "edit":
            p = self._inside(str(a.get("path") or ""))
            find, rep = str(a.get("find") or ""), str(a.get("replace") or "")
            if not p or not p.is_file():
                return {"error": "No such file inside the project."}
            text = p.read_text(errors="replace")
            n = text.count(find) if find else 0
            if n != 1:
                return {"error": f"\"find\" must match exactly once; it matched {n} times. Read the file and copy the exact text."}
            before, text = text, text.replace(find, rep)
            if len(text.encode()) > preview.MAX_EDIT:
                return {"error": "File too big."}
            self._change = (str(a.get("path")), before, text)
            tmp = p.with_name(f".{p.name}.agent")
            tmp.write_text(text)
            tmp.replace(p)
            return {"edited": str(a.get("path")), "bytes": len(text.encode())}
        if kind == "repo":
            return self._repo(a)
        if kind == "run":
            return run_in_sandbox(self.root, str(a.get("cmd") or "true")[:2000])
        if kind == "hermes":
            if not self.connected:
                return {"error": "Hermes tools need connected mode (🔌). This Lab is standalone."}
            tool = str(a.get("tool") or "")
            if tool not in AGENT_TOOLS:
                return {"error": f"{tool!r} isn't on the agent's Hermes list: {', '.join(AGENT_TOOLS)}"}
            args = a.get("args") if isinstance(a.get("args"), dict) else {}
            try:
                if tool == "pidima_propose":                  # file NAMES in, file text read from the project folder
                    names = args.get("files") if isinstance(args.get("files"), list) else []
                    paths = {str(n): self._inside(str(n)) for n in names}
                    missing = [n for n, p in paths.items() if not p or not p.is_file()]
                    if not names or missing:
                        return {"error": "files must be a list of file names in this project" + (f"; not found: {missing}" if missing else "")}
                    args = {"files": {n: p.read_text(errors="replace") for n, p in paths.items()}, "note": str(args.get("note") or "")}
                res = self.lab.mcp.call(tool, args)
                if tool == "pidima_source" and isinstance(res.get("files"), dict):    # text goes to disk, not through the model
                    wrote = []
                    for n, text in res["files"].items():
                        p = self._inside(str(n))
                        if p and isinstance(text, str) and len(text.encode()) <= preview.MAX_EDIT:
                            p.write_text(text)
                            wrote.append(n)
                    res = {**{k: v for k, v in res.items() if k != "files"}, "wrote": wrote}
                return res
            except HermesRefused as e:
                return {"error": f"Hermes refused ({e.code}): {e.message}"}
        if kind == "done":
            return {"done": True}
        return {"error": f"Unknown action {kind!r}."}

    def _start_msgs(self) -> list[dict]:
        linked = sorted(repos.linked(self.cfg))
        mem = ""
        if (self.cfg.get("flags") or {}).get("memory"):          # 🧠 M2 — what the Lab knows about Scott
            try:
                if not self.is_lane:
                    if not self.plan:                             # a build prompt's own rules are not Scott's words
                        self.memory_saved = memory.learn(self.task, "an agent task")
                mem, self.memory_used = memory.for_context(" ".join([self.project.get("name", "")] + linked), self.task)
            except Exception:                                     # noqa: BLE001 — memory is a help, never a blocker
                mem = ""
        return [{"role": "system", "content": SYSTEM + (ASK_FIRST if self.ask_first else "") + (HERMES_GUIDE if self.connected else "")
                 + (REPO_GUIDE.format(names=", ".join(linked)) if linked else "")
                 + (("\n\n" + mem + "\nUse it to match how Scott likes things; the task still wins.") if mem else "")},
                {"role": "user", "content": f"Task: {self.task}\nFiles: "
                 + ", ".join(f["path"] for f in preview.list_root(self.root))}]

    def _finish(self, words: str) -> bool:
        """Checks passed → the robot plays the page → ✅ done. False = robot red and the model gets one more go."""
        rb = self._selftest()
        if rb and rb.get("level") == "red":
            if self.robot_tries < 2 and len(self.steps) - self.bad < self.step_cap:
                return False
            self.state = "unproven"
            self.why = ("🔴 The code checks passed, but the robot opened the page and it did not work: " + self._robot_words())[:600]
            return True
        if rb and rb.get("skipped"):                       # 2026-11-24 Android Tetris: a bracket count is not "it runs"
            self.state = "unproven"
            self.why = ("⚠️ Built, not run — nothing here could start it, so this is not a ✅. " + words)[:1800]
            return True
        self.state = "done"
        self.why = words
        if rb and rb.get("level") == "yellow":
            self.why = (self.why + " · 🟡 " + self._robot_words())[:700]
        return True

    def _ask(self, msgs: list[dict], left: float):
        """One model reply. After a cut-off: one try with room for a long reply; if that can't run, the normal size."""
        base = int(self.cfg.get("agent_max_tokens", 4096))
        big = int(self.cfg.get("agent_long_max_tokens", 16384) or 0)
        task = f"lab-agent:{self.project['id']}"
        if self.long_next and big > base:
            self.long_next = False
            try:
                r = self.lab.chat(self.project, self.provider, self.model, msgs, big, cap_usd=left, task=task)
                self.long_used += 1
                return r
            except (HermesRefused, HttpError, SpendBlocked):              # model can't do that size, or $ est too high
                pass
        return self.lab.chat(self.project, self.provider, self.model, msgs, base, cap_usd=left, task=task)

    def loop(self) -> None:
        if self.msgs is None:
            self.msgs = self._start_msgs()
        msgs = self.msgs
        try:
            while True:
                self._check_stop()
                if len(self.steps) - self.bad >= self.step_cap:
                    # the Tetris run: every check had passed, the limit hit one step before it could say "done"
                    if self.changed and self.proof_ok() and self._finish(
                            "✅ Finished — its checks passed. (The step limit ended the run before it could say so.)"):
                        return
                    self.state, self.why, self.cap_kind = "capped", f"🔢 Step limit reached ({self.step_cap}).", "steps"
                    return
                left = self.cap_usd - self.usd
                if left <= 0:
                    self.state, self.why = "capped", f"💲 Run cap reached (${self.cap_usd:.2f})."
                    return
                r = self._ask(msgs, left)
                self.usd += float(r.usd or 0)
                self.tokens_in += int(r.tokens_in or 0)
                self.tokens_out += int(r.tokens_out or 0)
                self._check_stop()                                    # Stop pressed while the model thought
                msgs.append({"role": "assistant", "content": r.text})
                try:
                    a = parse_action(r.text)
                except ValueError as e:
                    cut = "no JSON object" not in str(e) and "no \"action\"" not in str(e)
                    self.long_next = cut
                    res = {"error": f"Reply was not one JSON action ({e}).", "tip": CUT_TIP if cut else JSON_TIP, "cut": cut}
                    self.bad += 1
                    self.bad_row += 1
                    self._record({"action": "bad_reply", "why": "", "result": res, "usd": r.usd})
                    msgs.append({"role": "user", "content": "RESULT: " + json.dumps(res)})
                    if self.bad_row >= BAD_ROW_MAX:
                        self.state = "failed"
                        self.why = (f"⚠️ This model sent {BAD_ROW_MAX} replies in a row the Lab can't read"
                                    + (" (too long, cut off)" if cut else "") + ". Try another model.")
                        return
                    continue
                self.bad_row = 0
                self.long_next = False
                res = self.act(a)
                shown = {k: (v if k not in ("find", "replace") else str(v)[:300]) for k, v in a.items() if k != "content"}
                if "content" in a:
                    shown["bytes"] = len(str(a["content"]).encode())
                step = {**shown, "result": res, "usd": r.usd}
                ch, self._change = self._change, None
                if ch:                                                # shown to Scott as a diff; ↩ Undo puts `before` back
                    step["diff"] = make_diff(ch[0], ch[1], ch[2])
                    self.undo[len(self.steps) + 1] = ch
                self._record(step)
                if res.get("done"):
                    summary = str(a.get("summary") or "")[:1500]   # 2026-11-24: was cut mid-sentence at 500
                    if self.proof_ok():
                        if self._finish((summary or "✅ Done") if self.changed else ("ℹ️ No files changed. " + summary)[:600]):
                            return
                        res = {"error": "Not accepted: the robot opened the page and it did not work — " + self._robot_words()
                                        + " Fix it, run a check, then say done."}
                        step["result"] = res
                        msgs.append({"role": "user", "content": "RESULT: " + json.dumps(res, default=str)})
                        continue
                    self.refused_done += 1
                    if self.refused_done >= 2:                       # asked twice without a passing check: say so, never ✅
                        self.state = "unproven"
                        self.why = ("⚠️ The model says it finished, but no check passed after its last change. "
                                    "Look before you keep it. Its words: " + summary)[:600]
                        return
                    res = {"error": "Not accepted: no check passed after your last change (step "
                                    f"{self.changed}). Run a check that exits 0 (node --check, python3 -m py_compile, "
                                    "a grep, the test bot), fix what fails, then say done."}
                    step["result"] = res                             # the step card shows the refusal, not "done"
                left_steps = self.step_cap - (len(self.steps) - self.bad)
                msgs.append({"role": "user", "content": "RESULT: " + json.dumps(res, default=str)[:MAX_OUT + 500]
                             + (f"\nNOTE: {left_steps} steps left — run your check now, then say done." if left_steps == 2 else "")})
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
            store.autosave(self.project["id"], self.autosave_field, json.dumps(self.view())[:100_000])


class Agents:
    def __init__(self):
        self.runs: dict[str, Run] = {}
        self.lock = threading.Lock()

    def start(self, lab, cfg, project, provider, model, task, step_cap: int | None = None, ask_first: bool = False,
              selftest=None) -> Run:
        if not task.strip():
            raise ValueError("Tell the agent what to do.")
        with self.lock:
            if any(r.state == "running" and r.project["id"] == project["id"] for r in self.runs.values()):
                raise ValueError("An agent is already working on this project. Stop it first.")
            run = Run(lab, cfg, project, provider, model, task, step_cap=step_cap, ask_first=ask_first, selftest=selftest)
            self.runs[run.id] = run
        threading.Thread(target=run.loop, daemon=True, name=f"agent-{run.id}").start()
        return run

    def more(self, rid: str, n: int | None = None) -> Run:
        """▶ Continue a run that hit its step limit."""
        r = self.get(rid)
        with self.lock:
            if any(x.state == "running" and x.project["id"] == r.project["id"] for x in self.runs.values()):
                raise ValueError("An agent is already working on this project. Stop it first.")
            r.more(n)
        threading.Thread(target=r.loop, daemon=True, name=f"agent-{r.id}").start()
        return r

    def answer(self, rid: str, text: str) -> Run:
        r = self.get(rid)
        r.answer(text)
        return r

    def get(self, rid: str) -> Run:
        r = self.runs.get(rid)
        if not r:
            raise KeyError("No such run.")
        return r

    def stop_all(self) -> None:
        for r in self.runs.values():
            r.stop("⏹ Lab shutting down")
