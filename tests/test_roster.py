"""⭐ roster: recommended models float to the top of a live list; nothing is invented for a live provider."""
import unittest

from ailab import roster


class Roster(unittest.TestCase):
    def test_live_list_stars_only_what_is_really_there_newest_dated_id_first(self):
        ids = ["a/b", "deepseek/deepseek-v4.1-flash", "deepseek/deepseek-v4.1-flash-1017", "z-ai/glm-5.3", "z-ai/glm-5.3-flash"]
        out, picks = roster.arrange("openrouter", ids, live=True, extra=["my/model"])
        self.assertEqual(out[:3], ["deepseek/deepseek-v4.1-flash-1017", "z-ai/glm-5.3", "my/model"])
        self.assertEqual(set(picks), {"deepseek/deepseek-v4.1-flash-1017", "z-ai/glm-5.3"})
        self.assertEqual(sorted(out), sorted(ids + ["my/model"]))

    def test_hermes_list_gets_fallback_ids_marked_unconfirmed_but_ollama_never_does(self):
        out, picks = roster.arrange("openrouter", ["x/default"], live=False)
        self.assertIn("moonshotai/kimi-k3.1-pro", out)
        self.assertTrue(all("not confirmed" in v for v in picks.values()))
        out, picks = roster.arrange("ollama", ["qwen3.5:4b", "dolphin3:8b"], live=True)
        self.assertEqual((out, list(picks)), (["qwen3.5:4b", "dolphin3:8b"], ["qwen3.5:4b"]))

    def test_status_says_pull_or_key(self):
        class Lab:
            def list_models(self, prov, project=None):
                if prov == "ollama":
                    return {"source": "live", "models": [{"id": "qwen3.5:4b"}]}
                raise KeyError("No openrouter key.")
        rows = {r["model"]: r for r in roster.status(Lab())}
        self.assertEqual(rows["qwen3.5:4b"]["state"], "ready")
        self.assertEqual(rows["qwen3.8:27b"]["todo"], "ollama pull qwen3.8:27b")
        self.assertEqual(rows["z-ai/glm-5.3"]["state"], "needs a key")


if __name__ == "__main__":
    unittest.main()


class BestUse(unittest.TestCase):
    """2026-11-23: every model gets a best-use tag and a $ tier."""

    def test_tags_from_names(self):
        from ailab import roster as R
        self.assertEqual(R.use_tag("Qwen/Qwen3-Coder-30B"), "💻 coding")
        self.assertEqual(R.use_tag("qwen2.5-vl-72b"), "🖼 sees images")
        self.assertEqual(R.use_tag("deepseek-r1:14b"), "🔬 reasoning / research")
        self.assertEqual(R.use_tag("claude-haiku-5-5"), "⚡ fast & cheap")
        self.assertEqual(R.use_tag("qwen3.8:27b"), "🧠 hardest work")
        self.assertEqual(R.use_tag("text-embedding-3-small"), "⚙️ not a chat model")
        self.assertEqual(R.use_tag("grok-4-1"), "💬 general")

    def test_tiers_and_tags_dict(self):
        from ailab import roster as R
        self.assertEqual([R.cost_tier(x) for x in (0.5e-6, 3e-6, 10e-6, 20e-6, None)], ["$", "$$", "$$$", "$$$$", ""])
        t = R.tags("openrouter", [{"id": "a/b-coder", "price_out": 2e-6}, {"id": "c/d"}], lambda m, l: (0, 30e-6, True))
        self.assertEqual(t, {"a/b-coder": {"use": "💻 coding", "tier": "$$"}, "c/d": {"use": "💬 general", "tier": "$$$$"}})
        self.assertEqual(R.tags("ollama", [{"id": "qwen3.5:4b"}])["qwen3.5:4b"]["tier"], "free")
