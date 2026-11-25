"""2026-11-24 online Lab: only Scott — gandalf itself, or his Tailscale login through `tailscale serve`."""
from __future__ import annotations

import json
import unittest

from ailab import gate


class Gate(unittest.TestCase):
    def setUp(self):
        gate._CACHE.update(at=0.0, logins=frozenset())
        self.cfg = {"owner_logins": ["Scott@Example.com"]}

    def test_local_browser_at_gandalf(self):
        self.assertTrue(gate.allowed({}, "127.0.0.1", self.cfg))
        self.assertTrue(gate.allowed({}, "::1", self.cfg))

    def test_other_machine_without_proxy_refused(self):
        self.assertFalse(gate.allowed({}, "100.64.0.9", self.cfg))

    def test_tailscale_owner_allowed(self):
        h = {"X-Forwarded-For": "100.64.0.9", "Tailscale-User-Login": "scott@example.com"}
        self.assertTrue(gate.allowed(h, "127.0.0.1", self.cfg))
        self.assertTrue(gate.remote(h))

    def test_tailscale_other_login_or_none_refused(self):
        self.assertFalse(gate.allowed({"X-Forwarded-For": "1", "Tailscale-User-Login": "jazzy@x.com"}, "127.0.0.1", self.cfg))
        self.assertFalse(gate.allowed({"X-Forwarded-For": "100.64.0.9"}, "127.0.0.1", self.cfg))   # tagged node

    def test_reads_hermes_owner_list(self):
        import os, tempfile
        d = tempfile.mkdtemp()
        os.makedirs(f"{d}/access")
        with open(f"{d}/access/collaborators.json", "w") as f:
            json.dump({"owner_login": "a@x.com", "owner_logins": ["b@x.com"]}, f)
        old = os.environ.get("HERMES_KB")
        os.environ["HERMES_KB"] = d
        try:
            self.assertEqual(gate.owner_logins({}), frozenset({"a@x.com", "b@x.com"}))
        finally:
            if old is None:
                os.environ.pop("HERMES_KB")
            else:
                os.environ["HERMES_KB"] = old


from tests.test_server import Srv  # noqa: E402


class GateServer(Srv):
    def test_api_and_page_refuse_strangers_through_tailscale(self):
        gate._CACHE.update(at=0.0, logins=frozenset())
        self.app.cfg["owner_logins"] = ["scott@example.com"]
        code, r, _ = self.req("/api/state", headers={"X-Forwarded-For": "100.64.0.9", "Tailscale-User-Login": "jazzy@x.com"})
        self.assertEqual((code, r["code"]), (403, "not_scott"))
        code, r, _ = self.req("/", headers={"X-Forwarded-For": "100.64.0.9"})
        self.assertEqual(code, 403)
        self.assertIn("Only Scott", r)
        code, r, _ = self.req("/api/ship/start", {"project": "scratch"}, headers={"X-Forwarded-For": "1"})
        self.assertEqual(code, 403)

    def test_scott_through_tailscale_and_at_gandalf(self):
        gate._CACHE.update(at=0.0, logins=frozenset())
        self.app.cfg["owner_logins"] = ["scott@example.com"]
        code, r, _ = self.req("/api/state", headers={"X-Forwarded-For": "100.64.0.9", "Tailscale-User-Login": "Scott@example.com"})
        self.assertEqual(code, 200)
        code, r, _ = self.req("/api/state")
        self.assertEqual(code, 200)
