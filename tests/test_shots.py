"""📸 ✋ rows in plain words + Before | After pictures (2026-11-25) — and the 🔀 'real file moved' refusal."""
import hashlib
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from ailab import agent, review, shots


class Spots(unittest.TestCase):
    def test_kind(self):
        self.assertEqual(shots.kind("web/index.html"), "look")
        self.assertEqual(shots.kind("a/style.css"), "look")
        self.assertEqual(shots.kind("ailab/review.py"), "works")

    def test_html_new_element_first_neighbour_as_fallback(self):
        diff = ("--- a/index.html\n+++ b/index.html\n@@ -1,2 +1,3 @@\n"
                ' <button type="button" class="tile" onclick="openLab()" aria-label="Open the AI Lab">x</button>\n'
                '+<button type="button" class="tile" onclick="openGuard()" aria-label="Open Rollback">y</button>\n')
        s = shots.spots("index.html", diff)
        self.assertTrue(s["after"][0].startswith('button[aria-label="Open Rollback"]'))
        self.assertIn('[onclick="openGuard()"]', s["after"][0])
        self.assertIn('[onclick="openLab()"]', s["before"][0])            # Before has no new button → its neighbour

    def test_css_rule_selectors(self):
        diff = "@@ -1 +1,2 @@\n .a { x: 1; }\n+  .chg .hd b, .chg summary:hover, #guardline { font-size: 23px; }\n"
        s = shots.spots("index.html", diff)
        self.assertEqual(s["after"][:3], ["#guardline", ".chg .hd b", ".chg summary"])      # an id is specific → first

    def test_quotes_escaped(self):
        self.assertEqual(shots._q('a"b\\c'), 'a\\"b\\\\c')
        self.assertEqual(shots._html_sel('<a id="x" onclick="go(${n})">'), 'a[id="x"]')        # template bits skipped


class Make(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        (self.d / "site").mkdir()
        self.page = self.d / "site" / "index.html"
        self.page.write_text('<link rel="stylesheet" href="s.css"><p id="t">old</p>')
        (self.d / "site" / "s.css").write_text("p{color:red}")
        (self.d / "store").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_before_is_real_after_is_swapped_and_nothing_written(self):
        got = {}

        def driver(page, b_url, a_url, sels, base, cfg):
            for side, url in (("before", b_url), ("after", a_url)):
                got[side] = urllib.request.urlopen(url + page).read().decode()
                got[side + "_css"] = urllib.request.urlopen(url + "s.css").read().decode()
                Path(f"{base}-{side}.png").write_bytes(side.encode())
            with self.assertRaises(Exception):
                urllib.request.urlopen(b_url + "../store/x")             # nothing outside the folder
            return {"after": {"found": True}, "before": {"found": True}}
        m = shots.make("20261125-010101-abcdef", self.page, '<p id="t">new</p>', "+<p id=\"t\">new</p>",
                       self.d / "store", driver=driver)
        self.assertIn("old", got["before"])
        self.assertIn("new", got["after"])
        self.assertEqual(got["after_css"], "p{color:red}")
        self.assertTrue(m["ran"] and not m["same"] and m["found"])
        self.assertIn("old", self.page.read_text())                        # real file untouched
        self.assertEqual(shots.picture(self.d / "store", "20261125-010101-abcdef", "after"), b"after")
        self.assertIsNone(shots.picture(self.d / "store", "../x", "after"))
        calls = []
        shots.make("20261125-010101-abcdef", self.page, '<p id="t">new</p>', "", self.d / "store",
                   driver=lambda *a: calls.append(1))
        self.assertEqual(calls, [])                                        # cached by the proposal's sha

    def test_code_file_is_not_pictured(self):
        m = shots.make("20261125-010101-aaaaaa", self.d / "site" / "x.py", "y = 2\n", "", self.d / "store",
                       driver=lambda *a: self.fail("no browser for code"))
        self.assertFalse(m["visual"])
        self.assertIn("how it works", m["why"])


class Moved(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "AILAB_HOME": str(self.home / "cfg"),
                                                "AILAB_FILES": str(self.home / "files")})
        self.env.start()
        (self.home / "cfg").mkdir()
        (self.home / "cfg" / "config.json").write_text(json.dumps({"guarded": {}}))
        self.f = self.home / "work" / "page.txt"
        self.f.parent.mkdir()
        self.f.write_text("v1\n")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _hold(self):
        base = hashlib.sha256(self.f.read_bytes()).hexdigest()
        item = agent.hold_for_approval("p1", "r1", str(self.f), "v2\n", plain={"what": "w", "where": "x"}, base=base)
        return next(r for r in review.held() if r["id"] == item["id"])

    def test_apply_refuses_when_the_real_file_changed_since(self):
        row = self._hold()
        self.assertFalse(row["moved"])
        self.assertEqual(row["plain"]["what"], "w")
        self.f.write_text("someone else's edit\n")
        self.assertTrue(next(r for r in review.held() if r["id"] == row["id"])["moved"])
        with self.assertRaises(review.ReviewError) as e:
            review.apply(row["id"], row["sha"], "apply")
        self.assertEqual(e.exception.code, "moved")
        self.assertEqual(self.f.read_text(), "someone else's edit\n")      # their edit kept

    def test_apply_goes_through_when_unchanged(self):
        row = self._hold()
        self.assertTrue(review.apply(row["id"], row["sha"], "apply")["ok"])
        self.assertEqual(self.f.read_text(), "v2\n")


class Live(unittest.TestCase):
    """The Lab's own page: pictures go through a GET-only proxy to the running program, so they show real data."""
    def setUp(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.web = self.d / "lab" / "ailab" / "web"
        self.web.mkdir(parents=True)
        self.page = self.web / "index.html"
        self.page.write_text('<p class="chg">old</p><script>fetch("/api/held")</script>')
        (self.d / "store").mkdir()
        page, self.posts = self.page, []
        me = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):  # noqa: N802
                body = page.read_bytes() if self.path == "/" else b'{"held": 3}' if self.path == "/api/held" else None
                self.send_response(200 if body is not None else 404)
                self.send_header("Content-Length", str(len(body or b"")))
                self.end_headers()
                self.wfile.write(body or b"")

            def do_POST(self):  # noqa: N802
                me.posts.append(self.path)
                self.send_response(200)
                self.end_headers()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.cfg = {"guarded": {"ailab": str(self.d / "lab")}, "shot_live": {str(self.web): f"http://127.0.0.1:{self.srv.server_address[1]}"}}

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def test_live_data_passes_through_and_only_the_change_is_swapped(self):
        self.assertEqual(shots.live_for(self.page, self.cfg)[1], "/")
        got = {}

        def driver(page, b_url, a_url, sels, base, cfg):
            got["before"] = urllib.request.urlopen(b_url + page).read().decode()
            got["after"] = urllib.request.urlopen(a_url + page).read().decode()
            got["api"] = urllib.request.urlopen(a_url + "api/held").read().decode()
            req = urllib.request.Request(a_url + "api/apply", data=b"{}", method="POST")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(req)                                  # writes never reach the live program
            for side in ("before", "after"):
                Path(f"{base}-{side}.png").write_bytes(side.encode())
            return {"after": {"found": True}}
        import urllib.error  # noqa: F401
        m = shots.make("20261125-020202-bbbbbb", self.page, '<p class="chg">new</p>', "", self.d / "store",
                       cfg=self.cfg, driver=driver)
        self.assertTrue(m.get("live"))
        self.assertIn("old", got["before"])
        self.assertIn("new", got["after"])
        self.assertEqual(got["api"], '{"held": 3}')
        self.assertEqual(self.posts, [])

    def test_falls_back_to_the_folder_when_live_differs_from_disk(self):
        self.page.write_text("<p>edited on disk, not reloaded</p>")
        live_body = b"<p>something else</p>"
        with mock.patch.object(shots, "_fetch", return_value=(200, live_body, "text/html")):
            m = shots.make("20261125-020202-cccccc", self.page, "<p>new</p>", "", self.d / "store", cfg=self.cfg,
                           driver=lambda page, b, a, s, base, c: [Path(f"{base}-{x}.png").write_bytes(x.encode())
                                                                  for x in ("before", "after")] and {})
        self.assertFalse(m.get("live"))
        self.assertTrue(m["ran"])


class Words(unittest.TestCase):
    def test_text_only_change_is_found_by_its_words_not_a_generic_neighbour(self):
        diff = ("@@ -1,4 +1,4 @@\n"
                ' <section class="tile">\n  <div class="ic">🛟</div>\n'
                "-  <p>Put the AI Lab or Hermes back the way it was. Works even when the Lab is down.</p>\n"
                "+  <p>Put the AI Lab or Hermes back the way it was — even when the Lab won't open.</p>\n")
        s = shots.spots("remote.html", diff)
        self.assertTrue(s["after_text"][0].startswith("Put the AI Lab or Hermes back the way it was — even"))
        self.assertIn("Works even when the Lab is down.", s["before_text"][0])
        self.assertIn('section[class="tile"]', s["after"])                 # generic neighbours only as a fallback

    def test_specific_selectors_before_generic_ones(self):
        diff = ('@@ -1 +1,2 @@\n <div class="row">\n'
                '+<button class="tile" onclick="openGuard()">🛟</button>\n')
        s = shots.spots("index.html", diff)
        self.assertIn('[onclick="openGuard()"]', s["after"][0])
