"""M1/M2 (2026-11-24): 🧠 Lab memory — import copies Scott's Claude setup, never auto-saves sensitive info."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ailab import memory as M

FAKE_KEY = "sk-ant-" + "x" * 30      # secretscan: test-fixture


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        (self.home / "hermes").mkdir(parents=True)
        self.env = mock.patch.dict(os.environ, {"AILAB_HOME": str(Path(self.tmp.name) / "lab")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class Sensitive(Base):
    def test_kinds(self):
        self.assertEqual(M.sensitive(f"key is {FAKE_KEY}"), "secret")
        self.assertEqual(M.sensitive("has ADHD"), "health")
        self.assertEqual(M.sensitive("account balance is 4000"), "money")
        self.assertEqual(M.sensitive("SSN 123-45-6789"), "id-number")
        self.assertEqual(M.sensitive("prefers short paragraphs"), "")

    def test_auto_save_skips_sensitive_but_scott_can_add(self):
        self.assertFalse(M.add_fact("health", "takes medication daily", "lab")["saved"])
        self.assertTrue(M.add_fact("health", "takes medication daily", "scott")["saved"])
        self.assertTrue(M.add_fact("prefs", "likes numbered menus", "lab")["saved"])
        self.assertFalse(M.add_fact("prefs", "Likes numbered menus", "lab")["saved"])     # no duplicates


class Import(Base):
    def test_import_copies_skips_and_is_idempotent(self):
        src = self.home / "hermes/CLAUDE.md"
        src.write_text("# CLAUDE.md\n\n- Never `git add -A`\n- token is " + FAKE_KEY + "\n```\ncode\n```\n- has autism\n")
        before = src.read_text()
        r = M.import_all(self.home)
        self.assertIn("rules-hermes", r["subjects"])
        self.assertEqual(r["skipped"], {"secret": 1, "health": 1})
        texts = [l["text"] for l in M.read("rules-hermes")["lines"]]
        self.assertIn("Never `git add -A`", texts)
        self.assertFalse(any("code" == t for t in texts))
        self.assertEqual(src.read_text(), before)                          # source never edited
        M.add_fact("rules-hermes", "my own note", "scott")
        r2 = M.import_all(self.home)
        self.assertEqual(r2["unchanged"], 1)
        self.assertEqual(sum(1 for l in M.read("rules-hermes")["lines"] if l["text"] == "my own note"), 1)

    def test_ledger_section_one_only(self):
        (self.home / "hermes/SESSION-LEDGER.md").write_text("# L\n\n## 1. Rules\n- rule one\n\n## 2. History\n- old\n")
        M.import_all(self.home)
        texts = [l["text"] for l in M.read("hermes-ledger-rules")["lines"]]
        self.assertIn("rule one", texts)
        self.assertNotIn("old", texts)

    def test_export_frontmatter_and_tags_stripped(self):
        d = self.home / "hermes-data/claude-memory-export"
        d.mkdir(parents=True)
        (d / "preferences.md").write_text("---\nname: preferences\ndescription: How Scott wants replies\n---\n"
                                          "- [stated] blunt, facts-first\n")
        M.import_all(self.home)
        s = M.read("claude-preferences")
        self.assertEqual(s["description"], "How Scott wants replies")
        self.assertEqual(s["lines"][0]["text"], "blunt, facts-first")

    def test_undo(self):
        M.add_fact("prefs", "a", "scott")
        M.add_fact("prefs", "b", "scott")
        M.undo_last()
        self.assertEqual([l["text"] for l in M.read("prefs")["lines"]], ["a"])


class Context(Base):
    def test_context_uses_profile_and_project(self):
        M.add_fact("claude-profile", "Name: Scott", "scott")
        M.add_fact("rules-hermes", "stage named paths", "scott")
        M.add_fact("cooking", "likes chili", "scott")
        text, used = M.for_context("hermes", "make the scan button green")
        self.assertEqual(used[:2], ["claude-profile", "rules-hermes"])
        self.assertNotIn("cooking", used)
        self.assertIn("stage named paths", text)



class Server(Base):
    def test_memory_endpoints_off_then_on(self):
        from ailab import server
        app = server.App(cfg={**__import__("ailab.config", fromlist=["x"]).load(), "flags": {"memory": False}})
        self.assertEqual(app.memory_get({})[0], 403)
        app.cfg["flags"]["memory"] = True
        code, body = app.memory_post("add", {"name": "prefs", "text": "likes menus"})
        self.assertEqual((code, body["saved"]), (200, True))
        self.assertEqual(app.memory_get({"name": ["prefs"]})[1]["subject"]["lines"][0]["source"], "scott")
        self.assertEqual(app.memory_post("nope", {})[0], 404)


class Learn(Base):
    def test_learns_stated_preferences_only(self):
        saved = M.learn("Make the button green. I prefer big buttons with icons. Never use red for small errors.")
        self.assertEqual(len(saved), 2)
        texts = [l["text"] for l in M.read("lab-learned")["lines"]]
        self.assertTrue(any("big buttons" in t for t in texts))
        self.assertFalse(any("Make the button" in t for t in texts))
        self.assertEqual(M.learn("I want my medication reminders at 8"), [])        # sensitive → never auto-saved
        self.assertEqual(M.learn("I prefer big buttons with icons."), [])           # already known

if __name__ == "__main__":
    unittest.main()
