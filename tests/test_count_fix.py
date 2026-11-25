"""🔢 Counts (Scott 2026-11-25): 'five ducks' came out as 4 even with the craft note. The layout is said in code, and a
$0 local picture with the wrong count gets one more try with a new seed; the better one is the main picture."""
from unittest import mock

from ailab import agent, config, picture, picture_route
from tests.test_eyes import FakeMCP
from tests.test_picture import Base, Brain, PicMCP


def test_layout_only_for_two_to_eight_things():
    lay = picture.count_layout("Five yellow rubber ducks floating in a blue bathtub")
    assert lay.startswith("Exactly 5 yellow rubber ducks (5 in all), in one row side by side")
    assert "no other ducks" in lay
    assert picture.count_layout("3 foxes in snow").startswith("Exactly 3 foxes")
    assert picture.count_layout("a fox in snow") == ""
    assert picture.count_layout("twelve apples") == ""          # too many to lay out reliably
    assert picture.count_layout("two lovers on a beach") == ""  # two is drawn right on its own
    girls = picture.count_layout("three girls dancing in a field")
    assert girls.startswith("Exactly 3 girls (3 in all), each whole") and "row" not in girls


def test_count_missed_reads_only_count_points():
    assert picture.count_missed({"points": [{"kind": "count", "ok": False}]})
    assert not picture.count_missed({"points": [{"kind": "show", "ok": False}, {"kind": "count", "ok": True}]})
    assert not picture.count_missed(None)


class Hermes(PicMCP):
    """Local pictures; each 👁 check answers from the next list in `checks`."""
    def __init__(self, checks):
        super().__init__(polls=1)
        self.checks, self.eye = list(checks), None

    def call(self, tool, args=None):
        if tool == "vision_check":
            self.eye = FakeMCP(yes=self.checks.pop(0))
            self.calls.append(tool)
            self.args.append(args or {})
            return self.eye.call(tool, args)
        if tool == "job_wait" and (args or {}).get("key") == "vis:1":
            return self.eye.call(tool, args)
        if tool == "job_wait":
            self.polls = 1
        return super().call(tool, args)


class Retry(Base):
    def go(self, checks, cfg=None, local=True):
        b = Brain(["Five ducks bobbing, bright light."])
        b.mcp = Hermes(checks)
        model = "local/flux2-klein-4b" if local else "venice/lustify"
        with mock.patch.object(picture_route, "plan", return_value={"models": [model], "kind": "plain", "first": "local"}), \
             mock.patch.object(picture_route, "keys_line", return_value=""):
            r = agent.Run(b, config.load({"mode": "connected", **(cfg or {})}), self.project, "openrouter", "m",
                          "five yellow ducks in a bathtub", ctypes=["image"], ask_first=False)
            r.loop()
        return r, b.mcp

    def test_prompt_says_the_layout_after_his_words(self):
        r, m = self.go([[True, True, False]])
        self.assertEqual(r.state, "done", r.why)
        p = m.args[m.calls.index("image_make")]["prompt"]
        self.assertTrue(p.startswith("five yellow ducks in a bathtub. Exactly 5 yellow ducks (5 in all), in one row"), p)
        self.assertEqual(m.calls.count("image_make"), 1)                     # count right → no retry

    def test_wrong_count_retries_once_and_the_better_one_is_main(self):
        r, m = self.go([[False, True, False], [True, True, False]])
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(m.calls.count("image_make"), 2)
        self.assertEqual(len(r.pictures), 2)
        self.assertEqual(r.pictures[-1]["eyes"]["score"], 100)
        self.assertIn("👁 100% match", r.why)
        self.assertTrue(any("retry is better" in (s.get("why") or "") for s in r.steps))

    def test_worse_retry_keeps_the_first_as_main(self):
        r, m = self.go([[False, True, False], [False, False, False]])
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(m.calls.count("image_make"), 2)
        self.assertEqual(r.pictures[-1]["eyes"]["score"], 67)
        self.assertTrue(any("wasn't better" in (s.get("why") or "") for s in r.steps))

    def test_paid_route_and_switch_off_never_retry(self):
        r, m = self.go([[False, True, False]], local=False)
        self.assertEqual(m.calls.count("image_make"), 1)
        r, m = self.go([[False, True, False]], cfg={"count_fix": {"retry": 0, "layout": False}})
        self.assertEqual(m.calls.count("image_make"), 1)
        self.assertNotIn("in one row", m.args[m.calls.index("image_make")]["prompt"])
