"""M6 acceptance — 📋 Review: demos to Hermes (connected) / kept (standalone); held writes Apply / Reject."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

from ailab import agent, config, preview, review, store
from ailab.mcp_client import HermesRefused
from tests.test_server import Srv

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
WRITEUP = "A tiny page the agent gave a footer, checked with grep."


class FakeMCP:
    def __init__(self, refuse=None):
        self.calls, self.refuse = [], refuse

    def call(self, tool, args=None):
        self.calls.append((tool, args))
        if self.refuse:
            raise HermesRefused(*self.refuse)
        if tool == "review_submit":
            return {"ok": True, "id": "20261120-120000-abcdef", "state": "waiting"}
        if tool == "review_status":
            return {"ok": True, "items": [{"id": "20261120-120000-abcdef", "state": "approved",
                                           "url": "https://scottchristensen.dev/lab/footer/about.html"}]}
        raise AssertionError(tool)


def capture(pid="scratch"):
    preview.ensure_site(pid)
    preview.save_capture(pid, "data:image/png;base64," + base64.b64encode(PNG).decode())


class Standalone(Srv):
    def test_send_keeps_package_locally_with_models_and_capture(self):
        capture()
        d = config.home() / "projects" / "scratch" / "agent"
        d.mkdir(parents=True, exist_ok=True)
        (d / "r1.meta.json").write_text(json.dumps({"provider": "ollama", "model": "qwen3.5:9b"}))
        code, lst, _ = self.req("/api/review?project=scratch")
        self.assertEqual((code, lst["project"]["models"]), (200, ["ollama/qwen3.5:9b"]))
        self.assertTrue(lst["project"]["capture"].startswith("capture-"))
        code, r, _ = self.req("/api/review/send", {"project": "scratch", "title": "Footer", "writeup": WRITEUP})
        self.assertEqual((code, r["where"], r["state"]), (200, "kept", "kept"), r)
        pkg = json.loads((config.home() / "review" / "kept" / r["local_id"] / "package.json").read_text())
        self.assertIn("index.html", pkg["files"])
        self.assertEqual(base64.b64decode(pkg["screenshot_b64"]), PNG)
        self.assertEqual(pkg["models"], ["ollama/qwen3.5:9b"])
        self.assertEqual(self.req("/api/review")[1]["sent"][0]["title"], "Footer")

    def test_refusals(self):
        p = store.save_project("Private", sensitive=True)
        code, r, _ = self.req("/api/review/send", {"project": p["id"], "title": "x", "writeup": WRITEUP})
        self.assertEqual((code, r["code"]), (403, "sensitive"))
        code, r, _ = self.req("/api/review/send", {"project": "scratch", "title": "x", "writeup": "short"})
        self.assertEqual(code, 400)
        root = preview.ensure_site("scratch")
        (root / "index.html").write_text("<p>key ghp_" + "a" * 36 + "</p>")
        code, r, _ = self.req("/api/review/send", {"project": "scratch", "title": "x", "writeup": WRITEUP})
        self.assertEqual((code, r["code"]), (422, "secret"))
        self.assertNotIn("ghp_", json.dumps(r))


class Connected(Srv):
    def setUp(self):
        super().setUp()
        self.app.cfg["mode"] = "connected"
        self.lab.mcp = FakeMCP()

    def test_demo_goes_to_hermes_review_and_state_comes_back(self):
        capture()
        code, r, _ = self.req("/api/review/send", {"project": "scratch", "title": "Footer", "writeup": WRITEUP,
                                                  "models": ["openrouter/qwen3-coder"]})
        self.assertEqual((code, r.get("where"), r.get("hermes_id")), (200, "hermes", "20261120-120000-abcdef"), r)
        tool, args = self.lab.mcp.calls[0]
        self.assertEqual(tool, "review_submit")
        self.assertEqual((args["title"], args["models"], args["sensitive"]), ("Footer", ["openrouter/qwen3-coder"], False))
        self.assertTrue(args["screenshot_b64"] and "index.html" in args["files"])
        s = self.req("/api/review")[1]["sent"][0]
        self.assertEqual(s["state"], "approved")
        self.assertIn("scottchristensen.dev", s["url"])

    def test_hermes_refusal_is_shown(self):
        self.lab.mcp = FakeMCP(refuse=("secret", "looks like a key", "remove it"))
        code, r, _ = self.req("/api/review/send", {"project": "scratch", "title": "F", "writeup": WRITEUP})
        self.assertEqual((code, r["code"]), (502, "hermes"))
        self.assertIn("looks like a key", r["message"])


class HeldWrites(Srv):
    def hold(self, path, content="hello"):
        preview.ensure_site("scratch")
        return agent.hold_for_approval("scratch", "run1", path, content)

    def test_apply_needs_word_and_hash_then_backs_up_and_writes(self):
        home = Path(self.tmp.name) / "home"
        (home / "notes").mkdir(parents=True)
        (home / "notes" / "a.txt").write_text("old")
        os.environ["HOME"], old_home = str(home), os.environ.get("HOME")
        try:
            it = self.hold(str(home / "notes" / "a.txt"), "new text")
            row = self.req("/api/review")[1]["held"][0]
            self.assertEqual(row["sha"], hashlib.sha256(b"new text").hexdigest())
            code, r, _ = self.req("/api/review/apply", {"id": it["id"], "sha": row["sha"], "confirm": "yes"})
            self.assertEqual((code, r["code"]), (400, "confirm"))
            code, r, _ = self.req("/api/review/apply", {"id": it["id"], "sha": "0" * 64, "confirm": "apply"})
            self.assertEqual((code, r["code"]), (409, "stale"))
            code, r, _ = self.req("/api/review/apply", {"id": it["id"], "sha": row["sha"], "confirm": " Apply "})
            self.assertEqual((code, r["state"]), (200, "applied"), r)
            self.assertEqual((home / "notes" / "a.txt").read_text(), "new text")
            self.assertEqual(Path(r["backup"]).read_text(), "old")
            self.assertEqual(self.req("/api/review")[1]["held"], [])
            self.assertEqual(agent.approvals("applied")[0]["id"], it["id"])
        finally:
            os.environ["HOME"] = old_home or ""

    def test_never_dotfiles_symlinks_or_outside_home(self):
        home = Path(self.tmp.name) / "home2"
        (home / "real").mkdir(parents=True)
        (home / "link").symlink_to(home / "real")
        os.environ["HOME"], old_home = str(home), os.environ.get("HOME")
        try:
            for path, code in ((str(home / ".bashrc"), "dotfile"), (str(home / "link" / "x.txt"), "symlink"),
                               ("/etc/ailab-test.txt", "outside_home")):
                it = self.hold(path)
                sha = hashlib.sha256(b"hello").hexdigest()
                c, r, _ = self.req("/api/review/apply", {"id": it["id"], "sha": sha, "confirm": "apply"})
                self.assertEqual((c, r["code"]), (403, code), path)
            self.assertFalse((home / ".bashrc").exists() or (home / "real" / "x.txt").exists())
        finally:
            os.environ["HOME"] = old_home or ""

    def test_reject_is_logged_and_content_kept(self):
        it = self.hold("../../outside.txt")
        code, r, _ = self.req("/api/review/reject", {"id": it["id"]})
        self.assertEqual((code, r["state"]), (200, "rejected"))
        self.assertTrue((config.home() / "approvals" / f"{it['id']}.txt").exists())
        code, r, _ = self.req("/api/review/reject", {"id": it["id"]})
        self.assertEqual(code, 409)
