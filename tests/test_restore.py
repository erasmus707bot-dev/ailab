"""2026-11-24 Argus touch test finding 4: a Lab restart mid-run lost the run ("No such run" on ▶ Go)."""
from __future__ import annotations

import json
import threading

from ailab import agent, config
from tests.test_agent import Base, Brain, act
from tests.test_workflow import wait_for

DONE = act(action="done", summary="made it")


class Gated(Brain):
    """First reply at once; every later call waits for `go` (the Lab 'dies' while the model thinks)."""

    def __init__(self, replies, go):
        super().__init__(replies)
        self.go = go

    def chat(self, *a, **kw):
        if self.calls:
            self.go.wait(5)
        return super().chat(*a, **kw)


class Restart(Base):
    def cfg(self):
        return config.load({"mode": "standalone"})

    def start(self, brain):
        r = agent.Run(brain, self.cfg(), self.project, "openrouter", "m", "make a game")
        t = threading.Thread(target=r.loop, daemon=True)
        t.start()
        return r, t

    def kill(self, r, t, release=None):
        """What Agents.stop_all does at shutdown: the saved copy stays as it was."""
        r.shutting_down = True
        r.stop("⏹ Lab shutting down")
        if release:
            release.set()
        t.join(5)

    def back(self, r, brain):
        a = agent.Agents()
        self.assertEqual(a.restore(brain, self.cfg()), 1)
        return a, a.get(r.id)

    def test_plan_card_survives_a_restart_and_go_finishes(self):
        r, t = self.start(Brain([act(action="plan", steps=["Layout", "Rules"])]))
        self.assertTrue(wait_for(lambda: r.question))
        self.kill(r, t)
        a, n = self.back(r, Brain([act(action="list", module="2"), DONE]))
        v = n.view()
        self.assertEqual((v["state"], v["question"]["kind"], v["question"]["plan"], v["stuck"], v["restored"]),
                         ("running", "plan", ["Layout", "Rules"], False, True))
        a.answer(r.id, "▶ Go")
        self.assertTrue(wait_for(lambda: n.state != "running"))
        self.assertEqual(n.state, "done", n.why)
        self.assertTrue(n.plan_ok)
        self.assertEqual([s["action"] for s in n.steps], ["plan", "list", "done"])
        self.assertIn("Go", n.msgs[3]["content"])                  # sys, task, plan reply, RESULT(Go) …

    def test_mid_step_comes_back_paused_and_resume_carries_on(self):
        go = threading.Event()
        r, t = self.start(Gated([act(action="list"), act(action="list")], go))
        self.assertTrue(wait_for(lambda: len(r.steps) == 1))
        self.kill(r, t, release=go)
        b = Brain([DONE])
        a, n = self.back(r, b)
        v = n.view()
        self.assertEqual((v["state"], v["can_resume"], v["can_continue"]), ("interrupted", True, False))
        self.assertIn("Resume", v["why"])
        a.resume(r.id)
        self.assertTrue(wait_for(lambda: n.state != "running"))
        self.assertEqual(n.state, "done", n.why)
        self.assertEqual([s["action"] for s in n.steps], ["list", "done"])
        self.assertIn("RESULT", b.calls[0])                          # the model carries on from the saved talk
        with self.assertRaises(ValueError):
            a.resume(r.id)                                           # only once

    def test_half_done_action_is_told_not_replayed(self):
        r = agent.Run(Brain([DONE]), self.cfg(), self.project, "openrouter", "m", "x")
        r.msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "t"},
                  {"role": "assistant", "content": act(action="write", path="a.js", content="x")}]
        r.pending_action, r.state = {"action": "write", "path": "a.js"}, "interrupted"
        r.prepare_resume()
        self.assertIsNone(r._replay)
        self.assertIn("may or may not have happened", r.msgs[-1]["content"])

    def test_stop_on_a_restored_run_and_bad_files_are_skipped(self):
        r, t = self.start(Brain([act(action="ask", question="Colour?", choices=["a", "b"])]))
        self.assertTrue(wait_for(lambda: r.question))
        self.kill(r, t)
        bad = r.log.with_name("zzzzzzzzzz.state.json")
        bad.write_text("{not json")
        a, n = self.back(r, Brain([DONE]))                          # the broken file is skipped, not fatal
        n.stop()
        self.assertEqual((n.state, n.question), ("stopped", None))
        self.assertEqual(json.loads(n.state_file().read_text())["state"], "stopped")

    def test_compare_lanes_are_not_saved(self):
        lane = agent.Run(Brain([DONE]), self.cfg(), self.project, "openrouter", "m", "x",
                         root=self.project and agent.preview.ensure_site("scratch"), log_dir=agent.config.home() / "lanes")
        lane.loop()
        self.assertFalse(lane.state_file().exists())

    def test_done_run_restores_as_done(self):
        r, t = self.start(Brain([DONE]))
        t.join(5)
        a, n = self.back(r, Brain([DONE]))
        self.assertEqual((n.state, n.view()["can_resume"]), ("done", False))


from tests.test_server import Srv  # noqa: E402
from ailab import server  # noqa: E402


class RestartOverHttp(Srv):
    """The exact touch-test case: plan card up → Lab restarts → ▶ Go on the phone."""
    flags = {"agent": True}

    def test_go_after_a_restart_is_not_no_such_run(self):
        self.lab.chat = Brain([act(action="plan", steps=["A", "B"])]).chat
        self.lab.mcp = None
        rid = self.req("/api/agent/start", {"project": "scratch", "provider": "ollama", "model": "m", "task": "t"})[1]["run"]["id"]
        self.assertTrue(wait_for(lambda: self.req(f"/api/agent/run?id={rid}")[1]["run"]["question"]))
        self.app.agents.stop_all()                                   # Lab goes down
        self.srv.shutdown(); self.srv.server_close()
        self.lab.chat = Brain([act(action="list", module="2"), DONE]).chat
        self.app = server.App(config.load({"flags": self.flags}), lab=self.lab)   # Lab comes back, same home
        self.srv = server.make_server(self.app, port=0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        code, r, _ = self.req(f"/api/agent/run?id={rid}")
        self.assertEqual((code, r["run"]["question"]["kind"]), (200, "plan"))
        code, r, _ = self.req("/api/agent/answer", {"id": rid, "answer": "Go"})
        self.assertEqual(code, 200, r)
        self.assertTrue(wait_for(lambda: self.req(f"/api/agent/run?id={rid}")[1]["run"]["state"] != "running"))
        self.assertEqual(self.req(f"/api/agent/run?id={rid}")[1]["run"]["state"], "done")
        code, r, _ = self.req("/api/agent/resume", {"id": rid})
        self.assertNotEqual(code, 200)                               # a finished run can't be resumed


class NoRepeatPings(Restart):
    def test_restored_finished_runs_do_not_ping_again(self):
        from ailab import notify
        r, t = self.start(Brain([DONE]))
        t.join(5)
        a, _ = self.back(r, Brain([DONE]))
        sent = []
        w = notify.Watcher(a, {"phone_pings": True}, sender=lambda *x: sent.append(x))
        self.assertEqual((w.tick(), sent), ([], []))
