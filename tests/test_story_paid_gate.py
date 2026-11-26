"""💳 Story stills never fall to a paid picture model in silence (live 2026-11-25, ch3 on project test: the local
model wasn't ready, every still went to Venice's edit model at $0.04 — $0.32 for a chapter that cost $0 before).
No local model ready → wait for it, then ask: wait more / pay / stop. "Pay" holds for the chapter."""
from __future__ import annotations

import threading
import unittest

from ailab import agent, picture, picture_route, story


class Clock:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


class FakeRun:
    def __init__(self, answers=(), cfg=None):
        self.batch, self.cfg = {}, cfg if cfg is not None else {"story": {"local_wait_s": 0}}
        self.answers, self.asked, self.steps = list(answers), [], []
        self.question, self.why, self.last_progress = None, "", 0
        self.stop_flag = threading.Event()

    def _check_stop(self):
        if self.stop_flag.is_set():
            raise agent.Stopped(self.why)

    def _record(self, step):
        self.steps.append(step)

    def _wait(self):
        self.asked.append(self.question)
        self.question = None
        return self.answers.pop(0)


class PaidGate(unittest.TestCase):
    def setUp(self):
        self.ready = set()
        self.rows = [{"id": "venice/qwen-edit-uncensored", "usd_per_image": 0.04}, {"id": "venice/lustify", "usd_per_image": 0.01}]
        self.clock = Clock()
        saved = (picture_route.ready, picture_route.rows, picture_route.forget, picture.stage, story.time)
        picture_route.ready = lambda run: set(self.ready)
        picture_route.rows = lambda run: self.rows
        picture_route.forget = lambda: None
        picture.stage = lambda run, icon, text: None
        story.time = self.clock
        self.addCleanup(lambda: (setattr(picture_route, "ready", saved[0]), setattr(picture_route, "rows", saved[1]),
                                 setattr(picture_route, "forget", saved[2]), setattr(picture, "stage", saved[3]),
                                 setattr(story, "time", saved[4])))

    def test_local_ready_no_question(self):
        self.ready = {"local/flux2-klein-4b"}
        r = FakeRun()
        story.paid_gate(r, True, 8)
        self.assertEqual(r.asked, [])

    def test_with_refs_only_the_local_ref_model_counts(self):
        self.ready = {"local/juggernaut-xl-v9"}             # no reference support → still asks
        r = FakeRun(["💳 Pay"])
        story.paid_gate(r, True, 8)
        self.assertEqual(len(r.asked), 1)
        r2 = FakeRun()
        story.paid_gate(r2, False, 8)                        # no references: any local model will do
        self.assertEqual(r2.asked, [])

    def test_pay_shows_the_price_and_holds_for_the_chapter(self):
        r = FakeRun(["💳 Pay — about $0.04 a shot"])
        story.paid_gate(r, True, 8)
        q = r.asked[0]
        self.assertIn("💳 Pay — about $0.04 a shot on Venice (8 left ≈ $0.32)", q["choices"])
        self.assertEqual(q["items"][0]["best"], 0)          # ⭐ = keep waiting ($0)
        self.assertTrue(r.batch["paid_ok"])
        story.paid_gate(r, True, 7)                          # next shot: no second question
        self.assertEqual(len(r.asked), 1)

    def test_stop_keeps_shots_and_ends_the_run(self):
        r = FakeRun(["⏹ Stop here (shots so far are kept)"])
        with self.assertRaises(agent.Stopped):
            story.paid_gate(r, True, 3)
        self.assertTrue(r.stop_flag.is_set())

    def test_wait_then_local_comes_back(self):
        r = FakeRun(cfg={"story": {"local_wait_s": 120}})
        orig = self.clock.sleep

        def sleep(s):
            orig(s)
            if self.clock.t >= 1040:
                self.ready = {"local/flux2-klein-4b"}
        self.clock.sleep = sleep
        story.paid_gate(r, True, 8)
        self.assertEqual(r.asked, [])
        self.assertTrue(any("is back" in s["why"] for s in r.steps))

    def test_wait_more_then_pay(self):
        r = FakeRun(["⏳ Wait 2 more minutes", "💳 Pay"])
        story.paid_gate(r, True, 8)
        self.assertEqual(len(r.asked), 2)
        self.assertGreaterEqual(self.clock.t, 1120)         # the second wait really waited

    def test_no_paid_model_offers_no_pay(self):
        self.rows = []
        r = FakeRun(["⏹ Stop here"])
        with self.assertRaises(agent.Stopped):
            story.paid_gate(r, True, 8)
        self.assertFalse(any(c.startswith("💳") for c in r.asked[0]["choices"]))

    def test_a_forced_picture_model_is_left_alone(self):
        r = FakeRun(cfg={"picture_model": "venice/lustify"})
        story.paid_gate(r, True, 8)
        self.assertEqual(r.asked, [])
