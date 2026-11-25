"""🖼 Picture runs (2026-11-24): ❓ style/shape → prompt → Hermes image_make → picture file; live stage line."""
from __future__ import annotations

import base64
import threading

from ailab import agent, config, creation, picture
from ailab.mcp_client import HermesRefused
from tests.test_agent import Base, Brain, act
from tests.test_workflow import wait_for

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()


class PicMCP:
    def __init__(self, fail=None, polls=1, refuse=False):
        self.calls, self.args, self.fail, self.polls, self.refuse = [], [], fail, polls, refuse

    def call(self, tool, args=None):
        self.calls.append(tool)
        self.args.append(args or {})
        if tool == "image_make":
            if self.refuse:
                raise HermesRefused("over_cap", "openrouter daily cap reached", "Wait for tomorrow.")
            return {"ok": True, "key": "img:abc", "model": "black-forest-labs/flux-3-image-klein", "est_usd": 0.008}
        if tool == "job_wait":
            self.polls -= 1
            if self.polls > 0:
                return {"ok": True, "state": "running", "finished": False}
            if self.fail:
                return {"ok": True, "state": "failed", "finished": True, "error": {"message": self.fail}}
            return {"ok": True, "state": "done", "finished": True,
                    "result": {"b64": PNG, "media_type": "image/png", "model": "black-forest-labs/flux-3-image-klein",
                               "usd": 0.0071, "library": "ai-lab/x.png", "prompt": "p"}}
        return {"ok": True}


class Mode(Base):
    def test_picture_mode_only_for_image_alone(self):
        self.assertTrue(creation.picture_mode(["image"]))
        self.assertTrue(creation.picture_mode(["image", "text"]))
        self.assertFalse(creation.picture_mode(["image", "website"]))
        self.assertFalse(creation.picture_mode([]))

    def test_aspect(self):
        self.assertEqual(picture.aspect_from("Tall (phone)"), "9:16")
        self.assertEqual(picture.aspect_from("Wide (screen)"), "16:9")
        self.assertEqual(picture.aspect_from(""), "")


class PictureRun(Base):
    def make(self, mcp, ask=False, task="african woman by a tree at a desert oasis", replies=("A woman beside a palm tree at a desert oasis, golden light, painted style.",)):
        b = Brain(list(replies))
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", task, ctypes=["image"], ask_first=ask)
        return r, b

    def test_makes_and_saves_the_picture(self):
        mcp = PicMCP(polls=2)
        r, _ = self.make(mcp)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        pic = r.view()["pictures"][0]
        self.assertTrue((r.root / pic["path"]).read_bytes().startswith(b"\x89PNG"))
        self.assertIn("flux-3-image-klein", r.why)
        self.assertEqual(mcp.calls.count("job_wait"), 2)
        self.assertIn("palm tree", mcp.args[mcp.calls.index("image_make")]["prompt"])
        self.assertAlmostEqual(r.usd, 0.0071 + 0.001, places=6)
        self.assertEqual(r.view()["stage"]["icon"], "✅")
        self.assertEqual([s["action"] for s in r.steps], ["prompt", "picture"])

    def test_choices_card_then_shape_becomes_aspect(self):
        mcp = PicMCP()
        r, _ = self.make(mcp, ask=True)
        t = threading.Thread(target=r.loop)
        t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        self.assertEqual([i["q"] for i in r.question["items"]], ["Style?", "Shape?"])
        self.assertEqual(r.view()["stage"]["text"], "Waiting for your choice")
        r.answer("Style? → Photo-real · Shape? → Tall (phone)")
        t.join(5)
        self.assertEqual(r.state, "done", r.why)
        args = mcp.args[mcp.calls.index("image_make")]
        self.assertEqual(args["aspect_ratio"], "9:16")
        self.assertEqual(r.pictures[0]["shape"], "Tall (phone)")

    def test_make_another_reads_style_and_shape_from_the_words(self):
        mcp = PicMCP()
        r, b = self.make(mcp, task="a cabin\nStyle: Photo-real\nShape: Wide (screen)")
        r.loop()
        self.assertEqual(mcp.args[mcp.calls.index("image_make")]["aspect_ratio"], "16:9")
        self.assertEqual(b.calls[0].count("Style:"), 1)                      # not added twice

    def test_bad_writer_reply_falls_back_to_his_words(self):
        mcp = PicMCP()
        r, _ = self.make(mcp, replies=("Sorry, I can't help with that.",))
        r.loop()
        self.assertEqual(r.state, "done")
        self.assertIn("desert oasis", mcp.args[mcp.calls.index("image_make")]["prompt"])
        self.assertIn("your own words", r.steps[0]["why"])

    def test_failed_and_refused_are_plain_and_never_done(self):
        r, _ = self.make(PicMCP(fail="HTTP 400: content policy"))
        r.loop()
        self.assertEqual(r.state, "failed")
        self.assertIn("content policy", r.why)
        r2, _ = self.make(PicMCP(refuse=True))
        r2.loop()
        self.assertEqual(r2.state, "failed")
        self.assertIn("daily cap", r2.why)

    def test_standalone_says_it_needs_hermes(self):
        b = Brain(["x"])
        b.mcp = None
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", "a cat", ctypes=["image"])
        r.loop()
        self.assertEqual(r.state, "failed")
        self.assertIn("connected mode", r.why)

    def test_agent_saves_picture_bytes_to_a_file_not_the_model(self):
        mcp = PicMCP()
        b = Brain([act(action="hermes", tool="image_make", args={"prompt": "logo"}),
                   act(action="hermes", tool="job_wait", args={"key": "img:abc"}),
                   act(action="done", summary="made")])
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "site + logo", ctypes=["website", "image"])
        r.loop()
        res = r.steps[1]["result"]
        self.assertNotIn("b64", res.get("result", {}))
        self.assertTrue((r.root / res["result"]["saved_as"]).is_file())
        self.assertTrue(all(PNG not in c for c in b.calls))
        self.assertEqual(len(r.pictures), 1)


class Stage(Base):
    def test_stage_words_for_agent_runs(self):
        b = Brain([act(action="list"), act(action="done", summary="x")])
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "vendor/model-x", "look")
        self.assertIn("model-x", r.stage_view()["text"])
        r.loop()
        self.assertEqual(r.stage_view(), {"icon": "✅", "text": "Done", "busy": False})
        v = r.view()
        self.assertIn("elapsed_s", v)
        self.assertFalse(v["picture"])


def test_writer_never_adds_clothing():
    """2026-11-24 live: Scott asked for 'a woman by a palm tree', the writer added 'a flowing dress'."""
    from ailab import picture
    assert "Never add clothing" in picture.PROMPT_SYS


BP = ("Follow this build prompt. Do Module 0 first and stop at its gate.\n\n# a woman by a tree at an oasis — Build Prompt (2026-11-24)\n\n"
      "**For:** build session · **Repo:** `~/`\n**Idea (Scott's words):** a woman by a tree at an oasis\n\n---\n\n## 0. Working rules\n"
      "- **Do the work, report short.**\n| Module | Gate |\n|---|---|\n| 0 | audit |\n")


def test_build_prompt_picture_uses_only_the_idea_line():
    """2026-11-24 live: the whole build prompt (2,617 chars) went to the picture model and was drawn as text."""
    from ailab import picture
    assert picture.picture_words(BP) == "a woman by a tree at an oasis"
    assert picture.picture_words(BP + "Style: Photo-real\n") == "a woman by a tree at an oasis\nStyle: Photo-real"
    no_idea = BP.replace("**Idea (Scott's words):** a woman by a tree at an oasis\n", "")
    assert picture.picture_words(no_idea) == "a woman by a tree at an oasis"
    assert picture.picture_words("a cat on a roof\nShape: Wide") == "a cat on a roof\nShape: Wide"


def test_own_words_drops_markdown_marks_and_no_text_list():
    from ailab import picture
    assert picture.own_words("**a cat** on a `roof`") == "a cat on a roof"
    assert "watermark" in picture.NO_TEXT and "caption" in picture.NO_TEXT and "text" in picture.NO_TEXT
    assert "Never ask for text" in picture.PROMPT_SYS
