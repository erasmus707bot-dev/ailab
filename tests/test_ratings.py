"""⭐ ratings · 🔁 change verdicts · ✅ accept (Scott 2026-11-25)."""
import tempfile
import unittest
from pathlib import Path

from ailab import ratings, refs

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


class Ratings(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "pictures").mkdir()
        for n in ("a", "b", "src"):
            (self.root / f"pictures/{n}.png").write_bytes(PNG)
        refs.pin(self.root, "pictures/src.png", role="who")

    def test_rate_rerate_credits_sources_once(self):
        r = ratings.rate(self.root, "pictures/a.png", 5, ["nailed", "bogus"], "run1", "a fox\nLook: x", ["pictures/src.png"])
        self.assertTrue(r["ok"]); self.assertEqual(r["row"]["reasons"], ["nailed"])
        ratings.rate(self.root, "pictures/a.png", 2, ["style"])
        e = refs._load(self.root)["pool"]["pictures/src.png"]
        self.assertEqual((e["stars_sum"], e["stars_n"]), (2, 1), "re-rate replaces, sources remembered")
        self.assertFalse(ratings.rate(self.root, "../x.png", 3)["ok"])
        self.assertFalse(ratings.rate(self.root, "pictures/nope.png", 3)["ok"])

    def test_verdict_tally_and_taste(self):
        ratings.rate(self.root, "pictures/a.png", 5, [], "r1", "a red fox by a lake")
        ratings.rate(self.root, "pictures/b.png", 1, ["words"], "r2", "a blue whale")
        ratings.verdict(self.root, "r3", "r1", "make it sunset", ["pictures/a.png"], ["pictures/b.png"], "better")
        v = ratings.verdict(self.root, "r3", "r1", "make it sunset", [], [], "worse")
        self.assertEqual(v["tally"], {"better": 0, "same": 0, "worse": 1}, "one verdict per change run")
        self.assertFalse(ratings.verdict(self.root, "r4", "", "x", [], [], "meh")["ok"])
        t = ratings.taste(self.root)
        self.assertEqual(t["loved"], ["a red fox by a lake"]); self.assertIn("📝 Ignored my words", t["low"][0])
        self.assertEqual(t["bad_changes"], ["make it sunset"])

    def test_accept_keeps_row(self):
        ratings.rate(self.root, "pictures/a.png", 4)
        a = ratings.accept(self.root, "pictures/a.png", "r1", "fox", ["pictures/src.png"])
        self.assertTrue(a["row"]["accepted"]); self.assertEqual(a["row"]["stars"], 4); self.assertEqual(a["row"]["from"], ["pictures/src.png"])


if __name__ == "__main__":
    unittest.main()


class MadeFrom(unittest.TestCase):
    def test_library_rating_credits_recorded_sources(self):
        root = Path(tempfile.mkdtemp()); (root / "pictures").mkdir()
        for n in ("out", "src"):
            (root / f"pictures/{n}.png").write_bytes(PNG)
        refs.pin(root, "pictures/src.png")
        refs.note_made(root, "pictures/out.png", ["pictures/src.png"])
        r = ratings.rate(root, "pictures/out.png", 5)                     # no sources sent (📚 Library)
        self.assertEqual(r["row"]["sources"], ["pictures/src.png"])
        self.assertEqual(refs.avg(refs._load(root)["pool"]["pictures/src.png"]), 5.0)


class EditFirst(unittest.TestCase):
    """🖼 Start from in use → Venice's edit model first (Scott 2026-11-25 pick 1)."""
    def test_queue_and_start(self):
        q = ["local/juggernaut-xl-v9", "venice/lustify"]
        self.assertEqual(refs.queue(q, True, True)[:2], list(refs.REF_MODELS))
        self.assertEqual(refs.queue(q, True, True, edit_first=True)[:2], [refs.REF_MODELS[1], refs.REF_MODELS[0]])
        root = Path(tempfile.mkdtemp()); (root / "pictures").mkdir()
        (root / "pictures/s.png").write_bytes(PNG)
        self.assertEqual(refs.start_source(root), "")
        refs.pin(root, "pictures/s.png", role="start")
        self.assertEqual(refs.start_source(root), "pictures/s.png")
        refs.unpin(root, "pictures/s.png")
        self.assertEqual(refs.start_source(root), "", "off = not used")


class Steer(unittest.TestCase):
    """⭐ ratings steer the picture route, inside one side only."""
    def test_steer(self):
        root = Path(tempfile.mkdtemp()); (root / "pictures").mkdir()
        for i in range(6):
            (root / f"pictures/{i}.png").write_bytes(PNG)
            refs.note_model(root, f"pictures/{i}.png", "local/juggernaut-xl-v9" if i < 3 else "local/flux2-klein-4b")
            ratings.rate(root, f"pictures/{i}.png", 1 if i < 3 else 5)
        st = ratings.model_stats(root)
        self.assertEqual(st["local/juggernaut-xl-v9"], {"avg": 1.0, "n": 3})
        order, why = ratings.steer(["local/juggernaut-xl-v9", "local/flux2-klein-4b", "venice/lustify"], st)
        self.assertEqual(order, ["local/flux2-klein-4b", "local/juggernaut-xl-v9", "venice/lustify"])
        self.assertIn("first", why); self.assertIn("last", why)
        self.assertEqual(ratings.steer(["venice/lustify", "local/flux2-klein-4b"], {}), (["venice/lustify", "local/flux2-klein-4b"], ""))


class Strength(unittest.TestCase):
    def test_strength(self):
        root = Path(tempfile.mkdtemp()); (root / "pictures").mkdir()
        (root / "pictures/s.png").write_bytes(PNG)
        refs.pin(root, "pictures/s.png", role="style")
        self.assertEqual(refs.strength(root, "pictures/s.png"), refs.STYLE_DEFAULT)
        self.assertEqual(refs.set_strength(root, "pictures/s.png", 5)["strength"], refs.STYLE_MAX)
        self.assertEqual(refs.set_strength(root, "pictures/s.png", "0.35")["strength"], 0.35)
        self.assertEqual(refs.strength(root, "pictures/s.png"), 0.35)
        self.assertFalse(refs.set_strength(root, "pictures/x.png", 1)["ok"])
        self.assertFalse(refs.set_strength(root, "pictures/s.png", "abc")["ok"])
