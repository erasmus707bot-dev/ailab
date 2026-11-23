"""Fix 4 (2026-11-23): 🤖 robot check — the 🚦 light is green only when a real browser proved the change."""
from __future__ import annotations

import unittest
from unittest import mock

from ailab import robotcheck as rc

BTN = {"found": True, "visible": True, "tag": "button", "html": "<button>Save</button>", "style": "a", "box": [40, 20]}


def page(probe=None, **kw):
    return {"status": 200, "signin": False, "probe": probe or {}, "errors": [], **kw}


class Judge(unittest.TestCase):
    def test_changed_and_clicked_is_green(self):
        r = rc.judge(page(BTN, clicked=True), page({**BTN, "style": "b", "box": [80, 40]}, clicked=True), "#save")
        self.assertEqual((r["level"], r["ok"]), ("green", True), r)

    def test_spot_unchanged_is_red(self):
        r = rc.judge(page(BTN), page(dict(BTN), clicked=True), "#save")
        self.assertEqual(r["level"], "red")
        self.assertIn("exactly the same", r["why"][0])

    def test_click_failure_is_red(self):
        r = rc.judge(page(BTN), page({**BTN, "style": "b"}, clicked=False, click_error="timeout"), "#save")
        self.assertEqual(r["level"], "red")

    def test_new_page_error_is_red_but_shared_error_is_not(self):
        new = page({**BTN, "style": "b"}, clicked=True, errors=["boom", "old"])
        self.assertEqual(rc.judge(page(BTN, errors=["old"]), new, "#s")["level"], "red")
        self.assertEqual(rc.judge(page(BTN, errors=["old", "boom"]), new, "#s")["level"], "green")

    def test_signin_never_green(self):
        r = rc.judge(page(BTN, signin=True), page({**BTN, "style": "b"}, signin=True, clicked=True), "#s")
        self.assertEqual(r["level"], "yellow")

    def test_no_pointed_spot_is_yellow_at_best(self):
        r = rc.judge(page({"found": False, "text": "a"}), page({"found": False, "text": "b"}), "")
        self.assertEqual(r["level"], "yellow")
        self.assertIn("The page text changed.", r["good"])

    def test_new_page_fails_to_open_is_red(self):
        self.assertEqual(rc.judge(page(BTN), page(status=500), "#s")["level"], "red")


class Run(unittest.TestCase):
    def test_missing_playwright_is_yellow_not_green(self):
        with mock.patch.object(rc, "available", return_value=(False, "needs Playwright")):
            r = rc.run("http://x/", "http://y/", "#s")
        self.assertEqual((r["ran"], r["level"]), (False, "yellow"))

    def test_driver_crash_is_yellow(self):
        def boom(*a):
            raise RuntimeError("no chrome")
        r = rc.run("u", "v", "#s", driver=boom)
        self.assertEqual((r["ran"], r["level"]), (False, "yellow"))

    def test_fake_driver_flows_to_judge(self):
        r = rc.run("u", "v", "#s", driver=lambda *a: (page(BTN), page({**BTN, "box": [9, 9]}, clicked=True)))
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
