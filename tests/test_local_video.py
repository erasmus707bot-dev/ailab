"""🏠🎬 local video path + 🔒 locked 14B (2026-11-24, Scott: "keep 14B model off by default. takes an unlock button")."""
import threading

from ailab import agent, config, video
from tests.test_art_forms import ArtMCP, VideoRun
from tests.test_picture import Base, Brain
from tests.test_workflow import wait_for


class LocalMCP(ArtMCP):
    """Local model: $0 quote, and (lfail) a failed local job; anything else answers like Venice."""

    def __init__(self, lfail="", lrefuse=False, **k):
        super().__init__(**k)
        self.lfail, self.lrefuse, self.last = lfail, lrefuse, ""

    def call(self, tool, args=None):
        a = args or {}
        local = str(a.get("model", "")).startswith("local/")
        if tool == "video_quote" and local:
            self.calls.append(tool); self.args.append(a)
            if self.lrefuse:
                from ailab.mcp_client import HermesRefused
                raise HermesRefused("not_enabled", "Wan 2.2 5B isn't downloaded on gandalf yet.", "run install_video.sh")
            return {"ok": True, "usd": 0.0, "model": a["model"], "today_usd": 4.49, "daily_cap": 5.0, "fits": True}
        if tool == "video_make":
            self.last = "local" if local else "venice"
        if tool == "job_wait" and a.get("key", "").startswith("vid:") and self.last == "local" and self.lfail:
            self.calls.append(tool); self.args.append(a)
            return {"ok": True, "state": "failed", "finished": True, "error": {"message": self.lfail}}
        return super().call(tool, args)


class Paths(Base):
    def setUp(self):
        super().setUp()
        f = video._paths_file()
        if f.exists():
            f.unlink()

    def test_5b_on_14b_locked_off(self):
        ps = {p["id"]: p for p in video.all_paths()}
        self.assertTrue(ps["local_5b"]["on"] and not ps["local_5b"]["locked"])
        self.assertTrue(ps["local_14b"]["locked"] and not ps["local_14b"]["on"] and not ps["local_14b"]["unlocked"])
        self.assertEqual([p["id"] for p in ps.values() if p["star"]], ["picture_first"])       # default unchanged
        self.assertFalse(any("14B" in c for c in video.path_question(list(ps.values()))[0][1]))

    def test_locked_cant_switch_on_or_star_until_unlocked(self):
        for body in ({"id": "local_14b", "on": True}, {"star": "local_14b"}):
            with self.assertRaises(ValueError):
                video.set_path(body)
        self.assertFalse({p["id"]: p for p in video.all_paths()}["local_14b"]["on"])
        video.set_path({"id": "local_14b", "unlock": True})
        p = {p["id"]: p for p in video.all_paths()}["local_14b"]
        self.assertTrue(p["unlocked"] and not p["on"])                    # unlocked ≠ on: still his switch
        video.set_path({"id": "local_14b", "on": True})
        video.set_path({"star": "local_14b"})
        self.assertTrue(any("14B" in c for c in video.path_question(video.all_paths())[0][1]))
        video.set_path({"id": "local_14b", "unlock": False})              # lock again → off, star moves on
        p = {p["id"]: p for p in video.all_paths()}
        self.assertTrue(not p["local_14b"]["on"] and not p["local_14b"]["star"] and sum(x["star"] for x in p.values()) == 1)

    def test_file_cant_remove_the_lock(self):
        import json
        video._paths_file().parent.mkdir(parents=True, exist_ok=True)
        video._paths_file().write_text(json.dumps({"paths": [{"id": "local_14b", "on": True, "locked": False}]}))
        p = {p["id"]: p for p in video.all_paths()}["local_14b"]
        self.assertTrue(p["locked"] and not p["on"])
        with self.assertRaises(ValueError):
            video.set_path({"id": "words", "unlock": True})                # no lock on that one


class LocalRun(Base):
    def setUp(self):
        super().setUp()
        f = video._paths_file()
        if f.exists():
            f.unlink()
        video.set_path({"star": "local_5b"})

    def go(self, mcp):
        b = Brain(["she turns slowly"]); b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "x", ctypes=["video"])
        t = threading.Thread(target=r.loop); t.start()
        return r, t

    def test_local_clip_no_price_card_no_spend(self):
        mcp = LocalMCP(vid_path=VideoRun.mp4(self), quote=0.0)
        r, t = self.go(mcp)
        t.join(8)
        self.assertFalse(t.is_alive())                                    # never stopped to ask a price
        a = mcp.args[mcp.calls.index("video_make")]
        self.assertEqual(a["model"], "local/wan22-5b")
        self.assertTrue(a.get("image_b64"))                               # first frame drawn, then brought to life
        self.assertEqual(r.state, "done")

    def test_local_fails_then_venice_price_card(self):
        mcp = LocalMCP(vid_path=VideoRun.mp4(self), lfail="Video failed: ComfyUI failed: out of memory")
        r, t = self.go(mcp)
        self.assertTrue(wait_for(lambda: r.question is not None))        # the Venice price card — nothing spent yet
        self.assertEqual(mcp.calls.count("video_make"), 1)
        self.assertIn("$0.35", r.question["text"])
        r.answer(r.question["choices"][0]); t.join(8)
        makes = [a for c, a in zip(mcp.calls, mcp.args) if c == "video_make"]
        self.assertEqual(len(makes), 2)
        self.assertNotIn("model", makes[1])                               # Hermes's default 🔓 Venice model
        self.assertEqual(r.state, "done")

    def test_local_not_downloaded_goes_to_price_card(self):
        mcp = LocalMCP(vid_path=VideoRun.mp4(self), lrefuse=True)
        r, t = self.go(mcp)
        self.assertTrue(wait_for(lambda: r.question is not None))
        self.assertNotIn("video_make", mcp.calls)
        r.answer(r.question["choices"][-1]); t.join(8)                    # ✖ Don't make it
        self.assertNotIn("video_make", mcp.calls)
