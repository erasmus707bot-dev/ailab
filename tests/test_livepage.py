"""🪞 Show & change (2026-11-23): page list, Now/New look-through ports, changed-copy overlay, look-only, checks, Keep / Throw away."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from ailab import agent, config, livepage, preview, server

WEB = "dist/web"
PAGE = "<!doctype html><html><head><title>Gaming  Studio</title></head><body><button id=save>Save</button><script>var a = 1;</script></body></html>"


class Upstream(BaseHTTPRequestHandler):
    seen: list = []

    def log_message(self, *a):
        pass

    def _go(self):
        n = int(self.headers.get("Content-Length") or 0)
        type(self).seen.append((self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, self.rfile.read(n) if n else b""))
        p = self.path.split("?")[0]
        if p in ("/gaming.html", "/gaming", "/"):
            body, ctype = (self.server.webdir / ("index.html" if p == "/" else "gaming.html")).read_bytes(), "text/html; charset=utf-8"
        elif p == "/api/x":
            body, ctype = json.dumps({"ok": True, "m": self.command}).encode(), "application/json"
        else:
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _go


class Base(unittest.TestCase):
    flags = {"live": True}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        os.environ["AILAB_HOME"] = str(self.home / "labhome")
        self.repo = self.home / "hermes"
        self.webdir = self.repo / WEB
        self.webdir.mkdir(parents=True)
        (self.webdir / "gaming.html").write_text(PAGE)
        (self.webdir / "index.html").write_text("<html><head><title>Home</title></head><body>home</body></html>")
        (self.webdir / "app.js").write_text("var b = 2;\n")
        (self.repo / "core.py").write_text("x = 1\n")
        hp = mock.patch.object(Path, "home", return_value=self.home)
        hp.start()
        Upstream.seen = []
        self.up = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        self.up.webdir = self.webdir
        threading.Thread(target=self.up.serve_forever, daemon=True).start()
        self.cfg = config.load({"flags": self.flags, "repos": {"hermes": str(self.repo)}, "live_ports": [0, 0],
                                "live_apps": {"hermes": {"url": f"http://127.0.0.1:{self.up.server_address[1]}", "repo": "hermes", "web": WEB},
                                              "far": {"url": "http://example.com:80", "repo": "hermes", "web": WEB},
                                              "ghost": {"url": "http://127.0.0.1:9", "repo": "nope", "web": WEB}}})
        self.app = livepage.app_of(self.cfg, "hermes")
        self.live = livepage.Live(self.cfg)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "AILAB_HOME", None)
        self.addCleanup(hp.stop)
        self.addCleanup(self.up.server_close)
        self.addCleanup(self.up.shutdown)
        self.addCleanup(self.live.close)

    def copy(self, rel: str, text: str) -> Path:
        f = preview.site_dir("scratch") / "repos" / "hermes" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
        return f

    def get(self, side: str, path: str, data=None, headers=None):
        r = urllib.request.Request(f"http://127.0.0.1:{self.live.ports()[side]}{path}", data, headers or {})
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, resp.read().decode(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(), e.headers


class Pages(Base):
    def test_only_linked_loopback_apps(self):
        self.assertEqual(list(livepage.apps(self.cfg)), ["hermes"])
        with self.assertRaises(livepage.LiveError):
            livepage.app_of(self.cfg, "far")

    def test_page_list_home_first_with_titles(self):
        self.assertEqual([(p["path"], p["title"]) for p in livepage.pages(self.app)], [("/", "Home"), ("/gaming.html", "Gaming Studio")])
        self.assertTrue(livepage.is_up(self.app))


class Ports(Base):
    def setUp(self):
        super().setUp()
        self.live.open("scratch", "hermes")

    def test_now_passes_through_and_can_be_framed(self):
        code, body, hdrs = self.get("now", "/gaming.html", headers={"Cookie": "hx_tok=abc"})
        self.assertEqual(code, 200)
        self.assertIn('<script src="/__lab/pick.js?side=now"></script>', body)
        self.assertIn("<button id=save>", body)
        self.assertIsNone(hdrs.get("X-Frame-Options"))
        self.assertNotIn("frame-ancestors", hdrs.get("Content-Security-Policy"))
        seen = Upstream.seen[-1][2]
        self.assertEqual(seen["cookie"], "hx_tok=abc")
        self.assertEqual(seen["host"], f"127.0.0.1:{self.up.server_address[1]}")
        for marker in ("x-forwarded-for", "x-forwarded-host", "forwarded", "via", "x-real-ip"):   # must not add proxy markers…
            self.assertNotIn(marker, seen)
        self.get("now", "/gaming.html", headers={"X-Forwarded-For": "100.1.2.3", "Tailscale-User-Login": "x@y"})
        seen = Upstream.seen[-1][2]                                                                 # …and must never drop them
        self.assertEqual((seen["x-forwarded-for"], seen["tailscale-user-login"]), ("100.1.2.3", "x@y"))

    def test_fetched_html_is_not_touched(self):
        code, body, _ = self.get("now", "/gaming.html", headers={"Sec-Fetch-Dest": "empty"})
        self.assertEqual((code, body), (200, PAGE))

    def test_pick_script_served(self):
        code, body, hdrs = self.get("new", "/__lab/pick.js?side=new")
        self.assertEqual(code, 200)
        self.assertIn("javascript", hdrs["Content-Type"])
        self.assertIn('"picked"', body)

    def test_new_same_until_changed_then_shows_the_copy(self):
        self.copy(f"{WEB}/gaming.html", PAGE)                                   # pulled, not changed
        _, body, hdrs = self.get("new", "/gaming.html")
        self.assertIn("<button id=save>Save", body)
        self.assertEqual(livepage.changed("scratch", self.app), {"pages": [], "other": []})
        self.copy(f"{WEB}/gaming.html", PAGE.replace("Save<", "SAVE IT<"))
        n = len(Upstream.seen)
        for path in ("/gaming.html", "/gaming", "/gaming.html?_lab=1"):
            code, body, hdrs = self.get("new", path)
            self.assertEqual(code, 200)
            self.assertIn("SAVE IT", body)
            self.assertIn("pick.js?side=new", body)
            self.assertIn("default-src 'self'", hdrs["Content-Security-Policy"])
        self.assertEqual(len(Upstream.seen), n)                                 # served from the copy, app not asked
        self.assertIn("Save</button>", self.get("now", "/gaming.html")[1])       # Now is untouched
        self.assertEqual((self.webdir / "gaming.html").read_text(), PAGE)       # the real file never changes

    def test_new_is_look_only(self):
        n = len(Upstream.seen)
        code, body, _ = self.get("new", "/api/x", data=b"{}", headers={"Content-Type": "application/json"})
        self.assertEqual((code, json.loads(body)["error"]), (403, "look_only"))
        self.assertEqual((len(Upstream.seen), self.live.blocked), (n, 1))
        self.assertEqual(self.get("new", "/api/x")[0], 200)                     # reading is fine
        self.assertEqual(self.get("now", "/api/x", data=b"{}")[0], 200)         # Now is the real app
        self.live.allow_writes = True
        self.assertEqual(json.loads(self.get("new", "/api/x", data=b"{}")[1])["m"], "POST")
        self.assertEqual(Upstream.seen[-1][3], b"{}")

    def test_overlay_stays_in_the_web_folder(self):
        self.copy("core.py", "x = 2\n")
        self.copy(f"{WEB}/gaming.html", "changed")
        for bad in ("/../core.py", "/..%2fcore.py", "//etc/passwd", "/.env", "/core.py"):
            self.assertIsNone(livepage.overlay("scratch", self.app, bad), bad)
        self.assertIsNotNone(livepage.overlay("scratch", self.app, "/gaming"))
        os.symlink(self.repo / "core.py", preview.site_dir("scratch") / "repos" / "hermes" / WEB / "link.html")
        self.assertIsNone(livepage.overlay("scratch", self.app, "/link.html"))

    def test_app_down_says_so(self):
        self.up.shutdown(); self.up.server_close()
        code, body, _ = self.get("now", "/gaming.html")
        self.assertEqual(code, 502)
        self.assertIn("not answering", body)

    def test_status_of(self):
        self.assertEqual((self.live.status_of("now", "/gaming.html#x"), self.live.status_of("new", "/nope")), (200, 404))


class KeepToss(Base):
    def test_changed_keep_holds_and_discard_restores(self):
        self.copy(f"{WEB}/gaming.html", PAGE.replace("Save<", "Go<"))
        self.copy("core.py", "x = 2\n")
        self.copy(f"{WEB}/app.js", "var b = 2;\n")                              # same as real
        self.assertEqual(livepage.changed("scratch", self.app), {"pages": [f"{WEB}/gaming.html"], "other": ["core.py"]})
        res = livepage.keep("scratch", self.app, "bigger button")
        self.assertEqual([h["path"] for h in res["held"]], [f"{WEB}/gaming.html", "core.py"])
        items = agent.approvals()
        self.assertEqual({i["path"] for i in items}, {str(self.webdir / "gaming.html"), str(self.repo / "core.py")})
        self.assertEqual((self.webdir / "gaming.html").read_text(), PAGE)       # held, not written
        livepage.keep("scratch", self.app)                                      # keeping again replaces, never doubles
        self.assertEqual(len(agent.approvals()), 2)
        new = self.copy(f"{WEB}/brand-new.html", "<html></html>")
        self.assertEqual(livepage.discard("scratch", self.app)["discarded"], 3)
        self.assertEqual(livepage.changed("scratch", self.app), {"pages": [], "other": []})
        self.assertFalse(new.exists())

    def test_keep_skips_keys(self):
        self.copy(f"{WEB}/gaming.html", 'k = "sk-ant-api03-' + "a" * 40 + '"')
        res = livepage.keep("scratch", self.app)
        self.assertEqual((res["held"], len(res["skipped"])), ([], 1))

    def test_syntax_checks_never_run_code(self):
        self.copy("core.py", "def broken(:\n")
        self.copy(f"{WEB}/data.json", "{nope")
        self.copy(f"{WEB}/gaming.html", PAGE.replace("var a = 1;", "var a = ;"))
        self.copy(f"{WEB}/app.js", "var ok = 3;\n")
        res = livepage.syntax("scratch", self.app)
        by = {f["file"]: f["ok"] for f in res["files"]}
        self.assertFalse(by["core.py"])
        self.assertFalse(by[f"{WEB}/data.json"])
        if shutil.which("node"):
            self.assertEqual((by[f"{WEB}/gaming.html"], by[f"{WEB}/app.js"]), (False, True))


class Api(Base):
    def setUp(self):
        super().setUp()
        self.sapp = server.App(self.cfg, lab=object())
        self.srv = server.make_server(self.sapp, port=0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.addCleanup(lambda: self.sapp.live.close())

    def req(self, path, body=None):
        r = urllib.request.Request(self.base + path, json.dumps(body).encode() if body is not None else None,
                                   {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status, json.loads(resp.read()), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read()), e.headers

    def test_open_check_keep_discard(self):
        code, r, _ = self.req("/api/live/apps")
        self.assertEqual((code, [a["name"] for a in r["apps"]], r["apps"][0]["up"]), (200, ["hermes"], True))
        code, r, _ = self.req("/api/live/open", {"project": "scratch", "app": "hermes"})
        self.assertEqual(code, 200)
        self.assertTrue(r["ports"]["now"] and r["ports"]["new"] and r["ports"]["now"] != r["ports"]["new"])
        self.copy(f"{WEB}/gaming.html", PAGE.replace("Save<", "Go<"))
        code, r, _ = self.req("/api/live/check", {"project": "scratch", "app": "hermes", "path": "/gaming.html"})
        self.assertEqual((code, r["now"], r["new"], r["changed"]["pages"]), (200, 200, 200, [f"{WEB}/gaming.html"]))
        self.assertTrue(all(f["ok"] for f in r["syntax"]["files"]))
        self.assertTrue(self.req("/api/live/writes", {"allow": True})[1]["writes"])
        self.assertFalse(self.req("/api/live/open", {"project": "scratch", "app": "hermes"})[1]["writes"] is False)   # same page: stays
        self.assertEqual(len(self.req("/api/live/keep", {"project": "scratch", "app": "hermes"})[1]["held"]), 1)
        self.assertEqual(self.req("/api/live/discard", {"project": "scratch", "app": "hermes"})[1]["discarded"], 1)
        self.assertEqual(self.req("/api/live/changed?project=scratch&app=hermes")[1]["changed"]["pages"], [])
        self.assertEqual(self.req("/api/live/open", {"project": "scratch", "app": "nope"})[0], 404)

    def test_lab_page_may_frame_only_the_two_ports(self):
        self.req("/api/live/open", {"project": "scratch", "app": "hermes"})
        with urllib.request.urlopen(self.base + "/", timeout=5) as resp:
            csp, html = resp.headers["Content-Security-Policy"], resp.read().decode()
        ports = self.sapp.live.ports()
        self.assertIn(f"frame-src 'self' http://127.0.0.1:{ports['now']} https://127.0.0.1:{ports['now']} http://127.0.0.1:{ports['new']}", csp)
        self.assertIn("function liveView()", html)


class ApiOff(Api):
    flags = {"live": False}

    def test_open_check_keep_discard(self):
        for path, body in (("/api/live/apps", None), ("/api/live/open", {"app": "hermes"}), ("/api/live/keep", {"app": "hermes"})):
            code, r, _ = self.req(path, body)
            self.assertEqual((code, r["code"]), (403, "not_switched_on"))

    def test_lab_page_may_frame_only_the_two_ports(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as resp:
            self.assertNotIn("frame-src", resp.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()


class PycIgnored(unittest.TestCase):
    def test_pycache_is_not_a_change(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "copy"
            (base / "forge/__pycache__").mkdir(parents=True)
            (base / "forge/__pycache__/card.cpython-312.pyc").write_bytes(b"x")
            (base / "forge/card.py").write_text("changed")
            real = Path(d) / "real"
            (real / "forge").mkdir(parents=True)
            (real / "forge/card.py").write_text("orig")
            with mock.patch.object(livepage, "_copies", return_value=base):
                out = livepage.changed("p", {"web": "web", "root": real})
            self.assertEqual(out["other"], ["forge/card.py"])
