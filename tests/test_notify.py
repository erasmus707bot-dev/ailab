"""M5 (2026-11-24): 📱 phone pings — only "finished" or "stuck", once per run."""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from ailab import notify as N


def run(state, quiet=0, lane=False):
    r = SimpleNamespace(state=state, is_lane=lane, task="Make the scan button green\nmore", why="ok",
                        project={"id": "scratch", "name": "Scratch"})
    r.stuck_info = lambda: {"stuck": state == "running" and quiet >= 600, "quiet_s": quiet}
    return r


class Pings(unittest.TestCase):
    def test_verdicts(self):
        self.assertEqual(N.verdict(run("done")), "finished")
        for s in ("failed", "capped", "unproven"):
            self.assertEqual(N.verdict(run(s)), "stuck")
        self.assertEqual(N.verdict(run("running", 700)), "stuck")
        self.assertEqual(N.verdict(run("running", 10)), "")
        self.assertEqual(N.verdict(run("stopped")), "")              # he stopped it himself: no ping
        self.assertEqual(N.verdict(run("done", lane=True)), "")      # ⚖️ Compare lanes never ping

    def test_watcher_pings_once(self):
        sent = []
        agents = SimpleNamespace(runs={"a": run("done"), "b": run("running", 5)})
        w = N.Watcher(agents, {}, sender=lambda t, b, topic: sent.append((t, topic)))
        w.tick(); w.tick()
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0][0].startswith("✅ Lab finished"))
        agents.runs["b"] = run("running", 900)
        w.tick()
        self.assertEqual(len(sent), 2)
        self.assertEqual(N.Watcher(agents, {"phone_pings": False}, sender=lambda *a: sent.append(a)).tick(), [])

    def test_send_uses_alerts_json_and_is_silent_without_it(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "alerts.json"
            self.assertFalse(N.send("t", "b", alerts=f))
            f.write_text(json.dumps({"channel": "ntfy", "url": "http://127.0.0.1:1", "token": "x"}))
            seen = {}

            class R:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *a): return False

            def opener(req, timeout):
                seen["auth"], seen["body"] = req.get_header("Authorization"), json.loads(req.data)
                return R()
            self.assertTrue(N.send("t", "b", alerts=f, opener=opener))
            self.assertEqual(seen["auth"], "Bearer x")
            self.assertEqual(seen["body"]["topic"], N.DEFAULT_TOPIC)


if __name__ == "__main__":
    unittest.main()
