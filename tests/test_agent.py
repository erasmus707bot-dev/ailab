"""M5 acceptance — agent loop behind the `agent` flag: sandbox runs, caps, Stop, STOP_SHIFTS, approvals, MCP jobs."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from ailab import agent, config, preview, server, store
from ailab.mcp_client import HermesRefused
from ailab.providers.base import ChatResult
from ailab.spend import SpendBlocked
from tests.test_server import Srv

HAS_SRT = bool(shutil.which("srt"))


def act(**kw) -> str:
    return json.dumps(kw)


class Brain:
    """Scripted model: returns the replies in order (last one repeats)."""

    def __init__(self, replies, usd=0.001, gate=None):
        self.replies, self.usd, self.gate, self.calls = list(replies), usd, gate, []

    def chat(self, project, prov, model, msgs, max_tokens=1024, cap_usd=None, task=""):
        self.calls.append(msgs[-1]["content"])
        if self.gate:
            self.gate.wait(5)
        if cap_usd is not None and self.usd > cap_usd:
            raise SpendBlocked(f"Estimated ${self.usd:.4f} is over this run's cap of ${cap_usd:.2f}.")
        text = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return ChatResult(text, prov, model, 10, 5, self.usd, True)


class FakeMCP:
    def __init__(self, stopped=False, refuse_stop=False):
        self.stopped, self.refuse_stop, self.calls = stopped, refuse_stop, []

    def call(self, tool, args=None):
        self.calls.append(tool)
        if tool == "shifts_stopped":
            if self.refuse_stop:
                raise HermesRefused("not_allowed", "not on allowlist")
            return {"ok": True, "stopped": self.stopped, "why": "shifts stopped (STOP_SHIFTS)" if self.stopped else ""}
        if tool == "addon_build":
            return {"ok": True, "key": "addon:j1", "state": "queued"}
        if tool == "job_wait":
            return {"ok": True, "key": args["key"], "state": "done", "finished": True, "output": "dist/hello.zip"}
        return {"ok": True}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AILAB_HOME"] = self.tmp.name
        if not HAS_SRT:
            os.environ["AILAB_ALLOW_UNSANDBOXED"] = "1"
        self.project = store.project("scratch")

    def tearDown(self):
        os.environ.pop("AILAB_HOME", None)
        os.environ.pop("AILAB_ALLOW_UNSANDBOXED", None)
        self.tmp.cleanup()

    def run_agent(self, brain, mode="standalone", mcp=None, task="do it", **cfg):
        brain.mcp = mcp
        c = config.load({"mode": mode, **cfg})
        r = agent.Run(brain, c, self.project, "openrouter", "m", task)
        r.loop()
        return r


class Loop(Base):
    @unittest.skipUnless(HAS_SRT, "srt not installed — acceptance owed on gandalf")
    def test_acceptance_fixture_task_completes_in_srt(self):
        site = preview.ensure_site("scratch")
        html = (site / "index.html").read_text().replace("</main>", '<footer id="lab-footer">Made in the Lab</footer>\n</main>')
        r = self.run_agent(Brain([
            act(action="read", path="index.html", why="see the page"),
            act(action="write", path="index.html", content=html, why="add footer"),
            act(action="run", cmd="grep -c lab-footer index.html", why="check"),
            act(action="done", summary="Footer added; grep found it once.")]))
        self.assertEqual(r.state, "done", r.why)
        run = next(s for s in r.steps if s["action"] == "run")
        self.assertEqual((run["result"]["exit"], run["result"]["output"].strip()), (0, "1"))
        self.assertIn("lab-footer", (site / "index.html").read_text())
        self.assertTrue(r.log.exists())

    @unittest.skipUnless(HAS_SRT, "srt not installed")
    def test_sandboxed_run_cannot_escape(self):
        site = preview.ensure_site("scratch").resolve()
        target = Path.home() / f".ailab-escape-{os.getpid()}"
        res = agent.run_in_sandbox(site, f"echo x > {target}; echo y > {site}/ok.txt; "
                                         "python3 -c \"import urllib.request as u; u.urlopen('https://example.com', timeout=5)\" "
                                         "&& echo NET || echo NONET")
        self.assertFalse(target.exists())
        self.assertTrue((site / "ok.txt").exists())                            # inside the folder is fine
        self.assertIn("NONET", res["output"])

    def test_write_outside_project_is_held_for_approval(self):
        r = self.run_agent(Brain([
            act(action="write", path="../outside.html", content="nope"),
            act(action="write", path="/etc/agent.txt", content="nope"),
            act(action="done", summary="tried")]))
        self.assertEqual(r.state, "done")
        self.assertTrue(all(s["result"].get("held") for s in r.steps[:2]))
        self.assertFalse((Path(self.tmp.name) / "projects/scratch/outside.html").exists())
        items = agent.approvals()
        self.assertEqual([i["path"] for i in items], ["../outside.html", "/etc/agent.txt"])
        self.assertTrue(all(i["state"] == "waiting" and i["kind"] == "write_outside_project" for i in items))

    def test_step_cap(self):
        r = self.run_agent(Brain([act(action="list")]), agent_step_cap=3)
        self.assertEqual((r.state, len(r.steps)), ("capped", 3))

    def test_run_dollar_cap(self):
        r = self.run_agent(Brain([act(action="list")], usd=0.2), agent_cap_usd=0.5)
        self.assertEqual(r.state, "capped")
        self.assertLessEqual(r.usd, 0.5)
        self.assertEqual(len(r.steps), 2)

    def test_bad_reply_is_logged_and_loop_continues(self):
        r = self.run_agent(Brain(["sure, I'll do that!", act(action="done", summary="ok")]))
        self.assertEqual([s["action"] for s in r.steps], ["bad_reply", "done"])
        self.assertEqual(r.state, "done")

    def test_hermes_tools_need_connected_and_allowlist(self):
        r = self.run_agent(Brain([act(action="hermes", tool="addon_build"), act(action="done", summary="x")]))
        self.assertIn("connected mode", r.steps[0]["result"]["error"])
        r = self.run_agent(Brain([act(action="hermes", tool="job_cancel", args={"key": "k"}),
                                  act(action="done", summary="x")]), mode="connected", mcp=FakeMCP())
        self.assertIn("isn't on the agent's Hermes list", r.steps[0]["result"]["error"])

    def test_stop_button(self):
        gate = threading.Event()
        brain = Brain([act(action="list")], gate=gate)
        brain.mcp = None
        r = agent.Run(brain, config.load(), self.project, "openrouter", "m", "loop")
        t = threading.Thread(target=r.loop)
        t.start()
        time.sleep(0.2)
        r.stop()
        gate.set()
        t.join(5)
        self.assertEqual(r.state, "stopped")
        self.assertIn("Stopped by you", r.why)
        self.assertLessEqual(len(r.steps), 1)


class Connected(Base):
    def test_connected_run_starts_studio_job_and_collects_output(self):
        mcp = FakeMCP()
        r = self.run_agent(Brain([
            act(action="hermes", tool="addon_build", args={"template": "hello"}),
            act(action="hermes", tool="job_wait", args={"key": "addon:j1", "max_s": 45}),
            act(action="done", summary="built")]), mode="connected", mcp=mcp)
        self.assertEqual(r.state, "done")
        self.assertEqual(r.steps[0]["result"]["key"], "addon:j1")
        self.assertEqual(r.steps[1]["result"]["output"], "dist/hello.zip")
        self.assertEqual(mcp.calls.count("shifts_stopped"), 6)                  # before + after every model call
        self.assertIn("addon_build", mcp.calls)

    def test_stop_shifts_stops_before_any_model_call(self):
        brain = Brain([act(action="list")])
        r = self.run_agent(brain, mode="connected", mcp=FakeMCP(stopped=True))
        self.assertEqual(r.state, "stopped")
        self.assertIn("STOP_SHIFTS", r.why)
        self.assertEqual(brain.calls, [])

    def test_kill_switch_unreadable_means_stop(self):
        brain = Brain([act(action="list")])
        r = self.run_agent(brain, mode="connected", mcp=FakeMCP(refuse_stop=True))
        self.assertEqual(r.state, "stopped")
        self.assertEqual(brain.calls, [])


class AgentOff(Srv):
    flags = {"router": False}

    def test_all_agent_routes_403(self):
        for path, body in (("/api/agent/start", {"project": "scratch", "task": "x"}), ("/api/agent/stop", {"id": "x"}),
                           ("/api/agent/run?id=x", None), ("/api/agent/approvals", None)):
            code, r, _ = self.req(path, body)
            self.assertEqual((code, r["code"], r["flag"]), (403, "not_switched_on", "agent"), path)


class AgentOn(Srv):
    flags = {"agent": True}

    def setUp(self):
        super().setUp()
        self.lab.chat = Brain([act(action="list"), act(action="done", summary="looked")]).chat
        self.lab.mcp = None

    def test_start_poll_done_and_one_run_per_project(self):
        code, r, _ = self.req("/api/agent/start", {"project": "scratch", "provider": "ollama", "model": "m", "task": "look"})
        self.assertEqual(code, 200, r)
        rid = r["run"]["id"]
        for _ in range(50):
            v = self.req(f"/api/agent/run?id={rid}")[1]["run"]
            if v["state"] != "running":
                break
            time.sleep(0.05)
        self.assertEqual(v["state"], "done")
        self.assertEqual([s["action"] for s in v["steps"]], ["list", "done"])
        code, r, _ = self.req("/api/agent/start", {"project": "scratch", "task": ""})
        self.assertEqual(r["code"], "bad_args")



class MemoryInRun(Base):
    """🧠 M2 (2026-11-24): with the memory flag on, the agent gets Scott's memory and saves what he states."""
    def test_memory_flows_into_system_prompt(self):
        from ailab import memory
        memory.add_fact("claude-preferences", "numbered menus with a recommendation", "scott")
        seen = []
        b = Brain([act(action="done", summary="nothing to do")])
        orig = b.chat
        b.chat = lambda project, prov, model, msgs, *a, **k: (seen.append(msgs[0]["content"]), orig(project, prov, model, msgs, *a, **k))[1]
        r = self.run_agent(b, task="I prefer dark mode by default. Look at the page.",
                           flags={**config.DEFAULTS["flags"], "memory": True})
        self.assertIn("numbered menus", seen[0])
        self.assertIn("claude-preferences", r.view()["memory_used"])
        self.assertTrue(r.view()["memory_saved"])

    def test_memory_off_means_nothing_added(self):
        seen = []
        b = Brain([act(action="done", summary="x")])
        orig = b.chat
        b.chat = lambda project, prov, model, msgs, *a, **k: (seen.append(msgs[0]["content"]), orig(project, prov, model, msgs, *a, **k))[1]
        r = self.run_agent(b, task="I prefer dark mode.")
        self.assertNotIn("Lab memory", seen[0])
        self.assertEqual(r.view()["memory_saved"], [])


class AskAndPlan(Base):
    """M5 (2026-11-24): the agent can ask Scott a question on screen; the run shows done / doing / left."""
    def test_ask_waits_for_answer_and_plan_tracks_modules(self):
        import threading as th
        b = Brain([act(action="list", module="M0", why="look"),
                   act(action="ask", question="Green or blue?", choices=["green", "blue"], module="M1", why="his call"),
                   act(action="done", summary="asked")])
        c = config.load({"mode": "standalone"})
        r = agent.Run(b, c, self.project, "openrouter", "m", "Build it\n## Module 0 — Audit\n## Module 1 — Do\n## Module 2 — Prove")
        t = th.Thread(target=r.loop); t.start()
        for _ in range(100):
            if r.question:
                break
            __import__("time").sleep(0.05)
        self.assertEqual(r.view()["question"]["choices"], ["green", "blue"])
        self.assertEqual([p["state"] for p in r.view()["plan"]], ["done", "doing", "left"])
        r.answer("green")
        t.join(5)
        self.assertEqual(r.state, "done")
        self.assertIsNone(r.view()["question"])
        self.assertIn("green", b.calls[-1])
        with self.assertRaises(ValueError):
            r.answer("late")

    def test_stop_while_asking(self):
        import threading as th
        b = Brain([act(action="ask", question="?", why="x")])
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t")
        t = th.Thread(target=r.loop); t.start()
        for _ in range(100):
            if r.question:
                break
            __import__("time").sleep(0.05)
        r.stop()
        t.join(5)
        self.assertEqual(r.state, "stopped")

if __name__ == "__main__":
    unittest.main()


class GoalTools(Base):
    """2026-11-22: Mario level + Linux app tools are on the agent's list and explained only in connected mode."""

    def test_goal_tools_on_list_and_guide_only_when_connected(self):
        for t in ("mario_level_spec", "mario_level_check", "mario_level_make", "linux_app_describe",
                  "linux_app_change", "linux_app_build", "linux_app_package", "linux_app_get"):
            self.assertIn(t, agent.AGENT_TOOLS)
        seen = {}

        class Spy(Brain):
            def chat(self, project, prov, model, msgs, *a, **k):
                seen["system"] = msgs[0]["content"]
                return super().chat(project, prov, model, msgs, *a, **k)

        mcp = FakeMCP()
        r = self.run_agent(Spy([act(action="hermes", tool="mario_level_make", args={"name": "x", "seed": 1}),
                                act(action="done", summary="made")]), mode="connected", mcp=mcp)
        self.assertEqual(r.state, "done")
        self.assertIn("mario_level_make", mcp.calls)
        self.assertIn("linux_app_build", seen["system"])
        self.run_agent(Spy([act(action="done", summary="x")]))
        self.assertNotIn("linux_app_build", seen["system"])


class GameCode(Base):
    """2026-11-22: edit one spot in a big file; pull the game source in and push a proposal out without the text
    passing through the model."""

    def test_edit_needs_exactly_one_match(self):
        root = preview.ensure_site("scratch")
        (root / "big.js").write_text("const a = 1;\nconst b = 1;\n")
        r = self.run_agent(Brain([act(action="edit", path="big.js", find="= 1;", replace="= 2;"),
                                  act(action="edit", path="big.js", find="const a = 1;", replace="const a = 5;"),
                                  act(action="edit", path="../x", find="a", replace="b"),
                                  act(action="done", summary="ok")]))
        self.assertIn("matched 2 times", r.steps[0]["result"]["error"])
        self.assertEqual(r.steps[1]["result"]["edited"], "big.js")
        self.assertIn("error", r.steps[2]["result"])
        self.assertEqual((root / "big.js").read_text(), "const a = 5;\nconst b = 1;\n")

    def test_big_file_read_says_it_was_cut_and_ranges_work(self):
        root = preview.ensure_site("scratch")
        (root / "big.html").write_text("".join(f"<p>line {i} {'x' * 60}</p>\n" for i in range(1, 1001)))
        r = self.run_agent(Brain([act(action="read", path="big.html"),
                                  act(action="read", path="big.html", start=900, lines=3),
                                  act(action="done", summary="ok")]))
        first, part = r.steps[0]["result"], r.steps[1]["result"]
        self.assertTrue(first["truncated"])
        self.assertEqual(first["total_lines"], 1000)
        self.assertIn("start", first["tip"])
        self.assertEqual(part["text"].splitlines()[0][:13], "<p>line 900 x")
        self.assertEqual((part["start"], part["end"]), (900, 902))
        self.assertFalse(part["truncated"])

    def test_small_file_read_unchanged_and_bad_range_is_an_error(self):
        self.assertEqual(agent.read_range("a\nb\n"), {"text": "a\nb\n"})
        self.assertIn("past the end", agent.read_range("a\n", start=9)["error"])
        self.assertIn("whole numbers", agent.read_range("a\n", start="x")["error"])

    def test_pidima_source_lands_on_disk_and_propose_reads_from_disk(self):
        class MCP(FakeMCP):
            def call(self, tool, args=None):
                self.calls.append(tool)
                if tool == "pidima_source":
                    return {"ok": True, "files": {"engine.js": "ENGINE", "../evil.js": "x", ".hidden": "x"}, "test": "node bot.js"}
                if tool == "pidima_propose":
                    self.sent = args
                    return {"ok": True, "id": "p1", "state": "waiting"}
                return super().call(tool, args)
        mcp = MCP()
        r = self.run_agent(Brain([act(action="hermes", tool="pidima_source", args={}),
                                  act(action="edit", path="engine.js", find="ENGINE", replace="ENGINE2"),
                                  act(action="hermes", tool="pidima_propose", args={"files": ["engine.js"], "note": "n"}),
                                  act(action="hermes", tool="pidima_propose", args={"files": ["nope.js"]}),
                                  act(action="done", summary="ok")]), mode="connected", mcp=mcp)
        self.assertEqual(r.steps[0]["result"]["wrote"], ["engine.js"])               # nothing outside / hidden is written
        self.assertNotIn("files", r.steps[0]["result"])                                # the text never reaches the model
        self.assertEqual(mcp.sent, {"files": {"engine.js": "ENGINE2"}, "note": "n"})
        self.assertIn("not found", r.steps[3]["result"]["error"])
        self.assertIn("pidima_source", agent.HERMES_GUIDE)


class WorkbenchChanges(unittest.TestCase):
    """2026-11-22 workbench: every agent write carries a diff; ↩ Undo puts the old text back."""

    def test_make_diff_marks_new_file_and_caps(self):
        from ailab import agent
        d = agent.make_diff("a.txt", None, "one\ntwo")
        self.assertIn("/dev/null", d)
        self.assertIn("+two", d)
        self.assertIn("-old", agent.make_diff("a.txt", "old", "new"))
        self.assertIn("diff cut", agent.make_diff("a.txt", "", "x\n" * 9000, cap=500))

    def test_undo_step_restores_only_untouched_files(self):
        import tempfile
        from pathlib import Path
        from ailab import agent
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "a.txt").write_text("after")
            (root / "new.txt").write_text("fresh")
            r = agent.Run.__new__(agent.Run)
            r.root, r.state = root, "done"
            r.steps = [{"n": 1}, {"n": 2}, {"n": 3}]
            r.undo = {1: ("a.txt", "before", "after"), 2: ("new.txt", None, "fresh"), 3: ("a.txt", "x", "something else")}
            with self.assertRaises(ValueError):
                r.undo_step(3)                                   # file no longer holds what step 3 wrote
            self.assertEqual(r.undo_step(1)["path"], "a.txt")
            self.assertEqual((root / "a.txt").read_text(), "before")
            self.assertTrue(r.steps[0]["undone"])
            self.assertTrue(r.undo_step(2)["new_file"])
            self.assertFalse((root / "new.txt").exists())
            self.assertEqual((root / ".new.txt.undone").read_text(), "fresh")   # kept, hidden — never deleted
            with self.assertRaises(ValueError):
                r.undo_step(1)                                   # already undone
            r.state = "running"
            with self.assertRaises(ValueError):
                r.undo_step(2)
