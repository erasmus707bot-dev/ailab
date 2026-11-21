"""M3 acceptance — UI shell + router chat panel behind the `router` flag."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from ailab import config, server, store
from ailab.privacy import PrivacyRefused
from ailab.providers.base import ChatResult
from ailab.spend import SpendBlocked


class FakeLab:
    def __init__(self):
        self.calls = []

        class Sp:
            def spent_today(_):
                return 0.25
        self.spend = Sp()

    def list_models(self, prov, project):
        self.calls.append(("models", prov))
        return {"source": "cache", "models": [{"id": "m1"}, {"id": "m2"}]}

    def chat(self, project, prov, model, msgs, max_tokens, task=""):
        self.calls.append(("chat", prov, model, project.get("id")))
        if project.get("sensitive") and prov != "ollama":
            raise PrivacyRefused("sensitive: Ollama only")
        if model == "pricey":
            raise SpendBlocked("Lab daily cap reached")
        return ChatResult("hello back", prov, model, 7, 3, 0.0009, True)


class Srv(unittest.TestCase):
    flags = {"router": False}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AILAB_HOME"] = self.tmp.name
        self.lab = FakeLab()
        self.app = server.App(config.load({"flags": self.flags}), lab=self.lab)
        self.srv = server.make_server(self.app, port=0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()
        os.environ.pop("AILAB_HOME", None)

    def req(self, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data, {"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                raw, code, hdrs = resp.read(), resp.status, resp.headers
        except urllib.error.HTTPError as e:
            raw, code, hdrs = e.read(), e.code, e.headers
        try:
            return code, json.loads(raw), hdrs
        except ValueError:
            return code, raw.decode(), hdrs


class RouterOff(Srv):
    def test_page_loads_with_off_card_and_rules(self):
        code, html, hdrs = self.req("/")
        self.assertEqual(code, 200)
        self.assertEqual(hdrs["Cache-Control"], "no-store")
        self.assertIn('data-theme="dark"', html)                          # dark by default
        for must in ("not switched on yet", 'id="theme"', 'id="full"', 'id="back"', 'id="home"',
                     "/api/autosave", "viewport", "Nothing is sent and nothing is spent", "localStorage"):
            self.assertIn(must, html)
        self.assertNotRegex(html, r"<script[^>]+src=|<link[^>]+href=\"http")  # one self-contained file
        self.assertIn("try {", html)                                        # storage access is guarded

    def test_state_reports_flags_off_and_spend(self):
        code, s, _ = self.req("/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(s["flags"], {"router": False, "preview": False, "agent": False, "compare": False})
        self.assertEqual(s["spend"], {"today_usd": 0.25, "cap_usd": 2.0})
        self.assertEqual(s["projects"][0]["id"], "scratch")
        self.assertIn("ollama", [p["id"] for p in s["providers"]])

    def test_chat_and_models_refused_nothing_sent(self):
        for path, body in (("/api/chat", {"provider": "claude", "model": "m", "messages": [{"role": "user", "content": "x"}]}),
                           ("/api/models?provider=claude", None)):
            code, r, _ = self.req(path, body)
            self.assertEqual((code, r["code"], r["flag"]), (403, "not_switched_on", "router"))
            self.assertIn("Nothing was sent", r["message"])
        self.assertEqual(self.lab.calls, [])

    def test_no_way_to_flip_a_flag(self):
        for path in ("/api/flags", "/api/config", "/api/state"):
            code, _, _ = self.req(path, {"router": True})
            self.assertEqual(code, 404)
        self.assertFalse(self.req("/api/state")[1]["flags"]["router"])

    def test_cross_origin_post_refused(self):
        code, r, _ = self.req("/api/projects", {"name": "x"}, {"Origin": "http://evil.test"})
        self.assertEqual((code, r["code"]), (403, "cross_origin"))

    def test_autosave_recovery_and_projects(self):
        code, r, _ = self.req("/api/projects", {"name": "ERASMUS notes", "sensitive": True})
        self.assertEqual((code, r["project"]["id"], r["project"]["sensitive"]), (200, "erasmus-notes", True))
        self.req("/api/autosave", {"project": "erasmus-notes", "field": "chat-draft", "text": "half typ"})
        self.req("/api/autosave", {"project": "erasmus-notes", "field": "chat-draft", "text": "half typed line"})
        with open(Path(self.tmp.name) / "recovery" / "erasmus-notes.jsonl", "a") as fh:
            fh.write('{"at": 1, "field": "chat-dr')                      # power cut mid-write
        code, r, _ = self.req("/api/recover?project=erasmus-notes")
        self.assertEqual(r["fields"]["chat-draft"]["text"], "half typed line")
        code, r, _ = self.req("/api/autosave", {"project": "../etc", "text": "x"})
        self.assertEqual(code, 400)

    def test_busy_port_says_so_and_does_not_start(self):
        import contextlib
        import io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = server.serve("127.0.0.1", self.srv.server_address[1])
        self.assertEqual(rc, 2)
        self.assertIn("already in use", err.getvalue())

    def test_binds_localhost_only(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")


class RouterOn(Srv):
    flags = {"router": True}

    def test_models_and_chat_with_cost(self):
        code, r, _ = self.req("/api/models?provider=claude")
        self.assertEqual((code, r["models"]), (200, ["m1", "m2"]))
        code, r, _ = self.req("/api/chat", {"provider": "claude", "model": "m1",
                                            "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual((code, r["text"], r["model"], r["usd"]), (200, "hello back", "m1", 0.0009))
        self.assertEqual(r["spend"]["today_usd"], 0.25)

    def test_sensitive_and_cap_errors_are_plain(self):
        p = store.save_project("Private", True)
        code, r, _ = self.req("/api/chat", {"project": p["id"], "provider": "claude", "model": "m",
                                            "messages": [{"role": "user", "content": "x"}]})
        self.assertEqual((code, r["code"], r["icon"]), (403, "privacy", "🔒"))
        code, r, _ = self.req("/api/chat", {"provider": "claude", "model": "pricey",
                                            "messages": [{"role": "user", "content": "x"}]})
        self.assertEqual((code, r["code"]), (402, "over_cap"))
        code, r, _ = self.req("/api/chat", {"provider": "claude", "model": "m", "messages": []})
        self.assertEqual(code, 400)



if __name__ == "__main__":
    unittest.main()
