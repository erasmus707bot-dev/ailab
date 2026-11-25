"""🎥 Capture runs (Lab capture C2, 2026-11-25): one sentence → shot plan → ▶ Start → Hermes capture tools →
👁 Eyes → captures/ in the project; a miss retries once; desktop steps ask first; refusals say what to do."""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from ailab import agent, capturerun, config, creation
from tests.test_agent import Base, Brain
from tests.test_workflow import wait_for

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 600
PLAN = json.dumps({"steps": [
    {"target": "browser", "viewport": "phone", "url": "http://127.0.0.1:8850/preview/x/", "do": [{"click": "text=Family"}],
     "shot": True, "expect": "the Family view", "label": "Family view"},
    {"target": "argus", "url": "http://127.0.0.1:8850/preview/x/", "shot": True, "expect": "the calendar", "label": "Calendar"},
    {"target": "vm", "shot": True, "label": "VM"},
    {"target": "browser", "url": "https://evil.example/", "record": 10, "expect": "the app", "label": "Clip"}]})


class CapMCP:
    """Hermes C1 + vision_check, scripted. yes = the vision answers, in order (last repeats)."""

    def __init__(self, tmp: Path, yes=(True,), refuse=None):
        self.tmp, self.yes, self.refuse, self.calls, self.args, self.n = tmp, list(yes), refuse or {}, [], [], 0

    def call(self, tool, args=None):
        from ailab.mcp_client import HermesRefused
        self.calls.append(tool); self.args.append(args or {})
        if tool in ("capture_shot", "capture_clip_start"):
            t = (args or {}).get("target")
            if t in self.refuse:
                raise HermesRefused(*self.refuse[t])
            self.n += 1
            ext = ".mp4" if tool == "capture_clip_start" else ".png"
            p = self.tmp / f"cap{self.n}{ext}"
            p.write_bytes(PNG if ext == ".png" else b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2000)
            th = self.tmp / f"cap{self.n}.thumb.jpg"; th.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
            self.last = {"path": str(p), "thumb": str(th), "w": 393, "h": 851, "target": t, "library": "pictures: x"}
            return {"ok": True, "key": f"cap:{self.n}", "state": "running", "est_usd": 0.0}
        if tool == "vision_check":
            return {"ok": True, "key": "vis:1", "model": "qwen3.5:4b"}
        if tool == "job_wait":
            k = (args or {}).get("key", "")
            if k.startswith("cap:"):
                return {"ok": True, "state": "done", "finished": True, "result": self.last}
            if k.startswith("vis:"):
                pts = self.args[[i for i, c in enumerate(self.calls) if c == "vision_check"][-1]].get("points") or []
                y = (self.yes.pop(0) if len(self.yes) > 1 else self.yes[0]) if any(q.startswith("Does") for q in pts) else True
                ans = [{"n": i + 1, "q": q, "yes": y if q.startswith("Does") else False} for i, q in enumerate(pts)]
                return {"ok": True, "state": "done", "finished": True, "result": {"answers": ans, "caption": "an app screen"}}
        if tool == "shifts_stopped":
            return {"ok": True, "stopped": False}
        return {"ok": True}


class Modes(Base):
    def test_capture_wins_and_is_an_art_run(self):
        self.assertTrue(creation.capture_mode(["capture", "video"]))
        self.assertIn("capture", creation.guess("take three phone screenshots of Epochron"))
        self.assertTrue(agent.art_request("x", ["capture"], None))

    def test_norm_keeps_tools_happy(self):
        known = {"this project (preview)": "http://127.0.0.1:8850/preview/x/"}
        s = capturerun.norm(json.loads(PLAN)["steps"] + [{"target": "tv"}] * 3, known)
        self.assertEqual([x["target"] for x in s], ["browser", "argus", "vm", "browser"])
        self.assertEqual(s[3]["url"], known["this project (preview)"])      # never a remote host
        self.assertEqual(s[3]["record"], 10)
        self.assertNotIn("url", s[2])


class Run(Base):
    def make(self, mcp, replies=(PLAN,), task="phone walk-through of Epochron's Family view"):
        b = Brain(list(replies))
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", task, ctypes=["capture"])
        return r, b

    def go(self, r):
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        self.assertEqual(r.question["kind"], "plan")
        self.assertEqual(r.question["title"], "🎥 Shot plan")
        self.assertEqual(len(r.question["plan"]), 4)
        r.answer("Go")
        return t

    def test_plan_start_capture_eyes_keep(self):
        tmp = Path(tempfile.mkdtemp())
        mcp = CapMCP(tmp)
        r, _ = self.make(mcp)
        t = self.go(r)
        t.join(10)
        self.assertEqual(r.state, "done", r.why)
        v = r.view()
        self.assertEqual(len(v["pictures"]), 3)
        self.assertEqual(len(v["videos"]), 1)
        for p in v["pictures"]:
            self.assertTrue(p["path"].startswith("captures/") and (r.root / p["path"]).is_file())
        self.assertTrue((r.root / v["videos"][0]["poster"]).is_file())
        shot_args = [a for c, a in zip(mcp.calls, mcp.args) if c.startswith("capture_")]
        self.assertEqual(shot_args[0]["project"], self.project["id"])
        self.assertEqual(shot_args[3]["seconds"], 10)
        self.assertEqual(mcp.calls.count("vision_check"), 4)
        self.assertIn("3 shots + 1 clip", r.why)

    def test_miss_retries_once_with_longer_wait(self):
        tmp = Path(tempfile.mkdtemp())
        one = json.dumps({"steps": [json.loads(PLAN)["steps"][0]]})
        mcp = CapMCP(tmp, yes=(False, True))
        r, _ = self.make(mcp, replies=(one,))
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        r.answer("Go"); t.join(10)
        self.assertEqual(r.state, "done", r.why)
        caps = [a for c, a in zip(mcp.calls, mcp.args) if c == "capture_shot"]
        self.assertEqual(len(caps), 2)
        self.assertEqual(caps[1]["steps"][0], {"scroll": -5000, "wait": 0.5})
        self.assertEqual(len(r.view()["pictures"]), 1)

    def test_desktop_step_asks_first_and_skip_is_star(self):
        tmp = Path(tempfile.mkdtemp())
        plan = json.dumps({"steps": [{"target": "desktop", "window_id": "0x1", "record": 10, "label": "Lynceus window"},
                                     {"target": "vm", "shot": True, "label": "VM"}]})
        mcp = CapMCP(tmp)
        r, _ = self.make(mcp, replies=(plan,))
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None and r.question["kind"] == "plan"))
        r.answer("Go")
        self.assertTrue(wait_for(lambda: r.question is not None and r.question["kind"] == "ask"))
        q = r.question["items"][0]
        self.assertIn("✋", q["q"]); self.assertIn("10 s clip", q["q"]); self.assertIn("sound off", q["q"])
        self.assertEqual(q["choices"][q["best"]], "Skip the desktop steps")
        r.answer(q["choices"][q["best"]]); t.join(10)
        self.assertEqual(r.state, "done", r.why)
        self.assertNotIn("desktop", [a.get("target") for a in mcp.args])

    def test_refusal_says_what_to_do_and_run_goes_on(self):
        tmp = Path(tempfile.mkdtemp())
        mcp = CapMCP(tmp, refuse={"argus": ("not_enabled", "The Argus test phone isn't running.", "Start it in Hermes ▸ Argus.")})
        r, _ = self.make(mcp)
        t = self.go(r); t.join(10)
        self.assertEqual(r.state, "done", r.why)
        self.assertIn("1 step didn't make it", r.why)
        why = [s.get("result", {}).get("error", "") for s in r.steps if s.get("action") == "capture"]
        self.assertTrue(any("Start it in Hermes" in w for w in why))

    def test_change_rewrites_the_plan(self):
        tmp = Path(tempfile.mkdtemp())
        two = json.dumps({"steps": [{"target": "vm", "shot": True, "label": "VM only"}]})
        mcp = CapMCP(tmp)
        r, b = self.make(mcp, replies=(PLAN, two))
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        r.answer("just the VM please")
        self.assertTrue(wait_for(lambda: r.question is not None and len(r.question["plan"]) == 1))
        r.answer("Go"); t.join(10)
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual([a["target"] for c, a in zip(mcp.calls, mcp.args) if c == "capture_shot"], ["vm"])
