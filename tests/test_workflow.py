"""2026-11-24 workflow build (from the Tetris test run): no dead ends, question cards, plan gate, Before copy, robot play-test."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from ailab import agent, config, preview, robotcheck
from tests.test_agent import Base, Brain, act

W = act(action="write", path="index.html", content="<h1>new</h1>", why="w")
OK = act(action="run", cmd="true", why="check")
DONE = act(action="done", summary="made it")


def wait_for(fn, s=5.0):
    end = time.time() + s
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.02)
    return False


class NoDeadEnds(Base):
    def test_bad_replies_do_not_use_up_steps(self):
        r = self.run_agent(Brain(["hello!", act(action="list"), "oops", act(action="list")]), agent_step_cap=3)
        v = r.view()
        self.assertEqual((r.state, v["real_steps"], v["bad"], len(r.steps)), ("capped", 3, 2, 5))
        self.assertTrue(v["can_continue"])

    def test_three_unreadable_replies_in_a_row_stop_the_run(self):
        r = self.run_agent(Brain(["no json here"]))
        self.assertEqual((r.state, len(r.steps)), ("failed", 3))
        self.assertIn("another model", r.why)

    def test_cut_off_reply_gets_the_write_in_parts_tip(self):
        r = self.run_agent(Brain(['{"action":"write","path":"app.js","content":"let a = 1;', "plain words", DONE]))
        self.assertTrue(r.steps[0]["result"]["cut"])
        self.assertIn("marker", r.steps[0]["result"]["tip"])
        self.assertFalse(r.steps[1]["result"]["cut"])
        self.assertIn("marker", agent.SYSTEM)

    def test_limit_after_passing_checks_is_done_not_a_dead_end(self):
        """The Tetris run: wrote, checked, checks passed — the limit hit before it could say done."""
        r = self.run_agent(Brain([W, OK, OK]), agent_step_cap=2)
        self.assertEqual(r.state, "done", r.why)
        self.assertIn("checks passed", r.why)

    def test_limit_without_proof_stays_capped_and_continue_finishes(self):
        b = Brain([W, act(action="list"), OK, DONE])
        r = self.run_agent(b, agent_step_cap=2)
        self.assertEqual((r.state, r.view()["can_continue"]), ("capped", True))
        r.more(5)
        self.assertEqual((r.state, r.step_cap), ("running", 7))
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertIn("Continue", b.calls[-2] + b.calls[-1] + "".join(b.calls))

    def test_dollar_cap_cannot_be_continued(self):
        r = self.run_agent(Brain([act(action="list")], usd=0.2), agent_cap_usd=0.5)
        self.assertEqual((r.state, r.view()["can_continue"]), ("capped", False))
        with self.assertRaises(ValueError):
            r.more()

    def test_two_steps_left_note(self):
        b = Brain([act(action="list")])
        self.run_agent(b, agent_step_cap=4)
        self.assertTrue(any("2 steps left" in c for c in b.calls))


class Questions(Base):
    def start(self, brain, **kw):
        c = config.load({"mode": "standalone"})
        r = agent.Run(brain, c, self.project, "openrouter", "m", "make a game", **kw)
        t = threading.Thread(target=r.loop, daemon=True)
        t.start()
        return r, t

    def test_question_cards_carry_choices_and_the_recommended_pick(self):
        ask = act(action="ask", questions=[{"q": "Which look?", "choices": ["Classic", "Neon"], "best": 1, "why": "easier on the eyes"},
                                           {"q": "How fast?", "choices": ["Slow", "Fast"]},
                                           {"q": "x", "choices": ["a"], "best": 7}, {"q": "fourth is dropped"}])
        b = Brain([ask, DONE])
        r, t = self.start(b)
        self.assertTrue(wait_for(lambda: r.question))
        q = r.view()["question"]
        self.assertEqual((q["kind"], len(q["items"])), ("ask", 3))
        self.assertEqual((q["items"][0]["best"], q["items"][0]["why"]), (1, "easier on the eyes"))
        self.assertEqual((q["items"][1]["best"], q["items"][2]["best"]), (-1, -1))      # no pick given → no ⭐ invented
        r.answer("Which look? → Neon · How fast? → Slow")
        t.join(5)
        self.assertEqual(r.state, "done")
        self.assertIn("Neon", b.calls[-1])
        self.assertIsNone(r.question)

    def test_old_single_question_form_still_works(self):
        r, t = self.start(Brain([act(action="ask", question="Colour?", choices=["green", "blue"]), DONE]))
        self.assertTrue(wait_for(lambda: r.question))
        self.assertEqual((r.question["text"], r.question["choices"]), ("Colour?", ["green", "blue"]))
        r.answer("blue")
        t.join(5)
        self.assertEqual(r.state, "done")

    def test_plan_gate_go_and_progress_list(self):
        b = Brain([act(action="plan", steps=["Layout", "Rules", "Test it"]), act(action="list", module="2"), DONE])
        r, t = self.start(b)
        self.assertTrue(wait_for(lambda: r.question))
        self.assertEqual((r.question["kind"], r.question["plan"]), ("plan", ["Layout", "Rules", "Test it"]))
        self.assertFalse(r.plan_ok)
        r.answer("▶ Go")
        t.join(5)
        self.assertTrue(r.plan_ok)
        self.assertEqual(r.view()["plan"], [{"module": "Layout", "state": "done"}, {"module": "Rules", "state": "done"},
                                            {"module": "Test it", "state": "done"}])

    def test_plan_change_asks_for_a_new_plan(self):
        b = Brain([act(action="plan", steps=["A", "B"]), DONE])
        r, t = self.start(b)
        self.assertTrue(wait_for(lambda: r.question))
        r.answer("add a sound step")
        t.join(5)
        self.assertFalse(r.plan_ok)
        self.assertIn("new plan", b.calls[-1])
        self.assertEqual(r.plan, [])

    def test_ask_first_holds_the_first_write_once(self):
        r = agent.Run(Brain([W, W, OK, DONE]), config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t", ask_first=True)
        r.loop()
        self.assertIn("choose first", r.steps[0]["result"]["error"])
        self.assertEqual(r.steps[1]["result"].get("wrote"), "index.html")
        self.assertEqual(r.state, "done", r.why)
        self.assertIn("FIRST", r.msgs[0]["content"])

    def test_without_ask_first_nothing_is_held_and_prompt_is_unchanged(self):
        r = self.run_agent(Brain([W, OK, DONE]))
        self.assertEqual(r.steps[0]["result"].get("wrote"), "index.html")
        self.assertNotIn("Scott chooses before you build", r.msgs[0]["content"])

    def test_compare_lane_never_waits_for_an_answer(self):
        root = Path(self.tmp.name) / "lane"
        root.mkdir()
        r = agent.Run(Brain([act(action="ask", question="Colour?", choices=["a", "b"]), act(action="plan", steps=["A", "B"]), DONE]),
                      config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t", root=root, ask_first=True)
        r.loop()
        self.assertEqual(r.state, "done")
        self.assertFalse(r.ask_first)
        self.assertEqual(r.before, "")


class BeforeAndRobot(Base):
    def test_before_copy_holds_the_page_as_it_was(self):
        site = preview.ensure_site("scratch")
        was = (site / "index.html").read_text()
        r = self.run_agent(Brain([W, OK, DONE]))
        self.assertTrue(r.view()["before"])
        self.assertEqual((Path(r.before) / "index.html").read_text(), was)
        self.assertEqual((site / "index.html").read_text(), "<h1>new</h1>")

    def robot_run(self, results, replies):
        seen = []

        def robot(run):
            seen.append(run.id)
            return results.pop(0) if len(results) > 1 else results[0]
        r = agent.Run(Brain(replies), config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t", selftest=robot)
        r.loop()
        return r, seen

    def test_green_robot_is_done(self):
        r, seen = self.robot_run([{"level": "green", "why": [], "good": ["The page opens."]}], [W, OK, DONE])
        self.assertEqual((r.state, len(seen), r.view()["robot"]["level"]), ("done", 1, "green"))

    def test_red_robot_sends_the_model_back_then_passes(self):
        red = {"level": "red", "why": ["Error on the page: x is not defined"]}
        r, seen = self.robot_run([red, {"level": "green", "why": []}], [W, OK, DONE, W, OK, DONE])
        self.assertEqual((r.state, len(seen)), ("done", 2))
        self.assertIn("x is not defined", r.steps[2]["result"]["error"])

    def test_red_robot_twice_is_never_a_tick(self):
        r, _ = self.robot_run([{"level": "red", "why": ["Error on the page: boom"]}], [W, OK, DONE])
        self.assertEqual(r.state, "unproven")
        self.assertIn("boom", r.why)

    def test_robot_that_cannot_run_is_yellow_and_said_so(self):
        def robot(run):
            raise RuntimeError("no browser")
        r = agent.Run(Brain([W, OK, DONE]), config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t", selftest=robot)
        r.loop()
        self.assertEqual((r.state, r.robot["level"]), ("done", "yellow"))
        self.assertIn("did not run", r.why)

    def test_no_change_means_no_robot(self):
        r, seen = self.robot_run([{"level": "red", "why": ["x"]}], [DONE])
        self.assertEqual((r.state, seen), ("done", []))

    def test_judge_play(self):
        j = robotcheck.judge_play
        self.assertEqual(j({"status": 200, "errors": [], "button": "Start Game", "clicked": True, "moved": True})["level"], "green")
        self.assertEqual(j({"status": 200, "errors": [], "button": "Start", "clicked": True, "moved": False})["level"], "yellow")
        self.assertEqual(j({"status": 200, "errors": [], "button": None})["level"], "green")          # plain page, nothing to press
        self.assertEqual(j({"status": 200, "errors": ["ReferenceError: x"], "button": None})["level"], "red")
        self.assertEqual(j({"load_error": "timeout"})["level"], "red")
        self.assertEqual(j({"status": 200, "errors": [], "button": "Play", "clicked": False, "click_error": "covered"})["level"], "red")
        self.assertEqual(robotcheck.play("http://x/", driver=lambda u, s, c: {"status": 404, "errors": []})["level"], "red")

        def broken(u, s, c):
            raise RuntimeError("chrome missing")
        self.assertEqual(robotcheck.play("http://x/", driver=broken)["level"], "yellow")


from tests.test_agent import AgentOn  # noqa: E402


class Routes(AgentOn):
    flags = {"agent": True, "preview": True}

    def test_continue_route_and_before_page_and_shot(self):
        self.app.cfg["agent_step_cap"] = 1
        self.lab.chat = Brain([act(action="list"), act(action="done", summary="looked")]).chat
        code, r, _ = self.req("/api/agent/start", {"project": "scratch", "provider": "ollama", "model": "m", "task": "look", "ask_first": True})
        self.assertEqual(code, 200, r)
        rid = r["run"]["id"]
        self.assertTrue(r["run"]["before"])
        self.assertTrue(wait_for(lambda: self.req(f"/api/agent/run?id={rid}")[1]["run"]["state"] == "capped"))
        self.assertTrue(self.req(f"/api/agent/run?id={rid}")[1]["run"]["can_continue"])
        code, r, _ = self.req("/api/agent/more", {"id": rid})
        self.assertEqual(code, 200, r)
        self.assertTrue(wait_for(lambda: self.req(f"/api/agent/run?id={rid}")[1]["run"]["state"] == "done"))
        self.assertEqual(self.req("/api/agent/more", {"id": rid})[0], 400)                 # a finished run can't be continued
        code, page, _ = self.req(f"/preview-before/scratch/{rid}/index.html")
        self.assertEqual(code, 200)
        self.assertIn("Hello from the Lab", page)
        self.assertEqual(self.req("/preview-before/scratch/0000000000/index.html")[0], 404)
        self.assertEqual(self.req("/preview-before/scratch/..%2F..%2Fx/index.html")[0], 404)
        self.assertEqual(self.req(f"/api/agent/shot?id={rid}&name=opened.png")[0], 404)   # no robot ran: no picture
        self.assertEqual(self.req(f"/api/agent/shot?id={rid}&name=../../config.json")[0], 404)
