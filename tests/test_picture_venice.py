"""🎨 Art freedom (2026-11-24): Venice picture model by style, his words kept exactly, uncensored writer first,
plain fallback when Venice isn't set up, Venice chat body."""
from __future__ import annotations

from ailab import agent, config, picture
from ailab.mcp_client import HermesRefused
from ailab.providers import build
from tests.test_agent import Base, Brain
from tests.test_picture import PicMCP

WORDS = "two lovers on a beach at night, nude, tasteful"


class NoVenice(PicMCP):
    def call(self, tool, args=None):
        if tool == "image_make" and str((args or {}).get("model", "")).startswith("venice/"):
            self.calls.append(tool)
            self.args.append(args or {})
            raise HermesRefused("no_key", "Hermes has no Venice key in Vault.", "Add your Venice key in Hermes Settings → API keys.")
        return super().call(tool, args)


class Brain2(Brain):
    def __init__(self, replies):
        super().__init__(replies)
        self.who = []

    def chat(self, project, prov, model, msgs, max_tokens=1024, cap_usd=None, task=""):
        self.who.append((prov, model))
        return super().chat(project, prov, model, msgs, max_tokens, cap_usd, task)


class ArtFreedom(Base):
    def make(self, mcp, task=WORDS, replies=("soft moonlight, oil painting, warm skin tones",), cfg=None):
        b = Brain2(list(replies))
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected", **(cfg or {})}), self.project, "openrouter", "coder/m",
                      task, ctypes=["image"])
        return r, b

    def test_words_kept_exactly_and_venice_writer_first(self):
        mcp = PicMCP()
        r, b = self.make(mcp)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        prompt = mcp.args[mcp.calls.index("image_make")]["prompt"]
        self.assertTrue(prompt.startswith(WORDS))
        self.assertIn("oil painting", prompt)
        self.assertEqual(b.who[0], ("venice", "venice-uncensored-1-2"))

    def test_refusing_writer_skipped_next_one_used(self):
        mcp = PicMCP()
        r, b = self.make(mcp, replies=("I'm sorry, I can't help with that.", "dramatic rim light, film grain"))
        r.loop()
        prompt = mcp.args[mcp.calls.index("image_make")]["prompt"]
        self.assertEqual(prompt, WORDS + ". dramatic rim light, film grain")
        self.assertEqual(len(b.who), 2)

    def test_style_picks_venice_model(self):
        mcp = PicMCP()
        r, _ = self.make(mcp, task="a cabin\nStyle: Photo-real")
        r.loop()
        a = mcp.args[mcp.calls.index("image_make")]
        self.assertEqual(a["model"], "venice/lustify-v8")
        self.assertNotIn("Style:", a["prompt"])
        mcp2 = PicMCP()
        r2, _ = self.make(mcp2, task="a cabin\nStyle: Painted / illustrated")
        r2.loop()
        a2 = mcp2.args[mcp2.calls.index("image_make")]
        self.assertEqual(a2["model"], "venice/lustify-v8")     # 2026-11-24 live: Chroma signed paintings; Lustify didn't
        self.assertTrue(a2["prompt"].startswith("a cabin. Painted / illustrated."), a2["prompt"])   # the style reaches the model

    def test_no_venice_key_says_so_and_uses_default(self):
        mcp = NoVenice()
        r, _ = self.make(mcp)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        makes = [a for t, a in zip(mcp.calls, mcp.args) if t == "image_make"]
        self.assertEqual(len(makes), 2)
        self.assertNotIn("model", makes[1])
        self.assertTrue(any("Venice isn't set up" in s["why"] for s in r.steps))

    def test_forced_model_never_falls_back(self):
        mcp = NoVenice()
        r, _ = self.make(mcp, cfg={"picture_model": "venice/chroma"})
        r.loop()
        self.assertEqual(r.state, "failed")
        self.assertIn("Venice", r.why)

    def test_venice_chat_body_has_no_house_prompt(self):
        p = build(config.load({}), lambda *a: {})["venice"]
        self.assertEqual(p.base_url, "https://api.venice.ai/api/v1")
        self.assertIs(p.extra_body()["venice_parameters"]["include_venice_system_prompt"], False)

    def test_own_words_strips_choice_lines(self):
        self.assertEqual(picture.own_words("a cat\nStyle: Photo-real\nShape: Tall"), "a cat")
