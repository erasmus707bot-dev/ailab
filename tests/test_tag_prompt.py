"""🏷 Tag prompts for Illustrious / Pony (M3 tags, 2026-11-24): builder, rules fallback, per-model switch, others untouched."""
from __future__ import annotations

import unittest

from ailab import agent, config, picture_route, tag_prompt as T
from tests.test_agent import Brain
from tests.test_local_route import LocalMCP, Route

ILL, PONY = "local/illustrious-xl-v0.1", "local/pony-v6-xl"
ALL = [{"id": i, "fits": True} for i in (ILL, PONY, "local/sdxl-base-1.0", "local/juggernaut-xl-v9", "local/flux2-klein-4b")]
TAGS = "1girl, solo, holding umbrella, open umbrella, red umbrella, rain, bus stop, standing"


class Builder(unittest.TestCase):
    def test_wants_only_anime_models(self):
        self.assertTrue(T.wants(ILL)); self.assertTrue(T.wants(PONY))
        for m in ("local/sdxl-base-1.0", "local/flux2-klein-4b", "venice/lustify-v8", ""):
            self.assertFalse(T.wants(m))

    def test_clean_drops_quality_doubles_sentences(self):
        got = T.clean("Tags: 1girl, Rain, rain, masterpiece, score_9, this is a very long sentence that is not a tag at all, \"bus stop\".")
        self.assertEqual(got, ["1girl", "rain", "bus stop"])

    def test_build_prefix_tags_then_words_exact(self):
        p = T.build(PONY, ["1girl", "rain"], "A Girl with a RED umbrella")
        self.assertTrue(p.startswith("score_9, score_8_up, score_7_up, source_anime, 1girl, rain, "))
        self.assertTrue(p.endswith("A Girl with a RED umbrella"))
        self.assertTrue(T.build(ILL, [], "x").startswith("masterpiece"))

    def test_build_cuts_tags_never_words(self):
        mine = "w" * 200
        p = T.build(ILL, [f"tag{i}" for i in range(40)], mine, limit=300)
        self.assertLessEqual(len(p), 300); self.assertTrue(p.endswith(mine))

    def test_rules(self):
        got = T.rules("a girl with a red umbrella at a rainy bus stop", ["anime", "serene"])
        self.assertEqual(got, ["girl", "red umbrella", "rainy bus stop", "anime", "serene"])

    def test_negative(self):
        self.assertTrue(T.negative(PONY, "text").startswith("score_4"))
        self.assertTrue(T.negative(ILL, "text").endswith(", text"))


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
        self.assertTrue(a["prompt"].startswith("masterpiece, best quality, amazing quality, 1girl, solo, holding umbrella, open umbrella"))
        self.assertTrue(a["prompt"].endswith("a girl with a red umbrella at a rainy bus stop"))
        self.assertTrue(a["negative_prompt"].startswith("worst quality"))
        self.assertIn("photograph", a["negative_prompt"])
        self.assertTrue(any(s.get("action") == "tags" for s in r.steps))

    def test_writer_refuses_rules_take_over(self):
        m = LocalMCP(models=ALL)
        r, _ = self.go2(m, "a girl with a red umbrella\nLook: Anime", ["soft light", "Sorry, I can't help with that."])
        self.assertEqual(r.state, "done", r.why)
        p = self.makes(m)[0]["prompt"]
        self.assertTrue(p.startswith("masterpiece, best quality, amazing quality, girl, red umbrella"))
        self.assertTrue(p.endswith("a girl with a red umbrella"))

    def test_fallback_to_venice_gets_sentence_back(self):
        m = LocalMCP(models=ALL, fail_local=True)
        r, _ = self.go2(m, "a fox in snow\nLook: Anime", ["soft light", TAGS])
        a = self.makes(m)
        self.assertEqual([x["model"] for x in a], [ILL, "venice/lustify-v8"])
        self.assertFalse(a[1]["prompt"].startswith("masterpiece")); self.assertNotIn("worst quality", a[1]["negative_prompt"])
        self.assertTrue(a[1]["prompt"].startswith("a fox in snow"))

    def test_pony_when_illustrious_missing(self):
        m = LocalMCP(models=[x for x in ALL if x["id"] != ILL])
        self.go2(m, "a fox in snow\nLook: Manga", ["soft light", TAGS])
        a = self.makes(m)[0]
        self.assertEqual(a["model"], PONY); self.assertTrue(a["prompt"].startswith("score_9"))

    def test_watercolor_untouched(self):
        m = LocalMCP(models=ALL)
        r, b = self.go2(m, "a fox in snow\nLook: Watercolor", ["soft light", TAGS])
        a = self.makes(m)[0]
        self.assertEqual(a["model"], "local/sdxl-base-1.0")
        self.assertTrue(a["prompt"].startswith("a fox in snow")); self.assertNotIn("masterpiece", a["prompt"])
        self.assertEqual(len(b.calls), 1)                      # no extra writer call


if __name__ == "__main__":
    unittest.main()
