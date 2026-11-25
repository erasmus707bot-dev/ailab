"""🎬 Long clips (2026-11-24): video/audio stream from the sandbox with HTTP Range — any length opens and seeks."""
from __future__ import annotations

import os
import shutil
import unittest
import urllib.error
import urllib.request

from ailab import preview, server
from ailab.sandbox import pipe_server
from tests.test_server import Srv

HAS_SRT = bool(shutil.which("srt"))
SIZE = 30_000_000                                    # over the old 25 MB one-piece cap


class ParseRange(unittest.TestCase):
    def test_forms(self):
        p = server.parse_range
        self.assertIsNone(p(None, 100))
        self.assertIsNone(p("bytes=0-1,5-9", 100))                  # multi-range → whole file
        self.assertEqual(p("bytes=0-", 100), (0, 99))
        self.assertEqual(p("bytes=10-19", 100), (10, 19))
        self.assertEqual(p("bytes=90-500", 100), (90, 99))
        self.assertEqual(p("bytes=-10", 100), (90, 99))
        self.assertEqual(p("bytes=0-", 10**9, cap=1000), (0, 999))  # open end clipped to one chunk
        self.assertEqual(p("bytes=100-", 100), "bad")
        self.assertEqual(p("bytes=50-10", 100), "bad")


class PipeSlices(unittest.TestCase):
    def test_stat_and_range_stay_inside_root(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "a.mp4"), "wb").write(bytes(range(256)) * 10)
            pipe_server.ROOT = os.path.realpath(d)
            st = pipe_server.handle({"op": "stat", "path": "a.mp4"})
            self.assertEqual((st["size"], st["ctype"]), (2560, "video/mp4"))
            r = pipe_server.handle({"op": "range", "path": "a.mp4", "start": 255, "length": 3})
            import base64
            self.assertEqual(base64.b64decode(r["b64"]), bytes([255, 0, 1]))
            self.assertEqual(pipe_server.handle({"op": "range", "path": "a.mp4", "start": 9999})["status"], 416)
            for bad in ("../x.mp4", ".h.mp4", "/etc/passwd"):
                self.assertEqual(pipe_server.handle({"op": "range", "path": bad})["status"], 404, bad)
            big = pipe_server.handle({"op": "range", "path": "a.mp4", "start": 0, "length": 10**9})
            self.assertLessEqual(len(base64.b64decode(big["b64"])), pipe_server.MAX_SLICE)


class Streams(Srv):
    flags = {"preview": True}

    def setUp(self):
        if not HAS_SRT:
            os.environ["AILAB_ALLOW_UNSANDBOXED"] = "1"
        super().setUp()
        root = preview.ensure_site("scratch")
        (root / "videos").mkdir(exist_ok=True)
        self.blob = os.urandom(SIZE)
        (root / "videos" / "long.mp4").write_bytes(self.blob)

    def tearDown(self):
        if getattr(self.app, "_pv", None):
            self.app._pv.close()
        os.environ.pop("AILAB_ALLOW_UNSANDBOXED", None)
        super().tearDown()

    def get(self, path, rng=None):
        r = urllib.request.Request(self.base + path, headers={"Range": rng} if rng else {})
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def test_ranges_are_byte_exact(self):
        for start, end in ((0, 999), (SIZE // 2, SIZE // 2 + 4_999_999), (SIZE - 1000, SIZE - 1)):
            code, data, h = self.get("/preview/scratch/videos/long.mp4", f"bytes={start}-{end}")
            self.assertEqual(code, 206)
            self.assertEqual(h["Content-Range"], f"bytes {start}-{end}/{SIZE}")
            self.assertEqual(h["Accept-Ranges"], "bytes")
            self.assertEqual(data, self.blob[start:end + 1])
        code, data, h = self.get("/preview/scratch/videos/long.mp4", "bytes=0-")
        self.assertEqual((code, len(data)), (206, server.RANGE_CHUNK))   # open end → one chunk, player asks for more
        code, _, h = self.get("/preview/scratch/videos/long.mp4", f"bytes={SIZE}-")
        self.assertEqual((code, h["Content-Range"]), (416, f"bytes */{SIZE}"))

    def test_no_range_streams_the_whole_file(self):
        code, data, h = self.get("/preview/scratch/videos/long.mp4")
        self.assertEqual((code, h["Accept-Ranges"], len(data)), (200, "bytes", SIZE))
        self.assertEqual(data, self.blob)

    def test_pages_and_escapes_unchanged(self):
        code, html, h = self.get("/preview/scratch/")
        self.assertEqual(code, 200)
        self.assertNotIn("Accept-Ranges", h)
        self.assertEqual(self.get("/preview/scratch/../x.mp4")[0], 404)
        self.assertEqual(self.get("/preview/scratch/videos/.hid.mp4")[0], 404)
        self.assertEqual(self.get("/preview/scratch/videos/none.mp4", "bytes=0-9")[0], 404)


if __name__ == "__main__":
    unittest.main()
