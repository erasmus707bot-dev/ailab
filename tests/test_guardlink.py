"""🛡 Guarded self-edit (2026-11-24): prove → Guard copy → watch → write → restart; nothing written otherwise."""
import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from ailab import agent, config, guardlink, review


class FakeGuard:
    def __init__(self):
        self.calls, self.fail = [], set()
        me = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _out(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):  # noqa: N802
                me.calls.append(("GET", self.path, {}))
                self._out(200, {"targets": []})

            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                me.calls.append(("POST", self.path, body))
                if self.path in me.fail:
                    return self._out(400, {"ok": False, "error": "nope"})
                self._out(200, {"ok": True, "id": "20261124-120000-000"})

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def paths(self):
        return [c[1] for c in self.calls]


def ok_runner(root, cmd):
    return {"exit": 0, "output": "fine"}


class GuardedApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "AILAB_HOME": str(self.home / "cfg"),
                                                "AILAB_FILES": str(self.home / "files")})
        self.env.start()
        self.prog = self.home / "labcode"
        (self.prog / "ailab").mkdir(parents=True)
        (self.prog / "ailab" / "thing.py").write_text("X = 1\n")
        subprocess.run(["git", "init", "-q", str(self.prog)], check=True)
        self.guard = FakeGuard()
        (self.home / "cfg").mkdir()
        (self.home / "cfg" / "config.json").write_text(json.dumps(
            {"guarded": {"ailab": str(self.prog)}, "guard_url": self.guard.url}))
        self.restarts = []
        self.rl = mock.patch.object(guardlink, "restart_later", lambda cfg, name, delay=1.5: self.restarts.append(name))
        self.rl.start()

    def tearDown(self):
        self.rl.stop()
        self.env.stop()
        self.guard.srv.shutdown()
        self.tmp.cleanup()

    def hold(self, rel, text):
        item = agent.hold_for_approval("p1", "r1", str(self.prog / rel), text)
        row = next(r for r in review.held() if r["id"] == item["id"])
        return row

    def test_held_row_says_guarded(self):
        self.assertEqual(self.hold("ailab/thing.py", "X = 2\n")["guarded"], "ailab")

    def test_order_prove_copy_watch_write_restart(self):
        row = self.hold("ailab/thing.py", "X = 2\n")
        seen = []

        def runner(root, cmd):
            seen.append((root / "ailab" / "thing.py").read_text())     # the trial copy holds the change
            self.assertEqual((self.prog / "ailab" / "thing.py").read_text(), "X = 1\n")   # real code untouched
            return {"exit": 0, "output": ""}
        r = review.apply_group([{"id": row["id"], "sha": row["sha"]}], "apply", runner=runner)
        self.assertTrue(r["ok"])
        self.assertIn("X = 2\n", seen)
        self.assertEqual(self.guard.paths(), ["/api/snap", "/api/watch"])
        self.assertEqual((self.prog / "ailab" / "thing.py").read_text(), "X = 2\n")
        self.assertEqual(self.restarts, ["ailab"])
        self.assertEqual(agent.approvals("applied")[0]["backup"], "guard:ailab:20261124-120000-000")

    def test_guard_down_writes_nothing(self):
        row = self.hold("ailab/thing.py", "X = 2\n")
        self.guard.fail.add("/api/snap")
        with self.assertRaises(review.ReviewError) as e:
            review.apply_group([{"id": row["id"], "sha": row["sha"]}], "apply", runner=ok_runner)
        self.assertEqual(e.exception.code if hasattr(e.exception, "code") else "", "guard_down")
        self.assertEqual((self.prog / "ailab" / "thing.py").read_text(), "X = 1\n")
        self.assertEqual(self.restarts, [])

    def test_failed_proof_writes_nothing_and_asks_guard_nothing(self):
        row = self.hold("ailab/thing.py", "X = (\n")
        with self.assertRaises(review.ReviewError):
            review.apply_group([{"id": row["id"], "sha": row["sha"]}], "apply",
                               runner=lambda root, cmd: {"exit": 1, "output": "SyntaxError"})
        self.assertEqual(self.guard.paths(), [])
        self.assertEqual((self.prog / "ailab" / "thing.py").read_text(), "X = 1\n")

    def test_tests_that_already_failed_dont_block(self):
        row = self.hold("ailab/thing.py", "X = 2\n")

        def runner(root, cmd):
            return {"exit": 1 if "pytest" in cmd else 0, "output": "old failure"}  # fails with AND without the change
        r = review.apply_group([{"id": row["id"], "sha": row["sha"]}], "apply", runner=runner)
        notes = [c.get("note", "") for d in r["done"] for c in d["checks"]]
        self.assertTrue(any("already failed" in n for n in notes))

    def test_tests_broken_by_the_change_block(self):
        row = self.hold("ailab/thing.py", "X = 2\n")

        def runner(root, cmd):
            changed = (root / "ailab" / "thing.py").read_text() == "X = 2\n"
            return {"exit": 1 if ("pytest" in cmd and changed) else 0, "output": "broke"}
        with self.assertRaises(review.ReviewError):
            review.apply_group([{"id": row["id"], "sha": row["sha"]}], "apply", runner=runner)
        self.assertEqual((self.prog / "ailab" / "thing.py").read_text(), "X = 1\n")

    def test_needs_the_word(self):
        row = self.hold("ailab/thing.py", "X = 2\n")
        with self.assertRaises(review.ReviewError):
            review.apply_group([{"id": row["id"], "sha": row["sha"]}], "yes", runner=ok_runner)

    def test_guard_files_never_written(self):
        g = self.home / "hermes-forge" / "ailab-guard"
        g.mkdir(parents=True)
        item = agent.hold_for_approval("p1", "r1", str(g / "guard.py"), "evil = 1\n")
        row = next(r for r in review.held() if r["id"] == item["id"])
        with self.assertRaises(review.ReviewError):
            review.apply(row["id"], row["sha"], "apply")
        self.assertFalse((g / "guard.py").exists())

    def test_lab_checks_run_all_tests(self):
        labels = [c[0] for c in guardlink.checks_for("ailab", self.prog, ["ailab/thing.py"])]
        self.assertTrue(any("every Lab test" in x for x in labels))
        self.assertTrue(any("Python reads" in x for x in labels))

    def test_lab_links_itself(self):
        self.assertIn("ailab", config.load()["repos"])

    def test_preview_ports_off_the_guard(self):
        self.assertNotIn(8860, config.DEFAULTS["live_ports"])


if __name__ == "__main__":
    unittest.main()
