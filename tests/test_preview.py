"""M4 acceptance — live preview behind the `preview` flag, served from the srt sandbox."""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
import unittest
from pathlib import Path
from unittest import mock

from ailab import config, preview
from tests.test_server import Srv

HAS_SRT = bool(shutil.which("srt"))
PNG = "data:image/png;base64," + base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + bytes.fromhex("0000000d49484452000000010000000108060000001f15c489"
                                         "0000000d4944415478da63f8ffff3f0005fe02fea7d6a4d60000000049454e44ae426082")).decode()


class PreviewOff(Srv):
    flags = {"router": False}

    def test_everything_403_and_nothing_made(self):
        for path in ("/api/preview/files?project=scratch", "/api/preview/version?project=scratch",
                     "/api/preview/file?project=scratch&path=index.html"):
            code, body, _ = self.req(path)
            self.assertEqual((code, body["code"], body["flag"]), (403, "not_switched_on", "preview"), path)
        code, body, _ = self.req("/api/preview/file", {"project": "scratch", "path": "index.html", "text": "x"})
        self.assertEqual(code, 403)
        code, body, _ = self.req("/preview/scratch/")
        self.assertEqual(code, 403)
        self.assertFalse((Path(self.tmp.name) / "projects").exists())      # no folder, no sandbox started
        self.assertIsNone(getattr(self.app, "_pv", None))

    def test_start_page_lists_preview_off(self):
        code, html, _ = self.req("/")
        self.assertIn('id: "preview", flag: "preview"', html)
        self.assertIn('sandbox: "allow-scripts allow-forms allow-modals"', html)   # iframe is sandboxed


class PreviewOn(Srv):
    flags = {"preview": True}

    def setUp(self):
        if not HAS_SRT:
            os.environ["AILAB_ALLOW_UNSANDBOXED"] = "1"                     # logic only; acceptance needs srt
        super().setUp()

    def tearDown(self):
        if getattr(self.app, "_pv", None):
            self.app._pv.close()
        os.environ.pop("AILAB_ALLOW_UNSANDBOXED", None)
        super().tearDown()

    @unittest.skipUnless(HAS_SRT, "srt not installed — acceptance owed on gandalf")
    def test_acceptance_fixture_renders_in_srt_and_reloads_after_edit(self):
        code, body, _ = self.req("/api/preview/files?project=scratch")
        self.assertEqual((code, body["sandbox"]), (200, "srt"))
        self.assertEqual({f["path"] for f in body["files"]}, {"index.html", "style.css", "app.js"})
        code, html, hdrs = self.req("/preview/scratch/")
        self.assertEqual(code, 200)
        self.assertIn("Hello from the Lab", html)
        self.assertTrue(hdrs["Content-Security-Policy"].startswith("sandbox allow-scripts"))
        code, css, hdrs = self.req("/preview/scratch/style.css")
        self.assertIn("text/css", hdrs["Content-Type"])
        v1 = self.req("/api/preview/version?project=scratch")[1]["v"]
        time.sleep(0.01)
        code, r, _ = self.req("/api/preview/file", {"project": "scratch", "path": "index.html",
                                                      "text": "<h1>Edited in the Lab</h1>"})
        self.assertTrue(r["ok"])
        v2 = self.req("/api/preview/version?project=scratch")[1]["v"]
        self.assertNotEqual(v1, v2)                                         # page polls this → reload
        self.assertIn("Edited in the Lab", self.req("/preview/scratch/")[1])
        procs = subprocess.run(["pgrep", "-f", "srt -s .*srt-scratch.json"], capture_output=True, text=True)
        self.assertTrue(procs.stdout.strip(), "preview must be served by an srt process")

    @unittest.skipUnless(HAS_SRT, "srt not installed")
    def test_srt_settings_block_home_and_network(self):
        root = preview.ensure_site("scratch")
        secret = Path.home() / f".ailab-test-secret-{os.getpid()}"
        secret.write_text("nope")
        try:
            cfg = Path(self.tmp.name) / "s.json"
            scratch = Path(self.tmp.name) / "scratch"
            scratch.mkdir()
            cfg.write_text(json.dumps(preview.srt_settings(root.resolve(), scratch)))
            r = subprocess.run(["srt", "-s", str(cfg), "sh", "-c",
                                f"cat {secret}; echo x > {root}/w.txt; cat {root}/index.html | head -c 15"],
                               capture_output=True, text=True, timeout=60, cwd="/tmp",
                               stdin=subprocess.DEVNULL)
            self.assertNotIn("nope", r.stdout)
            self.assertFalse((root / "w.txt").exists())                       # sandbox writes nothing
            self.assertIn("<!DOCTYPE html>", r.stdout)                          # but can read the project
        finally:
            secret.unlink()

    def test_saves_stay_inside_the_project(self):
        preview.ensure_site("scratch")
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        os.symlink(outside, preview.site_dir("scratch") / "link")
        for bad in ("../x.html", "/etc/x.html", ".hidden.js", "run.py", "a/../../x.html", "link/x.html", ""):
            code, body, _ = self.req("/api/preview/file", {"project": "scratch", "path": bad, "text": "x"})
            self.assertFalse(body["ok"], bad)
            self.assertIn(code, (400, 403), bad)
        self.assertEqual(list(outside.iterdir()), [])
        code, body, _ = self.req("/api/preview/file", {"project": "scratch", "path": "pages/new.html", "text": "ok"})
        self.assertTrue(body["ok"])
        code, body, _ = self.req("/api/preview/file", {"project": "nope", "path": "a.html", "text": "x"})
        self.assertEqual(body["code"], "bad_args")

    def test_sandbox_serves_nothing_outside_root(self):
        site = preview.ensure_site("scratch")
        (Path(self.tmp.name) / "secret.txt").write_text("nope")
        os.symlink(Path(self.tmp.name) / "secret.txt", site / "peek.txt")
        code, body, _ = self.req("/preview/scratch/peek.txt")
        self.assertEqual(code, 404)
        self.assertNotIn("nope", str(body))

    def test_preview_frame_cannot_use_the_api(self):
        x = {"Sec-Fetch-Site": "cross-site"}
        self.assertEqual(self.req("/api/state", headers=x)[0], 403)
        self.assertEqual(self.req("/api/preview/file", {"project": "scratch", "path": "a.html", "text": "x"}, x)[0], 403)
        self.assertEqual(self.req("/api/chat", {"messages": [1]}, {"Origin": "null"})[0], 403)
        self.assertEqual(self.req("/api/autosave", {"project": "scratch"}, {"Content-Type": "text/plain"})[0], 415)

    def test_capture_saved_in_project(self):
        code, body, _ = self.req("/api/preview/capture", {"project": "scratch", "png": PNG})
        self.assertTrue(body["ok"], body)
        f = Path(self.tmp.name) / "projects/scratch/captures" / body["file"]
        self.assertTrue(f.read_bytes().startswith(b"\x89PNG"))
        code, body, _ = self.req("/api/preview/capture", {"project": "scratch", "png": "data:image/png;base64,AAAA"})
        self.assertEqual(code, 400)

    def test_no_srt_means_no_preview_never_unsandboxed(self):
        os.environ.pop("AILAB_ALLOW_UNSANDBOXED", None)
        with mock.patch("ailab.preview.shutil.which", return_value=None), \
                mock.patch("ailab.preview.subprocess.Popen") as popen:
            code, body, _ = self.req("/api/preview/version?project=scratch")
            self.assertEqual((code, body["code"], body["icon"]), (503, "no_sandbox", "🧱"))
            code, text, _ = self.req("/preview/scratch/")
            self.assertEqual(code, 503)
            popen.assert_not_called()

    def test_runtime_prefix_under_home_is_readable(self):
        npm = str(Path.home() / ".npm-global/lib/node_modules/@anthropic-ai/sandbox-runtime/dist/cli.js")
        self.assertEqual(preview._prefix(npm), Path.home() / ".npm-global")
        self.assertEqual(preview._prefix("/usr/bin/python3"), Path("/usr"))
        s = preview.srt_settings(Path("/x"))
        self.assertNotIn(str(Path.home()), s["filesystem"]["allowRead"])         # never the whole home
        self.assertIn("/x", s["filesystem"]["denyWrite"])

    def test_dead_sandbox_restarts(self):
        self.req("/preview/scratch/")
        box = self.app.pv.box("scratch")
        box.proc.kill()
        box.proc.wait()
        code, html, _ = self.req("/preview/scratch/")
        self.assertEqual(code, 200)


if __name__ == "__main__":
    unittest.main()
