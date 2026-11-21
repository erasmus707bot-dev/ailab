"""M2 acceptance — mocked providers, both modes. Runs with stdlib unittest or pytest."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from ailab import config, privacy
from ailab.keys import KeyMissing, LocalKeys
from ailab.lab import Lab
from ailab.mcp_client import HermesMCP, HermesRefused
from ailab.models import ModelCache
from ailab.spend import LocalLedger, SpendBlocked

SECRET = "sk-test-SHOULD-NEVER-APPEAR-0000"  # secretscan: test-fixture


class FakeHTTP:
    """Records calls; answers by URL suffix."""

    def __init__(self, routes: dict):
        self.routes, self.calls = routes, []

    def __call__(self, method, url, headers, body):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        for suffix, resp in self.routes.items():
            if url.split("?")[0].endswith(suffix):
                return resp(body) if callable(resp) else resp
        raise AssertionError(f"unexpected call {method} {url}")


OR_CHAT = {"model": "x/m", "choices": [{"message": {"content": "hi"}}],
           "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0012}}
OLLAMA_CHAT = {"choices": [{"message": {"content": "local"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}}


class StaticKeys:
    def get(self, name):
        return SECRET


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AILAB_HOME"] = self.tmp.name
        os.environ["AILAB_CACHE"] = str(Path(self.tmp.name) / "cache")

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("AILAB_HOME", None)
        os.environ.pop("AILAB_CACHE", None)

    def lab(self, routes, mode="standalone", **kw):
        http = FakeHTTP(routes)
        cfg = config.load({"mode": mode, **kw})
        return Lab(cfg, transport=http, keys=None if mode == "connected" else StaticKeys()), http


class Standalone(Base):
    def test_openrouter_call_carries_zdr_and_records_cost(self):
        lab, http = self.lab({"/chat/completions": OR_CHAT})
        r = lab.chat({"name": "demo"}, "openrouter", "x/m", [{"role": "user", "content": "hello"}], 100)
        self.assertEqual((r.text, r.usd, r.tokens_in), ("hi", 0.0012, 10))
        self.assertEqual(http.calls[0]["body"]["provider"], {"zdr": True, "data_collection": "deny"})
        self.assertAlmostEqual(lab.spend.spent_today(), 0.0012)

    def test_sensitive_project_refuses_every_hosted_provider(self):
        lab, http = self.lab({})
        for name in ("openrouter", "hf", "qwen", "kimi", "claude"):
            with self.assertRaises(privacy.PrivacyRefused):
                lab.chat({"name": "erasmus", "sensitive": True}, name, "m", [{"role": "user", "content": "x"}])
        self.assertEqual(http.calls, [])                       # nothing left the machine

    def test_sensitive_project_allows_ollama_and_spends_nothing(self):
        lab, http = self.lab({"/chat/completions": OLLAMA_CHAT})
        r = lab.chat({"name": "erasmus", "sensitive": True}, "ollama", "qwen3.5:9b", [{"role": "user", "content": "x"}])
        self.assertEqual((r.text, r.usd), ("local", 0.0))
        self.assertTrue(http.calls[0]["url"].startswith("http://127.0.0.1:11434/"))
        self.assertNotIn("Authorization", http.calls[0]["headers"])
        self.assertEqual(lab.spend.spent_today(), 0)

    def test_deepseek_first_party_host_blocked(self):
        lab, http = self.lab({}, base_urls={"kimi": "https://api.deepseek.com/v1"})
        with self.assertRaises(privacy.PrivacyRefused):
            lab.chat({}, "kimi", "deepseek-chat", [{"role": "user", "content": "x"}])
        self.assertEqual(http.calls, [])

    def test_over_daily_cap_blocked_before_call(self):
        lab, http = self.lab({"/chat/completions": OR_CHAT}, daily_cap_usd=2.0)
        lab.spend.record("openrouter", "x/m", 1.999)
        with self.assertRaises(SpendBlocked):
            lab.chat({}, "openrouter", "x/m", [{"role": "user", "content": "x"}], 1000)
        self.assertEqual(http.calls, [])

    def test_comparison_cap(self):
        lab, http = self.lab({"/chat/completions": OR_CHAT})
        with self.assertRaises(SpendBlocked):              # fallback price $75/Mtok × 10k = $0.75 > $0.50
            lab.chat({}, "claude", "claude-x", [{"role": "user", "content": "x"}], 10_000, cap_usd=0.50)
        self.assertEqual(http.calls, [])

    def test_claude_adapter_splits_system_and_prices_from_config(self):
        resp = {"model": "claude-x", "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1_000_000, "output_tokens": 0}}
        lab, http = self.lab({"/messages": resp}, prices_per_mtok={"claude/claude-x": {"in": 3.0, "out": 15.0}},
                             daily_cap_usd=100)
        r = lab.chat({}, "claude", "claude-x", [{"role": "system", "content": "be brief"},
                                                {"role": "user", "content": "x"}], 10)
        b = http.calls[0]["body"]
        self.assertEqual(b["system"], "be brief")
        self.assertEqual([m["role"] for m in b["messages"]], ["user"])
        self.assertEqual((r.text, r.usd, r.priced), ("ok", 3.0, True))
        self.assertEqual(http.calls[0]["headers"]["anthropic-version"], "2023-06-01")

    def test_model_list_cached_then_stale_on_failure(self):
        listing = {"data": [{"id": "a/b", "pricing": {"prompt": "0.000001", "completion": "0.000002"}}]}
        lab, http = self.lab({"/models": listing})
        now = [1000.0]
        lab.models = ModelCache(Path(self.tmp.name) / "c", ttl_s=60, now=lambda: now[0])
        self.assertEqual(lab.list_models("openrouter")["source"], "live")
        self.assertEqual(lab.list_models("openrouter")["source"], "cache")
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(lab.models.lookup("openrouter", "a/b")["price_out"], 0.000002)
        now[0] += 120
        http.routes["/models"] = lambda b: (_ for _ in ()).throw(OSError("down"))
        self.assertEqual(lab.list_models("openrouter")["source"], "stale")

    def test_listed_price_used_for_cost_when_no_usage_cost(self):
        lab, http = self.lab({"/chat/completions": {"choices": [{"message": {"content": "y"}}],
                                                    "usage": {"prompt_tokens": 100, "completion_tokens": 100}},
                              "/models": {"data": [{"id": "h/m", "pricing": {"prompt": "0.00001",
                                                                            "completion": "0.00002"}}]}})
        lab.list_models("hf")
        r = lab.chat({}, "hf", "h/m", [{"role": "user", "content": "x"}], 100)
        self.assertAlmostEqual(r.usd, 0.003)


class Connected(Base):
    def setUp(self):
        super().setUp()
        self.tok = Path(self.tmp.name) / "ailab.token"
        self.tok.write_text("hermes-token-xyz")
        self.hermes = {"spent": 0.0, "cap": 2.0, "tools": []}

    def mcp_route(self, body):
        name, args = body["params"]["name"], body["params"]["arguments"]
        self.hermes["tools"].append(name)
        self.hermes.setdefault("args", []).append(args)
        if name == "llm_call":
            est = args["max_tokens"] * 75 / 1e6
            if args.get("sensitive"):
                sc = {"ok": False, "code": "sensitive", "message": "sensitive"}
            elif self.hermes["spent"] + est > self.hermes["cap"]:
                sc = {"ok": False, "code": "over_cap", "message": "ailab daily cap reached"}
            else:
                self.hermes["spent"] += 0.0012
                sc = {"ok": True, "text": "via hermes", "model": args["model"], "tokens_in": 10, "tokens_out": 5,
                      "usd": 0.0012, "priced": True, "today_usd": self.hermes["spent"]}
        elif name == "llm_providers":
            sc = {"ok": True, "providers": [{"provider": "claude", "models": ["claude-x"], "has_key": True}]}
        elif name == "spend_status":
            sc = {"ok": True, "categories": {"ailab": {"today_usd": self.hermes["spent"]}}}
        else:
            sc = {"ok": False, "code": "not_allowed", "message": f"{name} not on allowlist"}
        return {"jsonrpc": "2.0", "id": body["id"], "result": {"structuredContent": sc, "isError": not sc["ok"]}}

    def clab(self):
        return self.lab({"/mcp": self.mcp_route, "/chat/completions": OLLAMA_CHAT}, mode="connected",
                        hermes_token_file=str(self.tok))

    def test_connected_hosted_call_goes_through_hermes_without_a_key(self):
        lab, http = self.clab()
        r = lab.chat({"name": "demo"}, "openrouter", "x/m", [{"role": "user", "content": "x"}], 100)
        self.assertEqual((r.text, r.usd), ("via hermes", 0.0012))
        self.assertEqual(self.hermes["tools"], ["llm_call"])          # Hermes checks + records; no key asked
        self.assertEqual(self.hermes["args"][0]["category"], "ailab")
        self.assertFalse(any("openrouter.ai" in c["url"] for c in http.calls))
        self.assertTrue(all(c["headers"]["Authorization"] == "Bearer hermes-token-xyz" for c in http.calls))
        self.assertAlmostEqual(lab.status()["spent_today_usd"], 0.0012)

    def test_connected_cap_blocks(self):
        self.hermes["spent"] = 1.9999
        lab, http = self.clab()
        with self.assertRaises(SpendBlocked):
            lab.chat({}, "claude", "c", [{"role": "user", "content": "x"}], 1000)

    def test_connected_sensitive_refused_before_hermes(self):
        lab, http = self.clab()
        with self.assertRaises(privacy.PrivacyRefused):
            lab.chat({"sensitive": True}, "claude", "c", [{"role": "user", "content": "x"}])
        self.assertEqual(http.calls, [])

    def test_connected_ollama_stays_local(self):
        lab, http = self.clab()
        r = lab.chat({"sensitive": True}, "ollama", "qwen3.5:9b", [{"role": "user", "content": "x"}])
        self.assertEqual(r.text, "local")
        self.assertEqual(self.hermes["tools"], [])

    def test_connected_models_come_from_hermes(self):
        lab, http = self.clab()
        r = lab.list_models("claude")
        self.assertEqual((r["source"], r["models"][0]["id"]), ("hermes", "claude-x"))
        with self.assertRaises(HermesRefused):
            lab.list_models("kimi")

    def test_hermes_refusal_is_plain(self):
        lab, http = self.clab()
        with self.assertRaises(HermesRefused) as e:
            lab.mcp.call("provider_key", {"provider": "x"})
        self.assertEqual(e.exception.code, "not_allowed")

    def test_mcp_repr_hides_token(self):
        m = HermesMCP("http://127.0.0.1:8790/mcp", str(self.tok), None)
        self.assertNotIn("hermes-token-xyz", repr(m))


class Keys(Base):
    def test_env_file_must_be_private_and_outside_repo(self):
        f = Path(self.tmp.name) / "keys.env"
        f.write_text("OPENROUTER_API_KEY=abc\n")
        f.chmod(0o644)
        os.environ.pop("OPENROUTER_API_KEY", None)
        with self.assertRaises(KeyMissing):
            LocalKeys(f, use_keyring=False).get("openrouter")
        f.chmod(0o600)
        self.assertEqual(LocalKeys(f, use_keyring=False).get("openrouter"), "abc")
        with self.assertRaises(KeyMissing):
            LocalKeys(config.REPO / "keys.env", use_keyring=False).get("openrouter")

    def test_missing_key_message_names_no_value(self):
        os.environ.pop("MOONSHOT_API_KEY", None)
        with self.assertRaises(KeyMissing) as e:
            LocalKeys(Path(self.tmp.name) / "none.env", use_keyring=False).get("kimi")
        self.assertIn("MOONSHOT_API_KEY", str(e.exception))

    def test_ledger_survives_parallel_writers(self):
        led = LocalLedger(Path(self.tmp.name) / "l.json", 100)
        code = ("import sys;from pathlib import Path;from ailab.spend import LocalLedger;"
                "l=LocalLedger(Path(sys.argv[1]),100);[l.record('p','m',0.01) for _ in range(20)]")
        ps = [subprocess.Popen([os.sys.executable, "-c", code, str(led.path)], cwd=config.REPO) for _ in range(4)]
        for p in ps:
            p.wait()
        self.assertEqual(len(json.loads(led.path.read_text())), 80)


class RepoHygiene(unittest.TestCase):
    def test_no_vault_paths_or_keys_in_repo(self):
        bad = re.compile(r"secret/hermes|sk-or-v1-[A-Za-z0-9]{20}|sk-ant-[A-Za-z0-9-]{20}|hf_[A-Za-z0-9]{30}")
        hits = []
        for p in config.REPO.rglob("*"):
            if ".git" in p.parts or not p.is_file() or p.suffix not in (".py", ".md", ".toml", ".txt", ".json", ""):
                continue
            if p.name == "test_lab.py":
                continue
            if bad.search(p.read_text(errors="ignore")):
                hits.append(str(p))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()


class TransportTimeouts(unittest.TestCase):
    """2026-11-21 real run: qwen3.5:4b's first call took > 60 s and surfaced as a raw TimeoutError."""

    def test_local_gets_longer_timeout_and_timeout_is_a_plain_http_error(self):
        import socket
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from ailab import transport

        class Slow(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                time.sleep(1.5)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")
        srv = HTTPServer(("127.0.0.1", 0), Slow)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{srv.server_address[1]}/x"
            with self.assertRaises(transport.HttpError) as e:
                transport.http_json("GET", url, timeout=0.3)
            self.assertIn("no answer within", str(e.exception))
            self.assertNotIsInstance(e.exception, socket.timeout)
            self.assertEqual(transport.http_json("GET", url), {})          # default local timeout is long
            self.assertGreater(transport.LOCAL_TIMEOUT_S, transport.HOSTED_TIMEOUT_S)
        finally:
            srv.shutdown()
            srv.server_close()
