"""🏃 Motion Presets M2/M5 runs (Scott 2026-11-25): the three ways in (write · pull from a video · save from a result)
end as a draft he names and saves; making pictures sends each moment's pose to a local SDXL model (a refusal falls back
to words and says so) and the cast anchors of who is in it; making video chains clips (pan-and-zoom here, $0) and joins
them; the ⛓ last-frame video path exists, off by default; the scene API turns words into blocks and back."""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from ailab import agent, batch, config, motion_fill, motion_make, motions as MO, timeline as TL, video
from ailab.mcp_client import HermesRefused
from tests.test_agent import Base, ChatResult
from tests.test_refs import RefMCP, png

WRITER = {"name": "Bench spot", "words": "person A presses the bar while person B spots",
          "roles": [{"label": "lifter"}, {"label": "spotter"}],
          "moments": [{"name": "unrack", "words": "person A lifts the bar off"}, {"name": "top", "words": "person A arms locked out"}],
          "star": 1, "shelves": ["lifting"]}


class Brain:
    def chat(self, project, prov, model, msgs, max_tokens=1024, cap_usd=None, task=""):
        sys = msgs[0]["content"]
        t = json.dumps(WRITER) if "motion preset" in sys else "strong light."
        return ChatResult(t, prov, model, 10, 5, 0.0, True)


class MotionMCP(RefMCP):
    def __init__(self, frames=None, refuse_pose=False, **kw):
        super().__init__(**kw)
        self.frames, self.refuse_pose = frames or [], refuse_pose

    def call(self, tool, args=None):
        args = args or {}
        if tool == "motion_pull":
            self.calls.append(tool)
            self.args.append(args)
            return {"ok": True, "key": "mot:1", "state": "running"}
        if tool == "job_wait" and args.get("key") == "mot:1":
            return {"state": "done", "finished": True, "result": {
                "id": "mp-0123456789abcdef", "frames": self.frames, "people": 2, "poses": bool(self.frames and self.frames[0].get("skeleton_path")),
                "poses_note": "", "camera": "low tracking", "words": "Two people. Person A lifts while person B spots.",
                "start": 1.0, "end": 5.0, "picture": False}}
        if tool == "image_make" and self.refuse_pose and args.get("pose_image"):
            self.calls.append(tool)
            self.args.append(args)
            raise HermesRefused("not_installed", "The pose model isn't installed.", "install_pose.sh --control")
        if tool == "cast_get":
            self.calls.append(tool)
            self.args.append(args)
            name = args["id"].split("-")[1].title()
            p = Path(self.anchor_dir) / f"{name}.png"
            p.write_bytes(png())
            return {"id": args["id"], "name": name, "brief": "", "anchor_path": str(p)}
        return super().call(tool, args)


class Motion(Base):
    def setUp(self):
        super().setUp()
        from ailab import picture_route
        orig = (picture_route.ready, picture_route.plan)
        picture_route.ready = lambda run: {"local/juggernaut-xl-v9"}
        picture_route.plan = lambda run, look, style, vm, forced: {"kind": "photo", "first": "local", "models": ["local/juggernaut-xl-v9"]}
        self.addCleanup(lambda: (setattr(picture_route, "ready", orig[0]), setattr(picture_route, "plan", orig[1])))
        self.assets = Path(self.tmp.name) / "assets"
        self.assets.mkdir()

    def run_(self, mcp, req, task="in a sunny gym", ctypes=("image",)):
        b = Brain()
        b.mcp = mcp
        mcp.anchor_dir = str(self.assets)
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", task, ctypes=list(ctypes),
                      batch=batch.norm(req, list(ctypes)))
        return r

    def frames(self, root):
        out = []
        for i in range(2):
            f = Path(self.tmp.name) / f"k{i}.jpg"
            f.write_bytes(png())
            s = Path(self.tmp.name) / f"pose{i}.png"
            s.write_bytes(png())
            out.append({"i": i, "t": 1.0 + 2 * i, "frame_path": str(f), "skeleton_path": str(s),
                        "people": [{"kps": [[0.3, 0.3, 0.9]] * 18}, {"kps": [[0.6, 0.3, 0.9]] * 18}]})
        return out

    # ---------- M2 three ways in
    def test_norms(self):
        self.assertIsNone(motion_fill.norm({"mode": "pull"}), "pull needs a clip")
        self.assertEqual(motion_fill.norm({"mode": "write", "words": "{A} waves"})["moments"], 4)
        self.assertEqual(batch.norm({"fill": {"mode": "write", "words": "x"}}, ["image"])["kind"], "motionfill")
        self.assertEqual(batch.norm({"motion": {"make": "video"}}, ["video"])["kind"], "motion")
        self.assertIsNone(batch.norm({"motion": {"make": "song"}}, ["image"]))

    def test_pull_from_video_then_save(self):
        m = MotionMCP()
        r = self.run_(m, {"fill": {"mode": "pull", "path": "videos/clip.mp4", "start": 1, "end": 5, "moments": 2}})
        (r.root / "videos").mkdir(parents=True, exist_ok=True)
        (r.root / "videos/clip.mp4").write_bytes(b"x" * 100)
        m.frames = self.frames(r.root)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(m.args[m.calls.index("motion_pull")]["start"], 1.0)
        d = r.batch["draft"]
        self.assertEqual(d["star"], "top")
        self.assertTrue(d["poses"])
        self.assertIn("{A} presses the bar while {B} spots", d["words"])
        out = motion_fill.save(r.id, {"name": "My bench spot", "star": 0})
        self.assertTrue(out["ok"], out)
        p = MO.get(out["motion"]["id"])
        self.assertEqual((p["name"], p["camera"], p["source"]["kind"]), ("My bench spot", "low tracking", "video"))
        self.assertTrue(p["moments"][0]["star"] and MO.asset(p["id"], p["moments"][0]["pose"]))
        self.assertFalse(motion_fill.save(r.id, {})["ok"], "a draft is saved once")

    def test_write_it(self):
        m = MotionMCP()
        r = self.run_(m, {"fill": {"mode": "write", "words": "{A} presses the bar while {B} spots", "roles": ["lifter", "spotter"],
                                   "feel": 0.9}})
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertNotIn("motion_pull", m.calls)
        out = motion_fill.save(r.id, {"name": "Written spot"})
        self.assertTrue(out["ok"], out)
        p = MO.get(out["motion"]["id"])
        self.assertEqual(p["words"], "{A} presses the bar while {B} spots", "his words kept exactly")
        self.assertGreater(p["feel"], 0.8)
        self.assertEqual(p["preview"], "preview.svg")

    def test_save_from_result_uses_the_result_file(self):
        m = MotionMCP()
        r = self.run_(m, {"fill": {"mode": "result", "path": "pictures/made.png", "prompt": "Mara lifts", "from_run": "abc"}})
        (r.root / "pictures").mkdir(parents=True, exist_ok=True)
        (r.root / "pictures/made.png").write_bytes(png())
        m.frames = self.frames(r.root)[:1]
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertTrue(m.args[m.calls.index("motion_pull")]["path"].endswith("made.png"))

    # ---------- M5 make it
    def scene(self, root):
        lift = MO.save({"name": "Bench spot", "words": "{A} presses the bar while {B} spots", "seconds": 4,
                        "moments": [{"name": "top", "words": "{A} arms locked out while {B} spots", "star": True, "pose": "poses/pose00.png"}]},
                       {"poses/pose00.png": self.frames(root)[0]["skeleton_path"]})["motion"]
        five = MO.save({"name": "High five", "words": "{A} and {B} high five", "seconds": 2,
                        "moments": [{"name": "slap", "words": "{A} and {B} palms meet", "star": True}]})["motion"]
        s = TL.blank(["Mara", "Jun", "Tess"])
        s["blocks"] = [{"preset": lift["id"], "who": {"A": "Mara", "B": "Jun"}, "dur": 4},
                       {"preset": five["id"], "who": {"A": "Mara", "B": "Jun"}, "dur": 2}]
        TL.save(root, s)

    def test_pictures_send_pose_and_cast(self):
        m = MotionMCP()
        r = self.run_(m, {"motion": {"make": "picture"}})
        self.scene(r.root)
        from ailab import cast
        cast.choose(r.root, "duo", ["c-mara-000001", "c-jun-000002"])
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        imgs = [a for c, a in zip(m.calls, m.args) if c == "image_make"]
        self.assertEqual(len(imgs), 2)
        self.assertTrue(imgs[0].get("pose_image", "").endswith("pose00.png"), "the ⭐ moment's pose guides SDXL")
        self.assertNotIn("pose_image", imgs[1], "no pose → words only")
        self.assertTrue(imgs[0]["prompt"].startswith("in a sunny gym"), "his words lead")
        self.assertIn("Tess in the background", imgs[0]["prompt"])

    def test_pose_refused_falls_back_to_words(self):
        m = MotionMCP(refuse_pose=True)
        r = self.run_(m, {"motion": {"make": "picture"}})
        self.scene(r.root)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertTrue(any(s.get("action") == "pose" and "not used" in s["why"] for s in r.steps))

    @unittest.skipUnless(shutil.which("ffmpeg"), "no ffmpeg")
    def test_video_chains_and_joins(self):
        m = MotionMCP()
        r = self.run_(m, {"motion": {"make": "video", "clips": "free"}}, ctypes=("video",))
        self.scene(r.root)
        pl = motion_make.plan(TL.load(r.root), "video", "free")
        self.assertEqual([c["start"] for c in pl["items"]][:1], ["picture"])
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertTrue(r.videos and (r.root / r.videos[-1]["path"]).is_file())

    def test_last_frame_path_is_off_by_default(self):
        row = next(p for p in video.all_paths() if p["id"] == "last_frame")
        self.assertFalse(row["on"])
        self.assertIn("last_frame", video.KINDS)

    @unittest.skipUnless(shutil.which("ffmpeg"), "no ffmpeg")
    def test_last_frame_grab(self):
        clip, out = Path(self.tmp.name) / "c.mp4", Path(self.tmp.name) / "l.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=2",
                        "-pix_fmt", "yuv420p", str(clip)], check=True, timeout=60)
        self.assertTrue(motion_make.last_frame(clip, out))

    def test_scene_api_words_and_add(self):
        from ailab.server import App
        app = App(config.load({}), lab=object())
        from ailab import preview
        root = preview.ensure_site("scratch")
        self.scene(root)
        _, v = app.motion_scene_get({"project": "scratch"})
        self.assertIn("Then Mara and Jun high five", v["words"])
        _, v2 = app.motion_scene_set({"project": "scratch", "words": "Mara and Jun high five. Then Mara and Jun bench spot"})
        self.assertEqual([v2["presets"][b["preset"]]["name"] for b in v2["resolved"]], ["High five", "Bench spot"])
        lift = next(k for k, p in v2["presets"].items() if p["name"] == "Bench spot")
        _, v3 = app.motion_scene_set({"project": "scratch", "add": {"preset": lift, "who": {"A": "Tess", "B": "Jun"}}})
        self.assertEqual(len(v3["resolved"]), 3)
        self.assertEqual(v3["plan"]["pictures"], 3)


class UI(unittest.TestCase):
    def test_wiring(self):
        html = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()
        for bit in ("function motionPicker(", "motion.row", "motion.show(", "/api/motion/scene", "/api/motion/save", "/api/motions?",
                    "🏃 Use this motion", "🏃 Save its motion", "motionDraftCard(run", "motionFill:", "✂️ Split into shots ⭐",
                    "🖼 Make pictures ⭐", "Who does", "in the background", "tlgrip"):
            self.assertIn(bit, html, bit)
