"""🏃 Art runs share a project (2026-11-24, Scott: "make pictures while a video renders"); builds stay one at a time."""
from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ailab import agent, picture
from ailab.spend import LocalLedger


def fake(pid="p1", state="running", **kw):
    r = SimpleNamespace(id=os.urandom(5).hex(), state=state, project={"id": pid}, task="t", usd=0.0, started=0,
                        picture=False, video=False, docmode=False, batch=None, ctypes=[], question=None)
    r.__dict__.update(kw)
    r.stage_view = lambda: {"icon": "🎬", "text": "Making it"}
    return r


class FakeRun:
    def __init__(self, lab, cfg, project, provider, model, task, **kw):
        self.id, self.project, self.task, self.state = os.urandom(5).hex(), project, task, "running"
        ids = kw.get("ctypes") or []
        self.picture, self.video = "image" in ids, "video" in ids
        self.docmode, self.batch = False, None

    def loop(self):
        pass


class Lock(unittest.TestCase):
    def start(self, ag, ctypes, task="make it"):
        return ag.start(None, {}, {"id": "p1"}, "openrouter", "m", task, ctypes=ctypes)

    def test_art_alongside_anything_builds_one_at_a_time(self):
        ag = agent.Agents()
        with mock.patch.object(agent, "Run", FakeRun):
            vid = self.start(ag, ["video"], "a woman walks on the beach")
            pic = self.start(ag, ["image"], "a red fox")                    # picture while the video renders
            build = self.start(ag, ["website"], "build a todo page")            # a build beside art runs is fine
            with self.assertRaises(ValueError) as e:
                self.start(ag, ["website"], "add a dark mode toggle")           # second build → refused
            self.assertIn("Art runs", str(e.exception))
            self.start(ag, ["image"], "a blue bird")                        # art still goes alongside the build
            other = ag.start(None, {}, {"id": "p2"}, "openrouter", "m", "build x", ctypes=["website"])   # other project fine
        self.assertEqual({vid.state, pic.state, build.state, other.state}, {"running"})

    def test_art_request_matches_run_flags(self):
        self.assertTrue(agent.art_request("x", ["image"], None))
        self.assertTrue(agent.art_request("x", ["video"], None))
        self.assertTrue(agent.art_request("x", ["text"], None))
        self.assertFalse(agent.art_request("build a page", ["website"], None))
        self.assertFalse(agent.art_request("x", ["image", "website"], None))   # picture inside a page = a build

    def test_more_and_resume_respect_the_rule(self):
        ag = agent.Agents()
        b1, b2 = fake(), fake(state="capped")
        ag.runs = {b1.id: b1, b2.id: b2}
        self.assertTrue(ag._build_busy("p1", but=b2.id))
        self.assertFalse(ag._build_busy("p1", but=b1.id))
        art = fake(video=True)
        ag.runs = {art.id: art}
        self.assertFalse(ag._build_busy("p1"))                             # art never blocks a build

    def test_live_lists_every_running_run(self):
        ag = agent.Agents()
        a, b, c = fake(video=True, task="clip"), fake(picture=True, task="pic"), fake(state="done")
        ag.runs = {x.id: x for x in (a, b, c)}
        rows = ag.live("p1")
        self.assertEqual({r["icon"] for r in rows}, {"🎬", "🖼"})
        self.assertTrue(all(r["art"] for r in rows))


class Names(unittest.TestCase):
    def test_same_second_same_words_two_files(self):
        with tempfile.TemporaryDirectory() as d:
            names = []
            ts = [threading.Thread(target=lambda: names.append(picture.claim(d, "pictures/20261124-200000-fox.png")))
                  for _ in range(8)]
            [t.start() for t in ts]
            [t.join() for t in ts]
            self.assertEqual(len(set(names)), 8)
            self.assertIn("pictures/20261124-200000-fox.png", names)
            self.assertIn("pictures/20261124-200000-fox-2.png", names)
            self.assertEqual(len(list(Path(d, "pictures").iterdir())), 8)


class Spend(unittest.TestCase):
    def test_hold_stops_two_runs_overshooting(self):
        with tempfile.TemporaryDirectory() as d:
            L = LocalLedger(Path(d) / "l.json", 1.00)
            L.record("x", "m", 0.40)
            results = []
            ts = [threading.Thread(target=lambda: results.append(L.hold(0.50))) for _ in range(4)]
            [t.start() for t in ts]
            [t.join() for t in ts]
            ok = [r for r in results if r[0]]
            self.assertEqual(len(ok), 1)                                     # $0.40 + 0.50 fits $1, a second doesn't
            L.record("x", "m", 0.50)
            L.release(ok[0][2])
            self.assertAlmostEqual(L.spent_today(), 0.90)
            self.assertFalse(L.hold(0.20)[0])
            self.assertTrue(L.hold(0.10)[0])


if __name__ == "__main__":
    unittest.main()
