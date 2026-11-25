"""🔁 Loop (Creative Loop Phase 3, 2026-11-25) — Lab side talks to Hermes only through creative_* MCP tools."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from ailab import config, loop, server
from ailab.mcp_client import HermesRefused
from ailab.providers.base import ChatResult

JOB = {"id": "cj_20261125_ab12cd34", "goal": "packet travel", "project": "proready", "field": "aplus",
       "asset_type": "motion", "license_mode": "A", "state": "planned", "running": False, "waiting": [],
       "pieces": [{"n": 1, "do": "packet over four hops", "side": "proready", "method": "proready.primitive",
                   "why": "rule order", "est_usd": 0, "state": "planned", "needs": []}]}


class FakeMCP:
    def __init__(self):
        self.calls = []

    def call(self, tool, args=None):
        self.calls.append((tool, args or {}))
        if tool == "creative_spend_ok" and (args or {}).get("pin") != "1234":
            raise HermesRefused("pin", "Wrong PIN.", "Type your owner PIN.")
        if tool in ("creative_job_plan", "creative_job_get"):
            return {"ok": True, "job": JOB}
        if tool == "creative_jobs":
            return {"ok": True, "jobs": [{"id": JOB["id"], "goal": JOB["goal"], "state": "planned", "pieces": 1}]}
        if tool == "trust_list":
            return {"ok": True, "tasks": [{"task": "portfolio.publish", "on": False}], "never": ["erasmus.arm", "delete"]}
        return {"ok": True, "tool": tool}


class FakeLab:
    def __init__(self, reply='{"primitive":"packet-travel","params":{"hops":["PC","Switch","Router","ISP"]},"alt":"A packet hops."}'):
        self.mcp, self.reply, self.chats = FakeMCP(), reply, []

        class Sp:
            def spent_today(_):
                return 0.0
        self.spend = Sp()

    def chat(self, project, prov, model, msgs, max_tokens, task=""):
        self.chats.append((prov, model, project))
        return ChatResult(self.reply, prov, model, 10, 20, 0.0004, True)


class LoopUnit(unittest.TestCase):
    def test_plan_passes_only_known_fields(self):
        lab = FakeLab()
        lp = loop.Loop(server.App(config.load({}), lab=lab))
        lp.plan({"goal": "x", "project": "proready", "asset_type": "motion", "evil": 1, "planner_model": "m"})
        tool, args = lab.mcp.calls[-1]
        self.assertEqual(tool, "creative_job_plan")
        self.assertNotIn("evil", args)
        self.assertEqual(args["planner_model"], "m")
        with self.assertRaises(loop.LoopError):
            lp.plan({"goal": "  "})

    def test_author_writes_a_valid_primitive(self):
        lab = FakeLab()
        r = loop.Loop(server.App(config.load({}), lab=lab)).author({"job_id": JOB["id"], "piece": 1, "provider": "ollama", "model": "q"})
        self.assertEqual(r["payload"]["primitive"], "packet-travel")
        self.assertEqual(lab.chats[0][0], "ollama")

    def test_author_refuses_unknown_primitive(self):
        lab = FakeLab('{"primitive":"teleport","params":{},"alt":"x"}')
        with self.assertRaises(loop.LoopError):
            loop.Loop(server.App(config.load({}), lab=lab)).author({"job_id": JOB["id"], "piece": 1, "provider": "o", "model": "m"})

    def test_standalone_cannot_loop(self):
        lab = FakeLab()
        lab.mcp = None
        with self.assertRaises(loop.LoopError) as c:
            loop.Loop(server.App(config.load({}), lab=lab)).jobs({})
        self.assertEqual(c.exception.code, "standalone")

    def test_picture_only_from_ai_lab_folder(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HERMES_IMAGE_DIR"] = d
            try:
                (Path(d) / "ai-lab").mkdir()
                (Path(d) / "ai-lab" / "x.png").write_bytes(b"\x89PNG\r\n\x1a\nxx")
                (Path(d) / "secret.png").write_bytes(b"\x89PNG\r\n\x1a\nxx")
                self.assertEqual(loop.picture("ai-lab/x.png")[1], "image/png")
                self.assertEqual(loop.picture("secret.png"), (b"", ""))
                self.assertEqual(loop.picture("ai-lab/../secret.png"), (b"", ""))
            finally:
                os.environ.pop("HERMES_IMAGE_DIR", None)


class LoopServer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AILAB_HOME"] = self.tmp.name
        self.lab = FakeLab()
        self.app = server.App(config.load({}), lab=self.lab)
        self.srv = server.make_server(self.app, port=0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()
        os.environ.pop("AILAB_HOME", None)

    def req(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        rq = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(rq) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_page_and_link(self):
        code, body = self.req("/loop")
        self.assertEqual(code, 200)
        self.assertIn(b"Loop", body)
        for b in (b"\xe2\x9c\x85 Keep", b"\xf0\x9f\x94\x81 Redo", b"\xe2\x9d\x8c Wrong", b'id="theme"'):
            self.assertIn(b, body)
        self.assertIn(b'id="looptop"', self.req("/")[1])

    def test_api_round_trip(self):
        code, body = self.req("/api/loop/plan", {"goal": "packet travel", "asset_type": "motion"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["job"]["id"], JOB["id"])
        self.assertEqual(self.req(f"/api/loop/job?job_id={JOB['id']}")[0], 200)
        self.assertEqual(self.req("/api/loop/rate", {"job_id": JOB["id"], "piece": 1, "button": "keep"})[0], 200)
        self.assertEqual(self.lab.mcp.calls[-1][0], "creative_rate")
        code, body = self.req("/api/loop/spend_ok", {"job_id": JOB["id"], "piece": 1, "pin": "0000"})
        self.assertEqual(code, 409)
        self.assertIn("PIN", json.loads(body)["message"])
        self.assertEqual(json.loads(self.req("/api/loop/trust")[1])["tasks"][0]["on"], False)


if __name__ == "__main__":
    unittest.main()
