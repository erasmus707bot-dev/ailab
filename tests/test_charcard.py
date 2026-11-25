"""⭐ Make a character + 📇 Characters shelf (asset library M1, 2026-11-25)."""
from __future__ import annotations

import base64
import os
import tempfile
import unittest
from pathlib import Path

from ailab import cast, charcard
from tests.test_server import Srv

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMB/6XeYQAAAABJRU5ErkJggg==")


class FakeMCP:
    def __init__(self):
        self.calls = []

    def call(self, tool, args=None):
        self.calls.append((tool, args or {}))
        if tool == "cast_make":
            return {"ok": True, "new": True, "id": "c-mara-abc123", "name": args["name"], "anchor_path": "/x/anchor.png"}
        if tool == "cast_pin":
            return {"ok": True, "id": args["id"], "name": "Ben", "uses": 1}
        if tool == "cast_get":
            return {"id": args["id"], "name": "Ben", "age": 30, "used_by": [{"project": "p1"}]}
        if tool == "cast_list":
            return {"characters": [{"id": "c-ben-1", "name": "Ben", "age": 30}], "casts": []}
        raise AssertionError(tool)


class Card(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "pictures").mkdir()
        (self.root / "pictures" / "a.png").write_bytes(PNG)
        self.mcp = FakeMCP()

    def tearDown(self):
        self.tmp.cleanup()

    def test_make_sends_anchor_and_joins_the_cast(self):
        r = charcard.make_from(self.mcp, self.root, "p1", "pictures/a.png", " Mara ", "29", "red hair, green eyes")
        tool, a = self.mcp.calls[0]
        self.assertEqual((tool, a["name"], a["age"], a["project"]), ("cast_make", "Mara", 29, "p1"))
        self.assertEqual(base64.b64decode(a["anchor_b64"]), PNG)
        self.assertTrue(r["joined"])
        self.assertEqual(cast.chosen(self.root)["ids"], ["c-mara-abc123"])

    def test_adults_only_and_name_required_nothing_sent(self):
        for age in ("17", "", "abc", None, 121):
            with self.assertRaises(charcard.CharError):
                charcard.make_from(self.mcp, self.root, "p1", "pictures/a.png", "Mara", age)
        with self.assertRaises(charcard.CharError):
            charcard.make_from(self.mcp, self.root, "p1", "pictures/a.png", "  ", 30)
        self.assertEqual(self.mcp.calls, [])

    def test_only_pictures_inside_the_project(self):
        outside = Path(self.tmp.name).parent / f"out-{os.getpid()}.png"
        outside.write_bytes(PNG)
        try:
            for bad in ("../" + outside.name, "/etc/passwd", ".hidden/a.png", "pictures/none.png", "notes.md"):
                with self.assertRaises(charcard.CharError, msg=bad):
                    charcard.make_from(self.mcp, self.root, "p1", bad, "Mara", 30)
        finally:
            outside.unlink()
        self.assertEqual(self.mcp.calls, [])

    def test_use_leave_and_full_cast(self):
        cast.choose(self.root, "Crew", ["c-a-1", "c-b-1", "c-c-1"])
        r = charcard.use(self.mcp, self.root, "p1", "c-ben-1")
        self.assertTrue(r["joined"])
        self.assertEqual(self.mcp.calls[-1], ("cast_pin", {"id": "c-ben-1", "project": "p1"}))
        r = charcard.join(self.root, "c-zed-1", "Zed")                       # 5th face: refused, says why
        self.assertFalse(r["joined"])
        self.assertIn("full", r["note"])
        r = charcard.leave(self.root, "c-ben-1")
        self.assertNotIn("c-ben-1", r["ids"])
        with self.assertRaises(charcard.CharError):
            charcard.use(self.mcp, self.root, "p1", "nope")


class Api(Srv):
    flags = {"agent": True}

    def test_routes_answer_plainly_without_hermes(self):
        code, r, _ = self.req("/api/cast/character", {"project": "scratch", "path": "pictures/a.png", "name": "Mara", "age": 17})
        self.assertEqual(code, 200)
        self.assertFalse(r["ok"])
        code, r, _ = self.req("/api/cast/one?id=c-x-1")
        self.assertEqual(code, 200)
        self.assertFalse(r["ok"])

    def test_page_has_the_buttons(self):
        code, html, _ = self.req("/")
        for m in ("function charForm(", "function charShelf(", "⭐ Make a character", "📇 Characters", "/api/cast/character"):
            self.assertIn(m, html)


if __name__ == "__main__":
    unittest.main()
