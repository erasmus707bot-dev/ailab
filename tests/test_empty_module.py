"""⚠️ Empty-module guard (2026-11-24): a build-prompt module meant to MAKE something is never ✅ when nothing was made."""
from __future__ import annotations

from ailab import agent, config
from tests.test_agent import Base, Brain, act
from tests.test_workflow import OK

HEAD = "Follow this build prompt. Do Module {n} {w} and stop at its gate.\n\n"
BODY = ("# Build\n## Module 0 — Audit (read-only)\nlook around, write nothing\n"
        "## Module 1 — Generate base image\nCreate base.png from the brief.\n## Module 2 — Polish\nmake it nicer")



class EmptyModule(Base):
    def go(self, replies, n="1", w="next", body=BODY, files=()):
        for name in files:
            p = self.make_root_file(name)
        r = agent.Run(Brain(replies), config.load({"mode": "standalone"}), self.project, "openrouter", "m",
                      HEAD.format(n=n, w=w) + body)
        r.loop()
        return r

    def make_root_file(self, name):
        r = agent.Run(Brain(["x"]), config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t")
        (r.root / name).write_text("x")
        return r.root / name

    def test_empty_make_module_refused_then_not_done(self):
        r = self.go([act(action="done", summary="Module 1 preparation complete", module="1")])
        v = r.view()
        self.assertEqual(r.state, "unproven")
        self.assertIn("1 · Generate base image was meant to make something", r.why)
        self.assertIsNone(v["gate"])                                   # no ▶ Go on after a ⚠️ ending
        self.assertNotEqual(v["plan"][1]["state"], "done")

    def test_refusal_message_reaches_the_model(self):
        b = Brain([act(action="done", summary="prep", module="1"),
                   act(action="write", path="base.png", content="png", why="w"), OK,
                   act(action="done", summary="made it", module="1")])
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", HEAD.format(n="1", w="next") + BODY)
        r.loop()
        self.assertTrue(any("is meant to make something" in c for c in b.calls))
        self.assertEqual(r.state, "done")

    def test_read_only_module_passes(self):
        r = self.go([act(action="list", module="0"), act(action="done", summary="audit done", module="0")], n="0", w="first")
        self.assertEqual(r.state, "done")
        self.assertEqual(r.view()["gate"]["next"], "1")

    def test_named_file_already_there_passes(self):
        r = self.go([act(action="done", summary="already in place", module="1")], files=("base.png",))
        self.assertEqual(r.state, "done")

    def test_real_output_passes(self):
        r = self.go([act(action="write", path="base.png", content="png", why="w"), OK,
                     act(action="done", summary="made", module="1")])
        self.assertEqual(r.state, "done")
        self.assertEqual(r.view()["gate"]["next"], "2")

    def test_plain_task_untouched(self):
        r = agent.Run(Brain([act(action="done", summary="nothing to do")]), config.load({"mode": "standalone"}),
                      self.project, "openrouter", "m", "Create a page")
        r.loop()
        self.assertEqual(r.state, "done")
