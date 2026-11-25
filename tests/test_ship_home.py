"""2026-11-24 Hermes app library: the Lab's 📦 passes "where it goes" to Hermes and shows Hermes's label refusal."""
from __future__ import annotations

from ailab import preview
from tests.test_server import Srv
from tests.test_ship import FakeMCP


class Refusing(FakeMCP):
    def call(self, tool, args=None):
        if tool == "app_ship" and args["name"].lower() == "test":
            from ailab.mcp_client import HermesRefused
            raise HermesRefused("ship_refused", "'test' is a throwaway label — give the app a real name (e.g. starfall-tetris)")
        return super().call(tool, args)


class ShipHome(Srv):
    def _site(self):
        site = preview.ensure_site("scratch")
        (site / "index.html").write_text("<p>hi</p>")

    def test_home_group_passed_and_echoed(self):
        self.app.cfg["mode"] = "connected"
        self.app.lab.mcp = FakeMCP()
        self._site()
        code, r, _ = self.req("/api/ship/start", {"project": "scratch", "name": "Starfall Tetris",
                                                  "platforms": ["android"], "home_group": "Gifts"})
        self.assertTrue(r["ok"], r)
        tool, args = self.app.lab.mcp.calls[-1]
        self.assertEqual((tool, args["home_group"]), ("app_ship", "Gifts"))
        self.assertEqual((r["library_group"], r["home_group"]), ("Testing", "Gifts"))

    def test_unknown_home_group_left_to_hermes(self):
        self.app.cfg["mode"] = "connected"
        self.app.lab.mcp = FakeMCP()
        self._site()
        code, r, _ = self.req("/api/ship/start", {"project": "scratch", "name": "Board", "home_group": "Nowhere"})
        self.assertTrue(r["ok"], r)
        self.assertNotIn("home_group", self.app.lab.mcp.calls[-1][1])

    def test_bad_name_refusal_reaches_scott(self):
        self.app.cfg["mode"] = "connected"
        self.app.lab.mcp = Refusing()
        self._site()
        code, r, _ = self.req("/api/ship/start", {"project": "scratch", "name": "test"})
        self.assertFalse(r["ok"])
        self.assertIn("real name", r.get("message", "") + str(r))
