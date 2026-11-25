"""📓 Loop pictures get the Lab's writer (2026-11-25): Craft Book notes + 🔢 count layout go to Hermes as the piece's
prompt; ✅ / 🔁 / ❌ on that piece count on the notes it used."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ailab import config, craft, loop, server
from ailab.providers.base import ChatResult
from tests.test_loop import FakeMCP

JOB = {"id": "cj_1", "goal": "a network rack", "sensitive": False,
       "pieces": [{"n": 1, "do": "five routers in a rack", "method": "lab.image", "state": "planned"},
                  {"n": 2, "do": "packet hops", "method": "proready.primitive", "state": "planned"},
                  {"n": 3, "do": "old picture", "method": "lab.image", "state": "done"}]}


class MCP(FakeMCP):
    def call(self, tool, args=None):
        if tool == "creative_job_get":
            self.calls.append((tool, args or {}))
            return {"ok": True, "job": JOB}
        return super().call(tool, args)


class Lab:
    def __init__(self, reply="Shiny metal, blinking green lights, cool blue light."):
        self.mcp, self.reply, self.chats = MCP(), reply, []
        self.providers = {"venice": 1, "openrouter": 1}

    def chat(self, project, prov, model, msgs, max_tokens, cap_usd=None, task=""):
        self.chats.append((prov, msgs[0]["content"]))
        return ChatResult(self.reply, prov, model, 10, 20, 0.0001, True)


class LoopCraft(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(config, "home", lambda: Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.note = craft.add({"kind": "picture", "do": "Name the light."}, "scott", "live")["note"]

    def loop(self, lab, **cfg):
        return loop.Loop(server.App(config.load({"flags": {"craft": True}, "craft": {"holdout": 0}, **cfg}), lab=lab))

    def test_picture_pieces_get_a_written_prompt_with_notes_and_layout(self):
        lab = Lab()
        self.loop(lab).run({"job_id": "cj_1"})
        tool, args = lab.mcp.calls[-1]
        self.assertEqual(tool, "creative_job_run")
        self.assertEqual(list(args["payloads"]), ["1"])                     # only the picture not yet made
        text = args["payloads"]["1"]["prompt"]
        self.assertTrue(text.startswith("five routers in a rack — a network rack. Exactly 5 routers (5 in all), in one row"), text)
        self.assertIn("blinking green lights", text)
        self.assertIn("Name the light.", lab.chats[0][1])                    # the craft note rode with the writer

    def test_keep_and_wrong_count_on_the_notes(self):
        lab = Lab()
        lp = self.loop(lab)
        lp.run({"job_id": "cj_1"})
        lp.rate({"job_id": "cj_1", "piece": 1, "button": "keep"})
        n = next(x for x in craft.notes() if x["id"] == self.note["id"])
        self.assertEqual((n["kept"], n["tossed"]), (1, 0))
        lp.rate({"job_id": "cj_1", "piece": 1, "button": "wrong"})
        n = next(x for x in craft.notes() if x["id"] == self.note["id"])
        self.assertEqual((n["kept"], n["tossed"]), (1, 1))

    def test_switch_off_and_a_broken_writer_leave_hermes_alone(self):
        lab = Lab()
        self.loop(lab, loop_writer=False).run({"job_id": "cj_1"})
        self.assertEqual(lab.mcp.calls[-1][1]["payloads"], {})
        lab = Lab(reply="Sorry, I can't help with that.")
        self.loop(lab).run({"job_id": "cj_1"})
        self.assertEqual(lab.mcp.calls[-1][1]["payloads"]["1"]["prompt"],
                         "five routers in a rack — a network rack. Exactly 5 routers (5 in all), in one row side by side, "
                         "evenly spaced, each whole and fully in view; no other routers anywhere in the picture.")
