"""M8 acceptance — ⚖️ Compare (flag `compare`): 2–4 models, own sandbox copy each, one $ cap, saved page, Review."""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from ailab import compare, config, providers, secretscan, store
from ailab.privacy import PrivacyRefused
from ailab.providers.base import ChatResult
from ailab.spend import SpendBlocked
from tests.test_server import Srv

HAS_SRT = bool(shutil.which("srt"))
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 64).decode()
FOOTER = '<!DOCTYPE html><html><body><h1>Hi</h1><footer>2026</footer></body></html>'


def act(**kw) -> str:
    return json.dumps(kw)


class Brains:
    """Scripted models, one script per model id (last reply repeats). Has .provider() like the real Lab."""

    def __init__(self, scripts: dict, usd=0.001, gate=None):
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.usd, self.gate, self.calls, self.mcp = usd, gate, [], None
        self.providers = providers.build(config.load(), None)

    def provider(self, name):
        return self.providers[name]

    def chat(self, project, prov, model, msgs, max_tokens=1024, cap_usd=None, task=""):
        self.calls.append((prov, model))
        if self.gate:
            self.gate.wait(5)
        if cap_usd is not None and self.usd > cap_usd + 1e-12:
            raise SpendBlocked(f"Estimated ${self.usd:.4f} is over this run's cap of ${cap_usd:.4f}.")
        s = self.scripts[model]
        text = s.pop(0) if len(s) > 1 else s[0]
        return ChatResult(text, prov, model, 100, 20, self.usd, True)


GOOD = [act(action="write", path="index.html", content=FOOTER, why="add footer"),
        act(action="run", cmd="grep -c footer index.html", why="check"),
        act(action="done", summary="footer added")]
LAZY = [act(action="done", summary="nothing to do")]
MESSY = ["sure! here you go", act(action="list"), act(action="done", summary="looked only")]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AILAB_HOME"] = self.tmp.name
        if not HAS_SRT:
            os.environ["AILAB_ALLOW_UNSANDBOXED"] = "1"
        self.project = store.project("scratch")

    def tearDown(self):
        os.environ.pop("AILAB_HOME", None)
        os.environ.pop("AILAB_ALLOW_UNSANDBOXED", None)
        self.tmp.cleanup()

    def cmp(self, brains, lanes, checks=("grep -q footer index.html",), project=None, **cfg):
        c = compare.Comparison(brains, config.load({"compare_cap_usd": 0.50, **cfg}), project or self.project,
                               "Add a footer with the year.", lanes, list(checks))
        c.loop()
        return c


class Acceptance(Base):
    def test_three_model_comparison_page_review_and_clean_scan(self):
        b = Brains({"good": GOOD, "lazy": LAZY, "messy": MESSY})
        c = self.cmp(b, [{"provider": "openrouter", "model": "good"}, {"provider": "claude", "model": "lazy"},
                         {"provider": "ollama", "model": "messy"}])
        v = c.view()
        self.assertEqual(v["state"], "done", v["why"])
        self.assertEqual([ln["state"] for ln in v["lanes"]], ["done", "done", "done"])
        self.assertEqual([ln["passed"] for ln in v["lanes"]], [1, 0, 0])
        self.assertEqual([ln["steps"] for ln in v["lanes"]], [3, 1, 3])
        self.assertEqual(v["lanes"][0]["tokens_in"], 300)
        self.assertLessEqual(v["usd"], 0.50)
        self.assertTrue(all(ln["secs"] is not None for ln in v["lanes"]))
        # lanes are isolated copies; the project itself is untouched
        site = Path(self.tmp.name) / "projects/scratch/site/index.html"
        lane = lambda k: (c.dir / "lanes" / str(k) / "site/index.html").read_text()   # noqa: E731
        self.assertIn("footer", lane(0))
        self.assertNotIn("<footer>", lane(1))
        self.assertNotIn("<footer>", site.read_text())
        # saved page
        page = (c.dir / "result.html").read_text()
        for m in ("good", "lazy", "messy", "1/1 passed", "0/1 passed", "Add a footer"):
            self.assertIn(m, page)
        self.assertIn('id="th"', page)                                  # theme toggle
        self.assertEqual(compare.load("scratch", c.id)["state"], "done")
        self.assertEqual(compare.listing("scratch")[0]["id"], c.id)
        # 📸 then 📋 Review (standalone → kept)
        compare.save_capture("scratch", c.id, "0", PNG)
        self.assertIn("data:image/png;base64,", (c.dir / "result.html").read_text())
        r = compare.to_review(b, config.load(), "scratch", c.id, "Footer bake-off", "Three models, one footer task, checked with grep.")
        self.assertEqual((r["where"], r["comparison"]), ("kept", c.id))
        pkg = json.loads((Path(self.tmp.name) / "review/kept" / r["local_id"] / "package.json").read_text())
        self.assertIn("index.html", pkg["files"])
        self.assertIn("lanes/0/index.html", pkg["files"])
        self.assertEqual(pkg["models"], ["openrouter/good", "claude/lazy", "ollama/messy"])
        self.assertTrue(pkg["screenshot_b64"])
        self.assertNotIn("data:image", pkg["files"]["index.html"])     # page in the bundle links the demos instead
        # portfolio repo secret scan is clean
        self.assertTrue(secretscan.scan(config.REPO)["ok"], secretscan.scan(config.REPO)["hits"])

    def test_connected_review_goes_to_hermes(self):
        b = Brains({"a": LAZY, "b": LAZY})
        c = self.cmp(b, [{"provider": "ollama", "model": "a"}, {"provider": "ollama", "model": "b"}])

        class M:
            sent = None

            def call(self, tool, args=None):
                M.sent = (tool, args)
                return {"id": "h1", "state": "waiting"}
        b.mcp = M()
        r = compare.to_review(b, config.load({"mode": "standalone"}) | {"mode": "connected"}, "scratch", c.id,
                              "Two locals", "Two local models compared on one tiny task.")
        self.assertEqual((r["where"], r["hermes_id"]), ("hermes", "h1"))
        self.assertEqual(M.sent[0], "review_submit")


class Limits(Base):
    def test_one_cap_split_across_lanes(self):
        b = Brains({"a": [act(action="list")], "b": [act(action="list")]}, usd=0.001)
        c = self.cmp(b, [{"provider": "ollama", "model": "a"}, {"provider": "ollama", "model": "b"}], compare_cap_usd=0.004)
        v = c.view()
        self.assertEqual(v["lane_cap_usd"], 0.002)
        self.assertEqual([ln["state"] for ln in v["lanes"]], ["capped", "capped"])
        self.assertLessEqual(v["usd"], 0.004 + 1e-9)

    def test_lane_count_and_task_rules(self):
        b = Brains({"a": LAZY})
        for lanes in ([{"provider": "ollama", "model": "a"}],
                      [{"provider": "ollama", "model": "a"}, {"provider": "ollama", "model": "a"}],   # duplicate = 1
                      [{"provider": "ollama", "model": f"m{i}"} for i in range(5)]):
            with self.assertRaises(compare.CompareError):
                self.cmp(b, lanes)
        with self.assertRaises(compare.CompareError):
            compare.Comparison(b, config.load(), self.project, "  ", [{"provider": "ollama", "model": "a"}] * 2, [])

    def test_sensitive_project_refused_before_anything_is_copied_or_sent(self):
        p = store.save_project("Private", sensitive=True)
        b = Brains({"a": LAZY, "b": LAZY})
        with self.assertRaises(PrivacyRefused):
            self.cmp(b, [{"provider": "ollama", "model": "a"}, {"provider": "openrouter", "model": "b"}], project=p)
        self.assertEqual(b.calls, [])
        self.assertFalse((Path(self.tmp.name) / "projects" / p["id"] / "compare").exists())
        c = self.cmp(b, [{"provider": "ollama", "model": "a"}, {"provider": "ollama", "model": "b"}], project=p)
        with self.assertRaises(compare.CompareError) as e:
            compare.to_review(b, config.load(), p["id"], c.id, "t", "long enough write-up here")
        self.assertEqual(e.exception.code, "sensitive")

    def test_stop_ends_current_lane_and_skips_the_rest(self):
        gate = threading.Event()
        b = Brains({"a": [act(action="list")], "b": LAZY, "c": LAZY}, gate=gate)
        c = compare.Comparison(b, config.load(), self.project, "loop", [{"provider": "ollama", "model": m} for m in "abc"], [])
        t = threading.Thread(target=c.loop)
        t.start()
        time.sleep(0.2)
        c.stop()
        gate.set()
        t.join(10)
        v = c.view()
        self.assertEqual(v["state"], "stopped")
        self.assertEqual([ln["state"] for ln in v["lanes"]], ["stopped", "skipped", "skipped"])
        self.assertNotIn(("ollama", "b"), b.calls)

    def test_review_refuses_a_key_in_a_lane(self):
        key = "ghp_" + "b" * 36
        b = Brains({"a": [act(action="write", path="index.html", content=f"<p>{key}</p>"), act(action="done")], "b": LAZY})
        c = self.cmp(b, [{"provider": "ollama", "model": "a"}, {"provider": "ollama", "model": "b"}], checks=())
        with self.assertRaises(compare.CompareError) as e:
            compare.to_review(b, config.load(), "scratch", c.id, "t", "a write-up that is long enough")
        self.assertEqual(e.exception.code, "secret")
        self.assertNotIn(key, str(e.exception))

    def test_bad_ids_and_bad_png(self):
        for pid, cid in (("../x", "20261120-000000-abcdef"), ("scratch", "../../etc"), ("scratch", "")):
            with self.assertRaises(compare.CompareError):
                compare.cdir(pid, cid)
        with self.assertRaises(compare.CompareError):
            compare.lane_dir("scratch", "20261120-000000-abcdef", "9")
        b = Brains({"a": LAZY, "b": LAZY})
        c = self.cmp(b, [{"provider": "ollama", "model": "a"}, {"provider": "ollama", "model": "b"}])
        with self.assertRaises(compare.CompareError):
            compare.save_capture("scratch", c.id, "0", "data:image/png;base64,QUJD")

    def test_page_escapes_model_output(self):
        res = {"id": "x", "task": "<script>alert(1)</script>", "state": "done", "checks": [], "usd": 0, "cap_usd": 0.5,
               "lanes": [{"k": 0, "provider": "p", "model": "<img src=x onerror=alert(1)>", "state": "done", "why": "</p><script>",
                          "secs": 1, "usd": 0, "tokens_in": 0, "tokens_out": 0, "steps": 0, "checks": [], "passed": 0}]}
        page = compare.page_html(res)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("<img src=x", page)


class SecretScan(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        git = lambda *a: subprocess.run(["git", "-C", str(self.d), *a], check=True, capture_output=True)   # noqa: E731
        self.git = git
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (self.d / "a.py").write_text("x = 1\n")
        git("add", "a.py")
        git("commit", "-qm", "init")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_finds_key_without_printing_it_marker_and_allow_file(self):
        key = "ghp_" + "c" * 36
        self.assertTrue(secretscan.scan(self.d)["ok"])
        (self.d / "b.py").write_text(f"k = '{key}'\n")
        r = secretscan.scan(self.d)
        self.assertFalse(r["ok"])
        self.assertNotIn(key, json.dumps(r))
        (self.d / "b.py").write_text(f"k = '{key}'  # secretscan: test-fixture\n")
        self.assertTrue(secretscan.scan(self.d)["ok"])

    def test_history_and_bad_file_names(self):
        key = "hf_" + "d" * 34
        (self.d / "c.py").write_text(f"k = '{key}'\n")
        self.git("add", "c.py")
        self.git("commit", "-qm", "oops")
        (self.d / "c.py").write_text("k = ''\n")
        self.git("commit", "-qam", "removed")
        r = secretscan.scan(self.d)
        self.assertTrue(any(h["where"].startswith("history") for h in r["hits"]), r)
        import hashlib
        (self.d / ".secretscan-allow").write_text(hashlib.sha256(key.encode()).hexdigest() + " fake\n")
        self.assertTrue(secretscan.scan(self.d)["ok"])
        (self.d / "prod.pem").write_text("x")
        self.assertFalse(secretscan.scan(self.d)["ok"])


class CompareOff(Srv):
    flags = {"agent": True}

    def test_all_compare_routes_403(self):
        for path, body in (("/api/compare/start", {"project": "scratch"}), ("/api/compare/stop", {"id": "x"}),
                           ("/api/compare/capture", {"project": "scratch"}), ("/api/compare/review", {"project": "scratch"}),
                           ("/api/compare?project=scratch", None)):
            code, r, _ = self.req(path, body)
            self.assertEqual((code, r["code"], r["flag"]), (403, "not_switched_on", "compare"), path)
        self.assertEqual(self.req("/compare-page/scratch/20261120-000000-abcdef/")[0], 403)


class CompareNeedsAgent(Srv):
    flags = {"compare": True}

    def test_start_needs_agent(self):
        code, r, _ = self.req("/api/compare/start", {"project": "scratch", "task": "x"})
        self.assertEqual((code, r["flag"]), (403, "agent"))


class CompareOn(Srv):
    flags = {"compare": True, "agent": True}

    def setUp(self):
        if not HAS_SRT:
            os.environ["AILAB_ALLOW_UNSANDBOXED"] = "1"
        super().setUp()
        b = Brains({"good": GOOD, "lazy": LAZY})
        self.lab.chat, self.lab.provider, self.lab.mcp = b.chat, b.provider, None

    def tearDown(self):
        if getattr(self.app, "_pv", None):
            self.app._pv.close()
        super().tearDown()
        os.environ.pop("AILAB_ALLOW_UNSANDBOXED", None)

    def test_start_poll_page_lane_and_history(self):
        code, r, _ = self.req("/api/compare/start", {"project": "scratch", "task": "footer", "checks": ["grep -q footer index.html"],
                                                     "lanes": [{"provider": "ollama", "model": "good"}, {"provider": "ollama", "model": "lazy"}]})
        self.assertEqual(code, 200, r)
        cid = r["comparison"]["id"]
        for _ in range(100):
            v = self.req(f"/api/compare?project=scratch&id={cid}")[1]["comparison"]
            if v["state"] != "running":
                break
            time.sleep(0.05)
        self.assertEqual(v["state"], "done", v)
        self.assertEqual([ln["passed"] for ln in v["lanes"]], [1, 0])
        code, page, h = self.req(f"/compare-page/scratch/{cid}/")
        self.assertEqual(code, 200)
        self.assertIn("default-src 'none'", h["Content-Security-Policy"])
        self.assertIn("1/1 passed", page)
        code, lane, h = self.req(f"/compare-page/scratch/{cid}/lanes/0/index.html")
        self.assertEqual(code, 200, lane)
        self.assertIn("<footer>", lane)
        self.assertIn("sandbox", h["Content-Security-Policy"])
        self.assertEqual(self.req(f"/compare-page/scratch/{cid}/lanes/7/index.html")[0], 400)
        code, r, _ = self.req("/api/compare/capture", {"project": "scratch", "id": cid, "lane": 1, "png": PNG})
        self.assertEqual(code, 200, r)
        self.assertTrue(self.req(f"/api/compare?project=scratch&id={cid}")[1]["comparison"]["lanes"][1]["shot"])
        self.assertEqual(self.req("/api/compare?project=scratch")[1]["items"][0]["id"], cid)
        code, r, _ = self.req("/api/compare/review", {"project": "scratch", "id": cid, "title": "t", "writeup": "short"})
        self.assertEqual((code, r["code"]), (400, "bad_args"))
        code, r, _ = self.req("/api/compare/review", {"project": "scratch", "id": cid, "title": "Bake-off",
                                                      "writeup": "Two models on one footer task."})
        self.assertEqual((code, r["where"]), (200, "kept"))


if __name__ == "__main__":
    unittest.main()


class RealRunFixes(Base):
    """2026-11-21 real run on gandalf: both local lanes timed out; the summary still said 'All lanes finished'."""

    def test_summary_says_when_models_did_not_finish(self):
        class Boom(Brains):
            def chat(self, *a, **k):
                if a[2] == "bad":
                    raise TimeoutError("timed out")
                return super().chat(*a, **k)
        c = self.cmp(Boom({"good": LAZY, "bad": LAZY}), [{"provider": "ollama", "model": "good"}, {"provider": "ollama", "model": "bad"}])
        self.assertEqual([ln["state"] for ln in c.lanes], ["done", "failed"])
        self.assertIn("1 of 2", c.why)

    def test_ollama_asks_for_no_thinking(self):
        self.assertEqual(providers.build(config.load(), None)["ollama"].extra_body(), {"reasoning_effort": "none"})
