"""🔑 Keys page (2026-11-23): set / remove / status never echo a key; connected mode refuses to hold one."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from ailab import keys


class KeyStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AILAB_HOME"] = self.tmp.name
        self.ks = keys.KeyStore(Path(self.tmp.name) / "keys.env", use_keyring=False)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: os.environ.pop("AILAB_HOME", None))
        self.addCleanup(lambda: os.environ.pop("MOONSHOT_API_KEY", None))

    def test_set_status_remove_round_trip_file_is_owner_only(self):
        self.assertEqual(self.ks.status("kimi"), {"set": False, "source": "none"})
        self.assertEqual(self.ks.set("kimi", "  sk-test-1234567890  "), "file")
        self.assertEqual(self.ks.status("kimi"), {"set": True, "source": "file"})
        self.assertEqual(self.ks.get("kimi"), "sk-test-1234567890")
        self.assertEqual(oct(self.ks.env_file.stat().st_mode & 0o777), "0o600")
        self.assertEqual(self.ks.remove("kimi"), ["file"])
        self.assertEqual(self.ks.status("kimi")["set"], False)
        self.assertNotIn("sk-test", self.ks.env_file.read_text())

    def test_rejects_junk_and_unknown_provider(self):
        for bad in ("short", "has space in it", "x" * 5000):
            with self.assertRaises(keys.KeyMissing):
                self.ks.set("kimi", bad)
        with self.assertRaises(keys.KeyMissing):
            self.ks.set("nope", "sk-test-1234567890")

    def test_environment_is_reported_but_never_removed(self):
        os.environ["MOONSHOT_API_KEY"] = "sk-env-1234567890"
        self.assertEqual(self.ks.status("kimi")["source"], "environment")
        self.assertEqual(self.ks.remove("kimi"), [])
        self.assertEqual(os.environ["MOONSHOT_API_KEY"], "sk-env-1234567890")


from tests.test_server import Srv                                  # noqa: E402


class KeysRoutes(Srv):
    flags = {"router": True}

    def test_status_never_contains_a_key_and_set_remove_work(self):
        self.lab.keys = keys.KeyStore(Path(self.tmp.name) / "keys.env", use_keyring=False)
        self.lab.models = type("M", (), {"forget": lambda s, n: None})()
        code, j, _ = self.req("/api/keys")
        self.assertEqual(code, 200)
        self.assertEqual({p["id"] for p in j["providers"]}, {"openrouter", "hf", "qwen", "kimi", "claude"})
        code, j, _ = self.req("/api/keys/set", {"provider": "qwen", "key": "sk-test-1234567890"})
        self.assertEqual((code, j["source"]), (200, "file"))
        code, j, _ = self.req("/api/keys")
        self.assertNotIn("sk-test", json.dumps(j))
        self.assertTrue(next(p for p in j["providers"] if p["id"] == "qwen")["set"])
        code, j, _ = self.req("/api/keys/remove", {"provider": "qwen"})
        self.assertEqual((code, j["removed"]), (200, ["file"]))
        code, j, _ = self.req("/api/keys/set", {"provider": "qwen", "key": "nope"})
        self.assertEqual(code, 400)

    def test_test_button_lists_models_with_the_key(self):
        code, j, _ = self.req("/api/keys/test", {"provider": "kimi"})
        self.assertEqual((code, j["models"]), (200, 2))


class KeysConnected(Srv):
    flags = {"router": True}

    def setUp(self):
        super().setUp()
        self.app.cfg["mode"] = "connected"

        class Mcp:
            def call(_, tool, args=None):
                return {"providers": [{"provider": "claude", "has_key": True, "models": ["claude-sonnet-5-5"]}]}
        self.lab.mcp = Mcp()

    def test_hermes_answer_shown_and_lab_refuses_to_hold_keys(self):
        code, j, _ = self.req("/api/keys")
        by = {p["id"]: p for p in j["providers"]}
        self.assertEqual((by["claude"]["listed"], by["claude"]["set"], by["kimi"]["listed"]), (True, True, False))
        code, j, _ = self.req("/api/keys/set", {"provider": "kimi", "key": "sk-test-1234567890"})
        self.assertEqual((code, j["code"]), (409, "hermes_holds_keys"))
