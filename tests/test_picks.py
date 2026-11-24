"""2026-11-24: ❓ question-card answers are saved to Lab memory (lab-picks) and fed back so they aren't asked again."""
from __future__ import annotations

import threading

from ailab import agent, config, memory as M
from tests.test_agent import Base, Brain, act
from tests.test_workflow import wait_for

DONE = act(action="done", summary="made it")
TWO = [{"q": "Which toggle look do you want?", "choices": ["Sun / moon icon", "Text button"], "best": 0, "why": ""},
       {"q": "First visit?", "choices": ["Follow the device", "Start light"], "best": 0, "why": ""}]


class Split(Base):
    def test_page_formats(self):
        one = TWO[:1]
        self.assertEqual(M.split_answer(one, "Text button"), [("Which toggle look do you want?", "Text button")])
        self.assertEqual(M.split_answer(one, "Text button · bigger please"), [("Which toggle look do you want?", "Text button · bigger please")])
        both = "Which toggle look do you want? → Sun / moon icon · First visit? → Start light · cream colours"
        self.assertEqual(M.split_answer(TWO, both), [("Which toggle look do you want?", "Sun / moon icon"),
                                                     ("First visit?", "Start light · cream colours")])
        self.assertEqual(M.split_answer(TWO, "just do it simple"), [("Which toggle look do you want?", "just do it simple")])
        self.assertEqual(M.split_answer(TWO, ""), [])


class Save(Base):
    def test_newest_answer_wins_and_is_scotts(self):
        M.save_pick("Which toggle look do you want?", "Text button", "scratch")
        r = M.save_pick("Which toggle look do you want", "Sun / moon icon", "scratch")
        self.assertTrue(r["saved"])
        lines = M.read(M.PICKS)["lines"]
        self.assertEqual([(l["source"], l["text"]) for l in lines],
                         [("scott", "Which toggle look do you want? → Sun / moon icon (project scratch)")])
        self.assertFalse(M.save_pick("Q", "(no answer)")["saved"])

    def test_context_shows_fitting_picks_first(self):
        M.save_pick("Which toggle look do you want?", "Sun / moon icon", "scratch")
        M.save_pick("Hold piece key?", "C key", "test")
        txt, used = M.for_context("scratch", "add a dark mode toggle look")
        self.assertIn(M.PICKS, used[0] if used else "")
        self.assertIn("Sun / moon icon", txt)
        self.assertNotIn("C key", txt)
        self.assertIn("don't ask these again", txt)


class FromARun(Base):
    def _run(self, memory_on=True):
        c = config.load({"mode": "standalone", "flags": {**config.load({})["flags"], "memory": memory_on}})
        r = agent.Run(Brain([act(action="ask", questions=TWO), DONE]), c, self.project, "openrouter", "m", "make a toggle")
        t = threading.Thread(target=r.loop, daemon=True)
        t.start()
        self.assertTrue(wait_for(lambda: r.question))
        r.answer("Which toggle look do you want? → Text button · First visit? → Follow the device")
        t.join(5)
        return r

    def test_card_answers_are_saved_and_shown(self):
        r = self._run()
        texts = [l["text"] for l in M.read(M.PICKS)["lines"]]
        self.assertEqual(len(texts), 2)
        self.assertIn("First visit? → Follow the device (project scratch)", texts)
        self.assertEqual(r.memory_saved[-2:], texts)                 # the run shows "🧠 saved: …"

    def test_memory_off_saves_nothing(self):
        self._run(memory_on=False)
        self.assertNotIn(M.PICKS, [x["name"] for x in M.subjects()])
