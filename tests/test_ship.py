"""lab-ship M3 (2026-11-24) — 📦 Make it an app: options, packing (text + b64), Hermes app_ship + job_wait."""
from __future__ import annotations

import base64

from ailab import preview, ship, store
from tests.test_server import Srv


class FakeMCP:
    def __init__(self):
        self.calls = []

    def call(self, tool, args=None):
        self.calls.append((tool, args))
        if tool == "app_ship":
            return {"ok": True, "key": "ship:abc123def456", "app": "tetris", "state": "running", "where": "🧪"}
        if tool == "job_wait":
            return {"ok": True, "state": "done", "finished": True, "detail": {"notes": ["linux: test"]},
                    "result": {"ok": True, "platforms": {"linux": {"ok": True, "result": "test"}}}}
        raise AssertionError(tool)


class Ship(Srv):
    def test_standalone_refuses_in_words(self):
        code, r, _ = self.req("/api/ship/start", {"project": "scratch"})
        self.assertEqual(r["code"], "no_hermes", r)

    def test_connected_web_and_godot(self):
        self.app.cfg["mode"] = "connected"
        self.app.lab.mcp = FakeMCP()
        site = preview.ensure_site("scratch")
        g = site / "tetris-android"
        g.mkdir()
        (g / "project.godot").write_text("config_version=5\n")
        (g / "main.gd").write_text("extends Node\n")
        (g / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\nxx")
        (g / ".godot").mkdir()
        (g / ".godot" / "cache.bin").write_bytes(b"x")
        code, o, _ = self.req("/api/ship/options?project=scratch")
        kinds = {(x["kind"], x["folder"]) for x in o["options"]}
        self.assertIn(("godot", "tetris-android"), kinds)
        code, r, _ = self.req("/api/ship/start", {"project": "scratch", "name": "Tetris", "folder": "tetris-android",
                                                  "platforms": ["android", "bogus"]})
        self.assertTrue(r["ok"], r)
        tool, args = self.app.lab.mcp.calls[-1]
        self.assertEqual((tool, args["platforms"]), ("app_ship", ["android"]))
        self.assertEqual(args["files"]["main.gd"], "extends Node\n")
        self.assertEqual(base64.b64decode(args["files"]["icon.png"]["b64"])[:4], b"\x89PNG")
        self.assertNotIn(".godot/cache.bin", args["files"])
        code, w, _ = self.req("/api/ship/wait", {"key": r["key"]})
        self.assertTrue(w["finished"] and w["result"]["platforms"]["linux"]["ok"], w)

    def test_outside_folder_refused(self):
        self.app.cfg["mode"] = "connected"
        self.app.lab.mcp = FakeMCP()
        code, r, _ = self.req("/api/ship/start", {"project": "scratch", "folder": "../../.."})
        self.assertFalse(r["ok"])
