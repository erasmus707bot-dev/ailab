"""2026-11-24: replies over 4096 tokens — Hermes runs them as an llm: job; the Lab waits with job_wait.
The agent asks for the long size only after a reply was cut off (so the per-run $ estimate stays small)."""
from __future__ import annotations

from ailab import config
from ailab.mcp_client import HermesRefused
from ailab.spend import SpendBlocked
from tests import test_agent, test_lab
from tests.test_agent import Brain, act

MSG = [{"role": "user", "content": "x"}]


class LongReply(test_lab.Connected):
    def route(self, waits, end):
        base = self.mcp_route

        def r(body):
            name, args = body["params"]["name"], body["params"]["arguments"]
            if name == "llm_call" and args["max_tokens"] > 4096:
                self.hermes["tools"].append(name)
                sc = {"ok": True, "key": "llm:abc", "state": "running"}
            elif name in ("job_wait", "job_cancel"):
                self.hermes["tools"].append(name)
                sc = {"ok": True, "key": "llm:abc", "finished": False, "state": "running"} if waits and waits.pop(0) else end
            else:
                return base(body)
            return {"jsonrpc": "2.0", "id": body["id"], "result": {"structuredContent": sc, "isError": False}}
        return r

    def clab_with(self, waits, end):
        return self.lab({"/mcp": self.route(waits, end)}, mode="connected", hermes_token_file=str(self.tok))[0]

    def test_long_reply_is_collected_through_job_wait(self):
        done = {"ok": True, "key": "llm:abc", "finished": True, "state": "done",
                "result": {"ok": True, "text": "a long file", "model": "claude-x", "tokens_in": 9, "tokens_out": 9000, "usd": 0.13}}
        lab = self.clab_with([True, True], done)
        r = lab.chat({}, "claude", "claude-x", MSG, 16384)
        self.assertEqual((r.text, r.tokens_out, r.usd), ("a long file", 9000, 0.13))
        self.assertEqual(self.hermes["tools"], ["llm_call", "job_wait", "job_wait", "job_wait"])

    def test_failed_long_reply_raises_plain(self):
        lab = self.clab_with([], {"ok": True, "finished": True, "state": "failed",
                                  "error": {"code": "provider_error", "message": "max_tokens too large for this model"}})
        with self.assertRaises(HermesRefused) as c:
            lab.chat({}, "claude", "claude-x", MSG, 16384)
        self.assertEqual(c.exception.code, "provider_error")

    def test_over_cap_inside_the_job_is_a_spend_block(self):
        lab = self.clab_with([], {"ok": True, "finished": True, "state": "failed", "error": {"code": "over_cap", "message": "cap"}})
        with self.assertRaises(SpendBlocked):
            lab.chat({}, "claude", "claude-x", MSG, 16384)

    def test_waiting_too_long_gives_up_and_cancels(self):
        lab = self.clab_with([True] * 999, {})
        lab.cfg["llm_long_wait_s"] = 0.05
        with self.assertRaises(HermesRefused) as c:
            lab.chat({}, "claude", "claude-x", MSG, 16384)
        self.assertEqual(c.exception.code, "timeout")
        self.assertEqual(self.hermes["tools"][-1], "job_cancel")

    def test_normal_size_still_answers_at_once(self):
        lab = self.clab_with([], {})
        self.assertEqual(lab.chat({}, "claude", "claude-x", MSG, 4096).text, "via hermes")
        self.assertNotIn("job_wait", self.hermes["tools"])


class Sizes(Brain):
    def __init__(self, replies, fail_big=False):
        super().__init__(replies)
        self.sizes, self.fail_big = [], fail_big

    def chat(self, project, prov, model, msgs, max_tokens=1024, cap_usd=None, task=""):
        self.sizes.append(max_tokens)
        if self.fail_big and max_tokens > 4096:
            raise HermesRefused("provider_error", "too big for this model")
        return super().chat(project, prov, model, msgs, max_tokens, cap_usd, task)


class AgentSizes(test_agent.Base):
    CUT = '{"action":"write","path":"app.js","content":"let a = 1;'

    def test_long_size_only_right_after_a_cut_off(self):
        b = Sizes([act(action="list"), self.CUT, act(action="list"), act(action="list"), act(action="done", summary="ok")])
        r = self.run_agent(b)
        self.assertEqual(b.sizes, [4096, 4096, 16384, 4096, 4096])
        self.assertEqual((r.state, r.view()["long_replies"]), ("done", 1))

    def test_plain_words_reply_does_not_trigger_long(self):
        b = Sizes(["just words", act(action="done", summary="ok")])
        self.run_agent(b)
        self.assertEqual(b.sizes, [4096, 4096])

    def test_model_that_cannot_do_long_falls_back_in_the_same_step(self):
        b = Sizes([self.CUT, act(action="list"), act(action="done", summary="ok")], fail_big=True)
        r = self.run_agent(b)
        self.assertEqual(b.sizes, [4096, 16384, 4096, 4096])
        self.assertEqual((r.state, r.view()["long_replies"]), ("done", 0))

    def test_long_size_can_be_switched_off(self):
        b = Sizes([self.CUT, act(action="done", summary="ok")])
        self.run_agent(b, agent_long_max_tokens=0)
        self.assertEqual(b.sizes, [4096, 4096])
