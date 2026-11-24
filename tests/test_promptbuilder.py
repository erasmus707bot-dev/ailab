"""M4 (2026-11-24): 📝 prompt builder — idea → prompt in Scott's format → Lab agent or a night AUDIT order."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ailab import promptbuilder as P
from ailab.providers.base import ChatResult


class Fake:
    def __init__(self, text):
        self.text = text

    def chat(self, project, prov, model, msgs, max_tokens=1024, cap_usd=None, task=""):
        self.msgs = msgs
        return ChatResult(self.text, prov, model, 10, 5, 0.002, True)


class Builder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"AILAB_HOME": str(Path(self.tmp.name) / "lab")})
        self.env.start()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_plain_has_gate_and_continue(self):
        md = P.plain("Add a dark mode toggle to Atlas", "~/hermes")
        for part in ("## 0. Working rules", "## Module 0", "Would you like me to proceed", "**Continue phrase:**"):
            self.assertIn(part, md)

    def test_size_hint(self):
        self.assertEqual(P.size_hint("make the scan button green")["size"], "small")
        self.assertEqual(P.size_hint("rebuild the whole android app and sync it with the server")["size"], "big")

    def test_draft_uses_model_or_falls_back(self):
        good = Fake("# X — Build Prompt\n\n## Module 0 — Audit\n- read\n")
        d = P.draft(good, {"id": "scratch", "name": "Scratch"}, "openrouter", "m", "add a toggle")
        self.assertFalse(d["fallback"])
        self.assertIn("Scott's idea: add a toggle", good.msgs[1]["content"])
        bad = P.draft(Fake("sure! here you go"), {"id": "s"}, "openrouter", "m", "add a toggle")
        self.assertTrue(bad["fallback"])
        self.assertIn("## Module 0", bad["md"])
        with self.assertRaises(ValueError):
            P.draft(good, {"id": "s"}, "o", "m", "  ")

    def test_save_needs_module0_and_queue_writes_audit_order(self):
        with self.assertRaises(ValueError):
            P.save("no gate here", root=self.root / "p")
        f = P.save(P.plain("Add a toggle", "~/hermes"), "toggle", root=self.root / "p")
        self.assertTrue(f.name.startswith("BUILD_PROMPT_") and f.name.endswith("_toggle.md"))
        with mock.patch.object(P, "_hermes_validate", return_value=None):
            q = P.queue_for_claude(f, "hermes", "/home/x/hermes", orders=self.root / "orders")
            o = json.loads(Path(q["order"]).read_text())
            self.assertEqual((o["kind"], o["module"], o["status"], o["prompt_anchor"]), ("audit", "M0", "queued", "## Module 0"))
            self.assertIn("Module 0", q["continue"])
            again = P.queue_for_claude(f, "hermes", "/home/x/hermes", orders=self.root / "orders")
            self.assertIsNone(again["order"])                           # never overwrites a queued order

    def test_validator_refusal_is_reported_not_written(self):
        f = P.save(P.plain("x y z", "~/"), "z", root=self.root / "p")
        with mock.patch.object(P, "_hermes_validate", return_value=lambda o: ["repo_path not found"]):
            q = P.queue_for_claude(f, "hermes", "/nope", orders=self.root / "orders")
        self.assertEqual(q["refused"], ["repo_path not found"])
        self.assertFalse((self.root / "orders").exists() and any((self.root / "orders").iterdir()))


if __name__ == "__main__":
    unittest.main()
