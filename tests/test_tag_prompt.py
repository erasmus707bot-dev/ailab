"""🏷 Tag prompts for Illustrious / Pony (M3 tags, 2026-11-24): builder, rules fallback, per-model switch, others untouched."""
from __future__ import annotations

import unittest

from ailab import agent, config, picture_route, tag_prompt as T
from tests.test_agent import Brain
from ailab.mcp_client import HermesRefused
from tests.test_local_route import LocalMCP, Route

ILL, PONY = "local/illustrious-xl-v0.1", "local/pony-v6-xl"
ALL = [{"id": i, "fits": True} for i in (ILL, PONY, "local/sdxl-base-1.0", "local/juggernaut-xl-v9", "local/flux2-klein-4b")]
TAGS = "1girl, solo, holding umbrella, open umbrella, red umbrella, rain, bus stop, standing"


class Client(unittest.TestCase):
    """The rules themselves are tested in Hermes (forge/projects/tests/test_prompt_dialect.py)."""
    def setUp(self):
        T.forget()

    def test_wants_asks_hermes_and_caches(self):
        m = LocalMCP(models=ALL)
        run = type("R", (), {"lab": type("L", (), {"mcp": m})()})()
        self.assertTrue(T.wants(ILL, run)); self.assertTrue(T.wants(PONY, run))
        self.assertFalse(T.wants("local/sdxl-base-1.0", run)); self.assertFalse(T.wants("venice/lustify-v8", run))
        self.assertTrue(T.wants(ILL, run)); self.assertEqual(m.calls.count("prompt_style"), 4)   # cached
        self.assertTrue(T.wants(ILL)); self.assertFalse(T.wants(""))

    def test_hermes_away_means_sentence(self):
        class Down:
            def call(self, tool, args=None):
                raise HermesRefused("rpc", "connection refused")
        run = type("R", (), {"lab": type("L", (), {"mcp": Down()})()})()
        self.assertFalse(T.wants(ILL, run))


class InRun(Route):
    def go2(self, mcp, task, replies, cfg=None):
        b = Brain(replies); b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected", **(cfg or {})}), self.project, "openrouter", "coder/m", task, ctypes=["image"])
        r.loop()
        return r, b

    def makes(self, mcp):
        return [a for t, a in zip(mcp.calls, mcp.args) if t == "image_make"]

    def test_anime_gets_tag_prompt(self):
        m = LocalMCP(models=ALL)
        r, b = self.go2(m, "a girl with a red umbrella at a rainy bus stop\nLook: Anime", ["soft light", TAGS])
        self.assertEqual(r.state, "done", r.why)
        a = self.makes(m)[0]
        self.assertEqual(a["model"], ILL)
        self.assertTrue(a["prompt"].startswith("1girl, solo, holding umbrella, open umbrella"))
        self.assertTrue(a["prompt"].endswith("a girl with a red umbrella at a rainy bus stop"))
        self.assertIn("photograph", a["negative_prompt"])
        self.assertTrue(any(s.get("action") == "tags" for s in r.steps))

    def test_look_mood_word_stays_writer_mood_goes(self):
        m = LocalMCP(models=ALL)
        self.go2(m, "a girl at a bus stop\nLook: Anime · Serene", ["soft light", TAGS + ", calm, quiet"])
        p = self.makes(m)[0]["prompt"]
        self.assertIn("serene mood", p); self.assertNotIn(", calm,", p); self.assertNotIn(", quiet,", p)

    def test_look_words_not_doubled(self):
        m = LocalMCP(models=ALL)
        self.go2(m, "a girl at a bus stop\nLook: Anime", ["soft light", TAGS + ", cel shading, anime style"])
        p = self.makes(m)[0]["prompt"]
        self.assertEqual(p.count("anime style"), 1); self.assertEqual(p.count("cel shading"), 1)

    def test_writer_refuses_rules_take_over(self):
        m = LocalMCP(models=ALL)
        r, _ = self.go2(m, "a girl with a red umbrella\nLook: Anime", ["soft light", "Sorry, I can't help with that."])
        self.assertEqual(r.state, "done", r.why)
        p = self.makes(m)[0]["prompt"]
        self.assertTrue(p.startswith("girl, red umbrella"))
        self.assertTrue(p.endswith("a girl with a red umbrella"))

    def test_fallback_to_venice_gets_sentence_back(self):
        m = LocalMCP(models=ALL, fail_local=True)
        r, _ = self.go2(m, "a fox in snow\nLook: Anime", ["soft light", TAGS])
        a = self.makes(m)
        self.assertEqual([x["model"] for x in a], [ILL, "venice/lustify-v8"])
        self.assertTrue(a[1]["prompt"].startswith("a fox in snow"))

    def test_pony_when_illustrious_missing(self):
        m = LocalMCP(models=[x for x in ALL if x["id"] != ILL])
        self.go2(m, "a fox in snow\nLook: Manga", ["soft light", TAGS])
        a = self.makes(m)[0]
        self.assertEqual(a["model"], PONY); self.assertTrue(a["prompt"].startswith("1girl, solo"))
        self.assertNotIn("score_", a["prompt"])

    def test_watercolor_untouched(self):
        m = LocalMCP(models=ALL)
        r, b = self.go2(m, "a fox in snow\nLook: Watercolor", ["soft light", TAGS])
        a = self.makes(m)[0]
        self.assertEqual(a["model"], "local/sdxl-base-1.0")
        self.assertTrue(a["prompt"].startswith("a fox in snow")); self.assertNotIn("1girl", a["prompt"])
        self.assertEqual(len(b.calls), 1)                      # no extra writer call


if __name__ == "__main__":
    unittest.main()
