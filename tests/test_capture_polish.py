"""✨ Lab capture C3.3 (2026-11-25): Polish a 🎥 capture from its card — Hermes capture_edit → captures/polished/ +
Before | After; ✕ Not this removes only a polished copy; refusals say what to do."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ailab import capturepolish as CP
from ailab.mcp_client import HermesRefused


class FakeMCP:
    def __init__(self, hermes: Path, fail=None):
        self.hermes, self.fail, self.calls = hermes, fail, []

    def call(self, tool, args=None):
        self.calls.append((tool, args))
        if tool == "capture_edit":
            if self.fail:
                raise HermesRefused(*self.fail)
            return {"ok": True, "key": "cap:1"}
        if tool == "job_wait":
            out = self.hermes / "100000-argus-home-edited.mp4"
            out.write_bytes(b"mp4"); out.with_suffix(".ba.jpg").write_bytes(b"jpg"); out.with_suffix(".thumb.jpg").write_bytes(b"j")
            return {"state": "done", "finished": True, "result": {"path": str(out), "kind": "clip", "library": "media: z",
                    "before_after": str(out.with_suffix(".ba.jpg")), "thumb": str(out.with_suffix(".thumb.jpg")),
                    "notes": ["🖱️ Cursor polish: 2 clicks"]}}
        return {"ok": True}


class Polish(unittest.TestCase):
    def setUp(self):
        self.site = Path(tempfile.mkdtemp()).resolve()
        self.hermes = Path(tempfile.mkdtemp()) / "captures" / "p" / "2026-11-25"
        self.hermes.mkdir(parents=True)
        self.app = mock.Mock(cfg={"mode": "connected"})
        self.app._pid = lambda v: "p"
        self.app.lab.mcp = FakeMCP(self.hermes)
        self.p1 = mock.patch.object(CP.store, "project", lambda pid: {"id": pid})
        self.p2 = mock.patch.object(CP.preview, "ensure_site", lambda pid: self.site)
        self.p1.start(); self.p2.start()

    def tearDown(self):
        self.p1.stop(); self.p2.stop()

    def body(self, **kw):
        return {"project": "p", "path": "captures/x.mp4", "hermes": str(self.hermes / "100000-argus-home.mp4"),
                "frame": "9:16", "zoom": True, "rings": True, "title": "  Epochron   family ", **kw}

    def test_polish_lands_in_polished_with_before_after(self):
        code, r = CP.polish(self.app, self.body())
        self.assertEqual(code, 200, r)
        it = r["item"]
        self.assertEqual(it["path"], "captures/polished/100000-argus-home-edited.mp4")
        self.assertTrue((self.site / it["before_after"]).is_file())
        self.assertTrue((self.site / it["path"]).is_file())
        tool, args = self.app.lab.mcp.calls[0]
        self.assertEqual(tool, "capture_edit")
        self.assertEqual(args["title"], "Epochron family")
        self.assertTrue(args["zoom"] and args["rings"])

    def test_not_a_capture_or_bad_shape(self):
        self.assertEqual(CP.polish(self.app, self.body(hermes=""))[0], 400)
        self.assertEqual(CP.polish(self.app, self.body(frame="3:2"))[0], 400)

    def test_hermes_refusal_says_what_to_do(self):
        self.app.lab.mcp = FakeMCP(self.hermes, fail=("busy", "Another polish is rendering.", "Wait for it."))
        code, r = CP.polish(self.app, self.body())
        self.assertEqual(code, 400)
        self.assertIn("Wait", r["fix"])

    def test_offline_mode_refused(self):
        self.app.cfg = {"mode": "offline"}
        self.assertEqual(CP.polish(self.app, self.body())[1]["code"], "not_connected")

    def test_drop_only_polished_copies(self):
        CP.polish(self.app, self.body())
        keep = self.site / "captures" / "x.mp4"; keep.parent.mkdir(parents=True, exist_ok=True); keep.write_bytes(b"orig")
        self.assertEqual(CP.drop(self.app, {"project": "p", "path": "captures/x.mp4"})[0], 400)
        self.assertTrue(keep.is_file())
        code, _ = CP.drop(self.app, {"project": "p", "path": "captures/polished/100000-argus-home-edited.mp4"})
        self.assertEqual(code, 200)
        self.assertFalse(list((self.site / "captures" / "polished").glob("*-edited*")))


class ArgusDuring(unittest.TestCase):
    def test_argus_clip_taps_play_during_recording(self):
        from ailab import capturerun
        run = mock.Mock(); run.project = {"id": "p"}
        a = capturerun._args(run, {"target": "argus", "record": 10, "label": "x", "do": [{"swipe": [540, 1600, 540, 600]}]}, 1, False)
        self.assertEqual(a["during"], [{"swipe": [540, 1600, 540, 600]}])
        self.assertNotIn("steps", a)
        b = capturerun._args(run, {"target": "argus", "shot": True, "label": "x", "do": [{"wait": 1}]}, 1, False)
        self.assertIn("steps", b)
