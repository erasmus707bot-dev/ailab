"""🏃 Motion Presets M1/M3/M4 (Scott 2026-11-25): preset shape + validator, store (global, versioned, trash not wipe),
search/shelves, role slots, feel words, $0 stick-figure preview, cast-and-stack (background people), timeline
timing (then / at N s / sequence per person), words ⇄ blocks both ways, the ~3-action shot split, clip cutting."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from ailab import motions as MO, timeline as TL

KPS = [[0.3, 0.2 + i * 0.03, 0.9] for i in range(18)]


def preset(name, words, roles=None, secs=4, aliases=(), camera="still", poses=False):
    ms = [{"name": "start", "words": words + " (start)"}, {"name": "top", "words": words + " at the top", "star": True}]
    if poses:
        for m in ms:
            m["people"] = [{"kps": KPS}]
    return {"name": name, "words": words, "roles": roles, "moments": ms, "seconds": secs, "aliases": list(aliases),
            "camera": camera, "shelves": ["lifting"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.environ["AILAB_HOME"] = self.home
        self.lift = MO.save(preset("Bench spot", "{A} presses the bar while {B} spots", [{"label": "lifter"}, {"label": "spotter"}],
                                   aliases=["the lift"], poses=True))["motion"]
        self.five = MO.save(preset("High five", "{A} and {B} high five", secs=2))["motion"]
        self.wave = MO.save(preset("Wave", "{A} waves", secs=2))["motion"]
        self.idle = MO.save(preset("Idle chat", "{A} chats quietly", secs=3))["motion"]
        self.P = {p["id"]: p for p in MO.all_motions()}

    def tearDown(self):
        os.environ.pop("AILAB_HOME", None)


class Library(Base):
    def test_validator_names_what_is_wrong(self):
        p = MO.clean({"name": "x", "words": "{A} lifts", "roles": [{"label": "a"}, {"label": "b"}], "moments": []})
        bad = MO.validate(p)
        self.assertTrue(any("{B}" in b for b in bad) and any("key moment" in b for b in bad))
        self.assertEqual(MO.validate(MO.clean(preset("ok", "{A} lifts"))), [])

    def test_exactly_one_star_and_ranges(self):
        p = MO.clean({"name": "x", "words": "{A} x", "moments": [{"name": "a", "star": True}, {"name": "b", "star": True}],
                      "feel_range": [0.9, 0.2], "roles": [{"label": "crowd", "min": 2, "max": 8}]})
        self.assertEqual(sum(m["star"] for m in p["moments"]), 1)
        self.assertEqual(p["feel_range"], [0.2, 0.9])
        self.assertEqual(MO.people_range(p), (2, 8))

    def test_store_is_global_versioned_and_trash_not_wipe(self):
        f = Path(self.home) / "motions" / self.lift["id"] / "motion.json"
        self.assertEqual(json.loads(f.read_text())["v"], 1)
        self.assertFalse(MO.save(preset("Bench spot", "{A} again"))["ok"], "a taken name is refused")
        self.assertTrue(MO.delete(self.wave["id"])["ok"])
        self.assertIsNone(MO.get(self.wave["id"]))
        self.assertTrue(any((Path(self.home) / "motions" / "_trash").iterdir()))

    def test_search_shelves_aliases(self):
        self.assertEqual([p["name"] for p in MO.search("spots")], ["Bench spot"])
        self.assertEqual(len(MO.search(shelf="lifting")), 4)
        self.assertEqual(MO.search(shelf="dance"), [])
        pub = MO.public()
        self.assertIn("sports", pub["shelves"]) and self.assertTrue(all("preview" in c for c in pub["motions"]))

    def test_fill_feel_and_sentence(self):
        self.assertEqual(MO.fill("{A} spots {B}", {"A": "Mara"}), "Mara spots someone")
        self.assertIn("explosive", MO.feel_word(0.95))
        self.assertEqual(MO.feel_word(0.5), "")
        s = MO.sentence(self.lift, {"A": "Mara", "B": "Jun"}, 0.1, "top")
        self.assertTrue(s.startswith("Mara presses the bar while Jun spots at the top") and "calm" in s)

    def test_preview_svg_from_poses_and_without(self):
        d = Path(self.home) / "motions"
        svg = (d / self.lift["id"] / "preview.svg").read_text()
        self.assertIn("<animate", svg) and self.assertIn("<path", svg)
        plain = (d / self.five["id"] / "preview.svg").read_text()
        self.assertIn("<circle", plain)
        self.assertIsNone(MO.asset(self.lift["id"], "../../x.svg"))
        self.assertIsNotNone(MO.asset(self.lift["id"], "preview.svg"))


class Timeline(Base):
    def scene(self):
        s = TL.blank(["Mara", "Jun", "Tess", "Kofi", "Ines"])
        s["blocks"] = [{"id": "b000001", "preset": self.lift["id"], "who": {"A": "Mara", "B": "Jun"}, "dur": 4},
                       {"id": "b000002", "preset": self.five["id"], "who": {"A": "Mara", "B": "Jun"}, "after": "b000001", "dur": 2},
                       {"id": "b000003", "preset": self.wave["id"], "who": {"A": "Tess"}, "start": 1, "dur": 2}]
        s["idle"] = {"Kofi": self.idle["id"]}
        return TL.clean(s)

    def test_timing_then_pin_sequence(self):
        r = {b["id"]: (b["t0"], b["t1"]) for b in TL.resolve(self.scene())}
        self.assertEqual(r, {"b000001": (0.0, 4.0), "b000002": (4.0, 6.0), "b000003": (1.0, 3.0)})
        self.assertEqual(TL.length(self.scene()), 6.0)
        self.assertEqual([b["id"] for b in TL.rows(self.scene())["Mara"]], ["b000001", "b000002"])

    def test_cycle_never_hangs(self):
        s = self.scene()
        s["blocks"][0]["after"] = "b000002"
        self.assertEqual(len(TL.resolve(s)), 3)

    def test_two_people_move_others_background(self):
        st = TL.stills(self.scene(), self.P)
        first = st[0]
        self.assertIn("Mara presses the bar while Jun spots at the top", first["words"])
        self.assertIn("Kofi chats quietly in the background", first["words"])
        self.assertIn("Ines in the background", first["words"])
        self.assertNotIn("Tess in the background", st[1]["words"], "Tess is waving at 1 s → stacked into that still")
        self.assertTrue(first["pose"] == "" or first["pose"])

    def test_words_round_trip(self):
        s = self.scene()
        w = TL.to_words(s, self.P)
        self.assertIn("After the bench spot, Mara and Jun high five", w)
        self.assertIn("At 1 s, Tess wave", w)
        back, notes = TL.from_words(w, self.P, s["people"])
        self.assertEqual(notes, [])
        self.assertEqual({b["id"]: (b["t0"], b["t1"]) for b in TL.resolve(back)}.__len__(), 3)
        self.assertEqual(sorted((b["t0"], b["t1"]) for b in TL.resolve(back)), [(0.0, 4.0), (1.0, 3.0), (4.0, 6.0)])

    def test_his_words_parse(self):
        s, notes = TL.from_words("Mara and Jun do the lift. After the lift, they high five with Mara and Jun. Tess waves for 3 seconds",
                                 self.P, ["Mara", "Jun", "Tess"])
        self.assertEqual(notes, [])
        r = TL.resolve(s)
        self.assertEqual([self.P[b["preset"]]["name"] for b in r], ["Bench spot", "Wave", "High five"])
        hf = next(b for b in r if self.P[b["preset"]]["name"] == "High five")
        self.assertEqual(hf["t0"], 4.0)
        self.assertEqual(next(b for b in r if b["who"] == {"A": "Tess"})["dur"], 3.0)

    def test_unknown_motion_is_named_not_guessed(self):
        _, notes = TL.from_words("Mara does a backflip", self.P, ["Mara"])
        self.assertTrue(notes and "backflip" in notes[0])

    def test_then_chains_and_feel_words(self):
        s, _ = TL.from_words("Mara and Jun bench spot explosively, then Mara and Jun high five calmly", self.P, ["Mara", "Jun"])
        a, b = TL.resolve(s)
        self.assertEqual(b["t0"], a["t1"])
        self.assertGreater(a["feel"], 0.7) and self.assertLess(b["feel"], 0.3)

    def test_busy_shot_is_split(self):
        s = TL.blank(["A1", "B1", "C1", "D1"])
        s["blocks"] = [{"preset": self.wave["id"], "who": {"A": n}, "start": 0, "dur": 4} for n in ("A1", "B1", "C1", "D1")]
        s = TL.clean(s)
        self.assertTrue(TL.too_busy(s))
        self.assertTrue(TL.too_busy(s, {"motion": {"max_actions": 3}}))
        self.assertFalse(TL.too_busy(s, {"motion": {"max_actions": 5}}))

    def test_clips_fit_the_model_length(self):
        c = TL.clips(self.scene(), self.P, 5)
        self.assertTrue(all(x["t1"] - x["t0"] <= 5.0 + 1e-6 for x in c))
        self.assertEqual(c[0]["t0"], 0.0) and self.assertEqual(c[-1]["t1"], 6.0)
        self.assertTrue(all(x["words"] for x in c))

    def test_save_load_scene(self):
        root = Path(tempfile.mkdtemp())
        TL.save(root, self.scene())
        self.assertEqual(len(TL.load(root)["blocks"]), 3)
