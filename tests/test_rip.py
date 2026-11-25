"""🎞 M4 video breakdown in the Lab: frame path guard, recipe → words with the chosen cast swapped in, recipe shelf,
📌 frame copied + pinned, improver sees the shelf, UI wiring."""
from __future__ import annotations

import os
from pathlib import Path

from ailab import cast, refs, rip
from tests.test_cast import CastBase
from tests.test_refs import png

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()
BID = "bd-0123456789abcdef"


class BdMCP:
    def __init__(self, frame):
        self.frame, self.calls = frame, []

    def call(self, tool, args=None):
        self.calls.append((tool, args))
        if tool == "breakdown_get":
            return {"id": BID, "title": "arm wrestle", "scenes": [{"i": 0, "start": 0.0, "end": 2.5, "frame_path": str(self.frame),
                    "recipe": {"subject": "person A arm-wrestles person B", "setting": "a bar table", "motion": "arms tip left",
                               "framing": "medium, eye level", "camera": "push in", "light": "warm lamp light"}}]}
        if tool == "cast_get":
            return {"id": args["id"], "name": {"c-mara-1": "Mara", "c-jun-2": "Jun"}[args["id"]]}
        raise AssertionError(tool)


class Rip(CastBase):
    def setUp(self):
        super().setUp()
        self.hd = Path(self.tmp.name) / "hd"
        os.environ["HERMES_DATA"] = str(self.hd)
        self.addCleanup(lambda: os.environ.pop("HERMES_DATA", None))
        self.frame = self.hd / "breakdowns" / BID / "frames" / "s000m.jpg"
        self.frame.parent.mkdir(parents=True)
        self.frame.write_bytes(png())
        self.m = BdMCP(self.frame)

    def test_frame_guard(self):
        self.assertEqual(rip.frame_file(str(self.frame)), self.frame.resolve())
        (self.hd / "settings").mkdir()
        (self.hd / "settings/a.jpg").write_bytes(png())
        for bad in (str(self.hd / "settings/a.jpg"), str(self.frame.parent.parent / "breakdown.json"), str(self.root / "pictures/p0.png"), ""):
            self.assertIsNone(rip.frame_file(bad), bad)

    def test_make_like_swaps_cast_and_shelves(self):
        cast.choose(self.root, "Mara & Jun", ["c-mara-1", "c-jun-2"])
        r = rip.make_like(self.m, self.root, BID, 0)
        self.assertTrue(r["ok"])
        self.assertTrue(r["task"].startswith("Mara arm-wrestles Jun, a bar table"))
        self.assertIn("camera push in", r["task"])
        self.assertEqual(rip.shelf(self.root)[-1]["words"], r["task"])
        rip.make_like(self.m, self.root, BID, 0)
        self.assertEqual(len(rip.shelf(self.root)), 1, "same scene twice = one shelf row")

    def test_without_cast_people_stay_person_a_b(self):
        self.assertIn("person A arm-wrestles person B", rip.make_like(self.m, self.root, BID, 0)["task"])

    def test_use_frame_copies_and_pins(self):
        r = rip.use_frame(self.m, self.root, BID, 0)
        self.assertTrue(r["ok"])
        self.assertTrue((self.root / r["path"]).is_file())
        self.assertIn(r["path"], refs.get(self.root))
        self.assertTrue(self.frame.is_file(), "the breakdown keeps its own frame")

    def test_improver_sees_recipe_shelf(self):
        from ailab import server
        rip.shelve(self.root, {"id": BID, "scene": 0, "words": "Mara arm-wrestles Jun, camera push in"})
        t = server.App._taste(self.root)
        self.assertEqual(t["recipes"], ["Mara arm-wrestles Jun, camera push in"])

    def test_ui_wiring(self):
        for s in ("function breakdownBox", "🎞 Break it down", "🎬 Make one like this", "📌 Use frame as reference",
                  "/api/breakdown/start", "/api/breakdown/search", "/api/breakdown/status", "make: task =>"):
            self.assertIn(s, HTML)
