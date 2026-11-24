"""Fix 5 (2026-11-23): no false "finished" — done needs a passing check after the last change; stuck timer;
compare lanes judged by Scott's checks; Review apply reads the file back."""
from __future__ import annotations

import time
import unittest

from ailab import agent, preview
from tests.test_agent import Base, Brain, act


class Proof(Base):
    def test_done_after_write_without_check_is_refused_then_unproven(self):
        r = self.run_agent(Brain([act(action="write", path="a.txt", content="x"),
                                  act(action="done", summary="all good")]))
        self.assertEqual(r.state, "unproven")
        self.assertIn("no check passed", r.why)
        self.assertIn("Not accepted", str(r.steps[1]["result"]))
        self.assertFalse(r.view()["proved"])

    def test_refusal_lets_the_model_check_then_done(self):
        r = self.run_agent(Brain([act(action="write", path="a.txt", content="x"),
                                  act(action="done", summary="early"),
                                  act(action="run", cmd="grep -c x a.txt"),
                                  act(action="done", summary="checked")]))
        self.assertEqual((r.state, r.why), ("done", "checked"))
        self.assertTrue(r.view()["proved"])

    def test_failing_check_is_not_proof(self):
        r = self.run_agent(Brain([act(action="write", path="a.txt", content="x"),
                                  act(action="run", cmd="grep -c nothere a.txt"),
                                  act(action="done", summary="d")]))
        self.assertEqual(r.state, "unproven")

    def test_check_before_last_change_does_not_count(self):
        r = self.run_agent(Brain([act(action="write", path="a.txt", content="x"),
                                  act(action="run", cmd="true"),
                                  act(action="write", path="a.txt", content="y"),
                                  act(action="done", summary="d")]))
        self.assertEqual(r.state, "unproven")

    def test_no_change_done_is_labelled(self):
        r = self.run_agent(Brain([act(action="list"), act(action="done", summary="looked")]))
        self.assertEqual(r.state, "done")
        self.assertTrue(r.why.startswith("ℹ️ No files changed"))

    def test_hermes_proof_tools(self):
        r = agent.Run(Brain([]), {"mode": "standalone"}, self.project, "p", "m", "t")
        r._record({"action": "write", "path": "a", "result": {"ok": True}})
        r._record({"action": "hermes", "tool": "linux_app_build", "result": {"verdict": "fail"}})
        self.assertFalse(r.proof_ok())
        r._record({"action": "hermes", "tool": "linux_app_build", "result": {"verdict": "pass"}})
        self.assertTrue(r.proof_ok())

    def test_stuck_timer(self):
        r = agent.Run(Brain([]), {"mode": "standalone", "stuck_after_s": 5}, self.project, "p", "m", "t")
        self.assertFalse(r.view()["stuck"])
        r.last_progress = time.time() - 6
        v = r.view()
        self.assertTrue(v["stuck"])
        self.assertGreaterEqual(v["quiet_s"], 6)
        r.state = "done"
        self.assertFalse(r.view()["stuck"])                      # only a running run can be stuck


if __name__ == "__main__":
    unittest.main()


class Prices(unittest.TestCase):
    def test_known_prices_and_config_json_adds_not_wipes(self):
        from ailab import config, providers
        c = config.load({"prices_per_mtok": {"my/model": {"in": 1, "out": 2}}})
        self.assertIn("claude-sonnet-5-5", c["prices_per_mtok"])
        self.assertIn("my/model", c["prices_per_mtok"])
        pin, pout, known = providers.build(c, None)["claude"].price("claude-sonnet-5-5")
        self.assertEqual((pin * 1e6, pout * 1e6, known), (2.0, 10.0, True))
