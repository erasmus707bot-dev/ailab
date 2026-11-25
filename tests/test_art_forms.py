"""🎬 📝 🎭 Art in every form (2026-11-24, Scott: "my art in video, document, game, and software forms")."""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from ailab import agent, config, content, creation, docrun, video
from tests.test_agent import Base, Brain
from tests.test_picture import PNG, PicMCP
from tests.test_workflow import wait_for


class ArtMCP(PicMCP):
    """Pictures as PicMCP; video_quote / video_make / job_wait for vid: keys."""

    def __init__(self, quote=0.35, fits=True, vid_path="", vfail="", **k):
        super().__init__(**k)
        self.quote, self.fits, self.vid_path, self.vfail = quote, fits, vid_path, vfail

    def call(self, tool, args=None):
        if tool == "video_quote":
            self.calls.append(tool); self.args.append(args or {})
            return {"ok": True, "usd": self.quote, "model": "wan-2-7-enhanced-text-to-video", "today_usd": 0.0,
                    "daily_cap": 5.0, "fits": self.fits}
        if tool == "video_make":
            self.calls.append(tool); self.args.append(args or {})
            return {"ok": True, "key": "vid:abc", "model": args.get("model") or "wan-2-7-enhanced-text-to-video", "est_usd": self.quote}
        if tool == "job_wait" and (args or {}).get("key", "").startswith("vid:"):
            self.calls.append(tool); self.args.append(args or {})
            if self.vfail:
                return {"ok": True, "state": "failed", "finished": True, "error": {"message": self.vfail}}
            return {"ok": True, "state": "done", "finished": True,
                    "result": {"path": self.vid_path, "model": "wan-2-7-enhanced-text-to-video", "usd": self.quote,
                               "seconds": 90, "duration": "5s", "media_item": "m1"}}
        return super().call(tool, args)


class Modes(Base):
    def test_modes(self):
        self.assertTrue(creation.video_mode(["video"]) and creation.video_mode(["video", "image"]))
        self.assertFalse(creation.video_mode(["video", "game"]))
        self.assertFalse(creation.picture_mode(["image", "video"]))
        self.assertTrue(creation.picture_mode(["image", "text"]))       # unchanged (batch relies on it)
        self.assertTrue(creation.doc_mode(["text"]))
        self.assertFalse(creation.doc_mode(["text", "image"]) or creation.doc_mode(["text", "website"]))


class VideoRun(Base):
    def make(self, mcp, ask=False, task="a dancer spinning in the rain", replies=("slow push-in, rain streaks, neon light",)):
        b = Brain(list(replies))
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", task, ctypes=["video"], ask_first=ask)
        return r, b

    def mp4(self):
        f = Path(tempfile.mkdtemp()) / "v.mp4"
        f.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2000)
        return str(f)

    def test_price_card_then_video_saved(self):
        mcp = ArtMCP(vid_path=self.mp4())
        r, b = self.make(mcp, ask=True)
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        r.answer("Length? → 5 seconds · Shape? → Tall (phone) · Start from? → Just my words")
        self.assertTrue(wait_for(lambda: r.question is not None and "costs" in r.question["text"]))
        self.assertIn("$0.35", r.question["text"])
        self.assertIn("of $5.00", r.question["text"])
        self.assertNotIn("video_make", mcp.calls)                 # nothing spent before the tap
        r.answer(r.question["choices"][0])
        t.join(5)
        self.assertEqual(r.state, "done", r.why)
        v = r.view()["videos"][0]
        self.assertTrue((r.root / v["path"]).read_bytes()[4:8] == b"ftyp")
        a = mcp.args[mcp.calls.index("video_make")]
        self.assertTrue(a["prompt"].startswith("a dancer spinning in the rain"))   # his words first, exactly
        self.assertEqual(a["aspect_ratio"], "9:16")
        self.assertIn("captions", a["negative_prompt"])
        self.assertIn("video", {m["kind"] for m in r.view()["made"]})
        self.assertIn("Media Studio", r.why)

    def test_cancel_spends_nothing(self):
        mcp = ArtMCP(vid_path=self.mp4())
        r, _ = self.make(mcp)
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        r.answer(video.CANCEL)
        t.join(5)
        self.assertEqual(r.state, "done")
        self.assertNotIn("video_make", mcp.calls)
        self.assertIn("nothing spent", r.why)

    def test_over_cap_offers_only_free(self):
        mcp = ArtMCP(fits=False)
        r, _ = self.make(mcp)
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        self.assertFalse(any(c.startswith("▶") for c in r.question["choices"]))
        r.answer(video.CANCEL); t.join(5)

    def test_picture_first_sends_the_picture(self):
        mcp = ArtMCP(vid_path=self.mp4())
        r, _ = self.make(mcp, ask=True, replies=("detail",))
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        r.answer("Length? → 8 seconds · Shape? → Wide (screen) · Start from? → Make a picture first, then bring it to life")
        self.assertTrue(wait_for(lambda: r.question is not None and "costs" in r.question["text"]))
        r.answer(r.question["choices"][0]); t.join(5)
        self.assertEqual(r.state, "done", r.why)
        a = mcp.args[mcp.calls.index("video_make")]
        self.assertTrue(a.get("image_b64"))
        self.assertNotIn("aspect_ratio", a)
        self.assertEqual(a["duration"], "8s")
        self.assertEqual(mcp.args[mcp.calls.index("image_make")]["aspect_ratio"], "16:9")

    def test_failure_is_plain(self):
        r, _ = self.make(ArtMCP(vfail="Video failed: Venice refused this one (content violation, 422)"))
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        r.answer(r.question["choices"][0]); t.join(5)
        self.assertEqual(r.state, "failed")
        self.assertIn("422", r.why)


class DocRun(Base):
    STORY = "# The Oasis\n\n## Dawn\nShe woke.\n\n## Dusk\nShe left."

    def make(self, mcp, ask=True, replies=None):
        b = Brain(list(replies or [self.STORY]))
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "write my oasis story", ctypes=["text"], ask_first=ask)
        return r, b

    def test_writes_with_pictures_per_section(self):
        mcp = PicMCP()
        r, b = self.make(mcp)
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        self.assertIn("Pictures in it?", [i["q"] for i in r.question["items"]])
        r.answer("Pictures in it? → One per section (up to 4) · Also save as? → Just the text file (.md)")
        t.join(5)
        self.assertEqual(r.state, "done", r.why)
        md = (r.root / r.docs[0]["path"]).read_text()
        self.assertEqual(md.count("![](../pictures/"), 2)
        self.assertLess(md.index("## Dawn"), md.index("![]"))
        self.assertEqual(mcp.calls.count("image_make"), 2)
        self.assertIn("write my oasis story", b.calls[0])

    def test_refusals_skipped_then_fails_plainly(self):
        r, _ = self.make(PicMCP(), ask=False, replies=["I'm sorry, I can't write that."])
        r.loop()
        self.assertEqual(r.state, "failed")
        self.assertIn("No writer", r.why)

    def test_place_pictures_title(self):
        out = docrun.place_pictures("# T\n\nbody", [(-1, "../pictures/a.png")])
        self.assertLess(out.index("# T"), out.index("![](../pictures/a.png)"))


class Split(Base):
    REPLY = json.dumps({"build": "A side-scrolling game. Load dialogue from content/dialogue.json; hero is assets/hero.png.",
                        "content": {"content/dialogue.json": ["line one", "line two"], "../evil.md": "x", "story.md": "Once."},
                        "pictures": [{"file": "assets/hero.png", "prompt": "the hero", "shape": "tall", "sprite": True},
                                     {"file": "assets/bg", "prompt": "the oasis", "shape": "wide", "sprite": False}]})

    def make(self, mcp, replies, cfg=None):
        b = Brain(list(replies))
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected", **(cfg or {})}), self.project, "openrouter", "m",
                      "my oasis game with my characters", ctypes=["game"])
        return r, b

    def test_parse_keeps_files_inside_content(self):
        d = content.parse(self.REPLY)
        self.assertEqual(sorted(d["files"]), ["content/dialogue.json", "content/evil.md", "content/story.md"])
        self.assertEqual(d["pictures"][0]["aspect"], "9:16")
        self.assertIsNone(content.parse("not json"))

    def test_prepare_writes_art_and_gives_coder_a_plain_brief(self):
        mcp = PicMCP()
        r, b = self.make(mcp, [self.REPLY])
        self.assertTrue(content.wanted(r))
        content.prepare(r)
        self.assertTrue(r.split["ok"])
        self.assertTrue((r.root / "content/dialogue.json").is_file())
        self.assertEqual(len(r.split["pictures"]), 2)
        self.assertIn("magenta", mcp.args[mcp.calls.index("image_make")]["prompt"])
        self.assertNotIn("my oasis game", r.task)                  # the coder never sees his words
        self.assertIn("(sprite)", r.task)
        self.assertIn("ART RULES", r.task)
        self.assertEqual(r.task_words, "my oasis game with my characters")

    def test_unreadable_reply_leaves_task_alone(self):
        r, _ = self.make(PicMCP(), ["Sorry, I can't help with that."])
        content.prepare(r)
        self.assertFalse(r.split["ok"])
        self.assertEqual(r.task, "my oasis game with my characters")

    def test_off_for_edit_lane_standalone_or_cfg(self):
        r, _ = self.make(PicMCP(), [self.REPLY], {"art_split": False})
        self.assertFalse(content.wanted(r))
        b = Brain([self.REPLY]); b.mcp = PicMCP()
        r2 = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "fix the bug", ctypes=["game", "edit"])
        self.assertFalse(content.wanted(r2))
        r3 = agent.Run(b, config.load({}), self.project, "openrouter", "m", "x", ctypes=["game"])
        self.assertFalse(content.wanted(r3))


class PanZoom(Base):
    def test_free_moving_picture(self):
        import shutil, subprocess
        if not shutil.which("ffmpeg"):
            self.skipTest("no ffmpeg here")
        d = Path(tempfile.mkdtemp())
        src = d / "p.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=320x320", "-frames:v", "1", str(src)], check=True)
        why = video.pan_zoom(src, d / "o.mp4", 3, "9:16")
        self.assertEqual(why, "")
        self.assertEqual((d / "o.mp4").read_bytes()[4:8], b"ftyp")


class ArtRoute(Base):
    BP = ("Follow this build prompt. Modules already done: 0. Do Module 1 next and stop at its gate.\n\n"
          "# body-art — Build Prompt (2026-11-24)\n\n**Idea (Scott's words):** body art painting of a woman on a pink rug\n\n"
          "## Module 0 — Audit (read-only) → GATE\nx\n## Module 1 — Build it\ny\n## Module 2 — Live proof + handoff\nz\n")

    def test_no_chip_art_build_prompt_goes_to_picture_run(self):
        b = Brain(["detail"]); b.mcp = PicMCP()
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", self.BP, ctypes=[])
        self.assertTrue(r.art_routed and r.picture)
        self.assertEqual(r.ctypes, ["image"])
        self.assertEqual(r.plan, [])                                # no modules / gates for art
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(r.steps[0]["action"], "route")
        p = b.mcp.args[b.mcp.calls.index("image_make")]["prompt"]
        self.assertTrue(p.startswith("body art painting of a woman on a pink rug"))
        self.assertNotIn("Module", p)

    def test_chips_and_app_words_win(self):
        self.assertEqual(creation.art_route("a picture for my website", []), [])
        self.assertEqual(creation.art_route("a short video clip of waves", []), ["video"])
        self.assertEqual(creation.art_route("write a story", []), ["text"])
        self.assertEqual(creation.art_route("art", ["game"]), ["game"])
        b = Brain(["x"]); b.mcp = PicMCP()
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "fix the login bug", ctypes=[])
        self.assertFalse(r.art_routed)


class VideoPaths(Base):
    def setUp(self):
        super().setUp()
        f = video._paths_file()
        if f.exists():
            f.unlink()

    def test_picture_first_is_the_default(self):
        ps = video.all_paths()
        self.assertEqual([p["id"] for p in ps if p["star"]], ["picture_first"])
        q = video.path_question(ps)
        self.assertTrue(q[0][1][0].endswith("⭐"))

    def test_default_run_makes_a_picture_first(self):
        mcp = ArtMCP(vid_path=VideoRun.mp4(self))
        b = Brain(["detail"]); b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "x", ctypes=["video"])
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        self.assertIn("image_make", mcp.calls)                  # the first frame was drawn before the price card
        r.answer(r.question["choices"][0]); t.join(5)
        self.assertEqual(r.video_path, "picture_first")
        self.assertTrue(mcp.args[mcp.calls.index("video_make")].get("image_b64"))

    def test_toggle_star_and_custom_model_path(self):
        video.set_path({"id": "words", "on": False})
        self.assertNotIn("Just my words", video.path_question(video.all_paths())[0][1])
        video.set_path({"star": "newest"})
        self.assertEqual([p["id"] for p in video.all_paths() if p["star"]], ["newest"])
        f = video._paths_file()
        d = json.loads(f.read_text())
        d["paths"].append({"id": "kling-words", "label": "Kling v4 from my words", "kind": "words", "model": "kling-v4-text-to-video", "on": True})
        d["paths"].append({"id": "bad", "label": "x", "kind": "nope", "on": True})
        f.write_text(json.dumps(d))
        ids = [p["id"] for p in video.all_paths()]
        self.assertIn("kling-words", ids)
        self.assertNotIn("bad", ids)
        with self.assertRaises(ValueError):
            video.set_path({"id": "nope", "on": True})

    def test_custom_path_model_reaches_hermes(self):
        f = video._paths_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"star": "kling-words", "paths": [{"id": "kling-words", "label": "Kling v4 from my words", "kind": "words",
                                                                    "model": "kling-v4-text-to-video", "on": True}]}))
        mcp = ArtMCP(vid_path=VideoRun.mp4(self))
        b = Brain(["detail"]); b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "x", ctypes=["video"])
        t = threading.Thread(target=r.loop); t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        r.answer(r.question["choices"][0]); t.join(5)
        a = mcp.args[mcp.calls.index("video_make")]
        self.assertEqual(a["model"], "kling-v4-text-to-video")
        self.assertNotIn("image_b64", a)
        f.unlink()
