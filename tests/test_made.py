"""📦 What was made · ⏸ module gate · 🪄 Help me say it · prompt builder keeps the chips (2026-11-24)."""
from __future__ import annotations

from ailab import agent, config
from tests.test_agent import AgentOn, Base, Brain, act
from tests.test_picture import PicMCP
from tests.test_workflow import OK, wait_for

GATED = "Follow this build prompt. Do Module 0 first and stop at its gate.\n\n# Build\n## Module 0 — Audit\nlook\n## Module 1 — Make the page\nx\n## Module 2 — Polish\ny"


class Made(Base):
    def test_files_made_and_changed_with_kinds(self):
        b = Brain([act(action="write", path="notes.md", content="hi", why="w"),
                   act(action="write", path="index.html", content="<h1>x</h1>", why="w"),
                   act(action="write", path="art/logo.svg", content="<svg/>", why="w"),
                   act(action="write", path="notes.md", content="hi again", why="w"), OK, act(action="done", summary="ok")])
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t")
        r.loop()
        made = {m["path"]: m for m in r.view()["made"]}
        self.assertEqual(made["notes.md"]["kind"], "doc")
        self.assertTrue(made["notes.md"]["new"])                       # still "new" after a second write
        self.assertEqual(made["index.html"]["kind"], "page")
        self.assertFalse(made["index.html"]["new"])                    # scratch already had an index.html
        self.assertEqual(made["art/logo.svg"]["kind"], "picture")

    def test_undone_step_is_not_listed(self):
        b = Brain([act(action="write", path="a.md", content="1", why="w"), OK, act(action="done", summary="ok")])
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t")
        r.loop()
        r.undo_step(1)
        self.assertEqual(r.view()["made"], [])

    def test_picture_run_lists_the_picture(self):
        b = Brain(["A palm tree at an oasis."])
        b.mcp = PicMCP()
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "oasis", ctypes=["image"])
        r.loop()
        self.assertEqual([m["kind"] for m in r.view()["made"]], ["picture"])


class Gate(Base):
    def run_gated(self, task=GATED, module="0", make=False):
        # a module meant to make something must make it (empty-module guard, 2026-11-24)
        b = Brain(([act(action="write", path=f"m{module}.html", content="<p>x</p>", why="w", module=module), OK] if make
                   else [act(action="list", module=module)]) + [act(action="done", summary="done", module=module)])
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", task)
        r.loop()
        return r

    def test_stopped_at_gate_is_not_all_done(self):
        r = self.run_gated()
        v = r.view()
        self.assertEqual([m["state"] for m in v["plan"]], ["done", "left", "left"])
        self.assertEqual((v["gate"]["done"], v["gate"]["next"]), ("0", "1"))
        self.assertEqual(v["gate"]["next_name"], "1 · Make the page")
        self.assertTrue(v["gate"]["next_task"].startswith("Follow this build prompt. Modules already done: 0. Do Module 1 next"))
        self.assertIn("## Module 2", v["gate"]["next_task"])
        self.assertEqual(v["stage"]["icon"], "⏸")

    def test_next_task_gates_again_then_last_module_has_no_gate(self):
        r1 = self.run_gated()
        r2 = self.run_gated(r1.view()["gate"]["next_task"], "1", make=True)
        self.assertEqual(r2.view()["gate"]["next"], "2")
        r3 = self.run_gated(r2.view()["gate"]["next_task"], "2", make=True)
        self.assertIsNone(r3.view()["gate"])
        self.assertTrue(all(m["state"] == "done" for m in r3.view()["plan"]))

    def test_plain_task_has_no_gate(self):
        r = self.run_gated(task="just do it")
        self.assertIsNone(r.view()["gate"])


class Routes(AgentOn):
    flags = {"agent": True, "router": True, "prompt": True}

    def test_rephrase_returns_clear_words_and_falls_back(self):
        self.lab.chat = Brain(["Make the page title twice as big and dark blue."]).chat
        code, r, _ = self.req("/api/agent/rephrase", {"project": "scratch", "provider": "ollama", "model": "m",
                                                      "text": "title bigger, blue", "made": ["index.html"]})
        self.assertEqual(code, 200, r)
        self.assertEqual(r["text"], "Make the page title twice as big and dark blue.")
        self.lab.chat = lambda *a, **k: Brain([""]).chat(*a, **k)       # every writer gives nothing → says so, his words stay
        r = self.req("/api/agent/rephrase", {"project": "scratch", "provider": "ollama", "model": "m", "text": "x"})[1]
        self.assertFalse(r["ok"])
        self.assertIn("your own words work too", r["message"])
        self.assertEqual(self.req("/api/agent/rephrase", {"project": "scratch", "text": " "})[0], 400)

    def test_rephrase_skips_the_loading_placeholder(self):
        # 2026-11-24 live: the pane's model box still said ⏳ → "⏳ is not a valid model ID" (HTTP 400)
        seen = []
        def chat(proj, prov, model, *a, **k):
            seen.append((prov, model))
            return Brain(["Open the legs slightly."]).chat(proj, prov, model, *a, **k)
        self.lab.chat = chat
        code, r, _ = self.req("/api/agent/rephrase", {"project": "scratch", "provider": "openrouter", "model": "⏳", "text": "legs apart"})
        self.assertEqual(code, 200, r)
        self.assertTrue(r["ok"], r)
        self.assertNotIn("⏳", [m for _, m in seen])

    def test_picture_rephrase_tries_the_uncensored_writer_first_and_skips_refusals(self):
        seen = []
        def chat(proj, prov, model, *a, **k):
            seen.append((prov, model))
            text = "Sorry, I can't help with that." if len(seen) == 1 else "Stand with the legs slightly apart."
            return Brain([text]).chat(proj, prov, model, *a, **k)
        self.lab.chat = chat
        self.lab.providers = {"venice": 1, "openrouter": 1, "ollama": 1}
        code, r, _ = self.req("/api/agent/rephrase", {"project": "scratch", "provider": "openrouter", "model": "x/y",
                                                      "text": "legs slightly apart", "picture": True})
        self.assertEqual(code, 200, r)
        self.assertEqual(seen[0], ("venice", "venice-uncensored-1-2"))
        self.assertEqual(r["text"], "Stand with the legs slightly apart.")

    def test_prompt_send_keeps_the_chips(self):
        self.lab.chat = Brain([act(action="done", summary="ok")]).chat
        md = "# X\n## Module 0 — Audit\nlook"
        code, r, _ = self.req("/api/prompt/send", {"md": md, "target": "lab", "project": "scratch", "provider": "ollama",
                                                   "model": "m", "ctypes": ["website"]})
        self.assertEqual(code, 200, r)
        self.assertEqual(r["run"]["ctypes"], ["website"])
        rid = r["run"]["id"]
        self.assertTrue(wait_for(lambda: self.req(f"/api/agent/run?id={rid}")[1]["run"]["state"] != "running"))
