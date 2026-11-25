"""🎨 R2 official styles (build prompt #2, Scott 2026-11-25): no lesson bleed without promotion, promotion copies
lessons, the proposal fires once / respects Not now and Never, a chosen style feeds the writer and the Look."""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from ailab import looks, picture, shelf, styles
from ailab.server import App
from tests.test_agent import Base

LOOK = ["Watercolor", "Moody"]


def keep_n(root, n, look=LOOK, model="local/sdxl", task="a fox"):
    for i in range(n):
        shelf.keep(root, f"r{look[0]}{i}{task}", f"{task} {i}", [], {"score": 80, "caption": "fox"}, {"look": look, "model": model})


class Styles(Base):
    def setUp(self):
        super().setUp()
        self.a, self.b = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())

    def test_facts_from_run(self):
        r = SimpleNamespace(steps=[{"action": "look", "result": {"look": LOOK}}], pictures=[{"model": "local/sdxl"}], videos=[])
        self.assertEqual(styles.facts(r), {"look": LOOK, "model": "local/sdxl"})
        self.assertEqual(styles.facts(SimpleNamespace(steps=[], pictures=[], videos=[])), {})

    def test_keep_stores_look_and_model(self):
        keep_n(self.a, 1)
        x = shelf.view(self.a)["kept"][0]
        self.assertEqual((x["look"], x["model"]), (LOOK, "local/sdxl"))

    def test_no_bleed_without_promotion(self):
        keep_n(self.a, 2, task="secret-a")
        self.assertEqual(App._taste(self.b), {"kept": [], "tossed": []})
        self.assertEqual(styles.writer_note(self.b), "")
        self.assertEqual(styles.all_styles(), [])

    def test_promotion_copies_lessons_and_locks(self):
        keep_n(self.a, 2, task="fox-a")
        shelf.toss(self.a, "bad", "ugly blur", [])
        item = shelf.view(self.a)["kept"][-1]
        r = styles.promote(self.a, "Ink Fox", item, "projA")
        self.assertTrue(r["ok"])
        st = styles.get("ink fox")
        self.assertTrue(st["locked"])
        self.assertEqual((st["look"], st["model"]), (LOOK, "local/sdxl"))
        self.assertTrue(any(l.startswith("kept: fox-a") and "👁" in l for l in st["prompt_lessons"]))
        self.assertIn("avoid: ugly blur", st["prompt_lessons"])
        self.assertFalse(styles.promote(self.a, "INK FOX", item)["ok"], "a locked style is never overwritten")

    def test_choose_feeds_writer_look_and_taste_in_other_project(self):
        keep_n(self.a, 1, task="fox-a")
        styles.promote(self.a, "Ink Fox", shelf.view(self.a)["kept"][0])
        self.assertTrue(styles.choose(self.b, "Ink Fox")["ok"])
        self.assertEqual(styles.project_look(self.b), LOOK)
        self.assertEqual(looks.saved()["last"], LOOK)
        self.assertIn("fox-a", styles.writer_note(self.b))
        t = App._taste(self.b)
        self.assertEqual(t["kept"], [])                          # project B's own lessons stay empty
        self.assertEqual(t["style"]["name"], "Ink Fox")
        run = SimpleNamespace(root=self.b)
        self.assertIn("Ink Fox", picture._style_note(run))
        self.assertFalse(styles.choose(self.b, "nope")["ok"])
        styles.choose(self.b, "")
        self.assertEqual(styles.project_look(self.b), [])

    def test_proposal_fires_at_four_once_and_yes_locks(self):
        keep_n(self.a, 3)
        self.assertIsNone(styles.proposal(self.a, "A"))
        keep_n(self.a, 1, task="more")
        p = styles.proposal(self.a, "A")
        self.assertEqual(p["count"], 4)
        self.assertFalse(styles.answer(self.a, "A", p["sig"], "yes", "")["ok"], "yes needs a name")
        self.assertTrue(styles.answer(self.a, "A", p["sig"], "yes", "Moody WC")["ok"])
        self.assertIsNone(styles.proposal(self.a, "A"), "covered now")

    def test_not_now_snoozes_and_never_is_final(self):
        keep_n(self.a, 4)
        p = styles.proposal(self.a, "A")
        styles.answer(self.a, "A", p["sig"], "later")
        self.assertIsNone(styles.proposal(self.a, "A"))
        keep_n(self.a, 3, task="b")
        self.assertIsNone(styles.proposal(self.a, "A"))
        keep_n(self.a, 1, task="c")
        p = styles.proposal(self.a, "A")
        self.assertEqual(p["count"], 8)
        styles.answer(self.a, "A", p["sig"], "never")
        keep_n(self.a, 8, task="d")
        self.assertIsNone(styles.proposal(self.a, "A"))
        self.assertEqual(styles.all_styles(), [], "nothing official without his tap")

    def test_mixed_looks_do_not_count_together(self):
        keep_n(self.a, 2)
        keep_n(self.a, 2, look=["Oil paint"])
        keep_n(self.a, 2, model="venice/x")
        self.assertIsNone(styles.proposal(self.a, "A"))

    def test_ui_wiring(self):
        html = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()
        for s in ('"/api/styles/make"', '"/api/styles/choose"', '"/api/styles/answer"', "🔒 Make this an official style", "Never for this look"):
            self.assertIn(s, html)
