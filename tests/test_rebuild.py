"""🎬 R3 Video Rebuild: beat splitter, recipes carry no source-person looks, identity points + parser, synced-review
offsets, a whole run (stills with cast refs → 👁 identity → pan-and-zoom → joined), retry one beat leaves the rest,
no spend without a tap, a private source blocks level 3, lip sync says not available."""
from __future__ import annotations

import base64
import os
from pathlib import Path

from ailab import batch, cast, rebuild
from tests.test_agent import Base
from tests.test_cast import CastBase
from tests.test_refs import RefMCP, png

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()
BID = "bd-00112233445566aa"
SCENES = [
    {"i": 0, "start": 0.0, "end": 3.0, "said": "ready set", "frame_path": "",
     "recipe": {"subject": "person A with long blonde hair grips person B's hand", "setting": "a bar table", "motion": "arms tense",
                "framing": "medium", "camera": "static", "light": "warm lamp"}},
    {"i": 1, "start": 3.0, "end": 11.0, "said": "go go go push harder now yes", "frame_path": "",
     "recipe": {"subject": "person B resists as person A forces the arm down", "setting": "a bar table", "motion": "arm tips left",
                "framing": "close-up", "camera": "push in", "light": "warm lamp"}},
]
MARA = {"id": "c-mara-000001", "name": "Mara", "brief": "Mara: a 30-year-old woman, tall", "anchor_path": "",
        "traits": {"hair_colour": "copper red", "outfit_colour": "forest green"}}
JUN = {"id": "c-jun-000002", "name": "Jun", "brief": "Jun: a 34-year-old man, stocky", "anchor_path": "",
       "traits": {"hair_colour": "jet black", "outfit_colour": "mustard yellow"}}


class Pure(Base):
    def test_norm_defaults_and_guards(self):
        n = rebuild.norm({"bd": BID})
        self.assertEqual((n["mode"], n["level"], n["audio"], n["voice"], n["clips"], n["retry"]), ("whole", 2, "narrate", "narrator", "free", None))
        self.assertIsNone(rebuild.norm({"bd": "../x"}))
        self.assertEqual(rebuild.norm({"bd": BID, "level": 3, "retry": 2, "picks": [1, "0", -1, "x"]})["picks"], [0, 1])
        self.assertEqual(batch.norm({"rebuild": {"bd": BID}}, ["image"])["kind"], "rebuild")

    def test_beats_split_busy_scenes_2_to_4_s(self):
        bs = rebuild.beats(SCENES)
        self.assertEqual([(b["scene"], b["start"], b["end"]) for b in bs], [(0, 0.0, 3.0), (1, 3.0, 7.0), (1, 7.0, 11.0)])
        self.assertTrue(all(2 <= b["end"] - b["start"] <= 4 for b in bs))
        self.assertEqual([b["k"] for b in bs], [0, 1, 2])
        self.assertEqual(len(rebuild.beats([{**SCENES[1], "end": 14.0}])), 3, "11 s → three beats of ~3.7 s")
        self.assertEqual(" ".join(b["said"] for b in bs[1:]).split(), "go go go push harder now yes".split())
        self.assertEqual([b["scene"] for b in rebuild.beats(SCENES, [1])], [1, 1])

    def test_recipe_never_carries_source_looks(self):
        for b in rebuild.beats(SCENES):
            self.assertFalse(rebuild.has_looks(b["recipe"]), b["recipe"])
        w = rebuild.words_for(rebuild.beats(SCENES)[0], [MARA, JUN])
        self.assertNotIn("blonde", w)
        self.assertTrue(w.startswith("Mara (a 30-year-old woman, tall) grips Jun"), w)
        self.assertNotIn("long", w.split("grips")[0])

    def test_identity_points_and_failures(self):
        pts = rebuild.identity_points([MARA, JUN])
        kinds = [p["kind"] for p in pts]
        self.assertEqual(kinds, ["count", "identity", "identity", "swap", "limbs", "onlooker", "onlooker"])
        self.assertIn("exactly 2 main people", pts[0]["q"])
        self.assertIn("watching in the background", pts[0]["q"])
        self.assertFalse(pts[3]["want"] or pts[4]["want"])
        rows = [{"kind": "count", "ok": True, "what": "2"}, {"kind": "swap", "ok": False, "what": "no swap"},
                {"kind": "show", "ok": False, "what": "table"}, {"kind": "limbs", "ok": None, "what": "limbs"}]
        self.assertEqual(rebuild.identity_failed(rows), ["no swap"])

    def test_onlooker_copy_is_an_identity_miss_with_a_fix(self):
        """R4 shot 7: the spectator had Dina's grey hair + Mara's plum top; hair OR clothes, one point per cast member."""
        from ailab import eyes
        pts = rebuild.identity_points([MARA, JUN])
        self.assertEqual([p["kind"] for p in pts][-2:], ["onlooker", "onlooker"])
        a, b = pts[-2:]
        self.assertFalse(a["want"] or b["want"])
        self.assertIn("copper red hair or wears forest green clothes", a["q"])
        self.assertIn("jet black hair or wears mustard yellow clothes", b["q"])
        self.assertIn("main 2 people", a["q"])
        row = {**a, "ok": False}
        self.assertEqual(rebuild.identity_failed([row]), [a["what"]])
        fix = eyes.fix_words([row])
        self.assertIn("plain dark clothes (not forest green)", fix)
        self.assertIn("not copper red", fix)
        self.assertNotIn("clearly show", fix)
        self.assertEqual(eyes.onlooker_points([("", "red")]), [])
        self.assertEqual([p["kind"] for p in rebuild.identity_points([{"name": "X"}])], ["count"])

    def test_story_shot_gets_the_onlooker_point(self):
        from ailab import story
        cast_ = {"aria": {"name": "Aria", "brief": "Aria: a woman with copper red hair wearing a royal blue outfit"}}
        pts = story.onlooker_pts({"who": ["Aria"]}, {"people": []}, cast_)
        self.assertIn("copper red hair or wears royal blue clothes", pts[0]["q"])
        self.assertIn("main person", pts[0]["q"])
        self.assertEqual(story.onlooker_pts({"who": ["Aria"]}, {"people": []}, {"aria": {"name": "Aria", "brief": "tall"}}), [])

    def test_cast_for_maps_letters(self):
        b = rebuild.beats(SCENES)[0]
        self.assertEqual([c["name"] for c in rebuild.cast_for(b, [MARA, JUN])], ["Mara", "Jun"])
        solo = {**b, "recipe": {**b["recipe"], "subject": "person B waits"}}
        self.assertEqual([c["name"] for c in rebuild.cast_for(solo, [MARA, JUN])], ["Jun"])

    def test_sync_table_offsets(self):
        bs = rebuild.beats(SCENES)
        for x in bs:
            x["clip"] = "c.mp4"
        t = rebuild.table(bs)
        self.assertEqual([(r["out_start"], r["out_end"]) for r in t], [(0, 3), (3, 7), (7, 11)])
        self.assertEqual(rebuild.src_time(t, 1.5), 1.5)
        self.assertAlmostEqual(rebuild.src_time(t, 5.0), 5.0, places=1)
        self.assertEqual(rebuild.src_time(t, 99), 11.0)

    def test_private_blocks_level3(self):
        self.assertIn("private", rebuild.level3_block(True))
        self.assertIn("none is wired", rebuild.level3_block(False))


class RbMCP(RefMCP):
    def __init__(self, scenes=SCENES, private=False, identity_ok=True):
        super().__init__(same=True)
        self.scenes, self.private, self.identity_ok, self.spent_tools = scenes, private, identity_ok, []

    def call(self, tool, args=None):
        args = args or {}
        if tool == "breakdown_get":
            return {"id": BID, "title": "arm wrestle", "state": "done", "path": "", "private": self.private, "scenes": self.scenes}
        if tool == "cast_get":
            return {"c-mara-000001": MARA, "c-jun-000002": JUN}[args["id"]]
        if tool in ("video_make", "video_quote"):
            self.spent_tools.append(tool)
        if tool == "narrate":
            self.calls.append(tool)
            self.args.append(args)
            return {"b64": base64.b64encode(b"RIFF0000WAVEfmt ").decode()}
        if tool == "narrate_status":
            return {"available": True, "voices": ["af_heart", "am_adam"]}
        if tool == "vision_check":
            self.points = args["points"]
            self.calls.append(tool)
            self.args.append(args)
            return {"ok": True, "key": "vis:1"}
        if tool == "job_wait" and args.get("key") == "vis:1":
            ans = []
            for i, q in enumerate(self.points):
                yes = True
                if "merged" in q or "AND wear" in q or "written text" in q or "anyone else" in q:
                    yes = not self.identity_ok if "AND wear" in q else False
                ans.append({"n": i + 1, "q": q, "yes": yes})
            return {"state": "done", "finished": True, "result": {"caption": "two people", "answers": ans}}
        return super().call(tool, args)


class Run(CastBase):
    def _go(self, m, extra=None, task="Rebuild with my cast"):
        self._local_up()
        r = self._run(m, task=task, batch_req={"rebuild": {"bd": BID, **(extra or {})}})
        cast.choose(r.root, "Mara & Jun", ["c-mara-000001", "c-jun-000002"])
        orig = rebuild.story.segment if hasattr(rebuild, "story") else None
        return r

    def setUp(self):
        super().setUp()
        from ailab import makers, story
        self._orig = (story.segment, story.join)
        story.segment = lambda clip, wav, secs, aspect, out: (out.write_bytes(b"x" * 2000), "")[1]
        story.join = lambda pieces, out: (out.parent.mkdir(parents=True, exist_ok=True), out.write_bytes(b"y" * 4000), "")[2]
        self.addCleanup(lambda: (setattr(story, "segment", self._orig[0]), setattr(story, "join", self._orig[1])))
        from ailab import video
        self._pz = video.pan_zoom
        video.pan_zoom = lambda src, out, secs, aspect: (out.parent.mkdir(parents=True, exist_ok=True), out.write_bytes(b"z" * 2000), "")[2]
        self.addCleanup(lambda: setattr(video, "pan_zoom", self._pz))
        orig_write = makers.write
        makers.write = lambda run, s, u, t, label, task: ('["Ready?", "Push!", "Harder!", "Done."]', "w") if "Re-telling" in label else orig_write(run, s, u, t, label, task)
        self.addCleanup(lambda: setattr(makers, "write", orig_write))

    def test_whole_run_makes_film_with_identity_checks_and_no_spend(self):
        m = RbMCP()
        r = self._go(m)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        rec = rebuild.record(r.root, BID)
        self.assertEqual(len(rec["beats"]), 3)
        self.assertTrue(rec["film"] and (r.root / rec["film"]).is_file())
        self.assertTrue(rec["personal"])
        self.assertEqual(len(rec["table"]), 3)
        self.assertTrue(all(b["identity"] == [] for b in rec["beats"]))
        self.assertTrue(any("exactly 2 main people" in q or "exactly 1 main person" in q for q in m.points))
        self.assertEqual(m.spent_tools, [], "pan-and-zoom default never calls a paid tool")
        self.assertEqual([b.get("line") for b in rec["beats"]], ["Ready?", "Push!", "Harder!"])
        self.assertEqual(m.calls.count("narrate"), 3)
        self.assertIn("🔒", r.why)

    def test_identity_swap_triggers_one_free_remake_and_is_reported(self):
        m = RbMCP(identity_ok=False)
        r = self._go(m)
        r.loop()
        rec = rebuild.record(r.root, BID)
        self.assertTrue(all(b["identity"] for b in rec["beats"]))
        self.assertEqual(m.calls.count("image_make"), 6, "3 beats × (first try + one $0 remake)")
        self.assertIn("identity trouble", r.why)

    def test_retry_one_beat_leaves_others(self):
        m = RbMCP()
        r = self._go(m)
        r.loop()
        before = {b["k"]: b["still"] for b in rebuild.record(r.root, BID)["beats"]}
        m2 = RbMCP()
        r2 = self._go(m2, {"retry": 2}, task="Retry shot 3")
        r2.loop()
        after = {b["k"]: b["still"] for b in rebuild.record(r2.root, BID)["beats"]}
        self.assertEqual(m2.calls.count("image_make"), 1)
        self.assertEqual({k: v for k, v in after.items() if k != 2}, {k: v for k, v in before.items() if k != 2})
        self.assertNotEqual(after[2], before[2])
        self.assertEqual(rebuild.record(r2.root, BID)["beats"][2]["retries"], 1)

    def test_level3_private_and_lipsync_say_so(self):
        m = RbMCP(private=True)
        r = self._go(m, {"level": 3, "voice": "lipsync"})
        r.loop()
        notes = rebuild.record(r.root, BID)["notes"]
        self.assertTrue(any("private" in n for n in notes))
        self.assertTrue(any("Lip sync" in n for n in notes))
        self.assertEqual(m.spent_tools, [])
        self.assertEqual({a.get("voice") for t, a in zip(m.calls, m.args) if t == "narrate"}, {"af_heart", "am_adam"})

    def test_no_cast_or_unfinished_breakdown_explains(self):
        self._local_up()
        m = RbMCP()
        r = self._run(m, task="Rebuild", batch_req={"rebuild": {"bd": BID}})
        r.loop()
        self.assertIn("Pick a cast first", r.why)

    def test_venice_asks_price_before_spending(self):
        m = RbMCP()
        r = self._go(m, {"clips": "venice"})
        r.ask_first = False
        import threading
        t = threading.Thread(target=r.loop, daemon=True)
        t.start()
        for _ in range(400):
            if r.question:
                break
            t.join(0.01)
        self.assertIsNotNone(r.question, "a price card is shown")
        self.assertIn("Venice clips", r.question["text"])
        self.assertNotIn("video_make", m.spent_tools)
        r.stop() if hasattr(r, "stop") else None


class UI(Base):
    def test_ui_wiring(self):
        for s in ("function rebuildBox", "🔁 Whole video", "🎯 Pick scenes", "🔁 Retry this shot", "✅ Keep whole rebuild",
                  "/api/rebuild/src", "rebuild: (title, opts)", "🎬 Rebuild a video with my cast", ".rbpair"):
            self.assertIn(s, HTML)


class Motion(Run):
    """🏃 level 3 with a probed host: price card first, tap → picture + driving clip; private still never leaves."""
    def setUp(self):
        super().setUp()
        import json as _j
        self.hd = Path(self.tmp.name) / "hd"
        os.environ["HERMES_DATA"] = str(self.hd)
        self.addCleanup(lambda: os.environ.pop("HERMES_DATA", None))
        (self.hd / "settings").mkdir(parents=True)
        (self.hd / "settings/motion_probe.json").write_text(_j.dumps({"ok": True, "models": [
            {"id": "kling-v3-pro-motion-control", "usd_5s": 0.9}, {"id": "kling-v3-standard-motion-control", "usd_5s": 0.5}]}))
        self.src = self.hd / "ailab" / "src.mp4"
        self.src.parent.mkdir(parents=True)
        self.src.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 3000)
        self._cut = rebuild.cut_clip
        rebuild.cut_clip = lambda src, a, b, out: (out.parent.mkdir(parents=True, exist_ok=True), out.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"1" * 2000), True)[2]
        self.addCleanup(lambda: setattr(rebuild, "cut_clip", self._cut))
        self._fa = rebuild.frames_at
        rebuild.frames_at = lambda clip, n=3: [png()]
        self.addCleanup(lambda: setattr(rebuild, "frames_at", self._fa))

    def test_host_picks_standard_first(self):
        self.assertEqual(rebuild.motion_host(), {"model": "kling-v3-standard-motion-control", "usd_5s": 0.5})
        self.assertEqual(rebuild.level3_block(False, rebuild.motion_host()), "")
        self.assertIn("private", rebuild.level3_block(True, rebuild.motion_host()))

    def _mcp(self, private=False):
        test = self

        class M(RbMCP):
            def call(self, tool, args=None):
                args = args or {}
                if tool == "breakdown_get":
                    return {"id": BID, "title": "arm wrestle", "state": "done", "path": str(test.src), "private": private, "scenes": SCENES}
                if tool == "video_quote":
                    self.spent_tools.append(tool)
                    return {"usd": 0.5, "today_usd": 0.0, "daily_cap": 5.0}
                if tool == "video_make":
                    self.spent_tools.append(tool)
                    self.calls.append(tool)
                    self.args.append(args)
                    out = Path(test.tmp.name) / "venice.mp4"
                    out.write_bytes(b"v" * 3000)
                    self._out = str(out)
                    return {"key": "vid:1", "est_usd": 0.5}
                if tool == "job_wait" and args.get("key") == "vid:1":
                    return {"state": "done", "finished": True, "result": {"path": self._out, "usd": 0.5}}
                return super().call(tool, args)
        return M()

    def _answer_when_asked(self, r, choice_prefix):
        import threading
        t = threading.Thread(target=r.loop, daemon=True)
        t.start()
        for _ in range(600):
            if r.question:
                break
            t.join(0.01)
        self.assertIsNotNone(r.question)
        q = r.question
        pick = next(c for c in q["choices"] if c.startswith(choice_prefix))
        r.answer(pick) if hasattr(r, "answer") else r._answer(pick)
        t.join(10)
        return q

    def test_price_card_then_tap_sends_still_and_driver(self):
        m = self._mcp()
        r = self._go(m, {"level": 3})
        q = self._answer_when_asked(r, "▶")
        self.assertIn("Same movement", q["text"])
        self.assertIn("$1.50 total", q["text"])
        makes = [a for t, a in zip(m.calls, m.args) if t == "video_make"]
        self.assertEqual(len(makes), 3)
        self.assertTrue(all(a["model"] == "kling-v3-standard-motion-control" and a["video_b64"] and a["image_b64"] for a in makes))
        rec = rebuild.record(r.root, BID)
        self.assertTrue(all(b.get("level") == 3 for b in rec["beats"]))

    def test_saying_no_spends_nothing(self):
        m = self._mcp()
        r = self._go(m, {"level": 3})
        self._answer_when_asked(r, "🎯")
        self.assertNotIn("video_make", m.spent_tools)
        self.assertTrue(any("not bought" in n for n in rebuild.record(r.root, BID)["notes"]))

    def test_private_never_quotes(self):
        m = self._mcp(private=True)
        r = self._go(m, {"level": 3})
        r.loop()
        self.assertEqual(m.spent_tools, [])


class LiveR4(Base):
    """Live R4 2026-11-25: close-ups of one face were drawn with both women; arm-wrestles were drawn standing."""
    def test_in_frame_wins_and_pose_goes_in(self):
        sc = {**SCENES[0], "recipe": {**SCENES[0]["recipe"], "in_frame": "1 — only person B's face",
                                       "pose": "person A and person B sit at a table, right elbows on it, hands gripped, person B has long blonde hair"}}
        b = rebuild.beats([sc])[0]
        self.assertEqual([c["name"] for c in rebuild.cast_for(b, [MARA, JUN])], ["Jun"])
        w = rebuild.words_for(b, [MARA, JUN])
        self.assertIn("only Jun in the frame", w)
        self.assertIn("Mara and Jun sit at a table, right elbows on it", w)
        self.assertNotIn("blonde", w)
        pts = rebuild.check_points(b, [MARA, JUN])
        self.assertIn("exactly 1 main person", pts[0]["q"])
        self.assertTrue(any(p["q"].startswith("Are the people placed like this") for p in pts))

    def test_bad_in_frame_falls_back(self):
        sc = {**SCENES[0], "recipe": {**SCENES[0]["recipe"], "in_frame": "2 — person A"}}
        b = rebuild.beats([sc])[0]
        self.assertEqual([c["name"] for c in rebuild.cast_for(b, [MARA, JUN])], ["Mara", "Jun"])
